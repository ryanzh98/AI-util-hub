"""TTS input window — type text, click Convert TTS, hear it in cloned voice.

Wave-3 redesign: chrome follows `dialogs.jsx::TypeTTSDialog` (.win + .win-hd
+ field-row + disclosure + tts-area + rec-ft + btn.violet). The window
brand reads "AI Util Hub · Type → cloned voice".

Public surface preserved 1:1 for the tray controller — see class docstring.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from PyQt6.QtCore import (
    QEvent,
    QPoint,
    Qt,
    pyqtSignal,
)
from PyQt6.QtGui import QCursor, QGuiApplication, QKeyEvent
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from design import COLOR
from design.effects import fade_in
from design.icons import icon, icon_size

from . import voice_catalog
from .respeaker_client import resolve_output_dir
from .voice_settings_panel import VoiceSettingsPanel


WINDOW_W = 840
WINDOW_H_PANEL_COLLAPSED = 480
WINDOW_H_PANEL_EXPANDED = 900
OUTER_MARGIN = 0


# Brand-mark gradient for the TTS window — slightly lighter / softer than the
# default brand-mark (which is COLOR.violet → COLOR.violet_2). Matches the
# inline gradient in dialogs.jsx::TypeTTSDialog.
_BRAND_MARK_QSS = (
    "QLabel#ttsBrandMark{"
    "background: qlineargradient("
    " x1:0, y1:0, x2:0.6, y2:1,"
    " stop:0 #B399FF,"
    " stop:1 #7C66DE"
    ");"
    "border-radius: 12px;"
    "min-width: 24px; min-height: 24px;"
    "max-width: 24px; max-height: 24px;"
    "}"
)


# QComboBox needs an inline stylesheet — the .field-input chrome is a frame
# rule and combo-boxes have many extra sub-controls (drop-down arrow, popup
# view) that don't inherit cleanly.
def _voice_combo_qss() -> str:
    return (
        f"QComboBox{{background:{COLOR.surface_2}; color:{COLOR.text_1};"
        f" border:1px solid {COLOR.line_strong}; border-radius:10px;"
        f" padding:8px 36px 8px 14px; font-size:13px; min-height:38px;}}"
        f"QComboBox:hover{{border-color:{COLOR.violet_line};}}"
        f"QComboBox:focus{{border-color:{COLOR.violet_line};}}"
        f"QComboBox::drop-down{{border:none; width:28px;"
        f" subcontrol-origin:padding; subcontrol-position:right top;}}"
        f"QComboBox::down-arrow{{image:none; width:0; height:0;}}"
        f"QComboBox QAbstractItemView{{background:{COLOR.surface_2};"
        f" color:{COLOR.text_1}; selection-background-color:{COLOR.violet};"
        f" border:1px solid {COLOR.line_strong}; outline:0;}}"
    )


class TtsWindow(QWidget):
    """Frameless modal-ish popup that accepts text and pipes it through TTS+RVC.

    Public surface (must stay stable for the tray controller):
        textSubmitted = pyqtSignal(str)  # fires when user clicks Convert TTS
        voiceChanged = pyqtSignal(str, str, str)  # (label, model_path, index_path)
        voiceSettingsChanged = pyqtSignal(dict)   # full per-hotkey TTS+RVC dict
        replayRequested = pyqtSignal(str)         # absolute WAV path to re-play
        closeRequested = pyqtSignal()             # fires on Esc / ✕
        def present() -> None
        def set_busy(busy: bool, status: str = "") -> None
        def set_status(text: str) -> None
        def set_last_wav(path: str) -> None
        def set_voice_by_model_path(path: str | None) -> None
        def current_voice() -> tuple[str, str, str]
        def set_voice_settings(settings: dict | None) -> None
    """

    textSubmitted = pyqtSignal(str)
    voiceChanged = pyqtSignal(str, str, str)
    voiceSettingsChanged = pyqtSignal(dict)
    replayRequested = pyqtSignal(str)
    closeRequested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._voices: list[voice_catalog.Voice] = []
        self._last_wav: str | None = None
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(
            WINDOW_W + 2 * OUTER_MARGIN,
            WINDOW_H_PANEL_COLLAPSED + 2 * OUTER_MARGIN,
        )

        self._drag_pos: QPoint | None = None
        self._busy = False
        self._adv_open = False
        self._build_ui()
        self._title_bar.installEventFilter(self)

    # -- construction ----------------------------------------

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(OUTER_MARGIN, OUTER_MARGIN, OUTER_MARGIN, OUTER_MARGIN)
        outer.setSpacing(0)

        self._card = QFrame(self)
        self._card.setObjectName("ttsCard")
        self._card.setProperty("class", "win")
        self._card.setFixedSize(WINDOW_W, WINDOW_H_PANEL_COLLAPSED)
        outer.addWidget(self._card, alignment=Qt.AlignmentFlag.AlignCenter)

        # Soft violet-tinted radial glow overlay (covers the card).
        self._glow = QFrame(self._card)
        self._glow.setObjectName("ttsGlow")
        self._glow.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._glow.setGeometry(0, 0, WINDOW_W, WINDOW_H_PANEL_COLLAPSED)

        card_layout = QVBoxLayout(self._card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        self._build_header(card_layout)
        self._build_body(card_layout)
        self._build_footer(card_layout)

    # -- header ----------------------------------------------

    def _build_header(self, parent_layout: QVBoxLayout) -> None:
        self._title_bar = QWidget(self._card)
        self._title_bar.setObjectName("ttsHeader")
        self._title_bar.setProperty("class", "win-hd")
        self._title_bar.setFixedHeight(48)
        self._title_bar.setCursor(Qt.CursorShape.SizeAllCursor)

        h = QHBoxLayout(self._title_bar)
        h.setContentsMargins(18, 12, 12, 12)
        h.setSpacing(10)

        # Brand-mark with TTS-specific gradient + head_voice glyph.
        brand_mark = QLabel(self._title_bar)
        brand_mark.setObjectName("ttsBrandMark")
        brand_mark.setProperty("class", "brand-mark sm")
        brand_mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand_mark.setStyleSheet(_BRAND_MARK_QSS)
        brand_mark.setPixmap(icon("head_voice", "#FFFFFF", 12).pixmap(12, 12))
        brand_mark.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        h.addWidget(brand_mark, alignment=Qt.AlignmentFlag.AlignVCenter)

        # Brand title row: "AI Util Hub · Type → cloned voice".
        title_main = QLabel("AI Util Hub")
        title_main.setProperty("class", "brand-title")
        title_main.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        h.addWidget(title_main, alignment=Qt.AlignmentFlag.AlignVCenter)

        slash = QLabel("·")
        slash.setProperty("class", "brand-title-slash")
        slash.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        h.addWidget(slash, alignment=Qt.AlignmentFlag.AlignVCenter)

        sub = QLabel("Type → cloned voice")
        sub.setProperty("class", "brand-title-sub")
        sub.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        h.addWidget(sub, alignment=Qt.AlignmentFlag.AlignVCenter)

        h.addStretch(1)

        self._close_btn = QPushButton(self._title_bar)
        self._close_btn.setProperty("class", "icon-btn close")
        self._close_btn.setIcon(icon("close", COLOR.text_2, 18))
        self._close_btn.setIconSize(icon_size(14))
        self._close_btn.setToolTip("Close (Esc)")
        self._close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._close_btn.clicked.connect(self._on_close)
        h.addWidget(self._close_btn, alignment=Qt.AlignmentFlag.AlignVCenter)

        parent_layout.addWidget(self._title_bar)

    # -- body ------------------------------------------------

    def _build_body(self, parent_layout: QVBoxLayout) -> None:
        body = QWidget(self._card)
        body.setObjectName("ttsBody")
        b = QVBoxLayout(body)
        b.setContentsMargins(18, 14, 18, 18)
        b.setSpacing(16)

        self._build_voice_row(b)
        self._build_disclosure(b)
        self._build_settings_panel(b)
        self._build_rule(b)
        self._build_textarea(b)

        parent_layout.addWidget(body, 1)

    def _build_voice_row(self, parent_layout: QVBoxLayout) -> None:
        row = QWidget(self._card)
        row.setProperty("class", "field-row")
        row.setObjectName("ttsVoiceRow")

        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(12)

        label = QLabel("Voice")
        label.setProperty("class", "field-row-lbl")
        h.addWidget(label, alignment=Qt.AlignmentFlag.AlignVCenter)

        # The voice picker is a QComboBox styled as a .field-input. The drop
        # arrow caret is the SVG caret_down icon.
        combo_wrap = QFrame(row)
        combo_wrap.setObjectName("ttsVoiceComboWrap")
        wrap_l = QHBoxLayout(combo_wrap)
        wrap_l.setContentsMargins(0, 0, 0, 0)
        wrap_l.setSpacing(0)

        self._voice_combo = QComboBox(combo_wrap)
        self._voice_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        self._voice_combo.setStyleSheet(_voice_combo_qss())
        self._voices = voice_catalog.list_voices()
        for v in self._voices:
            display = v.label if v.available else f"{v.label} (missing)"
            self._voice_combo.addItem(display)
        self._voice_combo.currentIndexChanged.connect(self._on_voice_index_changed)
        wrap_l.addWidget(self._voice_combo, 1)

        # Caret overlay — sits on top of the combo's right edge so the JSX
        # `.field-input .caret` glyph is preserved. Mouse events fall through
        # to the combo so clicking the caret still opens the dropdown.
        self._voice_caret = QLabel(combo_wrap)
        self._voice_caret.setProperty("class", "field-input-caret")
        self._voice_caret.setPixmap(icon("caret_down", COLOR.text_3, 12).pixmap(12, 12))
        self._voice_caret.setFixedSize(12, 12)
        self._voice_caret.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        # Re-position whenever the combo lays out.
        combo_wrap.installEventFilter(self)

        h.addWidget(combo_wrap, 1)

        parent_layout.addWidget(row)

    def _build_disclosure(self, parent_layout: QVBoxLayout) -> None:
        self._disclosure_btn = QPushButton(self._card)
        self._disclosure_btn.setProperty("class", "disclosure")
        self._disclosure_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        # Icon + label live inside a tiny H layout so we can rotate the
        # triangle as part of "open" state without text re-layout.
        dl = QHBoxLayout(self._disclosure_btn)
        dl.setContentsMargins(2, 4, 8, 4)
        dl.setSpacing(6)

        self._disclosure_tri = QLabel(self._disclosure_btn)
        self._disclosure_tri.setProperty("class", "disclosure-tri")
        self._disclosure_tri.setPixmap(
            icon("tri_right", COLOR.violet, 12).pixmap(12, 12)
        )
        self._disclosure_tri.setFixedSize(12, 12)
        self._disclosure_tri.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, True
        )
        dl.addWidget(self._disclosure_tri, alignment=Qt.AlignmentFlag.AlignVCenter)

        self._disclosure_label = QLabel("Advanced voice settings", self._disclosure_btn)
        self._disclosure_label.setStyleSheet(
            f"color:{COLOR.violet}; font-size:12px; font-weight:600; background:transparent;"
        )
        self._disclosure_label.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, True
        )
        dl.addWidget(self._disclosure_label, alignment=Qt.AlignmentFlag.AlignVCenter)

        dl.addStretch(1)

        self._disclosure_btn.clicked.connect(self._on_disclosure_clicked)

        # Self-align to the start (left) — wrap in a row with stretch on the
        # right so the button hugs its content rather than stretching across
        # the body.
        wrap = QWidget(self._card)
        wl = QHBoxLayout(wrap)
        wl.setContentsMargins(0, 0, 0, 0)
        wl.setSpacing(0)
        wl.addWidget(self._disclosure_btn, 0, Qt.AlignmentFlag.AlignLeft)
        wl.addStretch(1)
        parent_layout.addWidget(wrap)

    def _build_settings_panel(self, parent_layout: QVBoxLayout) -> None:
        self._settings_panel = VoiceSettingsPanel(self._card)
        self._settings_panel.settingsChanged.connect(self.voiceSettingsChanged.emit)
        # We drive expansion from our own .disclosure button — hide the
        # panel's built-in toggle and listen for size changes via
        # expandedChanged just to keep state in sync if another caller
        # toggles it.
        try:
            self._settings_panel._toggle.setVisible(False)  # noqa: SLF001
        except AttributeError:
            pass
        self._settings_panel.expandedChanged.connect(self._on_panel_expanded)
        self._settings_panel.setVisible(False)
        parent_layout.addWidget(self._settings_panel)

    def _build_rule(self, parent_layout: QVBoxLayout) -> None:
        rule = QFrame(self._card)
        rule.setObjectName("ttsRule")
        rule.setFrameShape(QFrame.Shape.HLine)
        rule.setFrameShadow(QFrame.Shadow.Plain)
        rule.setFixedHeight(1)
        rule.setStyleSheet(
            f"QFrame#ttsRule{{background:{COLOR.line_soft}; border:0; max-height:1px;}}"
        )
        parent_layout.addWidget(rule)

    def _build_textarea(self, parent_layout: QVBoxLayout) -> None:
        self._text = QTextEdit(self._card)
        self._text.setObjectName("ttsTextInput")
        self._text.setProperty("class", "tts-area")
        self._text.setPlaceholderText(
            "Type something to speak in the cloned voice…\n"
            "Tip: Ctrl+Enter to convert."
        )
        self._text.setAcceptRichText(False)
        self._text.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._text.setMinimumHeight(200)
        parent_layout.addWidget(self._text, 1)

        self._status_label = QLabel("", self._card)
        self._status_label.setObjectName("ttsStatus")
        self._status_label.setWordWrap(True)
        parent_layout.addWidget(self._status_label)

    # -- footer ----------------------------------------------

    def _build_footer(self, parent_layout: QVBoxLayout) -> None:
        footer = QWidget(self._card)
        footer.setObjectName("ttsFooter")
        footer.setProperty("class", "rec-ft")
        footer.setFixedHeight(56)
        f = QHBoxLayout(footer)
        f.setContentsMargins(18, 10, 18, 10)
        f.setSpacing(16)

        # Clear — left-most chromeless link, matching .rec-ft .left.
        self._clear_btn = QPushButton("Clear")
        self._clear_btn.setProperty("class", "rec-left-btn")
        self._clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._clear_btn.setToolTip("Clear text")
        self._clear_btn.clicked.connect(lambda: self._text.clear())
        f.addWidget(self._clear_btn)

        # Play again — chromeless btn-text with a play triangle.
        self._replay_btn = QPushButton("Play again")
        self._replay_btn.setProperty("class", "btn-text disabled")
        self._replay_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._replay_btn.setIcon(icon("tri_right", COLOR.text_4, 14))
        self._replay_btn.setIconSize(icon_size(13))
        self._replay_btn.setToolTip("Replay last generation (Ctrl+P)")
        self._replay_btn.setEnabled(False)
        self._replay_btn.clicked.connect(self._on_replay)
        f.addWidget(self._replay_btn)

        # Save audio — chromeless btn-text with a save (disk) icon.
        self._save_btn = QPushButton("Save audio")
        self._save_btn.setProperty("class", "btn-text disabled")
        self._save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._save_btn.setIcon(icon("save", COLOR.text_4, 14))
        self._save_btn.setIconSize(icon_size(13))
        self._save_btn.setToolTip(
            "Save the last generated WAV to another location (Ctrl+S)"
        )
        self._save_btn.setEnabled(False)
        self._save_btn.clicked.connect(self._on_save_audio)
        f.addWidget(self._save_btn)

        # Open folder — always enabled.
        self._open_folder_btn = QPushButton("Open folder")
        self._open_folder_btn.setProperty("class", "btn-text")
        self._open_folder_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._open_folder_btn.setIcon(icon("folder", COLOR.text_2, 14))
        self._open_folder_btn.setIconSize(icon_size(13))
        self._open_folder_btn.setToolTip("Open the output folder in Explorer")
        self._open_folder_btn.clicked.connect(self._on_open_folder)
        f.addWidget(self._open_folder_btn)

        f.addStretch(1)

        # Convert TTS — primary violet pill.
        self._submit_btn = QPushButton("Convert TTS")
        self._submit_btn.setProperty("class", "btn violet")
        self._submit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._submit_btn.setToolTip("Synthesize + play (Ctrl+Enter)")
        self._submit_btn.clicked.connect(self._on_submit)
        f.addWidget(self._submit_btn)

        parent_layout.addWidget(footer)

    # -- lifecycle -------------------------------------------

    def present(self) -> None:
        """Centre on screen, focus the text box."""
        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        geom = screen.availableGeometry()
        x = geom.x() + (geom.width() - self.width()) // 2
        y = geom.y() + int(geom.height() * 0.18)
        self.move(x, y)

        self._status_label.setText("")
        self.show()
        self.raise_()
        self.activateWindow()
        self._text.setFocus()
        fade_in(self, duration_ms=200)

    def set_busy(self, busy: bool, status: str = "") -> None:
        """Toggle the Convert button enabled state; show progress text."""
        self._busy = busy
        self._submit_btn.setEnabled(not busy)
        self._submit_btn.setText("Working…" if busy else "Convert TTS")
        # Replay + Save: gated by both busy state AND having a generated WAV.
        can_use_last = not busy and bool(self._last_wav)
        self._replay_btn.setEnabled(can_use_last)
        self._save_btn.setEnabled(can_use_last)
        self._sync_textbtn_states()
        if status:
            self._status_label.setText(status)

    def set_last_wav(self, path: str) -> None:
        """Record the most-recent generation so the user can replay/save it."""
        self._last_wav = path or None
        if not self._busy:
            has_wav = bool(self._last_wav)
            self._replay_btn.setEnabled(has_wav)
            self._save_btn.setEnabled(has_wav)
            self._sync_textbtn_states()

    def set_status(self, text: str) -> None:
        self._status_label.setText(text)

    def set_voice_by_model_path(self, path: str | None) -> None:
        """Preselect a voice by its model path. No-op if not in the catalog."""
        if not path or not self._voices:
            return
        target = path.replace("\\", "/").lower()
        for i, v in enumerate(self._voices):
            if v.model_path and v.model_path.replace("\\", "/").lower() == target:
                self._voice_combo.blockSignals(True)
                self._voice_combo.setCurrentIndex(i)
                self._voice_combo.blockSignals(False)
                return

    def current_voice(self) -> tuple[str, str, str]:
        """Return (label, model_path, index_path) of the active selection.

        Empty strings for paths mean "use the env default" — this is the
        Default entry's contract when its files don't exist (shouldn't
        happen in practice but kept for safety).
        """
        if not self._voices:
            return ("", "", "")
        idx = self._voice_combo.currentIndex()
        if idx < 0 or idx >= len(self._voices):
            return ("", "", "")
        v = self._voices[idx]
        if v.is_default:
            return (v.label, "", "")
        return (v.label, v.model_path, v.index_path)

    # -- handlers --------------------------------------------

    def _on_voice_index_changed(self, idx: int) -> None:
        label, model_path, index_path = self.current_voice()
        if label:
            self.voiceChanged.emit(label, model_path, index_path)

    def _sync_textbtn_states(self) -> None:
        """Toggle the .disabled marker class on btn-text buttons."""
        for btn in (self._replay_btn, self._save_btn):
            cls = "btn-text" if btn.isEnabled() else "btn-text disabled"
            btn.setProperty("class", cls)
            # Re-polish so the new class takes effect.
            st = btn.style()
            if st is not None:
                st.unpolish(btn)
                st.polish(btn)

    # -- advanced voice settings ----------------------------

    def set_voice_settings(self, settings: dict | None) -> None:
        """Pre-populate the advanced panel from the persisted Item dict."""
        self._settings_panel.set_values(settings)

    def _on_disclosure_clicked(self) -> None:
        self._set_advanced_open(not self._adv_open)

    def _set_advanced_open(self, expanded: bool) -> None:
        self._adv_open = expanded
        cls = "disclosure open" if expanded else "disclosure"
        self._disclosure_btn.setProperty("class", cls)
        st = self._disclosure_btn.style()
        if st is not None:
            st.unpolish(self._disclosure_btn)
            st.polish(self._disclosure_btn)

        # Drive the embedded panel — this also fires expandedChanged → resize.
        if self._settings_panel.is_expanded() != expanded:
            self._settings_panel.set_expanded(expanded)
        else:
            # Already in the right state; just toggle visibility + resize.
            self._settings_panel.setVisible(expanded)
            self._apply_size(expanded)

        # When expanding, shrink the textarea minimum height per spec
        # (8-line collapsed → 4-line expanded).
        self._text.setMinimumHeight(140 if expanded else 200)

    def _on_panel_expanded(self, expanded: bool) -> None:
        # Keep panel visibility in sync with the panel's own expanded state.
        self._settings_panel.setVisible(expanded)
        self._apply_size(expanded)

    def _apply_size(self, expanded: bool) -> None:
        h = WINDOW_H_PANEL_EXPANDED if expanded else WINDOW_H_PANEL_COLLAPSED
        self.setFixedSize(WINDOW_W + 2 * OUTER_MARGIN, h + 2 * OUTER_MARGIN)
        self._card.setFixedSize(WINDOW_W, h)
        self._glow.setGeometry(0, 0, WINDOW_W, h)

    def _on_submit(self) -> None:
        if self._busy:
            return
        text = self._text.toPlainText().strip()
        if not text:
            self._status_label.setText("Type something first.")
            self._text.setFocus()
            return
        self.set_busy(True, "Synthesizing…")
        self.textSubmitted.emit(text)
        # Window does NOT close — stays open for next conversion.

    def _on_replay(self) -> None:
        if self._busy or not self._last_wav:
            return
        self.set_busy(True, "Replaying…")
        self.replayRequested.emit(self._last_wav)

    def _on_open_folder(self) -> None:
        try:
            out_dir = resolve_output_dir()
            os.startfile(str(out_dir))  # type: ignore[attr-defined]
        except Exception as e:
            self._status_label.setText(f"Could not open folder: {e}")

    def _on_save_audio(self) -> None:
        """Save-As dialog → copy the last generated WAV to a user-chosen path."""
        if self._busy or not self._last_wav:
            return
        src = Path(self._last_wav)
        if not src.exists():
            self._status_label.setText("Last clip no longer exists on disk.")
            return
        documents = Path.home() / "Documents"
        if not documents.exists():
            documents = Path.home()
        suggested = str(documents / src.name)
        dest, _ = QFileDialog.getSaveFileName(
            self, "Save audio as…", suggested, "WAV files (*.wav);;All files (*.*)"
        )
        if not dest:
            return
        try:
            shutil.copy2(str(src), dest)
        except OSError as e:
            self._status_label.setText(f"Save failed: {e}")
            return
        self._status_label.setText(f"Saved to {Path(dest).name}")

    def _on_close(self) -> None:
        self.closeRequested.emit()
        self.hide()

    # -- input -----------------------------------------------

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        mods = event.modifiers()
        if key == Qt.Key.Key_Escape:
            self._on_close()
            return
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and (
            mods & Qt.KeyboardModifier.ControlModifier
        ):
            self._on_submit()
            return
        if key == Qt.Key.Key_P and (mods & Qt.KeyboardModifier.ControlModifier):
            self._on_replay()
            return
        if key == Qt.Key.Key_S and (mods & Qt.KeyboardModifier.ControlModifier):
            self._on_save_audio()
            return
        super().keyPressEvent(event)

    def eventFilter(self, obj, event):
        # Re-pin the caret overlay on the right edge of the voice combo wrap.
        if (
            getattr(self, "_voice_caret", None) is not None
            and obj is self._voice_caret.parentWidget()
            and event.type() == QEvent.Type.Resize
        ):
            wrap = obj
            cw = wrap.width()
            ch = wrap.height()
            self._voice_caret.move(cw - 12 - 14, (ch - 12) // 2)

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
