"""Recorder window — frameless, dark, violet-accented redesign.

Visual reference: `_design_handoff_temp/project/recorder.jsx` and the
`.rec*` block in `styles-windows.css` (lines 469-647). The audio +
state-machine wiring (AudioRecorder, SpeakerMute, RecorderState) is
preserved 1:1 from the prior implementation — only the chrome changes.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from PyQt6.QtCore import (
    QByteArray,
    QEasingCurve,
    QEvent,
    QPoint,
    QPropertyAnimation,
    Qt,
    QTimer,
    pyqtProperty,
    pyqtSignal,
)
from PyQt6.QtGui import QCursor, QGuiApplication
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from design import COLOR, FONT, MOTION
from design.icons import icon, icon_size

from . import voice_catalog
from .audio_recorder import AudioRecorder
from .speaker_mute import SpeakerMute
from .state import RecorderState
from .voice_settings_panel import VoiceSettingsPanel

# Card is 360 wide (matches `.rec`); height fits waveform + dest hint.
WINDOW_W = 360
WINDOW_H = 320
WINDOW_H_RESPEAKER = 372  # extra space for voice picker row in respeaker mode
WINDOW_H_RESPEAKER_PANEL_COLLAPSED = WINDOW_H_RESPEAKER + 36
WINDOW_H_RESPEAKER_PANEL_EXPANDED = WINDOW_H_RESPEAKER + VoiceSettingsPanel.EXPANDED_HEIGHT + 10
OUTER_MARGIN = 0

# Waveform geometry — 44 bars at 3px wide with 3px gaps, ~44px tall.
BAR_COUNT = 44
BAR_WIDTH = 3
BAR_GAP = 3
WAVE_HEIGHT = 44


class _WaveBar(QFrame):
    """Single waveform bar with an animatable `barHeight` int property.

    The height is driven by a QPropertyAnimation; QSS handles the violet
    gradient fill (see `recorder_qss()` `.rec-bar`).
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("class", "rec-bar")
        self.setFixedWidth(BAR_WIDTH)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._bar_height = 6
        self.setFixedHeight(self._bar_height)

    def get_bar_height(self) -> int:
        return self._bar_height

    def set_bar_height(self, value: int) -> None:
        v = max(2, int(value))
        if v == self._bar_height:
            return
        self._bar_height = v
        self.setFixedHeight(v)

    barHeight = pyqtProperty(int, fget=get_bar_height, fset=set_bar_height)


