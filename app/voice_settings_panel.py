"""Per-hotkey TTS+RVC settings panel — shared by recorder + TTS windows.

A compact, collapsible widget exposing the parameters that meaningfully
affect cloned voice accuracy and quality:

    - Edge TTS base voice (language, accent, gender baseline)
    - RVC pitch shift (semitones, gender/octave)
    - Index rate (.index blend strength)
    - F0 extraction method (pitch tracking algorithm)
    - Filter radius (artifact smoothing on pitch contour)
    - Protect (voiceless consonant preservation)
    - RMS mix rate (volume envelope blending)

Each row carries a `?` tooltip explaining the parameter in plain English.
Values flow up via `settingsChanged(dict)` whenever the user changes any
control; the host window persists the dict back into the matching
`Item` (see `tray_controller._on_voice_settings_changed`).
"""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from design import COLOR

from . import tts_voice_catalog


# Defaults match `respeaker_client._DEFAULT_*` and the `tts_with_rvc` library.
DEFAULTS: dict[str, Any] = {
    "base_voice": tts_voice_catalog.DEFAULT_VOICE,
    "rvc_pitch": 0,
    "rvc_index_rate": 0.75,
    "rvc_f0_method": "rmvpe",
    "rvc_filter_radius": 3,
    "rvc_protect": 0.33,
    "rvc_rms_mix_rate": 0.5,
}

F0_METHODS = ["rmvpe", "fcpe", "crepe", "harvest", "dio", "pm"]

TOOLTIPS: dict[str, str] = {
    "language": (
        "Language of the synthesized speech. The Edge TTS engine speaks "
        "the text in this language first; the RVC model then re-colors "
        "that audio in your target voice.\n\nSwitch to Spanish, Japanese, "
        "etc. to make the same cloned voice speak other languages."
    ),
    "base_voice": (
        "The specific Microsoft Edge voice used as the base for synthesis. "
        "Affects accent, gender baseline, and pacing before RVC kicks in.\n\n"
        "Match the gender of your target voice for best results (or use "
        "the pitch slider below to compensate)."
    ),
    "rvc_pitch": (
        "Pitch shift in semitones, applied during RVC conversion.\n\n"
        "Range -12…+12. Use -12 to drop an octave (e.g. female base → "
        "male target), +12 to raise an octave. 0 means no shift."
    ),
    "rvc_index_rate": (
        "How strongly the .index file influences the output. The .index "
        "captures the target voice's accent and tone.\n\n"
        "0.0 = pure RVC model. 0.75 is a good default. 0.9+ for stronger "
        "character accent (can introduce artifacts at 1.0)."
    ),
    "rvc_f0_method": (
        "Algorithm used to extract pitch from the TTS audio.\n\n"
        "• rmvpe — fast + accurate, default\n"
        "• fcpe — newer alternative to rmvpe\n"
        "• crepe — very accurate, slower\n"
        "• harvest — robust, slow\n"
        "• dio / pm — fastest but less accurate"
    ),
    "rvc_filter_radius": (
        "Median filter applied to the pitch contour to smooth out spikes.\n\n"
        "Range 3-7. Higher values reduce breathiness and pitch jitter but "
        "can flatten emotion. 3 is the safe default."
    ),
    "rvc_protect": (
        "Protects voiceless consonants (s, f, th, sh) from being pitch-"
        "shifted into noise.\n\n"
        "Range 0.0-0.5. 0.33 is balanced. Lower = harder consonant edits, "
        "0.5 = effectively disabled."
    ),
    "rvc_rms_mix_rate": (
        "Blends the volume envelope of the original TTS with the RVC "
        "output.\n\n"
        "0.0 = follow the original TTS volume curve. 1.0 = use the model "
        "voice's volume curve. 0.5 splits the difference."
    ),
}


