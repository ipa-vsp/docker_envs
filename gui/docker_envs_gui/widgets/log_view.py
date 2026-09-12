"""The build log console.

stages.sh colours its own output and BuildKit adds more, so the view renders SGR
escapes rather than showing them raw or throwing the colour away.
"""

from __future__ import annotations

import re

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..theme import monospace_font

SGR = re.compile(r"\x1b\[([0-9;]*)m")
OTHER_ESCAPES = re.compile(r"\x1b\[[0-9;]*[A-Za-ln-z]|\x1b\][^\x07]*\x07")

# The eight normal and eight bright ANSI colours, tuned for the console ground.
COLOURS = {
    30: "#5c6370",
    31: "#f07178",
    32: "#98c379",
    33: "#e5c07b",
    34: "#61afef",
    35: "#c678dd",
    36: "#56b6c2",
    37: "#dcdfe4",
    90: "#7f8796",
    91: "#ff8b94",
    92: "#b5e890",
    93: "#f0d399",
    94: "#81c5ff",
    95: "#dc9ff0",
    96: "#79d3dd",
    97: "#ffffff",
}

# A long build produces a lot of output; keeping every line would grow without
# bound, so the console holds a window of the most recent ones.
MAX_LINES = 20000


def strip_ansi(text: str) -> str:
    return OTHER_ESCAPES.sub("", SGR.sub("", text))


class LogView(QWidget):
    """Read-only console with live filtering and a save action."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 14)
        layout.setSpacing(8)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        title = QLabel("BUILD LOG")
        title.setObjectName("SectionTitle")
        toolbar.addWidget(title)
        toolbar.addStretch(1)

        self.filter = QLineEdit()
        self.filter.setPlaceholderText("Filter lines…")
        self.filter.setClearButtonEnabled(True)
        self.filter.setMaximumWidth(240)
        self.filter.textChanged.connect(self._rerender)
        toolbar.addWidget(self.filter)

        self.autoscroll = QCheckBox("Follow")
        self.autoscroll.setChecked(True)
        toolbar.addWidget(self.autoscroll)

        self.save_button = QPushButton("Save…")
        self.save_button.setObjectName("Icon")
        self.save_button.clicked.connect(self._save)
        toolbar.addWidget(self.save_button)

        self.clear_button = QPushButton("Clear")
        self.clear_button.setObjectName("Icon")
        self.clear_button.clicked.connect(self.clear)
        toolbar.addWidget(self.clear_button)
        layout.addLayout(toolbar)

        self.console = QTextEdit()
        self.console.setObjectName("Console")
        self.console.setReadOnly(True)
        self.console.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.console.setFont(monospace_font(9))
        layout.addWidget(self.console, 1)

        self._lines: list[str] = []
        self._pending = ""

    # ----- content ------------------------------------------------------------ #

    def append(self, text: str) -> None:
        """Add streamed output, which may arrive split mid-line."""
        self._pending += text.replace("\r\n", "\n").replace("\r", "")
        *complete, self._pending = self._pending.split("\n")
        for line in complete:
            self._lines.append(line)
            if len(self._lines) > MAX_LINES:
                del self._lines[: len(self._lines) - MAX_LINES]
            if self._matches(line):
                self._write(line)
        self._scroll()

    def clear(self) -> None:
        self._lines.clear()
        self._pending = ""
        self.console.clear()

    def plain_text(self) -> str:
        return "\n".join(strip_ansi(line) for line in self._lines)

    # ----- rendering ---------------------------------------------------------- #

    def _matches(self, line: str) -> bool:
        needle = self.filter.text().strip().lower()
        return not needle or needle in strip_ansi(line).lower()

    def _rerender(self) -> None:
        self.console.clear()
        for line in self._lines:
            if self._matches(line):
                self._write(line)
        self._scroll()

    def _write(self, line: str) -> None:
        cursor = self.console.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat()
        position = 0
        for match in SGR.finditer(line):
            chunk = line[position : match.start()]
            if chunk:
                cursor.insertText(OTHER_ESCAPES.sub("", chunk), fmt)
            fmt = self._apply_sgr(fmt, match.group(1))
            position = match.end()
        tail = line[position:]
        cursor.insertText(OTHER_ESCAPES.sub("", tail) + "\n", fmt)

    @staticmethod
    def _apply_sgr(fmt: QTextCharFormat, parameters: str) -> QTextCharFormat:
        result = QTextCharFormat(fmt)
        for token in (parameters or "0").split(";"):
            if not token:
                continue
            code = int(token)
            if code == 0:
                result = QTextCharFormat()
            elif code == 1:
                result.setFontWeight(700)
            elif code == 22:
                result.setFontWeight(400)
            elif code == 39:
                result.clearForeground()
            elif code in COLOURS:
                result.setForeground(QColor(COLOURS[code]))
        return result

    def _scroll(self) -> None:
        if self.autoscroll.isChecked():
            bar = self.console.verticalScrollBar()
            bar.setValue(bar.maximum())

    # ----- actions ------------------------------------------------------------ #

    def _save(self) -> None:
        path, _filter = QFileDialog.getSaveFileName(
            self, "Save build log", "docker-envs-build.log", "Log files (*.log *.txt)"
        )
        if path:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(self.plain_text() + "\n")
