"""The builder window and the application entry point."""

from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QRunnable, QSettings, Qt, QThreadPool, QTimer, Signal
from PySide6.QtGui import QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from . import APP_NAME, APP_TITLE, ORGANISATION, __version__
from .bridge import Bridge, BridgeError, Defaults
from .builder import BuildRunner
from .model import Plan, overall_progress
from .repo import ENV_VAR, RepoError, is_repo_root, resolve
from .theme import active_palette, stylesheet
from .widgets.common import Badge
from .widgets.log_view import LogView
from .widgets.plan_view import PlanView
from .widgets.stage_cards import StageForm

# Long enough that typing a username does not launch a plan per keystroke, short
# enough that the image name feels like it updates as you type.
PLAN_DEBOUNCE_MS = 250

# The bar spans the whole plan, so it needs finer resolution than one unit per
# layer to show movement inside a layer that runs for minutes.
PROGRESS_SCALE = 1000

SETTINGS_REPO = "repo_root"
SETTINGS_GEOMETRY = "geometry"
SETTINGS_SPLIT_MAIN = "split_main"
SETTINGS_SPLIT_RIGHT = "split_right"


class _Signals(QObject):
    done = Signal(object, object)  # result, error


class Task(QRunnable):
    """Runs one bridge call off the UI thread.

    Auto-deletion is off and the caller keeps a reference until ``done`` has been
    delivered: the result crosses threads as a queued signal, and letting Qt
    destroy the runnable when ``run`` returns would free the signal object out
    from under an emission still in flight.
    """

    def __init__(self, work: Callable[[], Any]):
        super().__init__()
        self.signals = _Signals()
        self._work = work
        self.setAutoDelete(False)

    def run(self) -> None:
        try:
            self.signals.done.emit(self._work(), None)
        except Exception as exc:  # surfaced in the UI, never raised into the pool
            self.signals.done.emit(None, exc)


