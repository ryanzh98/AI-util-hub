"""Theme application entry point.

Loads Geist + Geist Mono TTFs (if present) from `assets/fonts/`, sets a
dark QPalette, then applies the concatenated stylesheet from
`design.stylesheet.build_qss`.
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtGui import QColor, QFont, QFontDatabase, QPalette
from PyQt6.QtWidgets import QApplication

from .stylesheet import build_qss
from .tokens import COLOR, FONT


_FONTS_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"


def _load_bundled_fonts() -> None:
    """Register every *.ttf under assets/fonts/ with QFontDatabase.

    Silently no-ops if the directory is missing or any individual font
    fails to load. We never want a missing font to crash the app.
    """
    try:
        if not _FONTS_DIR.exists():
            return
        for ttf in _FONTS_DIR.glob("*.ttf"):
            try:
                QFontDatabase.addApplicationFont(str(ttf))
            except Exception:
                # Ignore individual font failures (corrupt file, etc.).
                pass
    except Exception:
        # Glob/exists itself blew up - extremely defensive.
        pass


def _build_palette() -> QPalette:
    palette = QPalette()

    bg = QColor(COLOR.bg)
    surface_1 = QColor(COLOR.surface_1)
    surface_2 = QColor(COLOR.surface_2)
    text_1 = QColor(COLOR.text_1)
    text_3 = QColor(COLOR.text_3)
    violet = QColor(COLOR.violet)
    on_violet = QColor("#0C0D15")

    palette.setColor(QPalette.ColorRole.Window, bg)
    palette.setColor(QPalette.ColorRole.WindowText, text_1)
    palette.setColor(QPalette.ColorRole.Base, surface_1)
    palette.setColor(QPalette.ColorRole.AlternateBase, surface_2)
    palette.setColor(QPalette.ColorRole.Text, text_1)
    palette.setColor(QPalette.ColorRole.Button, surface_2)
    palette.setColor(QPalette.ColorRole.ButtonText, text_1)
    palette.setColor(QPalette.ColorRole.BrightText, QColor("#FFFFFF"))
    palette.setColor(QPalette.ColorRole.Highlight, violet)
    palette.setColor(QPalette.ColorRole.HighlightedText, on_violet)
    palette.setColor(QPalette.ColorRole.ToolTipBase, surface_2)
    palette.setColor(QPalette.ColorRole.ToolTipText, text_1)
    palette.setColor(QPalette.ColorRole.PlaceholderText, text_3)
    palette.setColor(QPalette.ColorRole.Link, violet)
    palette.setColor(QPalette.ColorRole.LinkVisited, violet)

    return palette


def apply_theme(app: QApplication) -> None:
    """Install fonts, palette, and the global QSS on the QApplication."""
    _load_bundled_fonts()

    font = QFont()
    # The stylesheet drives the sans family; the app font primarily
    # exists for widgets that don't pick up QSS (native dialogs).
    font.setFamilies(["Geist", "Segoe UI", "system-ui"])
    font.setPixelSize(FONT.size_md)
    app.setFont(font)

    app.setPalette(_build_palette())
    app.setStyleSheet(build_qss())


__all__ = ["apply_theme"]
