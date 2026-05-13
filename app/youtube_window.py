"""YouTube URL input window - frameless, dark, violet-accented redesign.

Visual reference: the `.win` chrome pattern + `.ed-input` / `.btn` rules in
`_design_handoff_temp/project/styles-windows.css` (lines 236-310). The
validation contract (`_looks_like_youtube_url`, `_ALLOWED_HOSTS`) and the
public signal surface are preserved 1:1 from the prior implementation -
only the chrome changes.
"""

from __future__ import annotations

from urllib.parse import urlparse

from PyQt6.QtCore import (
    QEvent,
    QPoint,
    Qt,
    pyqtSignal,
)
from PyQt6.QtGui import QCursor, QGuiApplication
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from design import COLOR
from design.effects import fade_in


# Card is 520 wide (a touch more breathing room than the legacy 480).
WINDOW_W = 520
WINDOW_H = 200
OUTER_MARGIN = 0


_ALLOWED_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtu.be",
}


def _looks_like_youtube_url(text: str) -> bool:
    if not text or not isinstance(text, str):
        return False
    text = text.strip()
    if not text:
        return False
    try:
        parsed = urlparse(text)
    except Exception:
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    return (parsed.hostname or "").lower() in _ALLOWED_HOSTS


class YoutubeWindow(QWidget):
    """Modal-ish popup that prompts for a YouTube URL.

    Public surface - must stay stable for the tray controller:

        urlSubmitted = pyqtSignal(str)
        cancelled = pyqtSignal()
        def present(self) -> None
    """

    urlSubmitted = pyqtSignal(str)
    cancelled = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setFixedSize(WINDOW_W + 2 * OUTER_MARGIN, WINDOW_H + 2 * OUTER_MARGIN)

        self._drag_pos: QPoint | None = None
        self._build_ui()
        self._title_bar.installEventFilter(self)

    # -- construction ----------------------------------------

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(OUTER_MARGIN, OUTER_MARGIN, OUTER_MARGIN, OUTER_MARGIN)
        outer.setSpacing(0)

        self._card = QFrame(self)
        self._card.setObjectName("youtubeCard")
        self._card.setProperty("class", "win")
        self._card.setFixedSize(WINDOW_W, WINDOW_H)
        outer.addWidget(self._card, alignment=Qt.AlignmentFlag.AlignCenter)

        # Soft violet-tinted radial glow overlay (decorative; covers card).
        self._glow = QFrame(self._card)
        self._glow.setObjectName("youtubeGlow")
        self._glow.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._glow.setGeometry(0, 0, WINDOW_W, WINDOW_H)

        card_layout = QVBoxLayout(self._card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        self._build_header(card_layout)
        self._build_body(card_layout)
        self._build_footer(card_layout)

    # -- header ----------------------------------------------

    def _build_header(self, parent_layout: QVBoxLayout) -> None:
        self._title_bar = QWidget(self._card)
        self._title_bar.setObjectName("youtubeHeader")
        self._title_bar.setFixedHeight(44)
        self._title_bar.setCursor(Qt.CursorShape.SizeAllCursor)

        h = QHBoxLayout(self._title_bar)
        h.setContentsMargins(18, 0, 12, 0)
        h.setSpacing(10)

        # Brand glyph (violet rounded square with play-mark glyph).
        brand_mark = QLabel("▶")  # right-pointing triangle
        brand_mark.setProperty("class", "brand-mark")
        brand_mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand_mark.setFixedSize(22, 22)
        brand_mark.setStyleSheet(
            f"background:{COLOR.violet}; color:#FFFFFF; border-radius:6px;"
            f"font-size:11px; font-weight:700;"
        )
        h.addWidget(brand_mark, alignment=Qt.AlignmentFlag.AlignVCenter)

        title_label = QLabel("Shortcut")
        title_label.setProperty("class", "yt-title")
        title_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        h.addWidget(title_label, alignment=Qt.AlignmentFlag.AlignVCenter)

        dot = QLabel("·")
        dot.setStyleSheet(f"color:{COLOR.text_3}; font-size:13px;")
        dot.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        h.addWidget(dot, alignment=Qt.AlignmentFlag.AlignVCenter)

        ctx_label = QLabel("Transcribe YouTube")
        ctx_label.setProperty("class", "yt-hint")
        ctx_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        h.addWidget(ctx_label, alignment=Qt.AlignmentFlag.AlignVCenter)

        h.addStretch(1)

        # Close (cancel) button - small unicode glyph in a transparent icon-btn.
        self._close_btn = QPushButton("✕")
        self._close_btn.setProperty("class", "icon-btn")
        self._close_btn.setToolTip("Cancel and close (Esc)")
        self._close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._close_btn.clicked.connect(self._on_cancel)
        h.addWidget(self._close_btn, alignment=Qt.AlignmentFlag.AlignVCenter)

        parent_layout.addWidget(self._title_bar)

    # -- body ------------------------------------------------

    def _build_body(self, parent_layout: QVBoxLayout) -> None:
        body = QWidget(self._card)
        body.setObjectName("youtubeBody")
        b = QVBoxLayout(body)
        b.setContentsMargins(18, 14, 18, 14)
        b.setSpacing(8)

        self._url_input = QLineEdit(body)
        self._url_input.setObjectName("youtubeUrlInput")
        self._url_input.setProperty("class", "ed-input ed-mono")
        self._url_input.setPlaceholderText("Paste YouTube URL…")
        self._url_input.setClearButtonEnabled(True)
        self._url_input.setMinimumHeight(38)
        self._url_input.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._url_input.returnPressed.connect(self._on_submit)
        b.addWidget(self._url_input)

        # Inline error label - leaf state, not covered by global QSS.
        self._error_label = QLabel("", body)
        self._error_label.setObjectName("youtubeError")
        self._error_label.setWordWrap(True)
        self._error_label.setStyleSheet(
            f"color:{COLOR.danger}; font-size:11px;"
        )
        self._error_label.setVisible(False)
        b.addWidget(self._error_label)

        b.addStretch(1)
        parent_layout.addWidget(body, 1)

    # -- footer ----------------------------------------------

    def _build_footer(self, parent_layout: QVBoxLayout) -> None:
        footer = QWidget(self._card)
        footer.setObjectName("youtubeFooter")
        footer.setFixedHeight(52)
        f = QHBoxLayout(footer)
        f.setContentsMargins(16, 10, 16, 10)
        f.setSpacing(8)

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setProperty("class", "btn ghost")
        self._cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cancel_btn.setToolTip("Cancel (Esc)")
        self._cancel_btn.clicked.connect(self._on_cancel)
        f.addWidget(self._cancel_btn)

        f.addStretch(1)

        self._submit_btn = QPushButton("Transcribe")
        self._submit_btn.setProperty("class", "btn primary")
        self._submit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._submit_btn.setToolTip("Download audio and transcribe (Enter)")
        self._submit_btn.clicked.connect(self._on_submit)
        f.addWidget(self._submit_btn)

        parent_layout.addWidget(footer)

    # -- lifecycle -------------------------------------------

    def present(self) -> None:
        """Centre on screen, prefill from clipboard if it looks valid, focus."""
        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        geom = screen.availableGeometry()
        x = geom.x() + (geom.width() - self.width()) // 2
        y = geom.y() + int(geom.height() * 0.18)
        self.move(x, y)

        # Clipboard auto-fill: preserved from the legacy implementation.
        clip_text = (QGuiApplication.clipboard().text() or "").strip()
        if _looks_like_youtube_url(clip_text):
            self._url_input.setText(clip_text)
            self._url_input.selectAll()
        else:
            self._url_input.clear()

        self._error_label.setVisible(False)

        self.show()
        self.raise_()
        self.activateWindow()
        self._url_input.setFocus()

        # Window-level fade-in (no graphics-effect conflict with the card shadow).
        fade_in(self, duration_ms=200)

    # -- handlers --------------------------------------------

    def _on_submit(self) -> None:
        url = self._url_input.text().strip()
        if not _looks_like_youtube_url(url):
            self._error_label.setText(
                "That doesn't look like a YouTube URL. Expected youtube.com or youtu.be."
            )
            self._error_label.setVisible(True)
            self._url_input.setFocus()
            self._url_input.selectAll()
            return
        self._error_label.setVisible(False)
        self.urlSubmitted.emit(url)
        self.close()

    def _on_cancel(self) -> None:
        self.cancelled.emit()
        self.close()

    # -- input -----------------------------------------------

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self._on_cancel()
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._on_submit()
        else:
            super().keyPressEvent(event)

    def eventFilter(self, obj, event):
        if obj is self._title_bar:
            et = event.type()
            if (
                et == QEvent.Type.MouseButtonPress
                and event.button() == Qt.MouseButton.LeftButton
            ):
                self._drag_pos = (
                    event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                )
                return True
            if et == QEvent.Type.MouseMove and (
                event.buttons() & Qt.MouseButton.LeftButton
            ):
                if self._drag_pos is not None:
                    self.move(event.globalPosition().toPoint() - self._drag_pos)
                    return True
            if et == QEvent.Type.MouseButtonRelease:
                self._drag_pos = None
        return super().eventFilter(obj, event)