class MainWindow(QMainWindow):
    """Nine-stage form on the left, plan and build log on the right."""

    def __init__(self, bridge: Bridge, defaults: Defaults):
        super().__init__()
        self.bridge = bridge
        self.settings = QSettings(ORGANISATION, APP_NAME)
        self.pool = QThreadPool.globalInstance()
        self._tasks: set[Task] = set()
        self._pending_lookups = 0
        self._docker_ready = False
        self.runner = BuildRunner(bridge.repo_root, self)
        self.plan: Plan = Plan()
        self._plan_sequence = 0
        self._build_started: float | None = None
        self._layer = (0, 0)
        self._layer_image = ""
        self._cuda_os = ""
        self._isaaclab_ref = ""

        self.setWindowTitle(APP_TITLE)
        self.resize(1400, 900)

        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_header())

        self.form = StageForm(defaults)
        self.form.changed.connect(self._schedule_plan)

        self.plan_view = PlanView()
        self.log_view = LogView()
        self.right_split = QSplitter(Qt.Orientation.Vertical)
        self.right_split.addWidget(self.plan_view)
        self.right_split.addWidget(self.log_view)
        self.right_split.setStretchFactor(0, 3)
        self.right_split.setStretchFactor(1, 2)

        self.main_split = QSplitter(Qt.Orientation.Horizontal)
        self.main_split.addWidget(self.form)
        self.main_split.addWidget(self.right_split)
        self.main_split.setStretchFactor(0, 5)
        self.main_split.setStretchFactor(1, 4)
        root.addWidget(self.main_split, 1)
        root.addWidget(self._build_footer())
        self.setCentralWidget(central)

        self._connect_runner()
        self._install_shortcuts()
        self._restore_layout()

        self._plan_timer = QTimer(self)
        self._plan_timer.setSingleShot(True)
        self._plan_timer.setInterval(PLAN_DEBOUNCE_MS)
        self._plan_timer.timeout.connect(self._refresh_plan)

        self._elapsed_timer = QTimer(self)
        self._elapsed_timer.setInterval(1000)
        self._elapsed_timer.timeout.connect(self._tick_elapsed)

        self._refresh_ros_options()
        self.refresh_versions()
        self._refresh_docker_status()
        self._refresh_plan()

    # ----- chrome -------------------------------------------------------------- #

    def _build_header(self) -> QWidget:
        header = QWidget()
        layout = QHBoxLayout(header)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        titles = QVBoxLayout()
        titles.setSpacing(1)
        title = QLabel(APP_TITLE)
        title.setObjectName("CardTitle")
        titles.addWidget(title)
        self.repo_label = QLabel()
        self.repo_label.setObjectName("CardHint")
        titles.addWidget(self.repo_label)
        layout.addLayout(titles)
        layout.addStretch(1)

        self.docker_badge = Badge("checking docker…")
        layout.addWidget(self.docker_badge)

        self.repo_button = QPushButton("Change checkout…")
        self.repo_button.setObjectName("Icon")
        self.repo_button.clicked.connect(self._choose_repo)
        layout.addWidget(self.repo_button)

        self.refresh_button = QPushButton("Refresh versions")
        self.refresh_button.setObjectName("Icon")
        # clicked() passes a bool, which would land in `kinds`.
        self.refresh_button.clicked.connect(lambda: self.refresh_versions())
        layout.addWidget(self.refresh_button)

        self._set_repo_label()
        return header

    def _build_footer(self) -> QWidget:
        footer = QWidget()
        layout = QHBoxLayout(footer)
        layout.setContentsMargins(16, 10, 16, 14)
        layout.setSpacing(12)

        status = QVBoxLayout()
        status.setSpacing(4)
        self.status_label = QLabel("Ready.")
        self.status_label.setObjectName("CardHint")
        status.addWidget(self.status_label)
        self.progress = QProgressBar()
        self.progress.setRange(0, PROGRESS_SCALE)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setVisible(False)
        status.addWidget(self.progress)
        layout.addLayout(status, 1)

        self.dry_run_button = QPushButton("Dry run")
        self.dry_run_button.setToolTip("Print the plan without building  (Ctrl+D)")
        self.dry_run_button.clicked.connect(lambda: self._start_build(dry_run=True))
        layout.addWidget(self.dry_run_button)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setObjectName("Danger")
        self.cancel_button.setEnabled(False)
        self.cancel_button.setToolTip("Stop the running build  (Esc)")
        self.cancel_button.clicked.connect(self.runner.cancel)
        layout.addWidget(self.cancel_button)

        self.build_button = QPushButton("Build image")
        self.build_button.setObjectName("Primary")
        self.build_button.setToolTip("Run the command shown above  (Ctrl+B)")
        self.build_button.clicked.connect(lambda: self._start_build(dry_run=False))
        layout.addWidget(self.build_button)
        return footer

    def _install_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+B"), self, lambda: self._start_build(False))
        QShortcut(QKeySequence("Ctrl+D"), self, lambda: self._start_build(True))
        QShortcut(QKeySequence("Ctrl+R"), self, lambda: self.refresh_versions())
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, self.runner.cancel)

    def _connect_runner(self) -> None:
        self.runner.output.connect(self.log_view.append)
        self.runner.started.connect(self._on_build_started)
        self.runner.layer_started.connect(self._on_layer)
        self.runner.step_progress.connect(self._on_step)
        self.runner.finished.connect(self._on_build_finished)

    # ----- background work ------------------------------------------------------ #

    def _submit(self, work: Callable[[], Any], done: Callable[[Any], None]) -> None:
        task = Task(work)
        self._tasks.add(task)
        task.signals.done.connect(
            lambda result, error, t=task: self._finish_task(t, done, result, error)
        )
        self.pool.start(task)

    def _finish_task(
        self, task: Task, done: Callable[[Any], None], result: Any, error: Any
    ) -> None:
        self._tasks.discard(task)
        if error is not None:
            self.status_label.setText(str(error))
            return
        done(result)

    def _schedule_plan(self) -> None:
        self._plan_timer.start()
        # Version-dependent lists follow the fields they depend on.
        selection = self.form.selection()
        if selection.os != self._cuda_os:
            self._cuda_os = selection.os
            self._refresh_ros_options()
            self._lookup_versions(("cuda",))
        if selection.isaaclab_version != self._isaaclab_ref:
            self._isaaclab_ref = selection.isaaclab_version
            self._refresh_isaaclab_selectors()

    def _refresh_plan(self) -> None:
        selection = self.form.selection()
        self._plan_sequence += 1
        sequence = self._plan_sequence

        def apply(plan: Plan) -> None:
            # A slower earlier request must not overwrite a newer answer.
            if sequence != self._plan_sequence:
                return
            self.plan = plan
            self.plan_view.set_plan(plan)
            self.form.set_derived_image(plan.image)
            self._update_actions()

        self._submit(lambda: self.bridge.plan(selection), apply)

    def _refresh_ros_options(self) -> None:
        os_version = self.form.selection().os
        self._submit(
            lambda: self.bridge.ros_for_os(os_version),
            self.form.set_ros_options,
        )

    def _refresh_isaaclab_selectors(self) -> None:
        version = self.form.selection().isaaclab_version or "release/3.0.0"
        self._submit(
            lambda: self.bridge.isaaclab_selectors(version),
            self.form.set_isaaclab_selectors,
        )

    def refresh_versions(self, kinds: tuple[str, ...] = ()) -> None:
        """Re-run the online lookups behind the version dropdowns."""
        self._lookup_versions(kinds or ("cuda", "mujoco", "isaacsim", "isaaclab"))

    def _lookup_versions(self, kinds: tuple[str, ...]) -> None:
        os_version = self.form.selection().os
        self.refresh_button.setEnabled(False)
        self._pending_lookups += len(kinds)
        for kind in kinds:
            self.form.version_combo(kind).set_loading(self.form.defaults.fallbacks[kind.upper()])
            if kind == "isaaclab":
                self._submit(self._isaaclab_choices, self._apply_isaaclab_choices)
            else:
                self._submit(
                    lambda k=kind: (k, self.bridge.versions(k, os_version)),
                    self._apply_versions,
                )

    def _isaaclab_choices(self) -> tuple[list[str], dict[str, str]]:
        """Tags and branches in one list, the way create_env.sh offers them."""
        tags = self.bridge.versions("isaaclab", limit=4)
        branches = self.bridge.branches(4)
        labels: dict[str, str] = {}
        for index, tag in enumerate(tags):
            labels[tag] = f"{tag} (latest tag)" if index == 0 else f"{tag} (tag)"
        for branch in branches:
            labels[branch] = f"{branch} (branch, moves with upstream)"
        return tags + branches, labels

    def _apply_isaaclab_choices(self, payload: tuple[list[str], dict[str, str]]) -> None:
        versions, labels = payload
        self.form.version_combo("isaaclab").set_versions(versions, labels)
        self._lookup_done()

    def _apply_versions(self, payload: tuple[str, list[str]]) -> None:
        kind, versions = payload
        self.form.version_combo(kind).set_versions(versions)
        self._lookup_done()

    def _lookup_done(self) -> None:
        self._pending_lookups = max(0, self._pending_lookups - 1)
        if not self._pending_lookups:
            self.refresh_button.setEnabled(True)

    def _refresh_docker_status(self) -> None:
        def apply(status: Any) -> None:
            self.docker_badge.setText(status.detail or "docker unavailable")
            self.docker_badge.setObjectName("BadgeOk" if status.ready else "BadgeWarning")
            self.docker_badge.setToolTip(
                "Ready to build."
                if status.ready
                else "Builds need a reachable Docker daemon and the buildx plugin."
            )
            self._docker_ready = status.ready
            self._repolish(self.docker_badge)
            self._update_actions()

        self._submit(self.bridge.docker_status, apply)

    # ----- building -------------------------------------------------------------- #

    def _update_actions(self) -> None:
        idle = not self.runner.running
        can_plan = self.plan.ok and idle
        self.dry_run_button.setEnabled(can_plan)
        self.build_button.setEnabled(can_plan and self._docker_ready)
        self.cancel_button.setEnabled(self.runner.running)
        self.form.setEnabled(idle)
        if not self.plan.ok and idle:
            self.build_button.setToolTip("Resolve the errors in the plan first.")
        elif not self._docker_ready and idle:
            self.build_button.setToolTip("Docker is not ready; see the badge in the header.")
        else:
            self.build_button.setToolTip("Run the command shown above  (Ctrl+B)")

    def _start_build(self, dry_run: bool) -> None:
        if self.runner.running or not self.plan.ok:
            return
        if not dry_run and not self._docker_ready:
            return
        self.log_view.clear()
        self._layer = (0, 0)
        self._layer_image = ""
        self.progress.setRange(0, PROGRESS_SCALE)
        self.progress.setValue(0)
        self.progress.setVisible(not dry_run)
        self.runner.start(self.plan.replay, dry_run=dry_run)

    def _on_build_started(self, command: str) -> None:
        self._build_started = time.monotonic()
        self._elapsed_timer.start()
        self.log_view.append(f"$ {command}\n\n")
        self.status_label.setText("Starting…")
        self._update_actions()

    def _on_layer(self, step: int, total: int, image: str) -> None:
        self._layer = (step, total)
        self._layer_image = image
        self._set_progress(0.0)
        self.status_label.setText(f"Layer {step} of {total} — building {image}")

    def _on_step(self, done: int, total: int) -> None:
        if not total or not self._layer[1]:
            return
        self._set_progress(done / total)
        layer, layers = self._layer
        self.status_label.setText(
            f"Layer {layer} of {layers} · step {done} of {total} — building {self._layer_image}"
        )

    def _set_progress(self, fraction: float) -> None:
        """Position the bar across the whole plan, not just the current layer."""
        layer, layers = self._layer
        if layers:
            self.progress.setValue(int(overall_progress(layer, layers, fraction) * PROGRESS_SCALE))

    def _on_build_finished(self, success: bool, summary: str) -> None:
        self._elapsed_timer.stop()
        if success:
            self.progress.setValue(self.progress.maximum())
        elapsed = self._elapsed_text()
        self.status_label.setText(f"{summary}{elapsed}")
        self.status_label.setObjectName("Ok" if success else "Error")
        self._repolish(self.status_label)
        self._build_started = None
        self._update_actions()

    def _tick_elapsed(self) -> None:
        if self._build_started is not None:
            self.status_label.setText(
                self.status_label.text().split("  ·  ")[0] + self._elapsed_text()
            )

    def _elapsed_text(self) -> str:
        if self._build_started is None:
            return ""
        seconds = int(time.monotonic() - self._build_started)
        return f"  ·  {seconds // 60}m {seconds % 60:02d}s"

    # ----- repository ------------------------------------------------------------ #

    def _set_repo_label(self) -> None:
        self.repo_label.setText(f"Building from {self.bridge.repo_root}")
        self.repo_label.setToolTip(
            f"Dockerfiles and scripts come from this checkout. Override with "
            f"--repo-root or {ENV_VAR}."
        )

    def _choose_repo(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, "Select a docker_envs checkout", str(self.bridge.repo_root)
        )
        if not path:
            return
        if not is_repo_root(Path(path)):
            QMessageBox.warning(
                self,
                "Not a docker_envs checkout",
                f"{path} does not contain creator/scripts/lib/stages.sh.",
            )
            return
        self.settings.setValue(SETTINGS_REPO, path)
        QMessageBox.information(
            self,
            "Checkout changed",
            "The new checkout will be used the next time the application starts.",
        )

    # ----- window state ----------------------------------------------------------- #

    @staticmethod
    def _repolish(widget: QWidget) -> None:
        widget.style().unpolish(widget)
        widget.style().polish(widget)

    def _restore_layout(self) -> None:
        geometry = self.settings.value(SETTINGS_GEOMETRY)
        if geometry is not None:
            self.restoreGeometry(geometry)
        for splitter, key in (
            (self.main_split, SETTINGS_SPLIT_MAIN),
            (self.right_split, SETTINGS_SPLIT_RIGHT),
        ):
            state = self.settings.value(key)
            if state is not None:
                splitter.restoreState(state)

    def closeEvent(self, event: Any) -> None:
        if self.runner.running:
            answer = QMessageBox.question(
                self,
                "Build in progress",
                "A build is still running. Cancel it and quit?",
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self.runner.cancel()
            self.runner.wait()
        self.settings.setValue(SETTINGS_GEOMETRY, self.saveGeometry())
        self.settings.setValue(SETTINGS_SPLIT_MAIN, self.main_split.saveState())
        self.settings.setValue(SETTINGS_SPLIT_RIGHT, self.right_split.saveState())
        super().closeEvent(event)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog=APP_NAME,
        description="Desktop front end for the docker_envs staged image builder.",
    )
    parser.add_argument(
        "--repo-root",
        metavar="PATH",
        help=f"docker_envs checkout to build from (also settable with {ENV_VAR})",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="resolve the checkout, plan the default stack and exit (no window)",
    )
    parser.add_argument("--version", action="version", version=f"{APP_NAME} {__version__}")
    return parser.parse_args(argv)


