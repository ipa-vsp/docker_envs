"""Headless checks that the form enforces the rules stages.sh would reject.

Skipped where PySide6 is unavailable, so the suite still runs on a machine that
only cares about the shell tooling. Everything here runs on the offscreen
platform plugin and never touches the network: the version lists are injected.
"""

import atexit
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "gui"))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# MainWindow persists geometry through QSettings; keep that out of the real
# user configuration.
_CONFIG = tempfile.mkdtemp(prefix="docker-envs-gui-tests-")
os.environ["XDG_CONFIG_HOME"] = _CONFIG
atexit.register(shutil.rmtree, _CONFIG, True)

try:
    from PySide6.QtWidgets import QApplication

    PYSIDE = True
except ImportError:  # pragma: no cover - depends on the environment
    PYSIDE = False

if PYSIDE:
    from PySide6.QtCore import QEventLoop, QTimer

    from docker_envs_gui.app import MainWindow
    from docker_envs_gui.bridge import Bridge
    from docker_envs_gui.builder import BuildRunner
    from docker_envs_gui.docker_cli import ContainerInfo, ImageInfo
    from docker_envs_gui.widgets.common import ANNOTATION_ROLE, VersionCombo
    from docker_envs_gui.widgets.docker_views import ContainersView, ImagesView
    from docker_envs_gui.widgets.log_view import LogView, strip_ansi
    from docker_envs_gui.widgets.plan_view import PlanView
    from docker_envs_gui.widgets.stage_cards import CUSTOM, StageForm


@unittest.skipUnless(PYSIDE, "PySide6 is not installed")
class StageFormTests(unittest.TestCase):
    application = None

    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])
        cls.bridge = Bridge(ROOT)
        cls.defaults = cls.bridge.defaults()

    def setUp(self):
        self.form = StageForm(self.defaults)
        self.form.set_ros_options(self.bridge.ros_for_os("24.04"))
        self.form.set_isaaclab_selectors(self.bridge.isaaclab_selectors("release/3.0.0"))

    def plan(self):
        return self.bridge.plan(self.form.selection())

    def test_the_form_opens_on_a_buildable_default(self):
        plan = self.plan()
        self.assertTrue(plan.ok, plan.errors)
        self.assertEqual(plan.image, "docker_envs:24.04-rolling")

    def test_changing_ubuntu_changes_the_available_ros_distros(self):
        self.form.set_ros_options(self.bridge.ros_for_os("22.04"))
        self.assertEqual(self.form.ros_choice.values(), ["humble", "iron"])
        self.form.os_choice.set_value("22.04")
        self.assertTrue(self.plan().ok)

    def test_toggling_a_layer_changes_the_derived_name(self):
        before = self.plan().image
        self.form.mujoco_card.set_on(True)
        self.form.mujoco_version.set_value("3.12.0")
        after = self.plan().image
        self.assertNotEqual(before, after)
        self.assertIn("mujoco3.12.0", after)

    def test_isaac_sim_only_options_are_disabled_until_isaac_sim_is_on(self):
        self.form.isaaclab_card.set_on(True)
        self.form.isaaclab_version.set_value("release/3.0.0")

        kit = self.form.isaaclab_visualizer.findData("kit")
        self.assertFalse(self.form.isaaclab_visualizer.model().item(kit).isEnabled())
        self.form.isaacsim_card.set_on(True)
        self.assertTrue(self.form.isaaclab_visualizer.model().item(kit).isEnabled())

    def test_an_isaac_sim_only_choice_is_reset_when_isaac_sim_goes_away(self):
        self.form.isaaclab_card.set_on(True)
        self.form.isaaclab_version.set_value("release/3.0.0")
        self.form.isaacsim_card.set_on(True)
        self.form.isaaclab_physics.setCurrentIndex(self.form.isaaclab_physics.findData("isaacsim"))
        self.assertEqual(self.form.selection().isaaclab_physics, "isaacsim")

        self.form.isaacsim_card.set_on(False)
        self.assertEqual(self.form.selection().isaaclab_physics, "default")
        self.assertTrue(self.plan().ok, self.plan().errors)

    def test_backend_pickers_are_disabled_for_isaac_lab_2x(self):
        # 2.x has no Kit-less installation path, so it also needs the Isaac Sim layer.
        self.form.isaaclab_card.set_on(True)
        self.form.isaaclab_version.set_value("v2.3.2")
        self.assertFalse(self.form.isaaclab_physics.isEnabled())
        self.assertFalse(self.form.isaaclab_visualizer.isEnabled())
        self.assertIn("Enable the Isaac Sim layer", self.form.isaaclab_note.text())

        self.form.isaacsim_card.set_on(True)
        self.form.isaacsim_version.set_value("6.1.0.0")
        plan = self.plan()
        self.assertTrue(plan.ok, plan.errors)
        self.assertIn("isaaclab2.3.2-python-env", plan.image)

    def test_installation_method_falls_back_when_it_becomes_invalid(self):
        self.form.isaaclab_card.set_on(True)
        self.form.isaaclab_version.set_value("release/3.0.0")
        self.form.isaaclab_method.set_value("legacy")
        self.assertEqual(self.form.selection().isaaclab_method, "legacy")

        self.form.isaacsim_card.set_on(True)  # legacy forbids the Isaac Sim layer
        self.assertEqual(self.form.selection().isaaclab_method, "auto")
        self.assertTrue(self.plan().ok, self.plan().errors)

    def test_custom_selectors_are_only_asked_for_when_chosen(self):
        self.form.isaaclab_card.set_on(True)
        self.assertFalse(self.form.isaaclab_custom.isVisible())
        self.form.isaaclab_packages.setCurrentIndex(self.form.isaaclab_packages.findData(CUSTOM))
        self.form.isaaclab_custom.setText("newton,rl[rsl-rl]")
        self.assertEqual(self.form.selection().isaaclab_install, "newton,rl[rsl-rl]")
        self.assertTrue(self.plan().ok, self.plan().errors)

    def test_an_image_name_override_reaches_the_plan(self):
        self.form.final_image.setText("acme/dev:latest")
        self.assertEqual(self.plan().image, "acme/dev:latest")
        self.form.final_image.clear()
        self.assertEqual(self.plan().image, "docker_envs:24.04-rolling")

    def test_a_rejected_selection_surfaces_an_error(self):
        self.form.os_choice.set_value("22.04")  # ROS options still list 24.04 distros
        plan = self.plan()
        self.assertFalse(plan.ok)
        self.assertTrue(any("not offered for Ubuntu" in message for message in plan.errors))


