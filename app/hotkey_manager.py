"""Config-driven global hotkey manager.

Builds a pynput ``GlobalHotKeys`` listener from an in-memory list of
:class:`Item` plus a launcher hotkey. Emits a single ``fired(item_id)``
signal so the tray controller can dispatch by id.
"""

from __future__ import annotations

from functools import partial
from typing import Optional, TYPE_CHECKING

from PyQt6.QtCore import QObject, pyqtSignal

if TYPE_CHECKING:
    from .actions_config import Item


class HotkeyManager(QObject):
    fired = pyqtSignal(str)
    error = pyqtSignal(str)

    LAUNCHER_ID = "__launcher__"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._listener = None
        self._pending: Optional[dict] = None

    def rebind(self, items: "list[Item]", launcher_hotkey: str) -> None:
        """Replace all current bindings and (re)start the listener."""
        try:
            from pynput import keyboard
        except ImportError as e:
            self.error.emit(f"pynput missing: {e}")
            return

        self._stop_listener()

        mapping: dict = {}
        for item in items:
            hk = (item.hotkey or "").strip()
            if not hk or not item.enabled:
                continue
            if hk in mapping:
                self.error.emit(f"Hotkey {hk} bound to multiple items; keeping first")
                continue
            mapping[hk] = partial(self._fire, item.id)

        launcher = (launcher_hotkey or "").strip()
        if launcher:
            if launcher in mapping:
                self.error.emit(f"Hotkey {launcher} bound to multiple items; keeping first")
            else:
                mapping[launcher] = partial(self._fire, self.LAUNCHER_ID)

        if not mapping:
            self._pending = None
            return

        self._pending = mapping
        try:
            self._listener = keyboard.GlobalHotKeys(mapping)
            self._listener.start()
        except Exception as e:
            self._listener = None
            self.error.emit(f"Hotkey unavailable: {e}")

    def start(self) -> None:
        """Start the listener if one is not already running."""
        if self._listener is not None:
            return
        if not self._pending:
            return
        try:
            from pynput import keyboard
        except ImportError as e:
            self.error.emit(f"pynput missing: {e}")
            return
        try:
            self._listener = keyboard.GlobalHotKeys(self._pending)
            self._listener.start()
        except Exception as e:
            self._listener = None
            self.error.emit(f"Hotkey unavailable: {e}")

    def stop(self) -> None:
        """Stop the listener if running."""
        self._stop_listener()

    def is_running(self) -> bool:
        """True iff a listener is currently installed."""
        return self._listener is not None

    def _stop_listener(self) -> None:
        if self._listener is not None:
            try:
                self._listener.stop()
            except Exception:
                pass
            self._listener = None

    def _fire(self, item_id: str) -> None:
        self._reset_hotkey_states()
        self.fired.emit(item_id)

    def _reset_hotkey_states(self) -> None:
        """Clear pynput's per-hotkey ``_state`` so a missed modifier-release
        (which happens when the popup steals focus before the user lifts the
        keys) cannot leave Ctrl+Alt latched and re-fire on a bare digit press."""
        if self._listener is None:
            return
        for hk in getattr(self._listener, "_hotkeys", []):
            try:
                hk._state.clear()
            except Exception:
                pass
