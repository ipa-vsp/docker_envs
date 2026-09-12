"""Colour tokens and the application stylesheet.

The palette follows the system theme: the window colour Qt reports decides
whether the light or dark token set is used, so the app matches the desktop
without asking.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette
from PySide6.QtWidgets import QApplication


@dataclass(frozen=True)
class Palette:
    """One complete set of colour tokens."""

    background: str
    surface: str
    raised: str
    border: str
    text: str
    muted: str
    accent: str
    accent_text: str
    ok: str
    warning: str
    error: str
    console: str
    console_text: str


DARK = Palette(
    background="#14161a",
    surface="#1b1e24",
    raised="#232830",
    border="#2f3541",
    text="#e6e9ef",
    muted="#98a1b3",
    accent="#2496ed",
    accent_text="#ffffff",
    ok="#3fb950",
    warning="#d29922",
    error="#f85149",
    console="#0e1014",
    console_text="#d5dae3",
)

LIGHT = Palette(
    background="#f3f5f8",
    surface="#ffffff",
    raised="#eef1f6",
    border="#d6dbe4",
    text="#1b2027",
    muted="#5d6775",
    accent="#1a73d4",
    accent_text="#ffffff",
    ok="#1a7f37",
    warning="#8a6100",
    error="#cf222e",
    console="#151922",
    console_text="#dfe4ec",
)


def active_palette(app: QApplication) -> Palette:
    """DARK when the desktop theme is dark, LIGHT otherwise."""
    window = app.palette().color(QPalette.ColorRole.Window)
    return DARK if window.lightness() < 128 else LIGHT


def monospace_font(point_size: int = 10) -> QFont:
    font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
    font.setPointSize(point_size)
    return font


def _mix(colour: str, other: str, ratio: float) -> str:
    """Blend two hex colours, for hover and pressed states."""
    first, second = QColor(colour), QColor(other)
    blend = QColor.fromRgbF(
        first.redF() * (1 - ratio) + second.redF() * ratio,
        first.greenF() * (1 - ratio) + second.greenF() * ratio,
        first.blueF() * (1 - ratio) + second.blueF() * ratio,
    )
    return blend.name()


def stylesheet(palette: Palette) -> str:
    """The whole application stylesheet for one palette."""
    accent_hover = _mix(palette.accent, "#ffffff", 0.15)
    accent_down = _mix(palette.accent, "#000000", 0.15)
    subtle = _mix(palette.surface, palette.text, 0.06)
    return f"""
    QWidget {{
        background: {palette.background};
        color: {palette.text};
        font-size: 10pt;
    }}
    QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; border: none; }}
    /* Cards sit on their own surface colour, so anything drawn on top of one has
       to be transparent or it repaints the window ground as a bar. */
    QLabel, QCheckBox, QRadioButton {{ background: transparent; }}
    QSplitter::handle {{ background: {palette.border}; }}
    QSplitter::handle:horizontal {{ width: 1px; }}
    QSplitter::handle:vertical {{ height: 1px; }}

    QFrame#Card {{
        background: {palette.surface};
        border: 1px solid {palette.border};
        border-radius: 10px;
    }}
    QLabel#CardStep {{
        color: {palette.accent};
        font-weight: 600;
        font-size: 9pt;
    }}
    QLabel#CardTitle {{ font-size: 11pt; font-weight: 600; }}
    QLabel#CardHint, QLabel#FieldHint {{ color: {palette.muted}; font-size: 9pt; }}
    QLabel#SectionTitle {{
        font-size: 9pt;
        font-weight: 700;
        color: {palette.muted};
        letter-spacing: 1px;
    }}
    QLabel#ImageName {{
        font-weight: 600;
        color: {palette.accent};
    }}
    QLabel#Placeholder {{ color: {palette.muted}; }}
    QLabel#Error {{ color: {palette.error}; }}
    QLabel#Warning {{ color: {palette.warning}; }}
    QLabel#Ok {{ color: {palette.ok}; }}

    QLabel#Badge, QLabel#BadgeOk, QLabel#BadgeWarning {{
        background: {palette.raised};
        color: {palette.muted};
        border: 1px solid {palette.border};
        border-radius: 8px;
        padding: 1px 7px;
        font-size: 8pt;
    }}
    QLabel#BadgeOk {{ color: {palette.ok}; border-color: {palette.ok}; }}
    QLabel#BadgeWarning {{ color: {palette.warning}; border-color: {palette.warning}; }}

    QPushButton {{
        background: {palette.raised};
        border: 1px solid {palette.border};
        border-radius: 7px;
        padding: 6px 14px;
    }}
    QPushButton:hover {{ background: {subtle}; }}
    QPushButton:disabled {{ color: {palette.muted}; background: {palette.surface}; }}
    QPushButton#Primary {{
        background: {palette.accent};
        color: {palette.accent_text};
        border: 1px solid {palette.accent};
        font-weight: 600;
    }}
    QPushButton#Primary:hover {{ background: {accent_hover}; border-color: {accent_hover}; }}
    QPushButton#Primary:pressed {{ background: {accent_down}; }}
    QPushButton#Primary:disabled {{
        background: {palette.raised};
        color: {palette.muted};
        border-color: {palette.border};
    }}
    QPushButton#Danger {{ color: {palette.error}; }}
    QPushButton#Segment {{
        border-radius: 0px;
        padding: 6px 12px;
        border-left-width: 0px;
    }}
    QPushButton#Segment:checked {{
        background: {palette.accent};
        color: {palette.accent_text};
        border-color: {palette.accent};
    }}
    QPushButton#Icon {{ padding: 4px 8px; }}

    QLineEdit, QComboBox, QSpinBox, QPlainTextEdit, QTextEdit {{
        background: {palette.background};
        border: 1px solid {palette.border};
        border-radius: 7px;
        padding: 5px 8px;
        selection-background-color: {palette.accent};
        selection-color: {palette.accent_text};
    }}
    QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{ border-color: {palette.accent}; }}
    QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled {{ color: {palette.muted}; }}
    QComboBox::drop-down {{ border: none; width: 20px; }}
    QComboBox QAbstractItemView {{
        background: {palette.surface};
        border: 1px solid {palette.border};
        selection-background-color: {palette.accent};
        selection-color: {palette.accent_text};
        outline: none;
    }}

    QCheckBox {{ spacing: 8px; }}
    QCheckBox::indicator, QRadioButton::indicator {{
        width: 16px; height: 16px;
        border: 1px solid {palette.border};
        background: {palette.background};
    }}
    QCheckBox::indicator {{ border-radius: 4px; }}
    QRadioButton::indicator {{ border-radius: 8px; }}
    QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
        background: {palette.accent};
        border-color: {palette.accent};
    }}

    QTreeView, QTableWidget {{
        background: {palette.background};
        border: 1px solid {palette.border};
        border-radius: 8px;
        alternate-background-color: {palette.surface};
        outline: none;
    }}
    QHeaderView::section {{
        background: {palette.surface};
        color: {palette.muted};
        border: none;
        border-bottom: 1px solid {palette.border};
        padding: 5px 8px;
        font-size: 9pt;
    }}

    QTextEdit#Console {{
        background: {palette.console};
        color: {palette.console_text};
        border: 1px solid {palette.border};
        border-radius: 8px;
    }}

    QProgressBar {{
        background: {palette.raised};
        border: none;
        border-radius: 4px;
        height: 8px;
        text-align: center;
    }}
    QProgressBar::chunk {{ background: {palette.accent}; border-radius: 4px; }}

    QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
    QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
    QScrollBar::handle {{ background: {palette.border}; border-radius: 5px; min-height: 28px; }}
    QScrollBar::handle:hover {{ background: {palette.muted}; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height: 0px; width: 0px; }}
    QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

    QToolTip {{
        background: {palette.raised};
        color: {palette.text};
        border: 1px solid {palette.border};
        padding: 4px 6px;
    }}
    """