@unittest.skipUnless(PYSIDE, "PySide6 is not installed")
class PanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])
        cls.bridge = Bridge(ROOT)

    def test_plan_view_renders_every_layer(self):
        from docker_envs_gui.model import Selection

        view = PlanView()
        plan = self.bridge.plan(Selection(os="24.04", ros="jazzy", usage="both"))
        view.set_plan(plan)
        self.assertEqual(view.layers.topLevelItemCount(), len(plan.layers))
        self.assertEqual(view.image_name.text(), plan.image)
        self.assertEqual(view.replay.text(), plan.replay)

    def test_plan_view_shows_errors_and_hides_the_command(self):
        from docker_envs_gui.model import Selection

        view = PlanView()
        view.set_plan(self.bridge.plan(Selection(os="24.04", ros="humble")))
        self.assertTrue(view.messages.isVisibleTo(view))
        self.assertEqual(view.replay.text(), "")

    def test_log_view_renders_colour_and_filters_lines(self):
        view = LogView()
        view.append("\x1b[32mINFO:\x1b[0m ready\n")
        view.append("\x1b[1;36m== Building img (layer 1/2) ==\x1b[0m\n")
        self.assertEqual(view.plain_text(), "INFO: ready\n== Building img (layer 1/2) ==")
        view.filter.setText("layer")
        self.assertEqual(view.console.toPlainText().strip(), "== Building img (layer 1/2) ==")

    def test_partial_lines_are_held_until_complete(self):
        view = LogView()
        view.append("half ")
        self.assertEqual(view.console.toPlainText(), "")
        view.append("a line\n")
        self.assertEqual(view.console.toPlainText().strip(), "half a line")

    def test_strip_ansi_removes_cursor_movement_too(self):
        self.assertEqual(strip_ansi("\x1b[2K\x1b[32mdone\x1b[0m"), "done")