def _info_dot(tooltip: str) -> QLabel:
    """Tiny `(?)` circle that surfaces a tooltip on hover."""
    dot = QLabel("?")
    dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
    dot.setFixedSize(14, 14)
    dot.setCursor(Qt.CursorShape.WhatsThisCursor)
    dot.setStyleSheet(
        f"QLabel{{background:{COLOR.surface_3}; color:{COLOR.text_2};"
        f" border-radius:7px; font-size:9px; font-weight:600;}}"
        f"QLabel:hover{{background:{COLOR.violet_soft};"
        f" color:{COLOR.violet};}}"
    )
    dot.setToolTip(tooltip)
    return dot


def _label_row(text: str, tooltip: str) -> QWidget:
    """Composite leading-label widget: `(?) text`."""
    w = QWidget()
    h = QHBoxLayout(w)
    h.setContentsMargins(0, 0, 0, 0)
    h.setSpacing(6)
    h.addWidget(_info_dot(tooltip), alignment=Qt.AlignmentFlag.AlignVCenter)
    lab = QLabel(text)
    lab.setStyleSheet(f"color:{COLOR.text_2}; font-size:11px;")
    h.addWidget(lab, alignment=Qt.AlignmentFlag.AlignVCenter)
    h.addStretch(1)
    return w


