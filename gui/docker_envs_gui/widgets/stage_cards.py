"""The nine-stage build form.

Layout and wording follow ``creator/scripts/create_env.sh`` stage for stage, so
somebody who knows the wizard recognises the form immediately. The difference is
that every answer is visible and revisable at once, and the consequences (image
name, layers, command) update as they are given.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..bridge import Defaults, RosOption
from ..model import (
    ISAACLAB_METHODS,
    ISAACLAB_PHYSICS,
    ISAACLAB_VISUALIZERS,
    SUPPORTED_OS,
    USAGE_CHOICES,
    Selection,
    isaaclab_major,
)
from .common import Card, SegmentedControl, VersionCombo

CUSTOM = "__custom__"


def _combo(options: tuple[tuple[str, str, str, bool], ...]) -> QComboBox:
    """A combo built from ``(value, label, tooltip, needs_isaacsim)`` rows."""
    box = QComboBox()
    for value, label, tooltip, _needs_sim in options:
        box.addItem(label, value)
        box.setItemData(box.count() - 1, tooltip, Qt.ItemDataRole.ToolTipRole)
    return box


def _set_item_enabled(box: QComboBox, index: int, enabled: bool, reason: str) -> None:
    """Grey out one entry of a combo instead of hiding it, so the rule is visible."""
    item = box.model().item(index)
    if item is None:
        return
    item.setEnabled(enabled)
    if not enabled and reason:
        box.setItemData(index, reason, Qt.ItemDataRole.ToolTipRole)


class StageForm(QScrollArea):
    """Scrollable column of stage cards producing a :class:`Selection`."""

    changed = Signal()

    def __init__(self, defaults: Defaults, parent: QWidget | None = None):
        super().__init__(parent)
        self.defaults = defaults
        self._suspend = False

        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        container = QWidget()
        self.column = QVBoxLayout(container)
        self.column.setContentsMargins(14, 14, 14, 14)
        self.column.setSpacing(12)
        self.setWidget(container)

        self._build_os()
        self._build_base()
        self._build_ros()
        self._build_usage()
        self._build_mujoco()
        self._build_isaacsim()
        self._build_isaaclab()
        self._build_extras()
        self._build_user()
        self.column.addStretch(1)

        self._apply_constraints()

    # ----- stage 1: Ubuntu -------------------------------------------------- #

    def _build_os(self) -> None:
        card = Card(
            "Stage 1 of 9",
            "Ubuntu release",
            "The base OS every later layer is built on. It also decides which ROS 2 "
            "distributions are available.",
        )
        self.os_choice = SegmentedControl()
        self.os_choice.set_options([(value, value, "") for value in SUPPORTED_OS])
        self.os_choice.set_value(self.defaults.selection.get("OS", "24.04"))
        self.os_choice.changed.connect(self._on_changed)
        card.add_full_row(self.os_choice)
        self.os_card = card
        self.column.addWidget(card)

    # ----- stage 2: base image ---------------------------------------------- #

    def _build_base(self) -> None:
        card = Card(
            "Stage 2 of 9",
            "Base image",
            "The NVIDIA CUDA + cuDNN devel base is needed for GPU workloads and Isaac Sim. "
            "Without it the image starts from plain ubuntu.",
            toggleable=True,
        )
        card.switch.setText("CUDA + cuDNN")
        self.cuda_version = VersionCombo()
        self.cuda_version.set_loading(self.defaults.fallbacks.get("CUDA", "13.3.1"))
        self.cuda_version.changed.connect(self._on_changed)
        card.add_row("CUDA version", self.cuda_version)
        card.toggled.connect(self._on_changed)
        self.base_card = card
        self.column.addWidget(card)

    # ----- stage 3: ROS ----------------------------------------------------- #

    def _build_ros(self) -> None:
        card = Card(
            "Stage 3 of 9",
            "ROS 2 distribution",
            "Offered per Ubuntu release. Combinations built in CI are the best tested.",
        )
        self.ros_choice = SegmentedControl()
        self.ros_choice.changed.connect(self._on_changed)
        card.add_full_row(self.ros_choice)
        self.ros_note = QLabel()
        self.ros_note.setObjectName("FieldHint")
        self.ros_note.setWordWrap(True)
        card.add_full_row(self.ros_note)
        self._ros_options: list[RosOption] = []
        self.ros_card = card
        self.column.addWidget(card)

    # ----- stage 4: application stack ---------------------------------------- #

    def _build_usage(self) -> None:
        card = Card(
            "Stage 4 of 9",
            "Application stack",
            "Pre-installed ROS 2 application packages. Each choice adds one layer.",
        )
        self.usage_choice = SegmentedControl()
        self.usage_choice.set_options(USAGE_CHOICES)
        self.usage_choice.set_value("skip")
        self.usage_choice.changed.connect(self._on_changed)
        card.add_full_row(self.usage_choice)
        self.usage_note = QLabel()
        self.usage_note.setObjectName("Warning")
        self.usage_note.setWordWrap(True)
        self.usage_note.setVisible(False)
        card.add_full_row(self.usage_note)
        self.usage_card = card
        self.column.addWidget(card)

    # ----- stage 5: MuJoCo --------------------------------------------------- #

    def _build_mujoco(self) -> None:
        card = Card("Stage 5 of 9", "MuJoCo", "Physics engine plus Gymnasium.", toggleable=True)
        self.mujoco_version = VersionCombo()
        self.mujoco_version.set_loading(self.defaults.fallbacks.get("MUJOCO", "3.12.0"))
        self.mujoco_version.changed.connect(self._on_changed)
        card.add_row("MuJoCo version", self.mujoco_version)

        self.gym_version = QLineEdit(self.defaults.fallbacks.get("GYM", "1.3.0"))
        self.gym_version.textChanged.connect(self._on_changed)
        card.add_row("Gymnasium version", self.gym_version)
        card.toggled.connect(self._on_changed)
        self.mujoco_card = card
        self.column.addWidget(card)

    # ----- stage 6: Isaac Sim ------------------------------------------------ #

    def _build_isaacsim(self) -> None:
        card = Card(
            "Stage 6 of 9",
            "NVIDIA Isaac Sim",
            "Large layer: several GB of wheels from the NVIDIA package index.",
            toggleable=True,
        )
        self.isaacsim_version = VersionCombo()
        self.isaacsim_version.set_loading(self.defaults.fallbacks.get("ISAACSIM", "6.1.0.0"))
        self.isaacsim_version.changed.connect(self._on_changed)
        card.add_row("Isaac Sim version", self.isaacsim_version)

        self.isaacsim_note = QLabel(
            "Without the CUDA base, this image needs a GPU runtime supplied at run time."
        )
        self.isaacsim_note.setObjectName("Warning")
        self.isaacsim_note.setWordWrap(True)
        card.add_full_row(self.isaacsim_note)
        card.toggled.connect(self._on_changed)
        self.isaacsim_card = card
        self.column.addWidget(card)

    # ----- stage 7: Isaac Lab ------------------------------------------------ #

    def _build_isaaclab(self) -> None:
        card = Card(
            "Stage 7 of 9",
            "NVIDIA Isaac Lab",
            "Released tags and the branches worth pinning to — a new Isaac Sim often "
            "lands on a branch before a tag supports it.",
            toggleable=True,
        )
        self.isaaclab_version = VersionCombo()
        self.isaaclab_version.set_loading(self.defaults.fallbacks.get("ISAACLAB", "release/3.0.0"))
        self.isaaclab_version.changed.connect(self._on_isaaclab_version_changed)
        card.add_row("Isaac Lab version", self.isaaclab_version)

        self.isaaclab_method = SegmentedControl()
        self.isaaclab_method.set_options(ISAACLAB_METHODS)
        self.isaaclab_method.set_value("auto")
        self.isaaclab_method.changed.connect(self._on_changed)
        card.add_row("Installation", self.isaaclab_method)

        self.isaaclab_packages = QComboBox()
        self.isaaclab_packages.currentIndexChanged.connect(self._on_changed)
        card.add_row("Packages", self.isaaclab_packages)

        self.isaaclab_custom = QLineEdit()
        self.isaaclab_custom.setPlaceholderText("newton,rl[rsl-rl],visualizer[newton]")
        self.isaaclab_custom.textChanged.connect(self._on_changed)
        self.isaaclab_custom.setVisible(False)
        card.add_row("Selectors", self.isaaclab_custom)
        self.isaaclab_custom_label = card.form.labelForField(self.isaaclab_custom)
        self.isaaclab_custom_label.setVisible(False)

        self.isaaclab_physics = _combo(ISAACLAB_PHYSICS)
        self.isaaclab_physics.currentIndexChanged.connect(self._on_changed)
        card.add_row("Physics", self.isaaclab_physics)

        self.isaaclab_visualizer = _combo(ISAACLAB_VISUALIZERS)
        self.isaaclab_visualizer.currentIndexChanged.connect(self._on_changed)
        card.add_row("Visualization", self.isaaclab_visualizer)

        self.isaaclab_note = QLabel()
        self.isaaclab_note.setObjectName("FieldHint")
        self.isaaclab_note.setWordWrap(True)
        card.add_full_row(self.isaaclab_note)

        card.toggled.connect(self._on_changed)
        self.isaaclab_card = card
        self.column.addWidget(card)
        with self.suspended():
            self.set_isaaclab_selectors({})

    # ----- stage 8: extras --------------------------------------------------- #

    def _build_extras(self) -> None:
        card = Card(
            "Stage 8 of 9",
            "Extra layers",
            "Optional motion generation, middleware and simulation. Every Python package "
            "shares one environment, /opt/venv.",
        )
        self.curobo = QCheckBox("NVIDIA cuRobo (GPU motion generation, Python 3.12)")
        self.curobo.toggled.connect(self._on_changed)
        card.add_full_row(self.curobo)
        self.curobo_version = QLineEdit(self.defaults.fallbacks.get("CUROBO", "main"))
        self.curobo_version.setToolTip("cuRobo branch or tag to build from.")
        self.curobo_version.textChanged.connect(self._on_changed)
        card.add_row("cuRobo branch or tag", self.curobo_version)
        self.curobo_note = QLabel()
        self.curobo_note.setObjectName("Warning")
        self.curobo_note.setWordWrap(True)
        self.curobo_note.setVisible(False)
        card.add_full_row(self.curobo_note)
        self.zenoh = QCheckBox("Zenoh middleware (rmw_zenoh_cpp)")
        self.zenoh.toggled.connect(self._on_changed)
        card.add_full_row(self.zenoh)
        self.gazebo = QCheckBox("Gazebo simulation")
        self.gazebo.toggled.connect(self._on_changed)
        card.add_full_row(self.gazebo)
        self.extras_card = card
        self.column.addWidget(card)

    # ----- stage 9: user and naming ------------------------------------------ #

    def _build_user(self) -> None:
        card = Card(
            "Stage 9 of 9",
            "Container user and image name",
            "The account created inside the image. Matching your host UID and GID keeps "
            "bind-mounted workspaces writable.",
        )
        self.username = QLineEdit(self.defaults.selection.get("USERNAME", "admin"))
        self.username.textChanged.connect(self._on_changed)
        card.add_row("Username", self.username)

        ids = QWidget()
        ids_layout = QHBoxLayout(ids)
        ids_layout.setContentsMargins(0, 0, 0, 0)
        ids_layout.setSpacing(8)
        self.user_uid = QLineEdit(self.defaults.selection.get("USER_UID", "1000"))
        self.user_gid = QLineEdit(self.defaults.selection.get("USER_GID", "1000"))
        for editor, label in ((self.user_uid, "UID"), (self.user_gid, "GID")):
            editor.setValidator(QIntValidator(0, 2**31 - 1, editor))
            editor.textChanged.connect(self._on_changed)
            caption = QLabel(label)
            caption.setObjectName("FieldHint")
            ids_layout.addWidget(caption)
            ids_layout.addWidget(editor, 1)
        card.add_row("Host identity", ids)

        self.namespace = QLineEdit(self.defaults.selection.get("NAMESPACE", "docker_envs"))
        self.namespace.textChanged.connect(self._on_changed)
        card.add_row("Image namespace", self.namespace)

        name_row = QWidget()
        name_layout = QHBoxLayout(name_row)
        name_layout.setContentsMargins(0, 0, 0, 0)
        name_layout.setSpacing(6)
        self.final_image = QLineEdit()
        self.final_image.textChanged.connect(self._on_changed)
        name_layout.addWidget(self.final_image, 1)
        self.reset_name = QPushButton("Use derived")
        self.reset_name.setObjectName("Icon")
        self.reset_name.setToolTip("Clear the override and use the name derived from the stages.")
        self.reset_name.clicked.connect(lambda: self.final_image.clear())
        name_layout.addWidget(self.reset_name)
        card.add_row("Final image name", name_row)
        self.user_card = card
        self.column.addWidget(card)

    # ----- population from the bridge ---------------------------------------- #

    def set_ros_options(self, options: list[RosOption]) -> None:
        """Rebuild the ROS choices for the selected Ubuntu release."""
        self._ros_options = options
        previous = self.ros_choice.value()
        entries = []
        for option in options:
            label = option.distro
            if option.in_ci:
                label += "  ·  CI"
            entries.append((option.distro, label, option.note or ""))
        with self.suspended():
            self.ros_choice.set_options(entries)
            if options:
                keep = previous if previous in [o.distro for o in options] else options[0].distro
                self.ros_choice.set_value(keep)
        self._on_changed()

    def set_isaaclab_selectors(self, selectors: dict[str, str]) -> None:
        """Rebuild the package presets for the selected Isaac Lab version."""
        previous = self.isaaclab_packages.currentData()
        labels = [("default", "default — upstream defaults", "default")]
        for framework, value in selectors.items():
            if framework == "none":
                labels.append(("core", f"core — no optional packages ({value})", value))
            elif framework == "all":
                labels.append(("all", f"all RL frameworks ({value})", value))
            else:
                labels.append((framework, f"{framework} ({value})", value))
        with self.suspended():
            self.isaaclab_packages.clear()
            for _key, label, value in labels:
                self.isaaclab_packages.addItem(label, value)
            self.isaaclab_packages.addItem("custom — type the selectors", CUSTOM)
            index = self.isaaclab_packages.findData(previous)
            self.isaaclab_packages.setCurrentIndex(max(index, 0))
        self._on_changed()

    def version_combo(self, kind: str) -> VersionCombo:
        return {
            "cuda": self.cuda_version,
            "mujoco": self.mujoco_version,
            "isaacsim": self.isaacsim_version,
            "isaaclab": self.isaaclab_version,
        }[kind]

    # ----- selection ---------------------------------------------------------- #

    def selection(self) -> Selection:
        packages = self.isaaclab_packages.currentData()
        if packages == CUSTOM:
            packages = self.isaaclab_custom.text().strip() or "core"
        return Selection(
            os=self.os_choice.value(),
            ros=self.ros_choice.value(),
            use_cuda=self.base_card.is_on(),
            cuda_version=self.cuda_version.value(),
            usage=self.usage_choice.value() or "skip",
            mujoco=self.mujoco_card.is_on(),
            mujoco_version=self.mujoco_version.value(),
            gym_version=self.gym_version.text().strip(),
            isaacsim=self.isaacsim_card.is_on(),
            isaacsim_version=self.isaacsim_version.value(),
            isaaclab=self.isaaclab_card.is_on(),
            isaaclab_version=self.isaaclab_version.value(),
            isaaclab_method=self.isaaclab_method.value() or "auto",
            isaaclab_install=packages or "default",
            isaaclab_physics=self.isaaclab_physics.currentData() or "default",
            isaaclab_visualizer=self.isaaclab_visualizer.currentData() or "default",
            curobo=self.curobo.isChecked(),
            curobo_version=self.curobo_version.text().strip(),
            zenoh=self.zenoh.isChecked(),
            simulation=self.gazebo.isChecked(),
            username=self.username.text().strip() or "admin",
            user_uid=self.user_uid.text().strip(),
            user_gid=self.user_gid.text().strip(),
            namespace=self.namespace.text().strip() or "docker_envs",
            final_image=self.final_image.text().strip(),
        )

    def set_derived_image(self, image: str) -> None:
        """Show the derived name as the placeholder of the override field."""
        self.final_image.setPlaceholderText(image)
        self.reset_name.setEnabled(bool(self.final_image.text().strip()))

    # ----- constraints -------------------------------------------------------- #

    def suspended(self) -> _Suspend:
        """Context manager that stops intermediate edits emitting ``changed``."""
        return _Suspend(self)

    def _on_isaaclab_version_changed(self, _value: str) -> None:
        self._on_changed()

    def _on_changed(self, *_args: object) -> None:
        if self._suspend:
            return
        self._apply_constraints()
        self.changed.emit()

    def _apply_constraints(self) -> None:
        """Enable only what stages.sh would accept, and explain what is off."""
        selection = self.selection()
        has_sim = selection.isaacsim
        sim_reason = "Requires the Isaac Sim layer (stage 6)."

        # Stage 3/4 annotations.
        current = next((o for o in self._ros_options if o.distro == selection.ros), None)
        self.ros_note.setText(current.note if current and current.note else "")
        self.ros_note.setVisible(bool(current and current.note))
        no_usage_layers = selection.ros not in {"rolling", "jazzy", "kilted", "iron", "humble"}
        self.usage_note.setText(
            f"MoveIt and Nav2 are not published for {selection.ros}; that layer would be a no-op."
        )
        self.usage_note.setVisible(no_usage_layers and selection.usage != "skip")

        # Stage 6: the CUDA warning only matters once Isaac Sim is on.
        self.isaacsim_note.setVisible(has_sim and not selection.use_cuda)

        # Stage 7.
        major = isaaclab_major(selection.isaaclab_version)
        self.isaaclab_method.set_option_enabled("python-env", has_sim, sim_reason)
        self.isaaclab_method.set_option_enabled(
            "legacy",
            not has_sim and major >= 3,
            "Kit-less Isaac Lab 3.x only: remove the Isaac Sim layer.",
        )
        if not self._method_available(self.isaaclab_method.value(), has_sim, major):
            with self.suspended():
                self.isaaclab_method.set_value("auto")

        is_custom = self.isaaclab_packages.currentData() == CUSTOM
        self.isaaclab_custom.setVisible(is_custom)
        self.isaaclab_custom_label.setVisible(is_custom)

        backends = major >= 3
        for box, options in (
            (self.isaaclab_physics, ISAACLAB_PHYSICS),
            (self.isaaclab_visualizer, ISAACLAB_VISUALIZERS),
        ):
            box.setEnabled(backends)
            sim_only = set()
            for index, (value, _label, _tip, needs_sim) in enumerate(options):
                _set_item_enabled(box, index, not needs_sim or has_sim, sim_reason)
                if needs_sim:
                    sim_only.add(value)
            # Fall back to "default" rather than leaving a now-invalid choice
            # selected, which stages.sh would reject at plan time.
            if not backends or (not has_sim and box.currentData() in sim_only):
                with self.suspended():
                    box.setCurrentIndex(0)

        # 2.x installs into the Isaac Sim environment and has no Kit-less path, so
        # say so here rather than leaving it to the plan's error message.
        if selection.isaaclab and not backends and not has_sim:
            note, style = (
                "Isaac Lab 2.x installs into the Isaac Sim environment. "
                "Enable the Isaac Sim layer in stage 6, or pick a 3.x version to build "
                "without it.",
                "Warning",
            )
        elif selection.isaaclab and not backends:
            note, style = (
                "Isaac Lab 2.x uses Isaac Sim physics and Kit visualization; "
                "backend selection needs 3.x.",
                "FieldHint",
            )
        else:
            note, style = (
                f"Installation: {selection.isaaclab_effective_method()}. "
                "Physics and visualization add packages; pick the runtime at task launch.",
                "FieldHint",
            )
        self.isaaclab_note.setText(note)
        self.isaaclab_note.setObjectName(style)
        self.isaaclab_note.style().unpolish(self.isaaclab_note)
        self.isaaclab_note.style().polish(self.isaaclab_note)

        # Stage 8: cuRobo installs for Python 3.12 only.
        self.curobo_version.setEnabled(selection.curobo)
        curobo_note = ""
        if selection.curobo and has_sim and not selection.isaacsim_version.startswith("6"):
            curobo_note = (
                "cuRobo needs Python 3.12; this Isaac Sim pins another Python. Use Isaac Sim 6.x."
            )
        elif selection.curobo and selection.os == "22.04":
            curobo_note = (
                "ROS on Ubuntu 22.04 uses Python 3.10, so ROS nodes cannot import cuRobo."
            )
        self.curobo_note.setText(curobo_note)
        self.curobo_note.setVisible(bool(curobo_note))

        self.reset_name.setEnabled(bool(self.final_image.text().strip()))

    @staticmethod
    def _method_available(method: str, has_sim: bool, major: int) -> bool:
        if method == "python-env":
            return has_sim
        if method == "legacy":
            return not has_sim and major >= 3
        return True


class _Suspend:
    """Blocks ``changed`` while a group of widgets is rebuilt."""

    def __init__(self, form: StageForm):
        self._form = form
        self._previous = False

    def __enter__(self) -> StageForm:
        self._previous = self._form._suspend
        self._form._suspend = True
        return self._form

    def __exit__(self, *_exc: object) -> None:
        self._form._suspend = self._previous