if __name__ == "__main__":
    unittest.main()


def group_gone(pgid, timeout=5.0):
    """True once no process in *pgid* is left.

    The shell exits on SIGTERM before its children have been reaped, so the group
    disappears shortly after the runner reports it finished, not at the same
    instant.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            os.killpg(pgid, 0)
        except ProcessLookupError:
            return True
        time.sleep(0.05)
    return False


@unittest.skipUnless(PYSIDE, "PySide6 is not installed")
class BuildRunnerTests(unittest.TestCase):
    """The runner against a real subprocess, without Docker.

    The command stands in for run_env.sh: the runner only ever reads its merged
    output and its exit status, so synthetic output exercises the same path a
    build takes.
    """

    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])

    def run_until_finished(self, command, timeout_ms=15000):
        runner = BuildRunner(ROOT)
        events = {"output": [], "layers": [], "steps": [], "result": None}
        runner.output.connect(events["output"].append)
        runner.layer_started.connect(lambda *a: events["layers"].append(a))
        runner.step_progress.connect(lambda *a: events["steps"].append(a))

        loop = QEventLoop()
        runner.finished.connect(lambda ok, summary: events.update(result=(ok, summary)))
        runner.finished.connect(loop.quit)
        guard = QTimer()
        guard.setSingleShot(True)
        guard.timeout.connect(loop.quit)
        guard.start(timeout_ms)

        runner.start(command)
        loop.exec()
        runner.wait()
        return runner, events

    def test_output_layers_and_steps_reach_the_signals(self):
        script = (
            r"printf '== Building docker_envs/base:24.04 (layer 1/2) ==\n'; "
            r"printf '#4 [1/4] FROM ubuntu:24.04\n'; "
            r"printf '#5 [ 3/4] RUN apt-get update\n'; "
            r"printf '== Building docker_envs:24.04 (layer 2/2) ==\n'; "
            r"printf '#9 DONE 1.2s\n'"
        )
        _runner, events = self.run_until_finished(script)
        self.assertEqual(events["result"], (True, "Build finished successfully."))
        self.assertEqual(
            events["layers"],
            [(1, 2, "docker_envs/base:24.04"), (2, 2, "docker_envs:24.04")],
        )
        self.assertEqual(events["steps"], [(1, 4), (3, 4)])
        self.assertIn("RUN apt-get update", "".join(events["output"]))

    def test_a_failing_command_reports_its_exit_status(self):
        _runner, events = self.run_until_finished("echo nope >&2; exit 3")
        self.assertEqual(events["result"], (False, "Build failed (exit status 3)."))
        # stderr is merged, so a failure explains itself in the log.
        self.assertIn("nope", "".join(events["output"]))

    def test_cancel_stops_the_whole_process_group(self):
        runner = BuildRunner(ROOT)
        result = {}
        loop = QEventLoop()
        runner.finished.connect(lambda ok, summary: result.update(ok=ok, summary=summary))
        runner.finished.connect(loop.quit)

        # A child that ignores its parent dying: only a process-group signal ends
        # this, which is what a docker build under run_env.sh behaves like.
        runner.start("sleep 120 & wait")
        self.assertTrue(runner.running)
        group = runner._process.pid

        QTimer.singleShot(300, runner.cancel)
        QTimer.singleShot(15000, loop.quit)
        loop.exec()
        runner.wait()

        self.assertEqual(result.get("summary"), "Build cancelled.")
        self.assertFalse(result.get("ok"))
        self.assertTrue(group_gone(group), "the build process group outlived the cancel")

    def test_the_build_environment_forces_plain_buildkit_output(self):
        from docker_envs_gui.builder import build_environment

        env = build_environment()
        self.assertEqual(env["BUILDKIT_PROGRESS"], "plain")
        self.assertEqual(env["DOCKER_BUILDKIT"], "1")


@unittest.skipUnless(PYSIDE, "PySide6 is not installed")
class LogPlacementTests(unittest.TestCase):
    """Giving the build log more room: expand in place, or its own window."""

    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])
        cls.bridge = Bridge(ROOT)
        cls.defaults = cls.bridge.defaults()

    def setUp(self):
        from PySide6.QtCore import QThreadPool

        class OfflineWindow(MainWindow):
            """MainWindow without the online version lookups."""

            def refresh_versions(self, kinds=()):
                return None

        self.window = OfflineWindow(self.bridge, self.defaults)
        self.window.resize(1400, 900)
        self.window.show()
        self.addCleanup(QThreadPool.globalInstance().waitForDone, 10000)
        self.addCleanup(self.window.close)

    @property
    def log(self):
        return self.window.log_view

    def test_expanding_collapses_the_form_and_the_plan_then_restores_them(self):
        before = (self.window.main_split.sizes(), self.window.right_split.sizes())

        self.log.expand_button.setChecked(True)
        self.assertEqual(self.window.main_split.sizes()[0], 0)
        self.assertEqual(self.window.right_split.sizes()[0], 0)
        self.assertEqual(self.log.expand_button.text(), "Restore")

        self.log.expand_button.setChecked(False)
        self.assertEqual((self.window.main_split.sizes(), self.window.right_split.sizes()), before)
        self.assertEqual(self.log.expand_button.text(), "Expand")

    def test_popping_out_moves_the_log_into_its_own_window(self):
        self.log.append("a line from the build\n")

        self.log.popout_button.setChecked(True)
        self.assertIsNotNone(self.window._log_window)
        self.assertIs(self.log.parent(), self.window._log_window)
        self.assertTrue(self.window._log_placeholder.isVisible())
        self.assertEqual(self.log.popout_button.text(), "Dock")

        # The view is the same object, so streamed output keeps arriving.
        self.log.append("and another\n")
        self.assertIn("and another", self.log.plain_text())

    def test_closing_the_detached_window_docks_the_log(self):
        self.log.popout_button.setChecked(True)
        self.window._log_window.close()

        self.assertIsNone(self.window._log_window)
        self.assertIs(self.log.parent(), self.window.log_container)
        self.assertFalse(self.window._log_placeholder.isVisible())
        self.assertEqual(self.log.popout_button.text(), "Pop out")
        self.assertFalse(self.log.popout_button.isChecked())

    def test_the_dock_button_puts_it_back_too(self):
        self.log.popout_button.setChecked(True)
        self.log.popout_button.setChecked(False)
        self.assertIsNone(self.window._log_window)
        self.assertIs(self.log.parent(), self.window.log_container)

    def test_popping_out_undoes_an_active_expand(self):
        before = self.window.main_split.sizes()
        self.log.expand_button.setChecked(True)
        self.log.popout_button.setChecked(True)

        self.assertFalse(self.log.expand_button.isChecked())
        self.assertEqual(self.window.main_split.sizes(), before)
        self.assertFalse(self.log.expand_button.isVisible())

    def test_closing_the_builder_leaves_no_detached_window_behind(self):
        self.log.popout_button.setChecked(True)
        detached = self.window._log_window
        self.window.close()
        self.assertIsNone(self.window._log_window)
        self.assertFalse(detached.isVisible())


@unittest.skipUnless(PYSIDE, "PySide6 is not installed")
class VersionComboTests(unittest.TestCase):
    """The version pickers for CUDA, MuJoCo, Isaac Sim and Isaac Lab.

    Isaac Lab is the demanding one: its entries are annotated as tags or branches,
    and its refs (``release/3.0.0``) look nothing like a version number. Because
    the combo is editable, an entry's text is both what the user sees in the edit
    box and what is read back, so the annotation must never be part of it.
    """

    REFS = ["v3.0.0-beta2", "v2.3.2", "main", "release/3.0.0"]
    NOTES = {
        "v3.0.0-beta2": "latest tag",
        "v2.3.2": "tag",
        "main": "branch, moves with upstream",
        "release/3.0.0": "branch, moves with upstream",
    }

    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])

    def combo(self, versions=None, notes=None, fallback="release/3.0.0"):
        widget = VersionCombo()
        widget.set_loading(fallback)
        widget.set_versions(versions if versions is not None else self.REFS, notes or self.NOTES)
        return widget

    def test_an_entrys_value_is_the_version_not_its_annotation(self):
        widget = self.combo()
        for index, expected in enumerate(self.REFS):
            with self.subTest(entry=expected):
                widget.combo.setCurrentIndex(index)
                self.assertEqual(widget.value(), expected)
                self.assertEqual(widget.combo.lineEdit().text(), expected)

    def test_the_annotation_is_kept_for_the_popup(self):
        widget = self.combo()
        self.assertEqual(widget.combo.itemData(0, ANNOTATION_ROLE), "latest tag")
        self.assertEqual(widget.combo.itemData(3, ANNOTATION_ROLE), "branch, moves with upstream")
        self.assertEqual(widget.values(), self.REFS)

    def test_refreshing_keeps_a_deliberate_choice(self):
        for index, chosen in enumerate(self.REFS):
            with self.subTest(chosen=chosen):
                widget = self.combo()
                widget.combo.setCurrentIndex(index)
                widget._mark_chosen()  # what activating an entry does
                widget.set_versions(self.REFS, self.NOTES)  # Refresh versions
                self.assertEqual(widget.value(), chosen)

    def test_an_untouched_picker_follows_the_newest_release(self):
        widget = self.combo(["3.13.0", "3.12.0"], {}, fallback="3.12.0")
        self.assertEqual(widget.value(), "3.13.0")
        widget.set_versions(["3.14.0", "3.13.0", "3.12.0"], {})
        self.assertEqual(widget.value(), "3.14.0")

    def test_a_hand_typed_version_is_taken_verbatim(self):
        widget = self.combo()
        widget.combo.lineEdit().setText("v3.0.0-beta2.patch1")
        self.assertEqual(widget.value(), "v3.0.0-beta2.patch1")

    def test_a_hand_typed_version_survives_a_refresh(self):
        widget = self.combo()
        widget.combo.lineEdit().setText("release/2.2.0")
        widget._mark_chosen()
        widget.set_versions(self.REFS, self.NOTES)
        # Not in the list any more, so the newest entry takes over rather than a
        # ref nothing offers; the important part is that it is a real ref.
        self.assertIn(widget.value(), self.REFS)

    def test_an_offline_lookup_falls_back_to_the_built_in_default(self):
        widget = self.combo([], {})
        self.assertEqual(widget.value(), "release/3.0.0")
        self.assertIn("Offline", widget.status.text())

    def test_every_picker_in_the_form_reports_a_plain_version(self):
        bridge = Bridge(ROOT)
        form = StageForm(bridge.defaults())
        form.set_ros_options(bridge.ros_for_os("24.04"))
        form.version_combo("cuda").set_versions(["13.3.1", "13.3.0"], {})
        form.version_combo("mujoco").set_versions(["3.13.0", "3.12.0"], {})
        form.version_combo("isaacsim").set_versions(["6.1.0.0", "6.0.1.0"], {})
        form.version_combo("isaaclab").set_versions(self.REFS, self.NOTES)
        for card in (form.base_card, form.mujoco_card, form.isaacsim_card, form.isaaclab_card):
            card.set_on(True)

        # Pick the second entry everywhere, as a user choosing an older release.
        for kind in ("cuda", "mujoco", "isaacsim", "isaaclab"):
            form.version_combo(kind).combo.setCurrentIndex(1)

        selection = form.selection()
        self.assertEqual(selection.cuda_version, "13.3.0")
        self.assertEqual(selection.mujoco_version, "3.12.0")
        self.assertEqual(selection.isaacsim_version, "6.0.1.0")
        self.assertEqual(selection.isaaclab_version, "v2.3.2")

        plan = bridge.plan(selection)
        self.assertTrue(plan.ok, plan.errors)
        for fragment in ("cuda13.3.0", "mujoco3.12.0", "isaacsim6.0.1.0", "isaaclab2.3.2"):
            self.assertIn(fragment, plan.image)

    def test_an_isaac_lab_branch_reaches_the_plan_as_a_git_ref(self):
        bridge = Bridge(ROOT)
        form = StageForm(bridge.defaults())
        form.set_ros_options(bridge.ros_for_os("24.04"))
        form.isaaclab_card.set_on(True)
        form.version_combo("isaaclab").set_versions(self.REFS, self.NOTES)
        form.version_combo("isaaclab").combo.setCurrentIndex(3)

        self.assertEqual(form.selection().isaaclab_version, "release/3.0.0")
        plan = bridge.plan(form.selection())
        self.assertTrue(plan.ok, plan.errors)
        # stages::tag_slug makes the ref safe for a tag; the -L flag keeps it whole.
        self.assertIn("isaaclabrelease-3.0.0", plan.image)
        self.assertIn("-L release/3.0.0", plan.replay)


def image(repository, tag, size="1GB", built_here=False, created="2026-09-12 12:00:00 +0200 CEST"):
    return ImageInfo(
        image_id=f"{repository}-{tag}"[:12],
        repository=repository,
        tag=tag,
        created=created,
        created_since="4 hours ago",
        size=size,
        containers="0",
        built_here=built_here,
    )


def container(name, state="running", image_name="docker_envs:24.04-jazzy"):
    return ContainerInfo(
        container_id=f"id-{name}",
        name=name,
        image=image_name,
        state=state,
        status="Up 9 hours" if state == "running" else "Exited (0) 2 hours ago",
        created="2026-09-12 07:00:00 +0200 CEST",
        created_since="9 hours ago",
        ports="",
        size="0B",
    )


@unittest.skipUnless(PYSIDE, "PySide6 is not installed")
class ImagesViewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self):
        self.view = ImagesView()
        self.view.set_images(
            [
                image("docker_envs", "24.04-jazzy", "130GB", built_here=True),
                image("docker_envs/ros", "24.04-jazzy", "30.4GB"),
                image("<none>", "<none>", "1.2GB", created="2026-09-10 09:00:00 +0200 CEST"),
            ]
        )

    def test_every_image_is_listed_including_dangling_ones(self):
        self.assertEqual(self.view.table.topLevelItemCount(), 3)
        self.assertIn("3 images", self.view.status.text())
        self.assertIn("1 built by this tool", self.view.status.text())

    def test_images_this_tool_built_are_marked(self):
        marks = {
            self.view.table.topLevelItem(i).text(0): self.view.table.topLevelItem(i).text(5)
            for i in range(self.view.table.topLevelItemCount())
        }
        self.assertEqual(marks["docker_envs"], "yes")
        self.assertEqual(marks["docker_envs/ros"], "")

    def test_newest_first_rather_than_alphabetical(self):
        self.assertEqual(self.view.table.topLevelItem(2).text(0), "<none>")

    def test_selecting_an_image_asks_for_its_build_command(self):
        seen = []
        self.view.selection_changed.connect(seen.append)
        self.view.select_reference("docker_envs:24.04-jazzy")
        self.assertEqual(seen, ["docker_envs:24.04-jazzy"])

        self.view.set_build_command("docker_envs:24.04-jazzy", "run_env.sh -b -v jazzy")
        self.assertEqual(self.view.replay.text(), "run_env.sh -b -v jazzy")

    def test_an_image_without_a_build_command_says_so(self):
        self.view.select_reference("docker_envs/ros:24.04-jazzy")
        self.view.set_build_command("docker_envs/ros:24.04-jazzy", "")
        self.assertEqual(self.view.replay.text(), "")
        self.assertIn("no build-command label", self.view.replay.field.placeholderText())

    def test_the_filter_narrows_the_listing(self):
        self.view.filter.setText("ros")
        visible = [
            self.view.table.topLevelItem(i).text(0)
            for i in range(self.view.table.topLevelItemCount())
            if not self.view.table.topLevelItem(i).isHidden()
        ]
        self.assertEqual(visible, ["docker_envs/ros"])
        self.assertIn("1 of 3", self.view.status.text())

    def test_a_docker_failure_is_shown_rather_than_an_empty_table(self):
        self.view.set_error("docker daemon is not reachable")
        self.assertEqual(self.view.table.topLevelItemCount(), 0)
        self.assertIn("not reachable", self.view.status.text())


@unittest.skipUnless(PYSIDE, "PySide6 is not installed")
class ContainersViewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self):
        self.view = ContainersView()
        self.view.set_containers(
            [container("alpha"), container("zulu", "exited"), container("bravo")]
        )

    def select(self, *names):
        self.view.table.clearSelection()
        for index in range(self.view.table.topLevelItemCount()):
            item = self.view.table.topLevelItem(index)
            if item.text(0) in names:
                item.setSelected(True)

    def test_running_and_stopped_containers_are_both_listed(self):
        self.assertEqual(self.view.table.topLevelItemCount(), 3)
        self.assertIn("3 containers", self.view.status.text())
        self.assertIn("2 running", self.view.status.text())

    def test_running_containers_come_first(self):
        order = [self.view.table.topLevelItem(i).text(0) for i in range(3)]
        self.assertEqual(order, ["alpha", "bravo", "zulu"])

    def test_no_action_is_offered_without_a_selection(self):
        for button in (self.view.stop_button, self.view.restart_button, self.view.remove_button):
            self.assertFalse(button.isEnabled())

    def test_stop_is_offered_only_when_something_selected_is_running(self):
        self.select("zulu")
        self.assertFalse(self.view.stop_button.isEnabled())
        self.assertTrue(self.view.restart_button.isEnabled())
        self.assertTrue(self.view.remove_button.isEnabled())

        self.select("alpha")
        self.assertTrue(self.view.stop_button.isEnabled())

    def test_actions_report_every_selected_container(self):
        requests = []
        self.view.action_requested.connect(lambda action, names: requests.append((action, names)))

        self.select("alpha", "bravo")
        self.view.stop_button.click()
        self.view.restart_button.click()
        self.view.remove_button.click()

        self.assertEqual([action for action, _names in requests], ["stop", "restart", "remove"])
        for _action, names in requests:
            self.assertEqual(sorted(names), ["alpha", "bravo"])

    def test_a_refresh_keeps_the_selection(self):
        self.select("bravo")
        self.view.set_containers(
            [container("alpha"), container("zulu", "exited"), container("bravo")]
        )
        self.assertEqual(self.view.selected_names(), ["bravo"])

    def test_actions_are_withheld_while_a_previous_one_is_running(self):
        self.select("alpha")
        self.view.set_busy(True)
        for button in (self.view.stop_button, self.view.restart_button, self.view.remove_button):
            self.assertFalse(button.isEnabled())
        self.view.set_busy(False)
        self.assertTrue(self.view.stop_button.isEnabled())


class FakeDocker:
    """Stands in for DockerCli so the tabs can be driven without a daemon."""

    def __init__(self):
        self.calls = []
        self.image_rows = [image("docker_envs", "24.04-jazzy", built_here=True)]
        self.container_rows = [container("alpha"), container("zulu", "exited")]

    def images(self):
        self.calls.append(("images",))
        return list(self.image_rows)

    def containers(self):
        self.calls.append(("containers",))
        return list(self.container_rows)

    def build_command(self, reference):
        self.calls.append(("build_command", reference))
        return "run_env.sh -b -v jazzy"

    def stop(self, name):
        self.calls.append(("stop", name))

    def restart(self, name):
        self.calls.append(("restart", name))

    def remove(self, name, force=False):
        self.calls.append(("remove", name, force))


@unittest.skipUnless(PYSIDE, "PySide6 is not installed")
class TabTests(unittest.TestCase):
    """The Build / Images / Containers tabs and the actions behind them."""

    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])
        cls.bridge = Bridge(ROOT)
        cls.defaults = cls.bridge.defaults()

    def setUp(self):
        from PySide6.QtCore import QThreadPool

        from docker_envs_gui.app import TAB_BUILD, TAB_CONTAINERS, TAB_IMAGES

        self.TAB_BUILD, self.TAB_IMAGES, self.TAB_CONTAINERS = (
            TAB_BUILD,
            TAB_IMAGES,
            TAB_CONTAINERS,
        )
        self.confirmations = []

        outer = self

        class TabWindow(MainWindow):
            """No online lookups, no daemon, and a recorded removal prompt."""

            def refresh_versions(self, kinds=()):
                return None

            def _confirm_removal(self, names, force):
                outer.confirmations.append((list(names), dict(force)))
                return outer.allow_removal

        self.allow_removal = True
        self.window = TabWindow(self.bridge, self.defaults)
        self.window.docker = FakeDocker()
        self.window.show()
        self.addCleanup(QThreadPool.globalInstance().waitForDone, 10000)
        self.addCleanup(self.window.close)

    def settle(self, timeout=10000):
        """Let a submitted task finish and its queued result be delivered."""
        from PySide6.QtCore import QThreadPool

        QThreadPool.globalInstance().waitForDone(timeout)
        self.application.processEvents()

    @property
    def docker(self):
        return self.window.docker

    def test_the_window_has_the_three_tabs(self):
        tabs = [self.window.tabs.tabText(i) for i in range(self.window.tabs.count())]
        self.assertEqual(tabs, ["Build", "Images", "Containers"])

    def test_nothing_is_read_from_docker_until_a_tab_is_opened(self):
        self.assertEqual(self.docker.calls, [])

    def test_opening_the_images_tab_loads_it_once(self):
        self.window.tabs.setCurrentIndex(self.TAB_IMAGES)
        self.settle()
        self.assertIn(("images",), self.docker.calls)
        self.assertEqual(self.window.images_view.table.topLevelItemCount(), 1)

        # Going away and back must not re-read; that is what Refresh is for.
        loads = self.docker.calls.count(("images",))
        self.window.tabs.setCurrentIndex(self.TAB_BUILD)
        self.window.tabs.setCurrentIndex(self.TAB_IMAGES)
        self.settle()
        self.assertEqual(self.docker.calls.count(("images",)), loads)

    def test_the_refresh_button_reloads_the_listing(self):
        self.window.tabs.setCurrentIndex(self.TAB_IMAGES)
        self.settle()
        before = self.docker.calls.count(("images",))
        self.window.images_view.refresh_button.click()
        self.settle()
        self.assertEqual(self.docker.calls.count(("images",)), before + 1)

    def test_version_refresh_belongs_to_the_build_tab_only(self):
        self.window.tabs.setCurrentIndex(self.TAB_IMAGES)
        self.assertFalse(self.window.refresh_button.isVisible())
        self.window.tabs.setCurrentIndex(self.TAB_BUILD)
        self.assertTrue(self.window.refresh_button.isVisible())

    def test_opening_the_containers_tab_loads_it(self):
        self.window.tabs.setCurrentIndex(self.TAB_CONTAINERS)
        self.settle()
        self.assertIn(("containers",), self.docker.calls)
        self.assertEqual(self.window.containers_view.table.topLevelItemCount(), 2)

    def load_containers(self):
        self.window.tabs.setCurrentIndex(self.TAB_CONTAINERS)
        self.settle()
        self.docker.calls.clear()

    def test_stopping_skips_containers_that_are_not_running(self):
        self.load_containers()
        self.window._on_container_action("stop", ["alpha", "zulu"])
        self.settle()
        self.assertIn(("stop", "alpha"), self.docker.calls)
        self.assertNotIn(("stop", "zulu"), self.docker.calls)

    def test_restart_applies_to_everything_selected(self):
        self.load_containers()
        self.window._on_container_action("restart", ["alpha", "zulu"])
        self.settle()
        self.assertIn(("restart", "alpha"), self.docker.calls)
        self.assertIn(("restart", "zulu"), self.docker.calls)

    def test_removal_asks_first_and_a_refusal_removes_nothing(self):
        self.load_containers()
        self.allow_removal = False
        self.window._on_container_action("remove", ["alpha", "zulu"])
        self.settle()
        self.assertEqual(len(self.confirmations), 1)
        self.assertEqual(sorted(self.confirmations[0][0]), ["alpha", "zulu"])
        self.assertFalse([call for call in self.docker.calls if call[0] == "remove"])

    def test_removal_forces_only_the_running_containers(self):
        self.load_containers()
        self.window._on_container_action("remove", ["alpha", "zulu"])
        self.settle()
        self.assertEqual(self.confirmations[0][1], {"alpha": True, "zulu": False})
        self.assertIn(("remove", "alpha", True), self.docker.calls)
        self.assertIn(("remove", "zulu", False), self.docker.calls)

    def test_a_completed_action_re_reads_the_listing(self):
        self.load_containers()
        self.window._on_container_action("restart", ["alpha"])
        self.settle()
        self.assertIn(("containers",), self.docker.calls)
        self.assertIn("restarted", self.window.status_label.text())

    def test_a_failing_action_is_reported_and_the_listing_re_read(self):
        from docker_envs_gui.docker_cli import DockerError

        self.load_containers()

        def boom(name):
            raise DockerError("no such container")

        self.docker.restart = boom
        self.window._on_container_action("restart", ["alpha"])
        self.settle()
        self.assertIn("no such container", self.window.containers_view.status.text())
