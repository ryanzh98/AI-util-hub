"""Click-to-record hotkey button widget.

Renders the current binding as a row of ``.kbd`` chip QLabels. Clicking
the widget enters recording mode: the chips are replaced by a "Press
shortcut..." prompt with a pulsing violet dot, and the widget grabs the
keyboard. The next valid keystroke is serialized to pynput notation
(``"<ctrl>+<alt>+1"``), stored as the new value, and emitted via the
``captured`` signal.

Validation rules:
- Esc cancels recording, reverts to the previous binding (no signal).
- Backspace/Delete with no modifiers clears the binding to "".
- Otherwise the chord must include at least one of Ctrl/Alt/Shift/Meta;
  if not, an inline warning flashes and recording continues.

The widget itself is unstyled; chip labels reuse the global ``.kbd``
rules from ``design/stylesheet.shared_qss``.
"""

from __future__ import annotations

from PyQt6.QtCore import (
    QByteArray,
    QEasingCurve,
    QPropertyAnimation,
    Qt,
    QTimer,
    pyqtSignal,
)
from PyQt6.QtGui import QKeyEvent, QMouseEvent
from PyQt6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)


# ---------------------------------------------------------------------------
# Qt.Key -> pynput token mapping
# ---------------------------------------------------------------------------

_SPECIAL_KEYS: dict = {
    Qt.Key.Key_Space: "<space>",
    Qt.Key.Key_Return: "<enter>",
    Qt.Key.Key_Enter: "<enter>",
    Qt.Key.Key_Tab: "<tab>",
    Qt.Key.Key_Backtab: "<tab>",
    Qt.Key.Key_Backspace: "<backspace>",
    Qt.Key.Key_Insert: "<insert>",
    Qt.Key.Key_Delete: "<delete>",
    Qt.Key.Key_Home: "<home>",
    Qt.Key.Key_End: "<end>",
    Qt.Key.Key_PageUp: "<page_up>",
    Qt.Key.Key_PageDown: "<page_down>",
    Qt.Key.Key_Left: "<left>",
    Qt.Key.Key_Right: "<right>",
    Qt.Key.Key_Up: "<up>",
    Qt.Key.Key_Down: "<down>",
}


def _key_to_token(event: QKeyEvent) -> str | None:
    """Translate a Qt.Key code to its pynput token, or None if unsupported."""
    k = event.key()
    # Letters A-Z
    if Qt.Key.Key_A.value <= k <= Qt.Key.Key_Z.value:
        return chr(k - Qt.Key.Key_A.value + ord("a"))
    # Digits 0-9
    if Qt.Key.Key_0.value <= k <= Qt.Key.Key_9.value:
        return chr(k - Qt.Key.Key_0.value + ord("0"))
    # Function keys F1-F24
    if Qt.Key.Key_F1.value <= k <= Qt.Key.Key_F24.value:
        return f"<f{k - Qt.Key.Key_F1.value + 1}>"
    # Named specials
    if k in _SPECIAL_KEYS:
        return _SPECIAL_KEYS[k]
    # Fallback: printable punctuation via event.text()
    text = event.text()
    if text and text.isprintable() and len(text) == 1 and not text.isspace():
        return text.lower()
    return None


# ---------------------------------------------------------------------------
# Token -> chip display label
# ---------------------------------------------------------------------------

_CHIP_LABELS: dict = {
    "ctrl": "Ctrl",
    "alt": "Alt",
    "shift": "Shift",
    "cmd": "Win",
    "enter": "Enter",
    "space": "Space",
    "tab": "Tab",
    "backspace": "⌫",
    "delete": "Del",
    "esc": "Esc",
    "insert": "Ins",
    "page_up": "PgUp",
    "page_down": "PgDn",
    "home": "Home",
    "end": "End",
    "left": "←",
    "right": "→",
    "up": "↑",
    "down": "↓",
}


def _chips_from_value(value: str) -> list[str]:
    """Split a pynput-notation chord string into display chip strings."""
    if not value:
        return []
    out: list[str] = []
    for raw in value.split("+"):
        tok = raw.strip()
        if not tok:
            continue
        if tok.startswith("<") and tok.endswith(">"):
            inner = tok[1:-1].lower()
            if inner in _CHIP_LABELS:
                out.append(_CHIP_LABELS[inner])
            elif inner.startswith("f") and inner[1:].isdigit():
                out.append(f"F{int(inner[1:])}")
            else:
                out.append(inner)
        elif len(tok) == 1:
            out.append(tok.upper())
        else:
            out.append(tok)
    return out


# ---------------------------------------------------------------------------
# Widget
# ---------------------------------------------------------------------------

