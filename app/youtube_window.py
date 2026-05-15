"""YouTube URL input window — frameless, dark, violet-accented.

Visual reference: ``shortcut-handoff/shortcut/project/dialogs.jsx::YoutubeDialog``
(the React blueprint shipped by design). Brand chrome reads
"AI Util Hub · Transcribe YouTube" and uses the shared ``.win`` /
``.win-hd`` / ``.url-body`` / ``.rec-ft`` selectors from
``design/stylesheet.py`` so the look stays in sync with the recorder
and TTS dialogs.

Public surface (kept stable for ``tray_controller``):

* ``YoutubeWindow(parent=None)`` — the QWidget class.
* ``urlSubmitted = pyqtSignal(str)`` — emitted with a validated URL.
* ``cancelled = pyqtSignal()`` — emitted when the user dismisses.
* ``present()`` — show the dialog, prefill from clipboard, focus input.
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
from design.icons import icon, icon_size


# 760×220 per dialogs.jsx::YoutubeDialog (single-line URL input + footer).
WINDOW_W = 760
WINDOW_H = 220
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

    Public surface — must stay stable for the tray controller:

        urlSubmitted = pyqtSignal(str)
        cancelled    = pyqtSignal()
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

    # ── construction ────────────────────────────────────────

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(OUTER_MARGIN, OUTER_MARGIN, OUTER_MARGIN, OUTER_MARGIN)
        outer.setSpacing(0)

        # Card matches the .win shell from styles.css / stylesheet.py.
        self._card = QFrame(self)
        self._card.setObjectName("youtubeCard")
        self._card.setProperty("class", "win")
        self._card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._card.setFixedSize(WINDOW_W, WINDOW_H)
        outer.addWidget(self._card, alignment=Qt.AlignmentFlag.AlignCenter)

        # Soft violet-tinted radial glow overlay (decorative, ignores mouse).
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

    # ── header (.win-hd) ────────────────────────────────────

    def _build_header(self, parent_layout: QVBoxLayout) -> None:
        self._title_bar = QWidget(self._card)
        self._title_bar.setObjectName("youtubeHeader")
        self._title_bar.setProperty("class", "win-hd")
        self._title_bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._title_bar.setFixedHeight(48)
        self._title_bar.setCursor(Qt.CursorShape.SizeAllCursor)

        h = QHBoxLayout(self._title_bar)
        h.setContentsMargins(16, 14, 12, 10)
        h.setSpacing(10)

        # Brand glyph — violet rounded square with the rec-launcher checkmark
        # (matches dialogs.jsx, which uses I["rec-launcher"]).
        self._brand_mark = QLabel()
        self._brand_mark.setProperty("class", "brand-mark sm")
        self._brand_mark.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._brand_mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._brand_mark.setPixmap(icon("rec_launcher", "#FFFFFF", 12).pixmap(12, 12))
        self._brand_mark.setFixedSize(24, 24)
        h.addWidget(self._brand_mark, alignment=Qt.AlignmentFlag.AlignVCenter)

        # Brand title block: "AI Util Hub · Transcribe YouTube".
        title_label = QLabel("AI Util Hub")
        title_label.setProperty("class", "brand-title")
        title_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        h.addWidget(title_label, alignment=Qt.AlignmentFlag.AlignVCenter)

        slash = QLabel("·")
        slash.setProperty("class", "brand-title-slash")
        slash.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        h.addWidget(slash, alignment=Qt.AlignmentFlag.AlignVCenter)

        sub_label = QLabel("Transcribe YouTube")
        sub_label.setProperty("class", "brand-title-sub")
        sub_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        h.addWidget(sub_label, alignment=Qt.AlignmentFlag.AlignVCenter)

        h.addStretch(1)

        # Close icon-button (.icon-btn.close).
        self._close_btn = QPushButton()
        self._close_btn.setProperty("class", "icon-btn close")
        self._close_btn.setIcon(icon("close", COLOR.text_2, 18))
        self._close_btn.setIconSize(icon_size(14))
        self._close_btn.setToolTip("Cancel and close (Esc)")
        self._close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._close_btn.clicked.connect(self._on_cancel)
        h.addWidget(self._close_btn, alignment=Qt.AlignmentFlag.AlignVCenter)

        parent_layout.addWidget(self._title_bar)

    # ── body (.url-body) ────────────────────────────────────

    def _build_body(self, parent_layout: QVBoxLayout) -> None:
        body = QWidget(self._card)
        body.setObjectName("youtubeBody")
        body.setProperty("class", "url-body")
        body.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        b = QVBoxLayout(body)
        b.setContentsMargins(18, 12, 18, 22)
        b.setSpacing(8)

        self._url_input = QLineEdit(body)
        self._url_input.setObjectName("youtubeUrlInput")
        self._url_input.setProperty("class", "url-input")
        self._url_input.setPlaceholderText("Paste YouTube URL…")
        self._url_input.setClearButtonEnabled(True)
        self._url_input.setMinimumHeight(50)
        self._url_input.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._url_input.returnPressed.connect(self._on_submit)
        b.addWidget(self._url_input)

        # Inline error label — leaf state, owns its own styling.
        self._error_label = QLabel("", body)
        self._error_label.setObjectName("youtubeError")
        self._error_label.setWordWrap(True)
        self._error_label.setStyleSheet(
            f"color:{COLOR.danger}; font-size:11px;"
        )
        self._error_label.setVisible(False)
        b.addWidget(self._error_label)

        parent_layout.addWidget(body, 1)

    # ── footer (.rec-ft) ────────────────────────────────────

    def _build_footer(self, parent_layout: QVBoxLayout) -> None:
        footer = QWidget(self._card)
        footer.setObjectName("youtubeFooter")
        footer.setProperty("class", "rec-ft")
        footer.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        footer.setFixedHeight(60)

        f = QHBoxLayout(footer)
        f.setContentsMargins(18, 12, 18, 12)
        f.setSpacing(10)

        # Cancel — .rec-ft .left (text-only, dismisses the dialog).
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setProperty("class", "rec-left-btn")
        self._cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cancel_btn.setToolTip("Cancel (Esc)")
        self._cancel_btn.clicked.connect(self._on_cancel)
        f.addWidget(self._cancel_btn, alignment=Qt.AlignmentFlag.AlignVCenter)

        # Spacer (matches <span className="spacer" />).
        spacer = QWidget(footer)
        spacer.setProperty("class", "rec-ft-spacer")
        spacer.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        f.addWidget(spacer, 1)

        # Transcribe — .btn.violet (primary action).
        self._submit_btn = QPushButton("Transcribe")
        self._submit_btn.setProperty("class", "btn violet")
        self._submit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._submit_btn.setToolTip("Download audio and transcribe (Enter)")
        self._submit_btn.setMinimumHeight(36)
        self._submit_btn.clicked.connect(self._on_submit)
        f.addWidget(self._submit_btn, alignment=Qt.AlignmentFlag.AlignVCenter)

        parent_layout.addWidget(footer)

    # ── lifecycle ───────────────────────────────────────────

    def present(self) -> None:
        """Centre on screen, prefill from clipboard if it looks valid, focus."""
        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        geom = screen.availableGeometry()
        x = geom.x() + (geom.width() - self.width()) // 2
        y = geom.y() + int(geom.height() * 0.18)
        self.move(x, y)

        # Clipboard auto-fill — preserved from the legacy implementation.
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

    # ── handlers ────────────────────────────────────────────

    def _on_submit(self) -> None:
        url = self._url_input.text().strip()
        if not _looks_like_youtube_url(url):
            self._error_label.setText(
                "That doesn't look like a YouTube URL. "
                "Expected youtube.com or youtu.be."
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

    # ── input ───────────────────────────────────────────────

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