class VoiceSettingsPanel(QWidget):
    """Compact form exposing per-hotkey TTS+RVC settings.

    Use:
        panel = VoiceSettingsPanel(parent)
        panel.set_values(item_settings_dict)
        panel.settingsChanged.connect(handler)
        panel.expandedChanged.connect(host_resizer)
    """

    # {field_name: value} — only contains keys that differ from defaults?
    # No: we always emit the *full* current view. Simpler for the host.
    settingsChanged = pyqtSignal(dict)
    expandedChanged = pyqtSignal(bool)

    COLLAPSED_HEIGHT = 30
    EXPANDED_HEIGHT = 296

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._suppress: bool = False
        self._expanded: bool = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Toggle header
        self._toggle = QPushButton("▸  Advanced voice settings")
        self._toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle.setCheckable(False)
        self._toggle.setStyleSheet(
            f"QPushButton{{background:transparent; border:none; text-align:left;"
            f" color:{COLOR.text_2}; font-size:11px; padding:4px 0px;}}"
            f"QPushButton:hover{{color:{COLOR.violet};}}"
        )
        self._toggle.clicked.connect(self._on_toggle_clicked)
        layout.addWidget(self._toggle)

        # Form body — built once, visibility flipped by toggle.
        self._body = QWidget(self)
        self._body.setVisible(False)
        self._build_form(self._body)
        layout.addWidget(self._body)

        self.setFixedHeight(self.COLLAPSED_HEIGHT)

    # ── construction ─────────────────────────────────────────

    def _build_form(self, host: QWidget) -> None:
        form = QFormLayout(host)
        form.setContentsMargins(2, 4, 2, 4)
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(6)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

        combo_qss = (
            f"QComboBox{{background:{COLOR.surface_2}; color:{COLOR.text_1};"
            f" border:1px solid {COLOR.line}; border-radius:6px;"
            f" padding:3px 8px; font-size:11px; min-height:20px;}}"
            f"QComboBox:hover{{border-color:{COLOR.violet};}}"
            f"QComboBox::drop-down{{border:none; width:18px;}}"
            f"QComboBox QAbstractItemView{{background:{COLOR.surface_2};"
            f" color:{COLOR.text_1}; selection-background-color:{COLOR.violet};"
            f" border:1px solid {COLOR.line};}}"
        )
        spin_qss = (
            f"QSpinBox, QDoubleSpinBox{{background:{COLOR.surface_2};"
            f" color:{COLOR.text_1}; border:1px solid {COLOR.line};"
            f" border-radius:6px; padding:2px 4px; font-size:11px;"
            f" min-height:20px; min-width:80px;}}"
            f"QSpinBox:hover, QDoubleSpinBox:hover{{border-color:{COLOR.violet};}}"
        )

        # Language
        self._language_combo = QComboBox(host)
        self._language_combo.setStyleSheet(combo_qss)
        for lang in tts_voice_catalog.languages():
            self._language_combo.addItem(lang)
        self._language_combo.currentTextChanged.connect(self._on_language_changed)
        form.addRow(_label_row("Language", TOOLTIPS["language"]), self._language_combo)

        # Base voice (filtered by language)
        self._voice_combo = QComboBox(host)
        self._voice_combo.setStyleSheet(combo_qss)
        self._voice_combo.currentIndexChanged.connect(self._on_any_changed)
        form.addRow(_label_row("Voice", TOOLTIPS["base_voice"]), self._voice_combo)
        self._refill_voices_for_language(tts_voice_catalog.languages()[0])

        # Pitch
        self._pitch_spin = QSpinBox(host)
        self._pitch_spin.setRange(-12, 12)
        self._pitch_spin.setSuffix(" st")
        self._pitch_spin.setStyleSheet(spin_qss)
        self._pitch_spin.valueChanged.connect(self._on_any_changed)
        form.addRow(_label_row("Pitch", TOOLTIPS["rvc_pitch"]), self._pitch_spin)

        # Index rate
        self._index_spin = QDoubleSpinBox(host)
        self._index_spin.setRange(0.0, 1.0)
        self._index_spin.setSingleStep(0.05)
        self._index_spin.setDecimals(2)
        self._index_spin.setStyleSheet(spin_qss)
        self._index_spin.valueChanged.connect(self._on_any_changed)
        form.addRow(_label_row("Index rate", TOOLTIPS["rvc_index_rate"]), self._index_spin)

        # F0 method
        self._f0_combo = QComboBox(host)
        self._f0_combo.setStyleSheet(combo_qss)
        for m in F0_METHODS:
            self._f0_combo.addItem(m)
        self._f0_combo.currentTextChanged.connect(self._on_any_changed)
        form.addRow(_label_row("F0 method", TOOLTIPS["rvc_f0_method"]), self._f0_combo)

        # Filter radius
        self._filter_spin = QSpinBox(host)
        self._filter_spin.setRange(3, 7)
        self._filter_spin.setStyleSheet(spin_qss)
        self._filter_spin.valueChanged.connect(self._on_any_changed)
        form.addRow(_label_row("Filter radius", TOOLTIPS["rvc_filter_radius"]), self._filter_spin)

        # Protect
        self._protect_spin = QDoubleSpinBox(host)
        self._protect_spin.setRange(0.0, 0.5)
        self._protect_spin.setSingleStep(0.01)
        self._protect_spin.setDecimals(2)
        self._protect_spin.setStyleSheet(spin_qss)
        self._protect_spin.valueChanged.connect(self._on_any_changed)
        form.addRow(_label_row("Protect", TOOLTIPS["rvc_protect"]), self._protect_spin)

        # RMS mix rate
        self._rms_spin = QDoubleSpinBox(host)
        self._rms_spin.setRange(0.0, 1.0)
        self._rms_spin.setSingleStep(0.05)
        self._rms_spin.setDecimals(2)
        self._rms_spin.setStyleSheet(spin_qss)
        self._rms_spin.valueChanged.connect(self._on_any_changed)
        form.addRow(_label_row("RMS mix rate", TOOLTIPS["rvc_rms_mix_rate"]), self._rms_spin)

        # Reset row
        reset_row = QWidget(host)
        rh = QHBoxLayout(reset_row)
        rh.setContentsMargins(0, 4, 0, 0)
        rh.setSpacing(8)
        rh.addStretch(1)
        self._reset_btn = QPushButton("Reset to defaults", host)
        self._reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._reset_btn.setStyleSheet(
            f"QPushButton{{background:{COLOR.surface_3}; color:{COLOR.text_2};"
            f" border:1px solid {COLOR.line}; border-radius:6px;"
            f" padding:3px 10px; font-size:11px;}}"
            f"QPushButton:hover{{color:{COLOR.violet};"
            f" border-color:{COLOR.violet_line};}}"
        )
        self._reset_btn.clicked.connect(self.reset_to_defaults)
        rh.addWidget(self._reset_btn)
        form.addRow(reset_row)

    # ── public API ───────────────────────────────────────────

    def set_values(self, item_settings: dict[str, Any] | None) -> None:
        """Populate controls from a settings dict (Item fields).

        Missing or None values fall back to module defaults. Signals are
        suppressed during population so no spurious save fires.
        """
        s = dict(DEFAULTS)
        if item_settings:
            for k, v in item_settings.items():
                if v is not None and k in DEFAULTS:
                    s[k] = v

        self._suppress = True
        try:
            # Language + voice — set language first so the voice combo is repopulated.
            lang = tts_voice_catalog.find_language(s["base_voice"]) or tts_voice_catalog.languages()[0]
            idx = self._language_combo.findText(lang)
            if idx >= 0:
                self._language_combo.setCurrentIndex(idx)
            self._refill_voices_for_language(lang)
            voice_idx = self._voice_combo.findData(s["base_voice"])
            if voice_idx >= 0:
                self._voice_combo.setCurrentIndex(voice_idx)

            self._pitch_spin.setValue(int(s["rvc_pitch"]))
            self._index_spin.setValue(float(s["rvc_index_rate"]))
            f0_idx = self._f0_combo.findText(str(s["rvc_f0_method"]))
            if f0_idx >= 0:
                self._f0_combo.setCurrentIndex(f0_idx)
            self._filter_spin.setValue(int(s["rvc_filter_radius"]))
            self._protect_spin.setValue(float(s["rvc_protect"]))
            self._rms_spin.setValue(float(s["rvc_rms_mix_rate"]))
        finally:
            self._suppress = False

    def current_values(self) -> dict[str, Any]:
        """Snapshot of all controls — keys match `Item` fields."""
        voice_id = self._voice_combo.currentData()
        if not voice_id:
            voice_id = DEFAULTS["base_voice"]
        return {
            "base_voice": voice_id,
            "rvc_pitch": int(self._pitch_spin.value()),
            "rvc_index_rate": round(float(self._index_spin.value()), 4),
            "rvc_f0_method": self._f0_combo.currentText(),
            "rvc_filter_radius": int(self._filter_spin.value()),
            "rvc_protect": round(float(self._protect_spin.value()), 4),
            "rvc_rms_mix_rate": round(float(self._rms_spin.value()), 4),
        }

    def reset_to_defaults(self) -> None:
        """Restore all fields to module defaults and emit settingsChanged."""
        self.set_values(None)
        # set_values suppresses signals; emit once after.
        self.settingsChanged.emit(self.current_values())

    def is_expanded(self) -> bool:
        return self._expanded

    def set_expanded(self, expanded: bool) -> None:
        if expanded == self._expanded:
            return
        self._expanded = expanded
        self._body.setVisible(expanded)
        self._toggle.setText(
            "▾  Advanced voice settings" if expanded else "▸  Advanced voice settings"
        )
        self.setFixedHeight(self.EXPANDED_HEIGHT if expanded else self.COLLAPSED_HEIGHT)
        self.expandedChanged.emit(expanded)

    # ── internal handlers ────────────────────────────────────

    def _on_toggle_clicked(self) -> None:
        self.set_expanded(not self._expanded)

    def _on_language_changed(self, language: str) -> None:
        current_voice = self._voice_combo.currentData()
        self._refill_voices_for_language(language)
        # Try to keep the same voice if it belongs to the new language; else
        # pick the first voice in the group.
        if current_voice:
            idx = self._voice_combo.findData(current_voice)
            if idx >= 0:
                self._voice_combo.setCurrentIndex(idx)
        if not self._suppress:
            self._on_any_changed()

    def _on_any_changed(self, *_args) -> None:
        if self._suppress:
            return
        self.settingsChanged.emit(self.current_values())

    def _refill_voices_for_language(self, language: str) -> None:
        self._voice_combo.blockSignals(True)
        try:
            self._voice_combo.clear()
            for voice_id, label in tts_voice_catalog.voices_for_language(language):
                self._voice_combo.addItem(label, voice_id)
        finally:
            self._voice_combo.blockSignals(False)