class HotkeyRecorderButton(QWidget):
    """A click-to-record hotkey chip group widget."""

    captured = pyqtSignal(str)
    cleared = pyqtSignal()

    def __init__(self, value: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("hotkeyRecorder")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._value: str = value or ""
        self._prev_value: str = self._value
        self._recording: bool = False

        # Outer horizontal layout
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(4)

        # Pulse dot for recording state (hidden by default)
        self._pulse_dot = QFrame(self)
        self._pulse_dot.setFixedSize(6, 6)
        self._pulse_dot.setStyleSheet(
            "background: #8B7FFF; border-radius: 3px;"
        )
        self._pulse_effect = QGraphicsOpacityEffect(self._pulse_dot)
        self._pulse_effect.setOpacity(1.0)
        self._pulse_dot.setGraphicsEffect(self._pulse_effect)
        self._pulse_anim = QPropertyAnimation(
            self._pulse_effect, QByteArray(b"opacity")
        )
        self._pulse_anim.setDuration(1400)
        self._pulse_anim.setKeyValueAt(0.0, 0.25)
        self._pulse_anim.setKeyValueAt(0.5, 0.9)
        self._pulse_anim.setKeyValueAt(1.0, 0.25)
        self._pulse_anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._pulse_anim.setLoopCount(-1)
        self._pulse_dot.hide()

        # Recording prompt label
        self._prompt_label = QLabel("Press shortcut…", self)
        self._prompt_label.setStyleSheet("color: #6A6D78; font-size: 12px;")
        self._prompt_label.hide()

        # Inline warning label
        self._warn_label = QLabel("needs Ctrl/Alt/Shift", self)
        self._warn_label.setStyleSheet("color: #FF6B7A; font-size: 11px;")
        self._warn_label.hide()
        self._warn_timer = QTimer(self)
        self._warn_timer.setSingleShot(True)
        self._warn_timer.timeout.connect(self._clear_warning)

        # Clear button
        self._clear_btn = QPushButton("Clear", self)
        self._clear_btn.setProperty("class", "btn ghost")
        self._clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._clear_btn.setStyleSheet(
            "QPushButton { background: transparent; border: 0;"
            " color: #6A6D78; font-size: 11px; padding: 2px 6px; }"
            "QPushButton:hover { color: #EEEFF2; }"
        )
        self._clear_btn.clicked.connect(self._on_clear_clicked)
        self._clear_btn.hide()

        # The chip labels are recreated on each render; keep a list for cleanup.
        self._chip_widgets: list[QWidget] = []

        self._render()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def value(self) -> str:
        return self._value

    def setValue(self, v: str) -> None:
        self._value = v or ""
        self._prev_value = self._value
        self._render()

    def is_recording(self) -> bool:
        return self._recording

    def start_recording(self) -> None:
        if self._recording:
            return
        self._prev_value = self._value
        self._recording = True
        self.setFocus(Qt.FocusReason.OtherFocusReason)
        self.grabKeyboard()
        self._render()
        self._pulse_anim.start()

    def cancel_recording(self) -> None:
        if not self._recording:
            return
        self._exit_recording()
        # Reverts to previous value (already preserved in _value).
        self._value = self._prev_value
        self._render()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _exit_recording(self) -> None:
        self._recording = False
        self._pulse_anim.stop()
        self._clear_warning()
        try:
            self.releaseKeyboard()
        except Exception:
            pass

    def _clear_warning(self) -> None:
        self.setProperty("warn", False)
        self._warn_label.hide()
        # Re-polish so the dynamic property change is picked up by QSS.
        style = self.style()
        if style is not None:
            style.unpolish(self)
            style.polish(self)

    def _flash_warning(self, text: str = "needs Ctrl/Alt/Shift") -> None:
        self.setProperty("warn", True)
        self._warn_label.setText(text)
        self._warn_label.show()
        style = self.style()
        if style is not None:
            style.unpolish(self)
            style.polish(self)
        self._warn_timer.start(1500)

    def _on_clear_clicked(self) -> None:
        if self._recording:
            return
        if not self._value:
            return
        self._value = ""
        self._prev_value = ""
        self._render()
        self.cleared.emit()

    def _clear_layout(self) -> None:
        """Remove all chip widgets and detach the persistent widgets."""
        # Detach known persistent widgets so we can re-add them in the right order.
        for w in (self._pulse_dot, self._prompt_label, self._warn_label, self._clear_btn):
            self._layout.removeWidget(w)
        # Dispose of chip widgets created last render.
        for w in self._chip_widgets:
            self._layout.removeWidget(w)
            w.setParent(None)
            w.deleteLater()
        self._chip_widgets.clear()

    def _make_chip(self, text: str, *, muted: bool = False) -> QLabel:
        chip = QLabel(text, self)
        chip.setProperty("class", "kbd")
        chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if muted:
            # Muted placeholder retains chip border but lighter glyph.
            chip.setStyleSheet("color: #4A4D58;")
        return chip

    def _render(self) -> None:
        self._clear_layout()

        if self._recording:
            self._pulse_dot.show()
            self._prompt_label.show()
            self._clear_btn.hide()
            self._layout.addWidget(self._pulse_dot)
            self._layout.addWidget(self._prompt_label)
            self._layout.addWidget(self._warn_label)
            self._layout.addStretch(1)
        else:
            self._pulse_dot.hide()
            self._prompt_label.hide()
            self._warn_label.hide()
            chip_strs = _chips_from_value(self._value)
            if not chip_strs:
                chip = self._make_chip("—", muted=True)
                self._chip_widgets.append(chip)
                self._layout.addWidget(chip)
            else:
                for cs in chip_strs:
                    chip = self._make_chip(cs)
                    self._chip_widgets.append(chip)
                    self._layout.addWidget(chip)
            self._layout.addStretch(1)
            if self._value:
                self._clear_btn.show()
                self._layout.addWidget(self._clear_btn)
            else:
                self._clear_btn.hide()

    # ------------------------------------------------------------------
    # Chord serialization
    # ------------------------------------------------------------------

    def _serialize(self, event: QKeyEvent) -> str | None:
        """Produce a pynput-notation chord from a Qt key event."""
        token = _key_to_token(event)
        if token is None:
            return None
        mods = event.modifiers()
        parts: list[str] = []
        if mods & Qt.KeyboardModifier.ControlModifier:
            parts.append("<ctrl>")
        if mods & Qt.KeyboardModifier.AltModifier:
            parts.append("<alt>")
        if mods & Qt.KeyboardModifier.ShiftModifier:
            parts.append("<shift>")
        if mods & Qt.KeyboardModifier.MetaModifier:
            parts.append("<cmd>")
        parts.append(token)
        return "+".join(parts)

    @staticmethod
    def _has_modifier(event: QKeyEvent) -> bool:
        mods = event.modifiers()
        return bool(
            mods & (
                Qt.KeyboardModifier.ControlModifier
                | Qt.KeyboardModifier.AltModifier
                | Qt.KeyboardModifier.ShiftModifier
                | Qt.KeyboardModifier.MetaModifier
            )
        )

    # ------------------------------------------------------------------
    # Event overrides
    # ------------------------------------------------------------------

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt API
        if event.button() == Qt.MouseButton.LeftButton:
            # Don't hijack clicks on the Clear button.
            child = self.childAt(event.position().toPoint())
            if child is self._clear_btn:
                super().mousePressEvent(event)
                return
            if not self._recording:
                self.start_recording()
                event.accept()
                return
        super().mousePressEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 - Qt API
        if not self._recording:
            super().keyPressEvent(event)
            return

        k = event.key()
        has_mod = self._has_modifier(event)

        # Ignore lone modifier presses (wait for the non-modifier key).
        if k in (
            Qt.Key.Key_Control,
            Qt.Key.Key_Alt,
            Qt.Key.Key_AltGr,
            Qt.Key.Key_Shift,
            Qt.Key.Key_Meta,
            Qt.Key.Key_Super_L,
            Qt.Key.Key_Super_R,
        ):
            event.accept()
            return

        # Esc cancels and reverts.
        if k == Qt.Key.Key_Escape and not has_mod:
            self._exit_recording()
            self._value = self._prev_value
            self._render()
            event.accept()
            return

        # Backspace/Delete with no modifiers clears.
        if k in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete) and not has_mod:
            self._exit_recording()
            self._value = ""
            self._prev_value = ""
            self._render()
            self.cleared.emit()
            event.accept()
            return

        # Otherwise require a modifier.
        if not has_mod:
            self._flash_warning("needs Ctrl/Alt/Shift")
            event.accept()
            return

        chord = self._serialize(event)
        if not chord:
            self._flash_warning("unsupported key")
            event.accept()
            return

        self._exit_recording()
        self._value = chord
        self._prev_value = chord
        self._render()
        self.captured.emit(chord)
        event.accept()

    def focusOutEvent(self, event) -> None:  # noqa: N802 - Qt API
        # Auto-cancel recording if the widget loses focus (e.g. another window).
        if self._recording:
            self._exit_recording()
            self._value = self._prev_value
            self._render()
        super().focusOutEvent(event)


__all__ = ["HotkeyRecorderButton"]
