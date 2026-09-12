"""The panel showing what the current selection will produce.

Everything here comes from ``stages::build_plan`` by way of the bridge: the
derived image name, the ordered layers, the diagnostics, and the ``run_env.sh``
command that reproduces the selection. The command is also what the Build button
executes, so this panel is a preview of the action, not a description of it.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QSizePolicy,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..model import Plan
from ..theme import monospace_font
from .common import CopyField


class PlanView(QWidget):
    """Image name, diagnostics, layer list and the replay command."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 10)
        layout.setSpacing(9)

        title = QLabel("FINAL IMAGE")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        name_row = QHBoxLayout()
        name_row.setSpacing(8)
        self.image_name = QLabel()
        self.image_name.setObjectName("ImageName")
        self.image_name.setFont(monospace_font(11))
        self.image_name.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.image_name.setWordWrap(True)
        self.image_name.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        name_row.addWidget(self.image_name, 1)
        layout.addLayout(name_row)

        self.messages = QLabel()
        self.messages.setWordWrap(True)
        self.messages.setTextFormat(Qt.TextFormat.RichText)
        self.messages.setVisible(False)
        layout.addWidget(self.messages)

        self.isaaclab_line = QLabel()
        self.isaaclab_line.setObjectName("CardHint")
        self.isaaclab_line.setWordWrap(True)
        self.isaaclab_line.setVisible(False)
        layout.addWidget(self.isaaclab_line)

        self.layers_title = QLabel("BUILD PLAN")
        self.layers_title.setObjectName("SectionTitle")
        layout.addWidget(self.layers_title)

        self.layers = QTreeWidget()
        self.layers.setColumnCount(3)
        self.layers.setHeaderLabels(["#", "Dockerfile", "Produces"])
        self.layers.setRootIsDecorated(False)
        self.layers.setAlternatingRowColors(True)
        self.layers.setUniformRowHeights(True)
        self.layers.setFont(monospace_font(9))
        # Layer images share a long prefix and differ at the end.
        self.layers.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        header = self.layers.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.layers, 1)

        command_title = QLabel("EQUIVALENT COMMAND")
        command_title.setObjectName("SectionTitle")
        layout.addWidget(command_title)

        self.replay = CopyField("Resolve the errors above to see the command.")
        layout.addWidget(self.replay)

        hint = QLabel(
            "This is the command the Build button runs, and the value stored on the image "
            "as org.docker_envs.build-command."
        )
        hint.setObjectName("CardHint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

    def set_plan(self, plan: Plan) -> None:
        """Render one plan, valid or not."""
        if plan.ok:
            self.image_name.setText(plan.image)
            self.image_name.setObjectName("ImageName")
        else:
            self.image_name.setText("—")
            self.image_name.setObjectName("Placeholder")
        self.image_name.style().unpolish(self.image_name)
        self.image_name.style().polish(self.image_name)

        lines = [f"<b>Cannot build:</b> {text}" for text in plan.errors]
        lines += [f"Heads up: {text}" for text in plan.warnings]
        self.messages.setText("<br>".join(lines))
        self.messages.setObjectName("Error" if plan.errors else "Warning")
        self.messages.style().unpolish(self.messages)
        self.messages.style().polish(self.messages)
        self.messages.setVisible(bool(lines))

        if plan.isaaclab_packages:
            self.isaaclab_line.setText(
                f"Isaac Lab: {plan.isaaclab_method} installation, "
                f"packages {plan.isaaclab_packages}"
            )
        self.isaaclab_line.setVisible(bool(plan.isaaclab_packages))

        self.layers.clear()
        for layer in plan.layers:
            item = QTreeWidgetItem([str(layer.index), layer.dockerfile, layer.image])
            details = [f"from {layer.base}"] + layer.build_args
            item.setToolTip(1, "\n".join(details))
            item.setToolTip(2, "\n".join(details))
            self.layers.addTopLevelItem(item)
        self.layers_title.setText(
            f"BUILD PLAN — {len(plan.layers)} LAYERS" if plan.layers else "BUILD PLAN"
        )

        self.replay.set_text(plan.replay)
