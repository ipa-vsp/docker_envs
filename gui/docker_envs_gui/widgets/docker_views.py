"""The Images and Containers tabs.

Both are views onto ``docker image ls`` and ``docker ps -a``. They render what
they are given and emit requests; the window owns the Docker client and does the
work off the UI thread, the same arrangement the build form uses.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..docker_cli import ContainerInfo, ImageInfo, parse_size, parse_timestamp
from ..theme import monospace_font
from .common import CopyField

# Where a row keeps a value to be sorted by, when the displayed text would sort
# wrongly (sizes, and the running-first order).
SORT_ROLE = Qt.ItemDataRole.UserRole + 1


class _Row(QTreeWidgetItem):
    """A row that sorts on SORT_ROLE where one is set, and on text otherwise."""

    def __lt__(self, other: QTreeWidgetItem) -> bool:
        column = self.treeWidget().sortColumn() if self.treeWidget() else 0
        mine, theirs = self.data(column, SORT_ROLE), other.data(column, SORT_ROLE)
        if mine is not None and theirs is not None:
            return mine < theirs
        return self.text(column).lower() < other.text(column).lower()


class _DockerTable(QWidget):
    """Shared chrome: a title, a filter, a refresh button, a table and a status."""

    refresh_requested = Signal()

    def __init__(self, title: str, columns: list[str], parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(9)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        heading = QLabel(title)
        heading.setObjectName("SectionTitle")
        toolbar.addWidget(heading)
        toolbar.addStretch(1)

        self.filter = QLineEdit()
        self.filter.setPlaceholderText("Filter…")
        self.filter.setClearButtonEnabled(True)
        self.filter.setMaximumWidth(260)
        self.filter.textChanged.connect(self._apply_filter)
        toolbar.addWidget(self.filter)

        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.setObjectName("Icon")
        self.refresh_button.clicked.connect(self.refresh_requested)
        toolbar.addWidget(self.refresh_button)
        self._toolbar = toolbar
        layout.addLayout(toolbar)

        self.table = QTreeWidget()
        self.table.setColumnCount(len(columns))
        self.table.setHeaderLabels(columns)
        self.table.setRootIsDecorated(False)
        self.table.setAlternatingRowColors(True)
        self.table.setUniformRowHeights(True)
        self.table.setSortingEnabled(True)
        self.table.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        self.table.setFont(monospace_font(9))
        layout.addWidget(self.table, 1)

        self.status = QLabel()
        self.status.setObjectName("CardHint")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self._layout = layout

    # ----- helpers ---------------------------------------------------------------- #

    def _stretch(self, column: int) -> None:
        header = self.table.header()
        for index in range(self.table.columnCount()):
            mode = (
                QHeaderView.ResizeMode.Stretch
                if index == column
                else QHeaderView.ResizeMode.ResizeToContents
            )
            header.setSectionResizeMode(index, mode)

    def _apply_filter(self) -> None:
        needle = self.filter.text().strip().lower()
        shown = 0
        for index in range(self.table.topLevelItemCount()):
            item = self.table.topLevelItem(index)
            columns = (item.text(c).lower() for c in range(self.table.columnCount()))
            match = not needle or any(needle in text for text in columns)
            item.setHidden(not match)
            shown += match
        self._on_filtered(shown)

    def _on_filtered(self, shown: int) -> None:
        """Hook for the subclass to report the filtered count."""

    def set_busy(self, busy: bool) -> None:
        self.refresh_button.setEnabled(not busy)
        self.refresh_button.setText("Refreshing…" if busy else "Refresh")

    def set_error(self, message: str) -> None:
        self.table.clear()
        self.status.setText(message)
        self.status.setObjectName("Error")
        self._repolish()

    def _repolish(self) -> None:
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)

    def _set_status(self, text: str) -> None:
        self.status.setText(text)
        self.status.setObjectName("CardHint")
        self._repolish()


class ImagesView(_DockerTable):
    """Everything ``docker image ls --all`` reports."""

    COLUMNS = ["Repository", "Tag", "Image ID", "Created", "Size", "Built here"]

    def __init__(self, parent: QWidget | None = None):
        super().__init__("IMAGES", self.COLUMNS, parent)
        self._stretch(1)
        # Docker lists newest first and that is the useful order here; enabling
        # sorting would otherwise silently re-sort by the first column.
        self.table.sortByColumn(3, Qt.SortOrder.DescendingOrder)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.itemSelectionChanged.connect(self._on_selection)

        self.command_label = QLabel("BUILD COMMAND")
        self.command_label.setObjectName("SectionTitle")
        self._layout.insertWidget(self._layout.count() - 1, self.command_label)
        self.replay = CopyField("Select an image built by this tool.")
        self._layout.insertWidget(self._layout.count() - 1, self.replay)

        self._images: list[ImageInfo] = []
        self._commands: dict[str, str] = {}

    selection_changed = Signal(str)  # the selected image reference, or ""

    def set_images(self, images: list[ImageInfo]) -> None:
        selected = self.selected_reference()
        self.table.setSortingEnabled(False)
        self.table.clear()
        self._images = images
        for image in images:
            row = _Row(
                [
                    image.repository,
                    image.tag,
                    image.image_id,
                    image.created_since,
                    image.size,
                    "yes" if image.built_here else "",
                ]
            )
            row.setData(4, SORT_ROLE, parse_size(image.size))
            row.setData(3, SORT_ROLE, parse_timestamp(image.created))
            row.setData(0, Qt.ItemDataRole.UserRole, image.reference)
            row.setToolTip(0, f"{image.reference}\ncreated {image.created}")
            if image.dangling:
                row.setToolTip(0, "Dangling layer left by a rebuild.")
            self.table.addTopLevelItem(row)
        self.table.setSortingEnabled(True)
        self._apply_filter()

        ours = sum(1 for image in images if image.built_here)
        self._set_status(
            f"{len(images)} images · {ours} built by this tool · "
            "'Built here' marks images carrying org.docker_envs.build-command"
        )
        if selected:
            self.select_reference(selected)

    def selected_reference(self) -> str:
        items = self.table.selectedItems()
        return items[0].data(0, Qt.ItemDataRole.UserRole) if items else ""

    def select_reference(self, reference: str) -> None:
        for index in range(self.table.topLevelItemCount()):
            item = self.table.topLevelItem(index)
            if item.data(0, Qt.ItemDataRole.UserRole) == reference:
                item.setSelected(True)
                return

    def set_build_command(self, reference: str, command: str) -> None:
        self._commands[reference] = command
        if reference == self.selected_reference():
            self._show_command(reference)

    def _show_command(self, reference: str) -> None:
        command = self._commands.get(reference, "")
        self.replay.set_text(command)
        self.replay.field.setPlaceholderText(
            "This image carries no build-command label."
            if reference and reference in self._commands and not command
            else "Select an image built by this tool."
        )

    def _on_selection(self) -> None:
        reference = self.selected_reference()
        self._show_command(reference)
        self.selection_changed.emit(reference)

    def _on_filtered(self, shown: int) -> None:
        if self.filter.text().strip():
            self._set_status(f"{shown} of {len(self._images)} images match the filter")


class ContainersView(_DockerTable):
    """Everything ``docker ps -a`` reports, with the three lifecycle actions."""

    COLUMNS = ["Name", "Image", "State", "Status", "Created", "Ports"]

    action_requested = Signal(str, list)  # "stop" | "restart" | "remove", names

    def __init__(self, parent: QWidget | None = None):
        super().__init__("CONTAINERS", self.COLUMNS, parent)
        self._stretch(1)
        self.table.sortByColumn(2, Qt.SortOrder.AscendingOrder)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.itemSelectionChanged.connect(self._update_actions)

        self.stop_button = QPushButton("Stop")
        self.stop_button.setObjectName("Icon")
        self.stop_button.clicked.connect(lambda: self._request("stop"))

        self.restart_button = QPushButton("Restart")
        self.restart_button.setObjectName("Icon")
        self.restart_button.clicked.connect(lambda: self._request("restart"))

        self.remove_button = QPushButton("Remove")
        self.remove_button.setObjectName("Danger")
        self.remove_button.clicked.connect(lambda: self._request("remove"))

        # Actions sit left of the filter, in the order they escalate.
        for position, button in enumerate(
            (self.stop_button, self.restart_button, self.remove_button)
        ):
            self._toolbar.insertWidget(1 + position, button)
        self._toolbar.insertSpacing(4, 12)

        self._containers: list[ContainerInfo] = []
        self._update_actions()

    def set_containers(self, containers: list[ContainerInfo]) -> None:
        selected = set(self.selected_names())
        self.table.setSortingEnabled(False)
        self.table.clear()
        self._containers = containers
        for container in containers:
            row = _Row(
                [
                    container.name,
                    container.image,
                    container.state,
                    container.status,
                    container.created_since,
                    container.ports or "—",
                ]
            )
            # Running first, then alphabetically, which is what the default
            # sort on this column should mean.
            row.setData(2, SORT_ROLE, (0 if container.running else 1, container.name.lower()))
            row.setData(4, SORT_ROLE, parse_timestamp(container.created))
            row.setData(0, Qt.ItemDataRole.UserRole, container.name)
            row.setToolTip(0, f"{container.name}\n{container.container_id}\n{container.image}")
            row.setToolTip(4, container.created)
            if container.running:
                row.setForeground(2, QColor("#3fb950"))
            elif container.state in {"dead", "removing"}:
                row.setForeground(2, QColor("#f85149"))
            self.table.addTopLevelItem(row)
        self.table.setSortingEnabled(True)
        self._apply_filter()

        running = sum(1 for container in containers if container.running)
        self._set_status(
            f"{len(containers)} containers · {running} running · "
            "select one or more to stop, restart or remove"
        )
        for index in range(self.table.topLevelItemCount()):
            item = self.table.topLevelItem(index)
            if item.data(0, Qt.ItemDataRole.UserRole) in selected:
                item.setSelected(True)
        self._update_actions()

    def selected_names(self) -> list[str]:
        return [item.data(0, Qt.ItemDataRole.UserRole) for item in self.table.selectedItems()]

    def selected_containers(self) -> list[ContainerInfo]:
        names = set(self.selected_names())
        return [container for container in self._containers if container.name in names]

    def containers(self) -> list[ContainerInfo]:
        """Everything currently listed, selected or not."""
        return list(self._containers)

    def set_busy(self, busy: bool) -> None:
        super().set_busy(busy)
        self._update_actions(busy)

    def _update_actions(self, busy: bool = False) -> None:
        selected = self.selected_containers()
        any_running = any(container.running for container in selected)
        self.stop_button.setEnabled(bool(selected) and any_running and not busy)
        self.restart_button.setEnabled(bool(selected) and not busy)
        self.remove_button.setEnabled(bool(selected) and not busy)
        self.stop_button.setToolTip(
            "Stop the selected running containers."
            if any_running
            else "Nothing selected is running."
        )

    def _request(self, action: str) -> None:
        names = self.selected_names()
        if names:
            self.action_requested.emit(action, names)

    def _on_filtered(self, shown: int) -> None:
        if self.filter.text().strip():
            self._set_status(f"{shown} of {len(self._containers)} containers match the filter")
