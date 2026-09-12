"""Small reusable pieces the stage form is assembled from."""

from __future__ import annotations

from collections.abc import Iterable

from PySide6.QtCore import QModelIndex, QTimer, Qt, Signal
from PySide6.QtGui import QGuiApplication, QPalette
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QStyle,
    QStyleOptionViewItem,
    QStyledItemDelegate,
    QVBoxLayout,
    QWidget,
)

from ..theme import monospace_font

# Where an entry's human annotation lives ("latest tag", "branch, moves with
# upstream"). It is deliberately NOT part of the item's text: these combos are
# editable, so the text is what lands in the edit box and is read back as the
# value. Mixing the annotation in would put "(latest tag)" into a git ref.
ANNOTATION_ROLE = Qt.ItemDataRole.UserRole + 1


class Badge(QLabel):
    """A small pill for annotations such as "built in CI"."""

    def __init__(self, text: str = "", parent: QWidget | None = None):
        super().__init__(text, parent)
        self.setObjectName("Badge")
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)


class AnnotationDelegate(QStyledItemDelegate):
    """Draws an entry's annotation right-aligned and muted, in the popup only."""

    MARGIN = 10

    def paint(self, painter, option, index: QModelIndex) -> None:
        super().paint(painter, option, index)
        note = index.data(ANNOTATION_ROLE)
        if not note:
            return
        painter.save()
        if option.state & QStyle.StateFlag.State_Selected:
            colour = option.palette.color(QPalette.ColorRole.HighlightedText)
            colour.setAlpha(170)
        else:
            colour = option.palette.color(QPalette.ColorRole.PlaceholderText)
        painter.setPen(colour)
        painter.drawText(
            option.rect.adjusted(0, 0, -self.MARGIN, 0),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            note,
        )
        painter.restore()

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex):
        size = super().sizeHint(option, index)
        note = index.data(ANNOTATION_ROLE)
        if note:
            size.setWidth(
                size.width() + option.fontMetrics.horizontalAdvance(note) + 3 * self.MARGIN
            )
        return size


class VersionCombo(QWidget):
    """An editable version picker with an inline lookup status.

    Every version list in stages.sh is fetched online, so the widget has to show
    three states: looking up, the discovered list, and the offline fallback. It
    stays editable throughout — an exact version can always be pinned by hand.
    """

    changed = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)

        self.combo = QComboBox()
        self.combo.setEditable(True)
        self.combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.combo.setItemDelegate(AnnotationDelegate(self.combo))
        self.combo.currentTextChanged.connect(self.changed)
        # Only a deliberate pick or edit counts as a choice; until then a freshly
        # discovered list should jump to the newest release, as create_env.sh does.
        self.combo.activated.connect(self._mark_chosen)
        self.combo.lineEdit().textEdited.connect(self._mark_chosen)
        layout.addWidget(self.combo)

        self.status = QLabel()
        self.status.setObjectName("FieldHint")
        layout.addWidget(self.status)
        self._fallback = ""
        self._chosen = False

    def _mark_chosen(self, *_args: object) -> None:
        self._chosen = True

    def set_loading(self, fallback: str) -> None:
        self._fallback = fallback
        if not self.combo.count():
            self.combo.addItem(fallback)
        self.status.setText("Looking up available versions…")

    def set_versions(self, versions: list[str], annotations: dict[str, str] | None = None) -> None:
        """Populate the list, keeping whatever the user typed or chose.

        *annotations* labels entries in the popup ("latest tag", "branch, moves
        with upstream"); it never becomes part of a value.
        """
        # Compare against the value, not the displayed text: a refresh must not
        # throw away a deliberate choice.
        current = self.value() or self._fallback
        if not self._chosen and versions:
            current = versions[0]

        blocked = self.combo.blockSignals(True)
        self.combo.clear()
        if versions:
            for version in versions:
                self.combo.addItem(version)
                note = (annotations or {}).get(version, "")
                if note:
                    self.combo.setItemData(self.combo.count() - 1, note, ANNOTATION_ROLE)
                    self.combo.setItemData(
                        self.combo.count() - 1, note, Qt.ItemDataRole.ToolTipRole
                    )
            self.status.setText(f"{len(versions)} versions found · newest first")
            self.status.setObjectName("FieldHint")
        else:
            self.combo.addItem(self._fallback)
            self.status.setText(f"Offline — using the built-in default {self._fallback}")
            self.status.setObjectName("Warning")
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)
        self.set_value(current if current in self.values() else self.values()[0])
        self.combo.blockSignals(blocked)
        self.changed.emit(self.value())

    def values(self) -> list[str]:
        return [self.combo.itemText(i) for i in range(self.combo.count())]

    def value(self) -> str:
        """The version itself — the item text is the value, annotations aside."""
        return self.combo.currentText().strip()

    def set_value(self, value: str) -> None:
        # setCurrentText selects the matching entry when there is one and simply
        # fills the edit box when there is not, which is what pinning by hand does.
        self.combo.setCurrentText(value)


