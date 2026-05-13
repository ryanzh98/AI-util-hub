"""TTS input window — type text, click Convert TTS, hear it in cloned voice.

Like the recorder for Ctrl+Alt+5 but the input is a multi-line text box instead
of a microphone. The window stays open after each conversion so the user can
queue up multiple lines back-to-back. Synthesis runs on the existing
RespeakerWorker (edge-tts → RVC → play).
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

from . import voice_catalog
from .respeaker_client import resolve_output_dir
from .voice_settings_panel import VoiceSettingsPanel


WINDOW_W = 560
WINDOW_H = 360
WINDOW_H_PANEL_COLLAPSED = WINDOW_H + VoiceSettingsPanel.COLLAPSED_HEIGHT + 8
WINDOW_H_PANEL_EXPANDED = WINDOW_H + VoiceSettingsPanel.EXPANDED_HEIGHT + 8
OUTER_MARGIN = 0


class TtsWindow(QWidget):
    """Frameless modal-ish popup that accepts text and pipes it through TTS+RVC.

    Public surface (must stay stable for the tray controller):
        textSubmitted = pyqtSignal(str)  # fires when user clicks Convert TTS
        voiceChanged = pyqtSignal(str, str, str)  # (label, model_path, index_path)
        closeRequested = pyqtSignal()    # fires on Esc / ✕
        def present() -> None
        def set_busy(busy: bool, status: str = "") -> None
        def set_status(text: str) -> None
        def set_voice_by_model_path(path: str | None) -> None
        def current_voice() -> tuple[str, str, str]
    """

    textSubmitted = pyqtSignal(str)
    voiceChanged = pyqtSignal(str, str, str)
    voiceSettingsChanged = pyqtSignal(dict)  # full per-hotkey TTS+RVC dict
    replayRequested = pyqtSignal(str)  # absolute WAV path to re-play
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

        # Soft violet-tinted radial glow overlay.
        self._glow = QFrame(self._card)
        self._glow.setObjectName("ttsGlow")
        self._glow.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._glow.setGeometry(0, 0, WINDOW_W, WINDOW_H_PANEL_COLLAPSED)

        card_layout = QVBoxLayout(self._card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        self._build_header(card_layout)
        self._build_voice_row(card_layout)
        self._build_settings_panel(card_layout)
        self._build_body(card_layout)
        self._build_footer(card_layout)

    def _build_header(self, parent_layout: QVBoxLayout) -> None:
        self._title_bar = QWidget(self._card)
        self._title_bar.setObjectName("ttsHeader")
        self._title_bar.setFixedHeight(44)
        self._title_bar.setCursor(Qt.CursorShape.SizeAllCursor)

        h = QHBoxLayout(self._title_bar)
        h.setContentsMargins(18, 0, 12, 0)
        h.setSpacing(10)

        brand_mark = QLabel("🗣️")
        brand_mark.setProperty("class", "brand-mark")
        brand_mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand_mark.setFixedSize(22, 22)
        brand_mark.setStyleSheet(
            f"background:{COLOR.violet}; color:#FFFFFF; border-radius:6px;"
            f"font-size:11px; font-weight:700;"
        )
        h.addWidget(brand_mark, alignment=Qt.AlignmentFlag.AlignVCenter)

        title_label = QLabel("Shortcut")
        title_label.setProperty("class", "tts-title")
        title_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        h.addWidget(title_label, alignment=Qt.AlignmentFlag.AlignVCenter)

        dot = QLabel("·")
        dot.setStyleSheet(f"color:{COLOR.text_3}; font-size:13px;")
        dot.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        h.addWidget(dot, alignment=Qt.AlignmentFlag.AlignVCenter)

        ctx_label = QLabel("Type → cloned voice")
        ctx_label.setProperty("class", "tts-hint")
        ctx_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        h.addWidget(ctx_label, alignment=Qt.AlignmentFlag.AlignVCenter)

        h.addStretch(1)

        self._close_btn = QPushButton("✕")
        self._close_btn.setProperty("class", "icon-btn")
        self._close_btn.setToolTip("Close (Esc)")
        self._close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._close_btn.clicked.connect(self._on_close)
        h.addWidget(self._close_btn, alignment=Qt.AlignmentFlag.AlignVCenter)

        parent_layout.addWidget(self._title_bar)

    def _build_voice_row(self, parent_layout: QVBoxLayout) -> None:
        row = QWidget(self._card)
        row.setObjectName("ttsVoiceRow")
        row.setFixedHeight(40)
        h = QHBoxLayout(row)
        h.setContentsMargins(18, 4, 18, 4)
        h.setSpacing(10)

        label = QLabel("Voice")
        label.setStyleSheet(f"color:{COLOR.text_2}; font-size:11px;")
        h.addWidget(label, alignment=Qt.AlignmentFlag.AlignVCenter)

        self._voice_combo = QComboBox(row)
        self._voice_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        self._voice_combo.setStyleSheet(
            f"QComboBox{{background:{COLOR.surface_2}; color:{COLOR.text_1};"
            f" border:1px solid {COLOR.line}; border-radius:6px;"
            f" padding:4px 8px; font-size:12px; min-height:22px;}}"
            f"QComboBox:hover{{border-color:{COLOR.violet};}}"
            f"QComboBox::drop-down{{border:none; width:18px;}}"
            f"QComboBox QAbstractItemView{{background:{COLOR.surface_2};"
            f" color:{COLOR.text_1}; selection-background-color:{COLOR.violet};"
            f" border:1px solid {COLOR.line};}}"
        )
        self._voices = voice_catalog.list_voices()
        for v in self._voices:
            display = v.label if v.available else f"{v.label} (missing)"
            self._voice_combo.addItem(display)
        self._voice_combo.currentIndexChanged.connect(self._on_voice_index_changed)
        h.addWidget(self._voice_combo, 1, alignment=Qt.AlignmentFlag.AlignVCenter)

        parent_layout.addWidget(row)

    def _build_settings_panel(self, parent_layout: QVBoxLayout) -> None:
        wrap = QWidget(self._card)
        wrap.setObjectName("ttsSettingsWrap")
        wl = QHBoxLayout(wrap)
        wl.setContentsMargins(18, 0, 18, 4)
        wl.setSpacing(0)
        self._settings_panel = VoiceSettingsPanel(wrap)
        self._settings_panel.settingsChanged.connect(self.voiceSettingsChanged.emit)
        self._settings_panel.expandedChanged.connect(self._on_settings_expanded)
        wl.addWidget(self._settings_panel)
        parent_layout.addWidget(wrap)

    def _build_body(self, parent_layout: QVBoxLayout) -> None:
        body = QWidget(self._card)
        body.setObjectName("ttsBody")
        b = QVBoxLayout(body)
        b.setContentsMargins(18, 14, 18, 10)
        b.setSpacing(8)

        self._text = QTextEdit(body)
        self._text.setObjectName("ttsTextInput")
        self._text.setProperty("class", "ed-textarea")
        self._text.setPlaceholderText(
            "Type something to speak in the cloned voice…\n"
            "Tip: Ctrl+Enter to convert."
        )
        self._text.setAcceptRichText(False)
        self._text.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        b.addWidget(self._text, 1)

        self._status_label = QLabel("", body)
        self._status_label.setObjectName("ttsStatus")
        self._status_label.setWordWrap(True)
        self._status_label.setStyleSheet(
            f"color:{COLOR.text_3}; font-size:11px;"
        )
        b.addWidget(self._status_label)

        parent_layout.addWidget(body, 1)

    def _build_footer(self, parent_layout: QVBoxLayout) -> None:
        footer = QWidget(self._card)
        footer.setObjectName("ttsFooter")
        footer.setFixedHeight(52)
        f = QHBoxLayout(footer)
        f.setContentsMargins(16, 10, 16, 10)
        f.setSpacing(8)

        self._clear_btn = QPushButton("Clear")
        self._clear_btn.setProperty("class", "btn ghost")
        self._clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._clear_btn.setToolTip("Clear text")
        self._clear_btn.clicked.connect(lambda: self._text.clear())
        f.addWidget(self._clear_btn)

        self._replay_btn = QPushButton("▶ Play again")
        self._replay_btn.setProperty("class", "btn ghost")
        self._replay_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._replay_btn.setToolTip("Replay last generation (Ctrl+P)")
        self._replay_btn.setEnabled(False)
        self._replay_btn.clicked.connect(self._on_replay)
        f.addWidget(self._replay_btn)

        f.addStretch(1)

        self._save_btn = QPushButton("💾 Save audio")
        self._save_btn.setProperty("class", "btn ghost")
        self._save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._save_btn.setToolTip("Save the last generated WAV to another location (Ctrl+S)")
        self._save_btn.setEnabled(False)
        self._save_btn.clicked.connect(self._on_save_audio)
        f.addWidget(self._save_btn)

        self._open_folder_btn = QPushButton("📂 Open folder")
        self._open_folder_btn.setProperty("class", "btn ghost")
        self._open_folder_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._open_folder_btn.setToolTip("Open the output folder in Explorer")
        self._open_folder_btn.clicked.connect(self._on_open_folder)
        f.addWidget(self._open_folder_btn)

        self._submit_btn = QPushButton("Convert TTS")
        self._submit_btn.setProperty("class", "btn primary")
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
        if status:
            self._status_label.setText(status)

    def set_last_wav(self, path: str) -> None:
        """Record the most-recent generation so the user can replay/save it."""
        self._last_wav = path or None
        # If we're not currently busy, light up the replay + save buttons.
        if not self._busy:
            has_wav = bool(self._last_wav)
            self._replay_btn.setEnabled(has_wav)
            self._save_btn.setEnabled(has_wav)

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

    # -- advanced voice settings ----------------------------

    def set_voice_settings(self, settings: dict | None) -> None:
        """Pre-populate the advanced panel from the persisted Item dict."""
        self._settings_panel.set_values(settings)

    def _on_settings_expanded(self, expanded: bool) -> None:
        new_h = WINDOW_H_PANEL_EXPANDED if expanded else WINDOW_H_PANEL_COLLAPSED
        self.setFixedSize(WINDOW_W + 2 * OUTER_MARGIN, new_h + 2 * OUTER_MARGIN)
        self._card.setFixedSize(WINDOW_W, new_h)
        self._glow.setGeometry(0, 0, WINDOW_W, new_h)

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
        # Suggest Documents/<original-basename>.wav so the dialog opens
        # somewhere sensible and pre-fills a meaningful name.
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