class RecorderWindow(QWidget):
    """Modal-ish recorder popup; emits the captured audio when stopped.

    Public surface — must stay stable for the tray controller:

        recordingStopped = pyqtSignal(bytes)
        recordingCancelled = pyqtSignal()
        def present(self, mode: str = "online") -> None
        def shutdown(self) -> None
    """

    recordingStopped = pyqtSignal(bytes)
    recordingCancelled = pyqtSignal()
    voiceChanged = pyqtSignal(str, str, str)  # (label, model_path, index_path)
    voiceSettingsChanged = pyqtSignal(dict)  # full per-hotkey TTS+RVC dict
    replayRequested = pyqtSignal(str)  # absolute WAV path to re-play

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._voices: list[voice_catalog.Voice] = []
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setFixedSize(WINDOW_W + 2 * OUTER_MARGIN, WINDOW_H + 2 * OUTER_MARGIN)

        # ── audio + state ──────────────────────────────────────
        self._drag_pos: QPoint | None = None
        self._elapsed_ms = 0
        self._state = RecorderState.IDLE
        self._mode = "online"
        self._last_wav: str | None = None  # set by set_done() in respeaker DONE
        self._recorder = AudioRecorder()
        self._speaker_mute = SpeakerMute()

        self._tick_timer = QTimer(self)
        self._tick_timer.setInterval(50)
        self._tick_timer.timeout.connect(self._on_tick)

        # Per-bar animations; populated in _build_wave.
        self._bar_anims: list[QPropertyAnimation] = []
        self._bars: list[_WaveBar] = []

        self._build_ui()
        self._wire_animations()
        self._title_bar.installEventFilter(self)
        self._set_state(RecorderState.IDLE)

    # ── construction ─────────────────────────────────────────

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(OUTER_MARGIN, OUTER_MARGIN, OUTER_MARGIN, OUTER_MARGIN)
        outer.setSpacing(0)

        self._card = QFrame(self)
        self._card.setObjectName("recorderCard")
        self._card.setFixedSize(WINDOW_W, WINDOW_H)
        outer.addWidget(self._card, alignment=Qt.AlignmentFlag.AlignCenter)

        # Soft danger-tinted radial glow overlay (purely decorative; covers card).
        self._glow = QFrame(self._card)
        self._glow.setObjectName("recorderGlow")
        self._glow.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._glow.setGeometry(0, 0, WINDOW_W, WINDOW_H)

        card_layout = QVBoxLayout(self._card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        self._build_header(card_layout)
        self._build_body(card_layout)
        self._build_footer(card_layout)

    # ── header ───────────────────────────────────────────────

    def _build_header(self, parent_layout: QVBoxLayout) -> None:
        self._title_bar = QWidget(self._card)
        self._title_bar.setObjectName("recorderHead")
        self._title_bar.setFixedHeight(40)
        self._title_bar.setCursor(Qt.CursorShape.SizeAllCursor)

        h = QHBoxLayout(self._title_bar)
        h.setContentsMargins(18, 14, 14, 0)
        h.setSpacing(10)

        # Brand glyph (violet rounded square with mic-ish sparkle stand-in).
        brand_mark = QLabel("✦")
        brand_mark.setProperty("class", "brand-mark")
        brand_mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand_mark.setFixedSize(18, 18)
        brand_mark.setStyleSheet(
            f"background:{COLOR.violet}; color:#FFFFFF; border-radius:5px;"
            f"font-size:10px; font-weight:700;"
        )
        h.addWidget(brand_mark, alignment=Qt.AlignmentFlag.AlignVCenter)

        title_label = QLabel("Voice → Clipboard")
        title_label.setProperty("class", "rec-title")
        title_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        h.addWidget(title_label, alignment=Qt.AlignmentFlag.AlignVCenter)

        h.addStretch(1)

        # REC / PAUSED pill with pulsing dot.
        self._live_pill = QWidget(self._title_bar)
        self._live_pill.setProperty("class", "rec-live-wrap")
        pill_h = QHBoxLayout(self._live_pill)
        pill_h.setContentsMargins(7, 2, 6, 2)
        pill_h.setSpacing(5)
        self._live_pill.setStyleSheet(
            f"QWidget[class~=\"rec-live-wrap\"]{{background:{COLOR.danger_soft};"
            f"border-radius:4px;}}"
        )

        self._pulse_dot = QLabel()
        self._pulse_dot.setProperty("class", "rec-pulse-dot")
        self._pulse_dot.setFixedSize(6, 6)
        pill_h.addWidget(self._pulse_dot, alignment=Qt.AlignmentFlag.AlignVCenter)

        self._live_label = QLabel("REC")
        self._live_label.setProperty("class", "rec-live")
        pill_h.addWidget(self._live_label, alignment=Qt.AlignmentFlag.AlignVCenter)

        h.addWidget(self._live_pill, alignment=Qt.AlignmentFlag.AlignVCenter)

        # Close (cancel) button.
        self._close_btn = QPushButton()
        self._close_btn.setProperty("class", "icon-btn")
        self._close_btn.setIcon(icon("close", COLOR.text_2, 18))
        self._close_btn.setIconSize(icon_size(14))
        self._close_btn.setToolTip("Cancel and close")
        self._close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._close_btn.clicked.connect(self._on_cancel)
        h.addWidget(self._close_btn, alignment=Qt.AlignmentFlag.AlignVCenter)

        parent_layout.addWidget(self._title_bar)

    # ── body ─────────────────────────────────────────────────

    def _build_body(self, parent_layout: QVBoxLayout) -> None:
        body = QWidget(self._card)
        body.setObjectName("recorderBody")
        b = QVBoxLayout(body)
        b.setContentsMargins(22, 6, 22, 12)
        b.setSpacing(0)
        b.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        # ── timer row (mm:ss + .ms suffix) ──────────────────
        timer_row = QWidget(body)
        tr = QHBoxLayout(timer_row)
        tr.setContentsMargins(0, 4, 0, 0)
        tr.setSpacing(6)
        tr.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._timer_label = QLabel("00:00")
        self._timer_label.setProperty("class", "rec-timer")
        tr.addWidget(self._timer_label, alignment=Qt.AlignmentFlag.AlignBottom)

        self._timer_ms_label = QLabel(".00")
        self._timer_ms_label.setProperty("class", "rec-timer-ms")
        tr.addWidget(self._timer_ms_label, alignment=Qt.AlignmentFlag.AlignBottom)

        b.addWidget(timer_row)

        # ── waveform ────────────────────────────────────────
        self._build_wave(b)

        # ── mode chip + locale ──────────────────────────────
        mode_row = QWidget(body)
        mr = QHBoxLayout(mode_row)
        mr.setContentsMargins(0, 4, 0, 0)
        mr.setSpacing(8)
        mr.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._mode_chip = QFrame(mode_row)
        self._mode_chip.setProperty("class", "rec-chip")
        chip_h = QHBoxLayout(self._mode_chip)
        chip_h.setContentsMargins(0, 0, 0, 0)
        chip_h.setSpacing(6)

        self._mode_icon = QLabel()
        self._mode_icon.setPixmap(icon("mic", COLOR.violet, 11).pixmap(11, 11))
        self._mode_icon.setFixedSize(11, 11)
        chip_h.addWidget(self._mode_icon, alignment=Qt.AlignmentFlag.AlignVCenter)

        self._mode_label = QLabel("Online STT · Whisper")
        chip_h.addWidget(self._mode_label, alignment=Qt.AlignmentFlag.AlignVCenter)

        mr.addWidget(self._mode_chip)

        self._locale_label = QLabel("en-US")
        self._locale_label.setStyleSheet(
            f"color:{COLOR.text_4}; font-size:11px;"
        )
        mr.addWidget(self._locale_label, alignment=Qt.AlignmentFlag.AlignVCenter)

        b.addWidget(mode_row)

        # ── voice picker (respeaker mode only; hidden otherwise) ─
        self._voice_row = QWidget(body)
        self._voice_row.setObjectName("recorderVoiceRow")
        vr = QHBoxLayout(self._voice_row)
        vr.setContentsMargins(0, 8, 0, 0)
        vr.setSpacing(8)
        vr.setAlignment(Qt.AlignmentFlag.AlignCenter)

        voice_label = QLabel("Voice")
        voice_label.setStyleSheet(f"color:{COLOR.text_3}; font-size:11px;")
        vr.addWidget(voice_label, alignment=Qt.AlignmentFlag.AlignVCenter)

        self._voice_combo = QComboBox(self._voice_row)
        self._voice_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        self._voice_combo.setMinimumWidth(220)
        self._voice_combo.setStyleSheet(
            f"QComboBox{{background:{COLOR.surface_2}; color:{COLOR.text_1};"
            f" border:1px solid {COLOR.line}; border-radius:6px;"
            f" padding:3px 8px; font-size:11px; min-height:20px;}}"
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
        vr.addWidget(self._voice_combo, alignment=Qt.AlignmentFlag.AlignVCenter)

        self._voice_row.setVisible(False)
        b.addWidget(self._voice_row)

        # ── advanced TTS+RVC settings (respeaker mode only) ─
        self._settings_panel = VoiceSettingsPanel(body)
        self._settings_panel.setVisible(False)
        self._settings_panel.settingsChanged.connect(self.voiceSettingsChanged.emit)
        self._settings_panel.expandedChanged.connect(self._on_settings_expanded)
        b.addWidget(self._settings_panel)

        # ── destination hint ────────────────────────────────
        self._dest = QFrame(body)
        self._dest.setProperty("class", "rec-dest")
        d = QHBoxLayout(self._dest)
        d.setContentsMargins(12, 8, 12, 8)
        d.setSpacing(8)
        d.setAlignment(Qt.AlignmentFlag.AlignCenter)

        clip_icon = QLabel("📋")
        clip_icon.setStyleSheet("font-size:12px;")
        clip_icon.setFixedSize(14, 14)
        d.addWidget(clip_icon, alignment=Qt.AlignmentFlag.AlignVCenter)

        dest_text = QLabel("Transcript will land on your")
        dest_text.setStyleSheet(f"color:{COLOR.text_2}; font-size:11px;")
        d.addWidget(dest_text, alignment=Qt.AlignmentFlag.AlignVCenter)

        dest_target = QLabel("clipboard")
        dest_target.setProperty("class", "rec-dest-target")
        dest_target.setStyleSheet(
            f"color:{COLOR.text_1}; font-size:11px; font-weight:{FONT.w_medium};"
        )
        d.addWidget(dest_target, alignment=Qt.AlignmentFlag.AlignVCenter)

        # Holder so we can centre the dest pill and give it the full body width.
        dest_holder = QWidget(body)
        dh = QHBoxLayout(dest_holder)
        dh.setContentsMargins(0, 12, 0, 0)
        dh.addWidget(self._dest, 1)
        b.addWidget(dest_holder)

        # ── config warning (hidden unless needed) ───────────
        self._warning = QLabel(
            "OPENAI_API_KEY is not set. Add it to .env to enable transcription."
        )
        self._warning.setObjectName("recorderWarning")
        self._warning.setWordWrap(True)
        self._warning.setStyleSheet(
            f"color:{COLOR.danger}; font-size:11px; padding-top:6px;"
        )
        self._warning.setVisible(False)
        b.addWidget(self._warning)

        b.addStretch(1)
        parent_layout.addWidget(body, 1)

    def _build_wave(self, body_layout: QVBoxLayout) -> None:
        """Build 44 violet bars with deterministic per-bar height animations."""
        wave = QWidget()
        wave.setObjectName("recorderWave")
        wave.setFixedHeight(WAVE_HEIGHT)
        wave.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        wl = QHBoxLayout(wave)
        wl.setContentsMargins(0, 0, 0, 0)
        wl.setSpacing(BAR_GAP)
        wl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Stable pseudo-random seeded bars — mirrors the JSX LCG (seed=7,
        # constants 9301 / 49297 / 233280) so the visual is reproducible.
        s = 7
        for _ in range(BAR_COUNT):
            s = (s * 9301 + 49297) % 233280
            r = s / 233280.0
            lo_pct = 6 + int(r * 14)            # 6..20
            hi_pct = 30 + int(r * 70)           # 30..100
            lo = max(2, int(WAVE_HEIGHT * lo_pct / 100))
            hi = max(lo + 4, int(WAVE_HEIGHT * hi_pct / 100))
            dur_ms = int((0.7 + r * 0.9) * 1000)
            delay_pct = (len(self._bars) * 0.04) % 1.0

            bar = _WaveBar()
            bar.set_bar_height(lo)
            self._bars.append(bar)
            wl.addWidget(bar, alignment=Qt.AlignmentFlag.AlignVCenter)

            anim = QPropertyAnimation(bar, QByteArray(b"barHeight"), self)
            anim.setDuration(dur_ms)
            anim.setLoopCount(-1)
            anim.setEasingCurve(QEasingCurve.Type.InOutSine)
            anim.setKeyValueAt(0.0, lo)
            anim.setKeyValueAt(0.5, hi)
            anim.setKeyValueAt(1.0, lo)
            # Offset start by shifting current-time within the loop so bars
            # don't all peak simultaneously.
            anim._start_offset_ms = int(delay_pct * dur_ms)  # cached for restart
            self._bar_anims.append(anim)

        wave_holder = QWidget()
        wh = QHBoxLayout(wave_holder)
        wh.setContentsMargins(0, 14, 0, 4)
        wh.addStretch(1)
        wh.addWidget(wave)
        wh.addStretch(1)
        body_layout.addWidget(wave_holder)

    # ── footer ───────────────────────────────────────────────

    def _build_footer(self, parent_layout: QVBoxLayout) -> None:
        footer = QWidget(self._card)
        footer.setObjectName("recorderFooter")
        footer.setFixedHeight(60)
        f = QHBoxLayout(footer)
        f.setContentsMargins(16, 14, 16, 16)
        f.setSpacing(8)

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setProperty("class", "rec-left-btn")
        self._cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cancel_btn.setToolTip("Discard recording (Esc)")
        self._cancel_btn.clicked.connect(self._on_cancel)
        f.addWidget(self._cancel_btn)

        f.addStretch(1)

        self._pause_btn = QPushButton("  Pause")
        self._pause_btn.setProperty("class", "rec-btn pause")
        self._pause_btn.setIcon(icon("pause", COLOR.text_1, 13))
        self._pause_btn.setIconSize(icon_size(13))
        self._pause_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._pause_btn.setToolTip("Pause / Resume (Space)")
        self._pause_btn.clicked.connect(self._on_toggle_pause)
        f.addWidget(self._pause_btn)

        self._stop_btn = QPushButton("  Stop & Transcribe")
        self._stop_btn.setProperty("class", "rec-btn stop")
        self._stop_btn.setIcon(icon("stop", "#0C0D15", 13))
        self._stop_btn.setIconSize(icon_size(13))
        self._stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._stop_btn.setToolTip("Stop and transcribe (Enter)")
        self._stop_btn.clicked.connect(self._on_stop)
        f.addWidget(self._stop_btn)

        # DONE-state buttons — appear after the cloned voice has played in
        # respeaker mode. Sized + styled like the rec-btn family but ghosted
        # so they don't compete with the primary action.
        done_btn_qss = (
            f"QPushButton{{background:{COLOR.surface_3}; color:{COLOR.text_1};"
            f" border:1px solid {COLOR.line}; border-radius:8px;"
            f" padding:5px 12px; font-size:11px;}}"
            f"QPushButton:hover{{border-color:{COLOR.violet};"
            f" color:{COLOR.violet};}}"
            f"QPushButton:disabled{{color:{COLOR.text_4};}}"
        )

        self._replay_btn = QPushButton("▶ Replay")
        self._replay_btn.setProperty("class", "rec-btn replay")
        self._replay_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._replay_btn.setToolTip("Replay the cloned voice")
        self._replay_btn.setStyleSheet(done_btn_qss)
        self._replay_btn.clicked.connect(self._on_replay)
        self._replay_btn.setVisible(False)
        f.insertWidget(1, self._replay_btn)  # right after Cancel

        self._save_btn = QPushButton("💾 Save audio")
        self._save_btn.setProperty("class", "rec-btn save")
        self._save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._save_btn.setToolTip("Save the cloned voice WAV to another location")
        self._save_btn.setStyleSheet(done_btn_qss)
        self._save_btn.clicked.connect(self._on_save_audio)
        self._save_btn.setVisible(False)
        f.insertWidget(2, self._save_btn)  # after Replay

        self._done_close_btn = QPushButton("Close")
        self._done_close_btn.setProperty("class", "rec-btn close")
        self._done_close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._done_close_btn.setToolTip("Close (Esc)")
        self._done_close_btn.setStyleSheet(done_btn_qss)
        self._done_close_btn.clicked.connect(lambda: self.close())
        self._done_close_btn.setVisible(False)
        f.addWidget(self._done_close_btn)

        parent_layout.addWidget(footer)

    # ── animations ───────────────────────────────────────────

    def _wire_animations(self) -> None:
        # Window-level entry fade — uses native windowOpacity (no QGraphicsEffect).
        self._entry_anim = QPropertyAnimation(
            self, QByteArray(b"windowOpacity"), self
        )
        self._entry_anim.setDuration(MOTION.base_ms)
        self._entry_anim.setStartValue(0.0)
        self._entry_anim.setEndValue(1.0)
        self._entry_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def _start_wave(self) -> None:
        for anim in self._bar_anims:
            if anim.state() != QPropertyAnimation.State.Running:
                anim.start()
                anim.setCurrentTime(getattr(anim, "_start_offset_ms", 0))
            else:
                anim.setPaused(False)

    def _pause_wave(self) -> None:
        for anim in self._bar_anims:
            if anim.state() == QPropertyAnimation.State.Running:
                anim.setPaused(True)

    def _stop_wave(self, freeze_low: bool = True) -> None:
        for anim, bar in zip(self._bar_anims, self._bars):
            anim.stop()
            if freeze_low:
                lo = anim.keyValueAt(0.0)
                if isinstance(lo, int):
                    bar.set_bar_height(lo)

    # ── lifecycle ────────────────────────────────────────────

    def present(self, mode: str = "online") -> None:
        """Centre on screen, start recording, configure for `mode`.

        `mode` ∈ {"online", "offline", "respeaker"}. Online needs `OPENAI_API_KEY`;
        offline + respeaker both use the local faster-whisper model.
        """
        self._mode = mode
        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        geom = screen.availableGeometry()
        x = geom.x() + (geom.width() - self.width()) // 2
        y = geom.y() + int(geom.height() * 0.18)
        self.move(x, y)

        self._elapsed_ms = 0
        self._update_timer_label()
        self._mode = mode
        self._last_wav = None
        # Reset DONE-state buttons to hidden on every fresh present().
        self._replay_btn.setVisible(False)
        self._save_btn.setVisible(False)
        self._done_close_btn.setVisible(False)
        self._cancel_btn.setVisible(True)
        self._pause_btn.setVisible(True)
        self._stop_btn.setVisible(True)
        self._cancel_btn.setEnabled(True)
        self._stop_btn.setEnabled(True)

        # Mode chip text + online/offline gating. Respeaker uses the same local
        # Whisper as offline, then pipes the transcript through TTS+RVC.
        is_respeaker = mode == "respeaker"
        self._voice_row.setVisible(is_respeaker)
        self._settings_panel.setVisible(is_respeaker)
        self._resize_for_mode()

        if is_respeaker:
            self._mode_label.setText("Offline STT → voice clone")
            self._warning.setVisible(False)
            self._stop_btn.setEnabled(True)
            self._stop_btn.setToolTip("Stop, transcribe locally, then speak in cloned voice (Enter)")
        elif mode == "offline":
            self._mode_label.setText("Offline STT · faster-whisper")
            self._warning.setVisible(False)
            self._stop_btn.setEnabled(True)
            self._stop_btn.setToolTip("Stop and transcribe locally (Enter)")
        else:
            self._mode_label.setText("Online STT · Whisper")
            raw = os.environ.get("OPENAI_API_KEY", "").strip()
            api_key_set = bool(raw) and raw != "sk-replace-me"
            self._warning.setVisible(not api_key_set)
            self._stop_btn.setEnabled(api_key_set)
            self._stop_btn.setToolTip(
                "Stop and transcribe (Enter)"
                if api_key_set
                else "Set OPENAI_API_KEY in .env to enable"
            )

        self.setWindowOpacity(0.0)
        self.show()
        self.raise_()
        self.activateWindow()
        self._entry_anim.start()

        # Begin capture.
        ok = self._recorder.start()
        if not ok:
            self._set_state(RecorderState.IDLE)
            self._live_label.setText("ERROR")
            self._mode_label.setText("Microphone unavailable")
            return
        self._speaker_mute.mute()
        self._tick_timer.start()
        self._set_state(RecorderState.RECORDING)

    def shutdown(self) -> None:
        """Force the window closed; closeEvent does the actual teardown."""
        self.close()

    # ── voice picker (respeaker mode) ────────────────────────

    def set_voice_by_model_path(self, path: str | None) -> None:
        """Preselect a voice by its stored model path. No-op if unknown."""
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
        """Return (label, model_path, index_path) for the active selection."""
        if not self._voices:
            return ("", "", "")
        idx = self._voice_combo.currentIndex()
        if idx < 0 or idx >= len(self._voices):
            return ("", "", "")
        v = self._voices[idx]
        if v.is_default:
            return (v.label, "", "")
        return (v.label, v.model_path, v.index_path)

    def _on_voice_index_changed(self, idx: int) -> None:
        label, model_path, index_path = self.current_voice()
        if label:
            self.voiceChanged.emit(label, model_path, index_path)

    # ── advanced voice settings panel ────────────────────────

    def set_voice_settings(self, settings: dict | None) -> None:
        """Pre-populate the advanced panel from the persisted Item dict."""
        self._settings_panel.set_values(settings)

    def _on_settings_expanded(self, _expanded: bool) -> None:
        self._resize_for_mode()

    def _resize_for_mode(self) -> None:
        """Pick the right card height for current mode + panel state."""
        if self._mode != "respeaker":
            new_h = WINDOW_H
        elif self._settings_panel.is_expanded():
            new_h = WINDOW_H_RESPEAKER_PANEL_EXPANDED
        else:
            new_h = WINDOW_H_RESPEAKER_PANEL_COLLAPSED
        self.setFixedSize(WINDOW_W + 2 * OUTER_MARGIN, new_h + 2 * OUTER_MARGIN)
        self._card.setFixedSize(WINDOW_W, new_h)
        self._glow.setGeometry(0, 0, WINDOW_W, new_h)

    def closeEvent(self, event):
        self._tick_timer.stop()
        self._stop_wave()
        try:
            self._recorder.stop()
        except Exception:
            pass
        self._speaker_mute.unmute()
        super().closeEvent(event)

    # ── state machine ────────────────────────────────────────

    def _set_state(self, new_state: RecorderState) -> None:
        self._state = new_state
        if new_state == RecorderState.RECORDING:
            self._live_label.setText("REC")
            self._start_wave()
            self._pause_btn.setText("  Pause")
            self._pause_btn.setIcon(icon("pause", COLOR.text_1, 13))
            self._pause_btn.setEnabled(True)
        elif new_state == RecorderState.PAUSED:
            self._live_label.setText("PAUSED")
            self._pause_wave()
            self._pause_btn.setText("  Resume")
            self._pause_btn.setIcon(icon("play", COLOR.text_1, 13))
            self._pause_btn.setEnabled(True)
        elif new_state == RecorderState.TRANSCRIBING:
            self._live_label.setText("…")
            self._pause_wave()
            self._pause_btn.setEnabled(False)
            self._stop_btn.setEnabled(False)
            self._cancel_btn.setEnabled(False)
        elif new_state == RecorderState.DONE:
            # Respeaker post-playback: swap the action buttons. The live
            # pill becomes "DONE"; the wave is frozen low to signal "no
            # active recording".
            self._live_label.setText("DONE")
            self._stop_wave(freeze_low=True)
            self._cancel_btn.setVisible(False)
            self._pause_btn.setVisible(False)
            self._stop_btn.setVisible(False)
            self._replay_btn.setVisible(True)
            self._save_btn.setVisible(True)
            self._done_close_btn.setVisible(True)
            self._replay_btn.setEnabled(bool(self._last_wav))
            self._save_btn.setEnabled(bool(self._last_wav))
        elif new_state == RecorderState.IDLE:
            self._live_label.setText("REC")
            self._stop_wave(freeze_low=True)

    # ── handlers ─────────────────────────────────────────────

    def _on_tick(self) -> None:
        if self._state == RecorderState.RECORDING:
            self._elapsed_ms += self._tick_timer.interval()
            self._update_timer_label()

    def _update_timer_label(self) -> None:
        total_sec = self._elapsed_ms // 1000
        m, s = divmod(total_sec, 60)
        cs = (self._elapsed_ms % 1000) // 10  # centiseconds (2 digits)
        self._timer_label.setText(f"{m:02d}:{s:02d}")
        self._timer_ms_label.setText(f".{cs:02d}")

    def _on_toggle_pause(self) -> None:
        if self._state == RecorderState.RECORDING:
            self._recorder.pause()
            self._set_state(RecorderState.PAUSED)
        elif self._state == RecorderState.PAUSED:
            self._recorder.resume()
            self._set_state(RecorderState.RECORDING)

    def _on_stop(self) -> None:
        if self._state not in (RecorderState.RECORDING, RecorderState.PAUSED):
            return
        audio = self._recorder.stop()
        self._set_state(RecorderState.TRANSCRIBING)
        self.recordingStopped.emit(audio)
        # Respeaker mode keeps the window open through TRANSCRIBING → DONE
        # so the user can Replay / Save the cloned WAV. Online / offline
        # modes have no follow-up audio, so close immediately as before.
        if self._mode != "respeaker":
            self.close()

    def _on_replay(self) -> None:
        if self._state != RecorderState.DONE or not self._last_wav:
            return
        self.replayRequested.emit(self._last_wav)

    def _on_save_audio(self) -> None:
        if self._state != RecorderState.DONE or not self._last_wav:
            return
        src = Path(self._last_wav)
        if not src.exists():
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
        except OSError:
            # Silently swallow — there's no status label on this window's
            # current chrome. If saving fails the user can use Open folder
            # / file manager. (Could surface via a toast later.)
            return

    def set_done(self, wav_path: str) -> None:
        """Switch to DONE state and show Replay / Save / Close buttons.

        Called by the tray controller's _on_respeak_done for the recorder
        flow (respeaker mode only). Storing the path lets Replay re-fire
        playback through RespeakerWorker.replayWav without re-recording.
        """
        if self._mode != "respeaker":
            return
        self._last_wav = wav_path or None
        self._set_state(RecorderState.DONE)

    def _on_cancel(self) -> None:
        # DONE state: recording already finished, suppress the cancelled
        # signal so the controller doesn't try to roll back state that no
        # longer exists.
        if self._state == RecorderState.DONE:
            self.close()
            return
        try:
            self._recorder.stop()
        except Exception:
            pass
        self.recordingCancelled.emit()
        self.close()

    # ── input ────────────────────────────────────────────────

    def keyPressEvent(self, event):
        key = event.key()
        # In DONE state the recording is finished, so Esc must NOT fire
        # recordingCancelled (which would race with tray_controller's
        # already-completed flow). Just close the window.
        if self._state == RecorderState.DONE:
            if key == Qt.Key.Key_Escape:
                self.close()
                return
            super().keyPressEvent(event)
            return
        if key == Qt.Key.Key_Escape:
            self._on_cancel()
        elif key == Qt.Key.Key_Space:
            self._on_toggle_pause()
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._on_stop()
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