def run_check(repo_root: Path) -> int:
    """Self-test used by the packaging pipeline.

    A packaged build is only useful if the copy of the repository it carries can
    still answer a plan, so prove that rather than just printing a version.
    """
    from .model import Selection

    bridge = Bridge(repo_root)
    print(f"version:   {__version__}")
    print(f"checkout:  {bridge.repo_root}")
    try:
        defaults = bridge.defaults()
        plan = bridge.plan(Selection())
    except BridgeError as exc:
        print(f"bridge:    FAILED — {exc}")
        return 1
    print(f"defaults:  {len(defaults.fallbacks)} fallbacks, os {defaults.supported_os}")
    if not plan.ok:
        print(f"plan:      FAILED — {'; '.join(plan.errors) or 'no image derived'}")
        return 1
    print(f"plan:      {plan.image} ({len(plan.layers)} layers)")
    status = bridge.docker_status()
    print(f"docker:    {status.detail or 'unavailable'}{'' if status.ready else '  (not ready)'}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)

    if args.check:
        # Deliberately before QApplication: this has to work without a display.
        # The saved setting is ignored on purpose, so a packaged build is checked
        # against the copy it ships rather than a checkout the tester happens to
        # have configured.
        try:
            return run_check(resolve(args.repo_root))
        except RepoError as exc:
            print(f"checkout:  FAILED — {exc}")
            return 2

    app = QApplication(sys.argv[:1])
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_TITLE)
    app.setOrganizationName(ORGANISATION)
    app.setStyleSheet(stylesheet(active_palette(app)))
    icon = Path(__file__).parent / "resources" / f"{APP_NAME}.svg"
    if icon.is_file():
        app.setWindowIcon(QIcon(str(icon)))

    settings = QSettings(ORGANISATION, APP_NAME)
    try:
        repo_root = resolve(args.repo_root, settings.value(SETTINGS_REPO))
    except RepoError as exc:
        QMessageBox.critical(None, APP_TITLE, str(exc))
        return 2

    bridge = Bridge(repo_root)
    try:
        defaults = bridge.defaults()
    except BridgeError as exc:
        QMessageBox.critical(None, APP_TITLE, f"Cannot read the stage defaults:\n{exc}")
        return 2

    window = MainWindow(bridge, defaults)
    window.show()
    return app.exec()