class Card(QFrame):
    """A titled section of the form, optionally switched on and off as a whole.

    Cards with ``toggleable=True`` correspond to the yes/no questions in
    create_env.sh: the switch is the answer, and the body holds the follow-up
    questions that only matter once it is on.
    """

    toggled = Signal(bool)

    def __init__(
        self,
        step: str,
        title: str,
        hint: str = "",
        toggleable: bool = False,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setObjectName("Card")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 13, 16, 15)
        outer.setSpacing(10)

        header = QHBoxLayout()
        header.setSpacing(9)
        titles = QVBoxLayout()
        titles.setSpacing(1)
        step_label = QLabel(step)
        step_label.setObjectName("CardStep")
        title_label = QLabel(title)
        title_label.setObjectName("CardTitle")
        titles.addWidget(step_label)
        titles.addWidget(title_label)
        header.addLayout(titles)
        header.addStretch(1)

        self.header_extra = QHBoxLayout()
        self.header_extra.setSpacing(6)
        header.addLayout(self.header_extra)

        self.switch: QCheckBox | None = None
        if toggleable:
            self.switch = QCheckBox("Include")
            self.switch.toggled.connect(self._on_toggled)
            header.addWidget(self.switch)
        outer.addLayout(header)

        if hint:
            hint_label = QLabel(hint)
            hint_label.setObjectName("CardHint")
            hint_label.setWordWrap(True)
            outer.addWidget(hint_label)

        self.body = QWidget()
        self.form = QFormLayout(self.body)
        self.form.setContentsMargins(0, 2, 0, 0)
        self.form.setSpacing(9)
        self.form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        outer.addWidget(self.body)

        if toggleable:
            self.body.setVisible(False)

    def add_badge(self, badge: QWidget) -> None:
        self.header_extra.addWidget(badge)

    def add_row(self, label: str, widget: QWidget) -> QWidget:
        # Editors size to their content by default, which leaves a card's rows
        # ragged; stretching them keeps the column of fields aligned.
        if isinstance(widget, (QComboBox, QLineEdit, VersionCombo)):
            widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.form.addRow(label, widget)
        return widget

    def add_full_row(self, widget: QWidget) -> QWidget:
        self.form.addRow(widget)
        return widget

    def is_on(self) -> bool:
        return self.switch is None or self.switch.isChecked()

    def set_on(self, value: bool) -> None:
        if self.switch is not None:
            self.switch.setChecked(value)

    def _on_toggled(self, checked: bool) -> None:
        self.body.setVisible(checked)
        self.toggled.emit(checked)


class SegmentedControl(QWidget):
    """A joined row of mutually exclusive buttons, for short fixed choices."""

    changed = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: dict[str, QPushButton] = {}
        self._layout.addStretch(1)

    def set_options(self, options: Iterable[tuple[str, str, str]]) -> None:
        """Replace the choices with ``(value, label, tooltip)`` triples."""
        for button in self._buttons.values():
            # deleteLater alone would leave the old buttons in the layout until
            # the next event-loop turn, which shows as a stale row.
            self._group.removeButton(button)
            self._layout.removeWidget(button)
            button.setParent(None)
            button.deleteLater()
        self._buttons.clear()

        items = list(options)
        for index, (value, label, tooltip) in enumerate(items):
            button = QPushButton(label)
            button.setObjectName("Segment")
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            if tooltip:
                button.setToolTip(tooltip)
            # Only the outer edges are rounded, so the row reads as one control.
            radii = []
            if index == 0:
                radii += ["border-top-left-radius:7px", "border-bottom-left-radius:7px"]
                radii += ["border-left-width:1px"]
            if index == len(items) - 1:
                radii += ["border-top-right-radius:7px", "border-bottom-right-radius:7px"]
            if radii:
                button.setStyleSheet("QPushButton#Segment{" + ";".join(radii) + ";}")
            button.clicked.connect(lambda _checked, v=value: self.changed.emit(v))
            self._group.addButton(button)
            self._buttons[value] = button
            self._layout.insertWidget(self._layout.count() - 1, button)

    def set_option_enabled(self, value: str, enabled: bool, reason: str = "") -> None:
        button = self._buttons.get(value)
        if button is not None:
            button.setEnabled(enabled)
            if reason:
                button.setToolTip(reason)

    def value(self) -> str:
        for value, button in self._buttons.items():
            if button.isChecked():
                return value
        return ""

    def set_value(self, value: str) -> None:
        button = self._buttons.get(value)
        if button is not None and not button.isChecked():
            button.setChecked(True)

    def values(self) -> list[str]:
        return list(self._buttons)


class CopyField(QWidget):
    """A read-only monospace value with a copy button."""

    def __init__(self, placeholder: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.field = QLineEdit()
        self.field.setReadOnly(True)
        self.field.setFont(monospace_font(9))
        self.field.setPlaceholderText(placeholder)
        self.field.setCursorPosition(0)
        layout.addWidget(self.field, 1)

        self.button = QPushButton("Copy")
        self.button.setObjectName("Icon")
        self.button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.button.clicked.connect(self._copy)
        layout.addWidget(self.button)

    def set_text(self, text: str) -> None:
        self.field.setText(text)
        self.field.setToolTip(text)
        self.field.setCursorPosition(0)
        self.button.setEnabled(bool(text))

    def text(self) -> str:
        return self.field.text()

    def _copy(self) -> None:
        clipboard = QGuiApplication.clipboard()
        if clipboard is not None and self.field.text():
            clipboard.setText(self.field.text())
            self.button.setText("Copied")
            QTimer.singleShot(1200, lambda: self.button.setText("Copy"))
