"""Frameless dashboard window for managing the unified library of actions.

Wave-3 redesign — two-pane layout per
``shortcut-handoff/shortcut/project/manager.jsx``:

  · Left rail (280px): search box, segmented tabs (All / System / AI /
    Snippets), grouped scrollable list of items.
  · Right pane: branches by item kind —
        - System / Launcher / Snippet  → :class:`SystemEditor`
          (read-only header + hotkey-only footer).
        - AI Action                    → :class:`AIActionEditor`
          (prompt textarea + model select + temperature + behavior).

Public surface preserved (HARD requirement — wired by tray_controller):

    class ManagerWindow(config: Config, config_path: Path, parent=None)
        configChanged = pyqtSignal(object)        # emits new Config
        closeRequested = pyqtSignal()
        set_config(config: Config)                # external refresh
        present()                                  # show + center on cursor
        hide()                                     # inherited from QWidget
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import (
    QEvent,
    QPoint,
    Qt,
    QTimer,
    pyqtSignal,
)
from PyQt6.QtGui import QCursor, QGuiApplication
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from design import COLOR, FONT, RADIUS
from design.icons import icon, icon_size

from .actions_config import Config, Item, new_item_id, save_config
from .hotkey_recorder import HotkeyRecorderButton


# ---------------------------------------------------------------------------
# Layout constants (handoff: 1000 × 660 outer card, 280 px left rail)
# ---------------------------------------------------------------------------

CARD_WIDTH = 1000
CARD_HEIGHT = 660
OUTER_PADDING = 0
RAIL_WIDTH = 280

LAUNCHER_PSEUDO_ID = "__launcher__"

AI_MODEL_CHOICES: list[tuple[str, str]] = [
    ("", "Default · grammar default model"),
    ("anthropic/claude-sonnet-4.5", "anthropic/claude-sonnet-4.5"),
    ("anthropic/claude-opus-4.5", "anthropic/claude-opus-4.5"),
    ("openai/gpt-4o", "openai/gpt-4o"),
    ("openai/gpt-5-mini", "openai/gpt-5-mini"),
    ("google/gemini-2.5-pro", "google/gemini-2.5-pro"),
]


# ---------------------------------------------------------------------------
# Item.subtype → SVG icon name (mirrors the launcher's mapping).
# ---------------------------------------------------------------------------

_SUBTYPE_ICON = {
    "voice_online":     "mic_solid",
    "voice_offline":    "mic_outline",
    "grammar":          "spark",
    "youtube":          "youtube",
    "voice_respeaker":  "head_voice",
    "voice_tts":        "type_voice",
}


def _icon_for_item(item: Item) -> str:
    """Return the registered SVG icon name for *item*."""
    if item.subtype and item.subtype in _SUBTYPE_ICON:
        return _SUBTYPE_ICON[item.subtype]
    if item.type == "ai":
        return "id_card"
    if item.type == "snippet":
        return "clipboard"
    return "spark"


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def _repolish(w: QWidget) -> None:
    style = w.style()
    if style is None:
        return
    style.unpolish(w)
    style.polish(w)
    w.update()


def _make_icon_label(name: str, color: str, size: int,
                     parent: Optional[QWidget] = None) -> QLabel:
    """Create a transparent QLabel rendering the named SVG icon at *size*."""
    lbl = QLabel(parent)
    lbl.setPixmap(icon(name, color, size).pixmap(icon_size(size)))
    lbl.setFixedSize(size, size)
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
    return lbl


def _make_kbd_lg(text: str, parent: Optional[QWidget] = None) -> QLabel:
    """Render a single ``.kbd.lg`` chip (used in the hotkey-row footer)."""
    lbl = QLabel(text, parent)
    lbl.setProperty("class", "kbd lg")
    lbl.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return lbl


def _humanize_chord(chord: str) -> list[str]:
    """``'<ctrl>+<alt>+1'`` → ``['Ctrl', 'Alt', '1']`` for chip rendering."""
    if not chord:
        return []
    out: list[str] = []
    for raw in chord.split("+"):
        tok = raw.strip().strip("<>")
        if not tok:
            continue
        low = tok.lower()
        if low in ("ctrl", "alt", "shift", "win", "meta", "cmd"):
            out.append(tok[:1].upper() + tok[1:].lower())
        elif len(tok) == 1:
            out.append(tok.upper())
        else:
            out.append(tok.title())
    return out


def _format_hotkey_chip(chord: str) -> str:
    """Compact trailing-key chip for the rail rows (e.g. ``'1'``, ``'F5'``)."""
    if not chord:
        return ""
    try:
        tail = chord.split("+")[-1].strip()
    except Exception:
        return ""
    if tail.startswith("<") and tail.endswith(">"):
        tail = tail[1:-1]
    return tail.upper()[:4]


# ---------------------------------------------------------------------------
# Library row (left rail list item)
# ---------------------------------------------------------------------------

class LibraryRow(QPushButton):
    """One row in the left rail. Clicking selects the item."""

    rowClicked = pyqtSignal(str)

    def __init__(self, item_id: str, icon_name: str, name: str,
                 hotkey_chip: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._item_id = item_id
        self.setProperty("class", "mgr-row")
        self.setProperty("on", "false")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(36)
        self.setText("")  # children render the row

        row = QHBoxLayout(self)
        row.setContentsMargins(8, 4, 8, 4)
        row.setSpacing(10)

        grip = QLabel("⠇⠇")  # decorative double-grip
        grip.setProperty("class", "mgr-grip")
        grip.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        row.addWidget(grip)

        self._icon_lbl = _make_icon_label(icon_name, COLOR.violet, 16, self)
        self._icon_lbl.setProperty("class", "mgr-row-icon")
        row.addWidget(self._icon_lbl)

        name_lbl = QLabel(name or "(unnamed)")
        name_lbl.setProperty("class", "mgr-row-name")
        name_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        row.addWidget(name_lbl, 1)

        self._chip = QLabel(hotkey_chip)
        self._chip.setProperty("class", "mgr-row-num")
        self._chip.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._chip.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        if not hotkey_chip:
            self._chip.setVisible(False)
        row.addWidget(self._chip)

        spark = _make_icon_label("spark", COLOR.violet_soft, 12, self)
        spark.setProperty("class", "mgr-row-spark")
        row.addWidget(spark)

        self.clicked.connect(self._on_click)

    @property
    def item_id(self) -> str:
        return self._item_id

    def set_selected(self, selected: bool) -> None:
        self.setProperty("on", "true" if selected else "false")
        _repolish(self)

    def _on_click(self) -> None:
        self.rowClicked.emit(self._item_id)


# ---------------------------------------------------------------------------
# Editor base — header + footer scaffold shared by both editors.
# ---------------------------------------------------------------------------

class _EditorBase(QWidget):
    """Common scaffold: optional warning banner + body slot + hotkey footer."""

    # Signals — superset across both editor variants. Each editor only emits
    # the ones relevant to its kind. ManagerWindow wires every signal even on
    # editors that never fire it; that's harmless.
    nameChanged = pyqtSignal(str, str)        # (item_id, new_name)
    emojiChanged = pyqtSignal(str, str)       # (item_id, new_emoji) — unused now
    enabledChanged = pyqtSignal(str, bool)
    hotkeyChanged = pyqtSignal(str, str)      # (item_id, new_hotkey)
    deleteRequested = pyqtSignal(str)
    duplicateRequested = pyqtSignal(str)
    promptChanged = pyqtSignal(str, str)
    modelChanged = pyqtSignal(str, str)
    temperatureChanged = pyqtSignal(str, float)
    bodyChanged = pyqtSignal(str, str)
    kindChanged = pyqtSignal(str, str)
    behaviorChanged = pyqtSignal(str, str)

    saveClicked = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._current_id: Optional[str] = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # --- duplicate-hotkey warning banner (hidden when empty)
        self._warn_banner = QFrame(self)
        self._warn_banner.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._warn_banner.setStyleSheet(
            "background: rgba(255,107,122,0.10);"
            "border-bottom: 1px solid rgba(255,107,122,0.30);"
        )
        warn_lyt = QHBoxLayout(self._warn_banner)
        warn_lyt.setContentsMargins(24, 8, 24, 8)
        warn_lyt.setSpacing(8)
        self._warn_label = QLabel("")
        self._warn_label.setStyleSheet(f"color: {COLOR.danger}; font-size: 12px;")
        self._warn_label.setWordWrap(True)
        warn_lyt.addWidget(self._warn_label, 1)
        self._warn_banner.hide()
        root.addWidget(self._warn_banner)

        # --- body host (subclasses populate via _build_body())
        self._body_host = QWidget(self)
        self._body_host.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._body_layout = QVBoxLayout(self._body_host)
        self._body_layout.setContentsMargins(24, 22, 24, 22)
        self._body_layout.setSpacing(18)
        root.addWidget(self._body_host, 1)

        # --- footer: hotkey-row + Save (.ed-ft)
        self._footer = QFrame(self)
        self._footer.setProperty("class", "ed-ft")
        self._footer.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        ft = QHBoxLayout(self._footer)
        ft.setContentsMargins(20, 12, 20, 12)
        ft.setSpacing(10)

        # Hotkey row container (.hotkey-row): label + chips + Clear button.
        # The chips are rendered/maintained by HotkeyRecorderButton; we just
        # group it next to the static label so everything reads as one row.
        hk_row = QFrame(self._footer)
        hk_row.setProperty("class", "hotkey-row")
        hk_row.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        hk_lyt = QHBoxLayout(hk_row)
        hk_lyt.setContentsMargins(0, 0, 0, 0)
        hk_lyt.setSpacing(8)

        hk_lbl = QLabel("Hotkey")
        hk_lbl.setProperty("class", "hotkey-row-lbl")
        hk_lyt.addWidget(hk_lbl)

        self._hotkey_btn = HotkeyRecorderButton("", hk_row)
        self._hotkey_btn.captured.connect(self._on_hotkey_captured)
        self._hotkey_btn.cleared.connect(self._on_hotkey_cleared)
        hk_lyt.addWidget(self._hotkey_btn)

        ft.addWidget(hk_row)
        ft.addStretch(1)

        # Violet Save button with leading save glyph.
        self._save_btn = QPushButton(self._footer)
        self._save_btn.setProperty("class", "btn violet")
        self._save_btn.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._save_btn.setText("  Save")
        self._save_btn.setIcon(icon("save", "#14101A", 14))
        self._save_btn.setIconSize(icon_size(14))
        self._save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._save_btn.setMinimumHeight(34)
        self._save_btn.setStyleSheet(
            "QPushButton[class~=\"btn\"][class~=\"violet\"] {"
            f"  border-radius: {RADIUS.md}px; padding: 6px 16px;"
            "}"
        )
        self._save_btn.clicked.connect(self._on_save_clicked)
        ft.addWidget(self._save_btn)

        root.addWidget(self._footer)

        # Save-flash timer ("Saved ✓" → restore after 1.5 s).
        self._save_flash_timer = QTimer(self)
        self._save_flash_timer.setSingleShot(True)
        self._save_flash_timer.timeout.connect(self._restore_save_label)

    # -- public surface ------------------------------------------------

    def current_id(self) -> Optional[str]:
        return self._current_id

    def set_warning(self, text: str) -> None:
        if not text:
            self._warn_banner.hide()
            self._warn_label.clear()
        else:
            self._warn_label.setText(text)
            self._warn_banner.show()

    def trigger_save_flash(self) -> None:
        self._save_btn.setText("  Saved ✓")
        self._save_flash_timer.start(1500)

    # -- internal ------------------------------------------------------

    def _restore_save_label(self) -> None:
        self._save_btn.setText("  Save")

    def _on_save_clicked(self) -> None:
        self.saveClicked.emit()

    def _on_hotkey_captured(self, value: str) -> None:
        if self._current_id is None:
            return
        self.hotkeyChanged.emit(self._current_id, value)

    def _on_hotkey_cleared(self) -> None:
        if self._current_id is None:
            return
        self.hotkeyChanged.emit(self._current_id, "")


# ---------------------------------------------------------------------------
# System / Launcher / Snippet editor
# ---------------------------------------------------------------------------

class SystemEditor(_EditorBase):
    """Read-only meta header + explanation paragraph + hotkey-only footer.

    Used for ``Item.type == 'system'``, the synthetic launcher pseudo-item,
    and (per the Wave-3 spec) snippets — for which only the hotkey is
    user-tunable from this window.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._build_body()

    def _build_body(self) -> None:
        # --- .ed-meta header row: 44px violet icon block + kind/h2/p stack
        self._meta_row = QFrame(self._body_host)
        self._meta_row.setProperty("class", "ed-meta")
        self._meta_row.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        meta_lyt = QHBoxLayout(self._meta_row)
        meta_lyt.setContentsMargins(0, 0, 0, 0)
        meta_lyt.setSpacing(14)

        self._meta_ic = QLabel(self._meta_row)
        self._meta_ic.setProperty("class", "ed-meta-ic")
        self._meta_ic.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._meta_ic.setAlignment(Qt.AlignmentFlag.AlignCenter)
        meta_lyt.addWidget(self._meta_ic, 0, Qt.AlignmentFlag.AlignTop)

        meta_col = QVBoxLayout()
        meta_col.setContentsMargins(0, 0, 0, 0)
        meta_col.setSpacing(4)

        self._kind_lbl = QLabel("")
        self._kind_lbl.setProperty("class", "ed-meta-kind")
        meta_col.addWidget(self._kind_lbl)

        self._name_lbl = QLabel("")
        self._name_lbl.setProperty("class", "ed-meta-h2")
        meta_col.addWidget(self._name_lbl)

        self._sub_lbl = QLabel("")
        self._sub_lbl.setProperty("class", "ed-meta-p")
        self._sub_lbl.setWordWrap(True)
        meta_col.addWidget(self._sub_lbl)

        meta_lyt.addLayout(meta_col, 1)
        self._body_layout.addWidget(self._meta_row)

        # --- .ed-body / .ed-explain paragraph
        self._explain_lbl = QLabel("")
        self._explain_lbl.setProperty("class", "ed-explain")
        self._explain_lbl.setWordWrap(True)
        self._body_layout.addWidget(self._explain_lbl)

        self._body_layout.addStretch(1)

    # -- public --------------------------------------------------------

    def populate_launcher(self, hotkey: str) -> None:
        self._current_id = LAUNCHER_PSEUDO_ID
        self._render_meta_icon("rec_launcher")
        self._kind_lbl.setText("LAUNCHER")
        self._name_lbl.setText("Launcher (open popup)")
        self._sub_lbl.setText("Global trigger — works from any window.")
        self._explain_lbl.setText(
            "This is the global hotkey that opens the launcher popup from "
            "anywhere. Pick a chord with at least one of Ctrl, Alt, Shift, "
            "or Win."
        )
        self._hotkey_btn.setValue(hotkey or "")

    def populate_system(self, item: Item) -> None:
        self._current_id = item.id
        self._render_meta_icon(_icon_for_item(item))
        self._kind_lbl.setText("SYSTEM ACTION")
        self._name_lbl.setText(item.name or "")
        self._sub_lbl.setText(
            "Built-in system action. Hotkey is the only thing you can edit."
        )
        bound = bool(item.hotkey)
        self._explain_lbl.setText(
            "Built-in system actions can't be edited — only their "
            "quick-fire chord. The launcher hotkey opens the popup and "
            + ("this chord runs it directly."
               if bound else "no chord is currently bound to run it directly.")
        )
        self._hotkey_btn.setValue(item.hotkey or "")

    def populate_snippet(self, item: Item) -> None:
        """Snippets share the system editor variant (per Wave-3 spec)."""
        self._current_id = item.id
        self._render_meta_icon(_icon_for_item(item))
        is_url = (item.kind or "text").lower() == "url"
        self._kind_lbl.setText("URL SNIPPET" if is_url else "TEXT SNIPPET")
        self._name_lbl.setText(item.name or "")
        if is_url:
            self._sub_lbl.setText(
                "Opens the URL in your default browser when fired."
            )
            self._explain_lbl.setText(
                "URL snippets open in your default browser. Edit the URL "
                "directly in clipboard_actions.json; only the hotkey is "
                "tunable from this window."
            )
        else:
            self._sub_lbl.setText(
                "Replaces the clipboard with this text. Paste with Ctrl+V."
            )
            self._explain_lbl.setText(
                "Text snippets are sent straight to the clipboard. Edit the "
                "body in clipboard_actions.json; only the hotkey is tunable "
                "from this window."
            )
        self._hotkey_btn.setValue(item.hotkey or "")

    # -- internal ------------------------------------------------------

    def _render_meta_icon(self, name: str) -> None:
        self._meta_ic.setPixmap(icon(name, COLOR.violet, 22).pixmap(icon_size(22)))


# ---------------------------------------------------------------------------
# AI Action editor — full form (prompt, model, temperature, behavior)
# ---------------------------------------------------------------------------

class AIActionEditor(_EditorBase):
    """Full editor for ``Item.type == 'ai'`` rows."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._build_body()

    def _build_body(self) -> None:
        # --- .ai-ed-hd header row: 56px icon, meta column, action buttons
        self._hd_row = QFrame(self._body_host)
        self._hd_row.setProperty("class", "ai-ed-hd")
        self._hd_row.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        hd_lyt = QHBoxLayout(self._hd_row)
        hd_lyt.setContentsMargins(0, 0, 0, 0)
        hd_lyt.setSpacing(16)

        self._hd_ic = QLabel(self._hd_row)
        self._hd_ic.setProperty("class", "ai-ed-hd-ic")
        self._hd_ic.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._hd_ic.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hd_lyt.addWidget(self._hd_ic, 0, Qt.AlignmentFlag.AlignTop)

        meta_col = QFrame(self._hd_row)
        meta_col.setProperty("class", "ai-ed-hd-meta")
        meta_col.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        mc_lyt = QVBoxLayout(meta_col)
        mc_lyt.setContentsMargins(0, 0, 0, 0)
        mc_lyt.setSpacing(4)

        self._kind_lbl = QLabel("AI ACTION")
        self._kind_lbl.setProperty("class", "ai-ed-hd-kind")
        mc_lyt.addWidget(self._kind_lbl)

        # Editable name. The plain-class is fine here; size is governed by
        # font metrics in the surrounding .ai-ed-hd-h2 selector. Keep the
        # field chromeless to match the JSX h2 visual.
        self._name_edit = QLineEdit(meta_col)
        self._name_edit.setPlaceholderText("Name…")
        self._name_edit.setStyleSheet(
            "QLineEdit {"
            "  background: transparent; border: 0;"
            f"  font-size: 22px; font-weight: {FONT.w_semibold};"
            f"  color: {COLOR.text_1}; padding: 2px 0;"
            "}"
        )
        self._name_edit.textEdited.connect(self._on_name_edited)
        mc_lyt.addWidget(self._name_edit)

        self._sub_lbl = QLabel(
            "Runs against your clipboard contents and replaces them with the result."
        )
        self._sub_lbl.setProperty("class", "ai-ed-hd-p")
        self._sub_lbl.setWordWrap(True)
        mc_lyt.addWidget(self._sub_lbl)

        hd_lyt.addWidget(meta_col, 1)

        # Action buttons (.ai-ed-actions): Change emoji / Duplicate / Delete
        self._actions_col = QFrame(self._hd_row)
        self._actions_col.setProperty("class", "ai-ed-actions")
        self._actions_col.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        ac_lyt = QHBoxLayout(self._actions_col)
        ac_lyt.setContentsMargins(0, 0, 0, 0)
        ac_lyt.setSpacing(4)

        self._change_emoji_btn = QPushButton("Change emoji", self._actions_col)
        self._change_emoji_btn.setProperty("class", "ai-ed-action")
        self._change_emoji_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._change_emoji_btn.clicked.connect(self._on_change_emoji)
        ac_lyt.addWidget(self._change_emoji_btn)

        self._duplicate_btn = QPushButton("Duplicate", self._actions_col)
        self._duplicate_btn.setProperty("class", "ai-ed-action")
        self._duplicate_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._duplicate_btn.clicked.connect(self._on_duplicate)
        ac_lyt.addWidget(self._duplicate_btn)

        self._delete_btn = QPushButton("Delete", self._actions_col)
        self._delete_btn.setProperty("class", "ai-ed-action danger")
        self._delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._delete_btn.clicked.connect(self._on_delete)
        ac_lyt.addWidget(self._delete_btn)

        hd_lyt.addWidget(self._actions_col, 0, Qt.AlignmentFlag.AlignTop)

        self._body_layout.addWidget(self._hd_row)

        # --- .ai-ed-cols 2-col grid (left flex / right 280)
        cols_wrap = QFrame(self._body_host)
        cols_wrap.setProperty("class", "ai-ed-cols")
        cols_wrap.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        cols_lyt = QHBoxLayout(cols_wrap)
        cols_lyt.setContentsMargins(0, 0, 0, 0)
        cols_lyt.setSpacing(20)

        # -- left column: PROMPT label + textarea + hint
        left = QVBoxLayout()
        left.setContentsMargins(0, 0, 0, 0)
        left.setSpacing(8)

        prompt_lbl = QLabel("PROMPT")
        prompt_lbl.setProperty("class", "ed-field-lbl")
        left.addWidget(prompt_lbl)

        self._prompt_edit = QTextEdit()
        self._prompt_edit.setProperty("class", "ai-prompt")
        self._prompt_edit.setMinimumHeight(220)
        self._prompt_edit.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._prompt_edit.textChanged.connect(self._on_prompt_changed)
        left.addWidget(self._prompt_edit, 1)

        prompt_hint = QLabel(
            "Sent as the system prompt. The clipboard contents are sent as "
            "the user message."
        )
        prompt_hint.setProperty("class", "ed-field-hint")
        prompt_hint.setWordWrap(True)
        left.addWidget(prompt_hint)

        left_wrap = QWidget(cols_wrap)
        left_wrap.setLayout(left)
        cols_lyt.addWidget(left_wrap, 1)

        # -- right column: .ai-side stack (Model / Temperature / Behavior)
        side = QFrame(cols_wrap)
        side.setProperty("class", "ai-side")
        side.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        side.setFixedWidth(280)
        side_lyt = QVBoxLayout(side)
        side_lyt.setContentsMargins(0, 0, 0, 0)
        side_lyt.setSpacing(20)

        # MODEL
        model_block = QVBoxLayout()
        model_block.setContentsMargins(0, 0, 0, 0)
        model_block.setSpacing(8)
        model_lbl = QLabel("MODEL")
        model_lbl.setProperty("class", "ed-field-lbl")
        model_block.addWidget(model_lbl)

        self._model_combo = QComboBox(side)
        self._model_combo.setProperty("class", "select-field")
        self._model_combo.setEditable(True)
        for value, label in AI_MODEL_CHOICES:
            self._model_combo.addItem(label, value)
        self._model_combo.currentIndexChanged.connect(self._on_model_changed)
        line_edit = self._model_combo.lineEdit()
        if line_edit is not None:
            line_edit.editingFinished.connect(self._on_model_text_finished)
        model_block.addWidget(self._model_combo)

        model_hint = QLabel(
            "Any OpenRouter model id. Leave blank for the grammar fallback default."
        )
        model_hint.setProperty("class", "ed-field-hint")
        model_hint.setWordWrap(True)
        model_block.addWidget(model_hint)
        side_lyt.addLayout(model_block)

        # TEMPERATURE — .temp-row label + .range slider + .range-marks + hint
        temp_block = QVBoxLayout()
        temp_block.setContentsMargins(0, 0, 0, 0)
        temp_block.setSpacing(6)

        temp_row = QFrame(side)
        temp_row.setProperty("class", "temp-row")
        temp_row.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        tr_lyt = QHBoxLayout(temp_row)
        tr_lyt.setContentsMargins(0, 0, 0, 0)
        tr_lyt.setSpacing(6)
        self._temp_lbl = QLabel("Temperature")
        self._temp_lbl.setProperty("class", "temp-row-lbl")
        tr_lyt.addWidget(self._temp_lbl)
        dot = QLabel("·")
        dot.setProperty("class", "temp-row-lbl")
        tr_lyt.addWidget(dot)
        self._temp_val = QLabel("0.00")
        self._temp_val.setProperty("class", "temp-row-val")
        tr_lyt.addWidget(self._temp_val)
        tr_lyt.addStretch(1)
        temp_block.addWidget(temp_row)

        self._temp_slider = QSlider(Qt.Orientation.Horizontal, side)
        self._temp_slider.setProperty("class", "range")
        self._temp_slider.setMinimum(0)
        self._temp_slider.setMaximum(20)  # 0..1 step 0.05
        self._temp_slider.setSingleStep(1)
        self._temp_slider.setPageStep(2)
        self._temp_slider.valueChanged.connect(self._on_temp_changed)
        temp_block.addWidget(self._temp_slider)

        marks_row = QFrame(side)
        marks_row.setProperty("class", "range-marks")
        marks_row.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        m_lyt = QHBoxLayout(marks_row)
        m_lyt.setContentsMargins(0, 0, 0, 0)
        m_lyt.setSpacing(0)
        for i, txt in enumerate(("0", "0.5", "1")):
            mlbl = QLabel(txt)
            mlbl.setProperty("class", "range-mark")
            m_lyt.addWidget(mlbl)
            if i < 2:
                m_lyt.addStretch(1)
        temp_block.addWidget(marks_row)

        temp_hint = QLabel("Lower = deterministic, higher = creative.")
        temp_hint.setProperty("class", "ed-field-hint")
        temp_hint.setWordWrap(True)
        temp_block.addWidget(temp_hint)
        side_lyt.addLayout(temp_block)

        # BEHAVIOR — checkbox using .behavior-check class
        behavior_block = QVBoxLayout()
        behavior_block.setContentsMargins(0, 0, 0, 0)
        behavior_block.setSpacing(8)
        b_lbl = QLabel("BEHAVIOR")
        b_lbl.setProperty("class", "ed-field-lbl")
        behavior_block.addWidget(b_lbl)
        self._show_in_launcher = QCheckBox("Show in launcher", side)
        self._show_in_launcher.setProperty("class", "behavior-check")
        self._show_in_launcher.stateChanged.connect(self._on_enabled_changed)
        behavior_block.addWidget(self._show_in_launcher)
        side_lyt.addLayout(behavior_block)

        side_lyt.addStretch(1)
        cols_lyt.addWidget(side, 0)

        self._body_layout.addWidget(cols_wrap, 1)

    # -- public --------------------------------------------------------

    def populate(self, item: Item) -> None:
        self._current_id = item.id
        self._render_hd_icon(_icon_for_item(item))

        self._name_edit.blockSignals(True)
        self._name_edit.setText(item.name or "")
        self._name_edit.blockSignals(False)

        self._prompt_edit.blockSignals(True)
        self._prompt_edit.setPlainText(item.prompt or "")
        self._prompt_edit.blockSignals(False)

        # Model combo: try to match a registered value, else show as raw text.
        self._model_combo.blockSignals(True)
        target_value = item.model or ""
        match_idx = -1
        for i in range(self._model_combo.count()):
            if self._model_combo.itemData(i) == target_value:
                match_idx = i
                break
        if match_idx >= 0:
            self._model_combo.setCurrentIndex(match_idx)
        else:
            self._model_combo.setEditText(target_value)
        self._model_combo.blockSignals(False)

        temp = item.temperature if item.temperature is not None else 0.2
        clamped = max(0.0, min(1.0, float(temp)))
        self._temp_slider.blockSignals(True)
        self._temp_slider.setValue(int(round(clamped * 20)))
        self._temp_slider.blockSignals(False)
        self._temp_val.setText(f"{clamped:.2f}")

        self._show_in_launcher.blockSignals(True)
        self._show_in_launcher.setChecked(bool(item.enabled))
        self._show_in_launcher.blockSignals(False)

        self._hotkey_btn.setValue(item.hotkey or "")

        self._delete_btn.setVisible(bool(item.deletable))
        self._duplicate_btn.setVisible(bool(item.deletable))

    # -- internal ------------------------------------------------------

    def _render_hd_icon(self, name: str) -> None:
        self._hd_ic.setPixmap(icon(name, COLOR.violet, 28).pixmap(icon_size(28)))

    def _on_name_edited(self, text: str) -> None:
        if self._current_id is None:
            return
        self.nameChanged.emit(self._current_id, text)

    def _on_change_emoji(self) -> None:
        # Kept for behavioral parity with the previous editor (and the JSX
        # action button). Updates the underlying Item.emoji even though the
        # new design favors SVG icons; harmless for downstream consumers.
        if self._current_id is None:
            return
        new, ok = QInputDialog.getText(
            self, "Change emoji", "Emoji or character:", QLineEdit.EchoMode.Normal, ""
        )
        if not ok:
            return
        new = (new or "").strip()
        if not new:
            return
        self.emojiChanged.emit(self._current_id, new)

    def _on_duplicate(self) -> None:
        if self._current_id is None:
            return
        self.duplicateRequested.emit(self._current_id)

    def _on_delete(self) -> None:
        if self._current_id is None:
            return
        self.deleteRequested.emit(self._current_id)

    def _on_prompt_changed(self) -> None:
        if self._current_id is None:
            return
        self.promptChanged.emit(self._current_id, self._prompt_edit.toPlainText())

    def _on_model_changed(self, idx: int) -> None:
        if self._current_id is None or idx < 0:
            return
        value = self._model_combo.itemData(idx)
        if value is None:
            value = self._model_combo.itemText(idx)
        self.modelChanged.emit(self._current_id, str(value or ""))

    def _on_model_text_finished(self) -> None:
        if self._current_id is None:
            return
        line_edit = self._model_combo.lineEdit()
        if line_edit is None:
            return
        text = line_edit.text().strip()
        for i in range(self._model_combo.count()):
            if self._model_combo.itemText(i) == text:
                value = self._model_combo.itemData(i)
                self.modelChanged.emit(self._current_id, str(value or ""))
                return
        self.modelChanged.emit(self._current_id, text)

    def _on_temp_changed(self, raw: int) -> None:
        value = raw / 20.0
        self._temp_val.setText(f"{value:.2f}")
        if self._current_id is None:
            return
        self.temperatureChanged.emit(self._current_id, value)

    def _on_enabled_changed(self, state: int) -> None:
        if self._current_id is None:
            return
        self.enabledChanged.emit(self._current_id, state == Qt.CheckState.Checked.value)


# ---------------------------------------------------------------------------
# Manager window
# ---------------------------------------------------------------------------

class ManagerWindow(QWidget):
    """Frameless dashboard for editing the unified action library.

    Public signals/methods are part of the contract with ``tray_controller``;
    do not rename without updating the controller.
    """

    configChanged = pyqtSignal(object)
    closeRequested = pyqtSignal()

    # Editor indices in the QStackedWidget.
    IDX_EMPTY = 0
    IDX_SYSTEM = 1     # also serves Launcher pseudo-item + Snippet rows
    IDX_AI = 2

    def __init__(self, config: Config, config_path: Path,
                 parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)

        self._config_path: Path = Path(config_path)
        self._original_config: Config = copy.deepcopy(config)
        self._working_config: Config = copy.deepcopy(config)
        self._selected_id: Optional[str] = LAUNCHER_PSEUDO_ID
        self._active_tab: str = "all"   # all | system | ai | snippet
        self._search_text: str = ""
        self._drag_pos: Optional[QPoint] = None
        self._row_widgets: dict[str, LibraryRow] = {}

        self._build_chrome()
        self._wire_editors()
        self._rebuild_list()
        self._select_initial()

    # ------------------------------------------------------------------
    # Chrome
    # ------------------------------------------------------------------

    def _build_chrome(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(OUTER_PADDING, OUTER_PADDING,
                                  OUTER_PADDING, OUTER_PADDING)
        outer.setSpacing(0)

        # Outer .win card (fixed 1000×660 per handoff).
        self._card = QFrame(self)
        self._card.setObjectName("managerCard")
        self._card.setProperty("class", "win mgr")
        self._card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._card.setFixedSize(CARD_WIDTH, CARD_HEIGHT)
        outer.addWidget(self._card)

        card_lyt = QVBoxLayout(self._card)
        card_lyt.setContentsMargins(0, 0, 0, 0)
        card_lyt.setSpacing(0)

        # Titlebar (.win-hd.bordered): brand mark + title block + close.
        self._titlebar = QFrame(self._card)
        self._titlebar.setObjectName("managerTitlebar")
        self._titlebar.setProperty("class", "win-hd bordered")
        self._titlebar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._titlebar.setFixedHeight(48)
        self._titlebar.setCursor(Qt.CursorShape.SizeAllCursor)
        tb = QHBoxLayout(self._titlebar)
        tb.setContentsMargins(16, 0, 10, 0)
        tb.setSpacing(10)

        # Brand mark — gradient circle containing the rec-launcher glyph.
        brand_mark = QFrame(self._titlebar)
        brand_mark.setProperty("class", "brand-mark sm")
        brand_mark.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        bm_lyt = QHBoxLayout(brand_mark)
        bm_lyt.setContentsMargins(0, 0, 0, 0)
        bm_lyt.setSpacing(0)
        glyph = QLabel(brand_mark)
        glyph.setPixmap(icon("rec_launcher", "#FFFFFF", 13).pixmap(icon_size(13)))
        glyph.setAlignment(Qt.AlignmentFlag.AlignCenter)
        glyph.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        bm_lyt.addWidget(glyph, 0, Qt.AlignmentFlag.AlignCenter)
        tb.addWidget(brand_mark, 0, Qt.AlignmentFlag.AlignVCenter)

        # Brand title block: "AI Util Hub / Manage Library".
        brand_title = QLabel("AI Util Hub", self._titlebar)
        brand_title.setProperty("class", "brand-title")
        tb.addWidget(brand_title, 0, Qt.AlignmentFlag.AlignVCenter)

        slash = QLabel("/", self._titlebar)
        slash.setProperty("class", "brand-title-slash")
        slash.setStyleSheet(f"color: {COLOR.text_4}; margin: 0 4px;")
        tb.addWidget(slash, 0, Qt.AlignmentFlag.AlignVCenter)

        sub = QLabel("Manage Library", self._titlebar)
        sub.setProperty("class", "brand-title-sub")
        tb.addWidget(sub, 0, Qt.AlignmentFlag.AlignVCenter)

        # Subtle dirty-state indicator (no JSX equivalent but useful to keep).
        self._dirty_lbl = QLabel("• Unsaved changes", self._titlebar)
        self._dirty_lbl.setStyleSheet(
            f"color: {COLOR.amber}; font-size: 11px; font-weight: 500; margin-left: 10px;"
        )
        self._dirty_lbl.hide()
        tb.addWidget(self._dirty_lbl)

        tb.addStretch(1)

        close_btn = QPushButton(self._titlebar)
        close_btn.setProperty("class", "icon-btn close")
        close_btn.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        close_btn.setIcon(icon("close", COLOR.text_2, 14))
        close_btn.setIconSize(icon_size(14))
        close_btn.setFixedSize(28, 28)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        close_btn.setToolTip("Close (Esc)")
        close_btn.clicked.connect(self._on_close_clicked)
        tb.addWidget(close_btn)

        card_lyt.addWidget(self._titlebar)
        self._titlebar.installEventFilter(self)

        # Body (.mgr-body): rail + edit pane.
        body_host = QFrame(self._card)
        body_host.setProperty("class", "mgr-body")
        body_host.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        body = QHBoxLayout(body_host)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        card_lyt.addWidget(body_host, 1)

        self._rail = self._build_rail()
        body.addWidget(self._rail)

        self._edit_pane = QFrame(body_host)
        self._edit_pane.setObjectName("managerEdit")
        self._edit_pane.setProperty("class", "mgr-edit")
        self._edit_pane.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        edit_lyt = QVBoxLayout(self._edit_pane)
        edit_lyt.setContentsMargins(0, 0, 0, 0)
        edit_lyt.setSpacing(0)

        self._stack = QStackedWidget(self._edit_pane)
        edit_lyt.addWidget(self._stack)

        # Index 0: empty placeholder.
        empty = QWidget()
        ev = QVBoxLayout(empty)
        ev.setContentsMargins(40, 40, 40, 40)
        ev.addStretch(1)
        ep = QLabel("Select an item from the left to edit.")
        ep.setStyleSheet(f"color: {COLOR.text_3}; font-size: 13px;")
        ep.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ev.addWidget(ep)
        ev.addStretch(1)
        self._stack.insertWidget(self.IDX_EMPTY, empty)

        # Index 1: System editor (also handles Launcher + Snippet).
        # Index 2: AI Action editor.
        self._system_editor = SystemEditor()
        self._ai_editor = AIActionEditor()
        self._stack.insertWidget(self.IDX_SYSTEM, self._system_editor)
        self._stack.insertWidget(self.IDX_AI, self._ai_editor)

        body.addWidget(self._edit_pane, 1)

    def _build_rail(self) -> QWidget:
        rail = QFrame(self._card)
        rail.setObjectName("managerRail")
        rail.setProperty("class", "mgr-rail")
        rail.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        rail.setFixedWidth(RAIL_WIDTH)
        rl = QVBoxLayout(rail)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(0)

        head = QFrame(rail)
        head.setObjectName("managerRailHead")
        head.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        hl = QVBoxLayout(head)
        hl.setContentsMargins(14, 14, 14, 10)
        hl.setSpacing(10)

        # Search field with leading icon overlay (.mgr-search has 30px
        # left-padding to clear the absolutely-positioned glyph).
        search_wrap = QFrame(head)
        search_wrap.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        search_wrap.setStyleSheet("background: transparent; border: 0;")

        sw_outer = QVBoxLayout(search_wrap)
        sw_outer.setContentsMargins(0, 0, 0, 0)
        sw_outer.setSpacing(0)

        self._search = QLineEdit(search_wrap)
        self._search.setProperty("class", "mgr-search")
        self._search.setPlaceholderText("Search library…")
        self._search.textChanged.connect(self._on_search_changed)
        sw_outer.addWidget(self._search)

        # Floating leading icon (parented to the search wrap; positioned in
        # showEvent / resizeEvent via fixed offsets — close enough for this
        # static layout).
        self._search_icon_lbl = QLabel(search_wrap)
        self._search_icon_lbl.setPixmap(
            icon("search", COLOR.text_3, 14).pixmap(icon_size(14))
        )
        self._search_icon_lbl.setFixedSize(14, 14)
        self._search_icon_lbl.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, True
        )
        self._search_icon_lbl.move(10, 10)  # static offset matches 32px input
        self._search_icon_lbl.raise_()

        hl.addWidget(search_wrap)

        # Tabs (.mgr-tabs / .mgr-tab)
        tabs = QFrame(head)
        tabs.setProperty("class", "mgr-tabs")
        tabs.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        tl = QHBoxLayout(tabs)
        tl.setContentsMargins(3, 3, 3, 3)
        tl.setSpacing(4)
        self._tab_buttons: dict[str, QPushButton] = {}
        for key, label in (
            ("all", "All"),
            ("system", "System"),
            ("ai", "AI"),
            ("snippet", "Snippets"),
        ):
            btn = QPushButton(label, tabs)
            btn.setProperty("class", "mgr-tab")
            btn.setProperty("on", "true" if key == self._active_tab else "false")
            btn.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.clicked.connect(lambda _checked=False, k=key: self._on_tab_changed(k))
            tl.addWidget(btn, 1)
            self._tab_buttons[key] = btn
        hl.addWidget(tabs)

        rl.addWidget(head)

        # Scrollable list (.mgr-list)
        self._list_scroll = QScrollArea(rail)
        self._list_scroll.setWidgetResizable(True)
        self._list_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._list_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._list_scroll.setStyleSheet("QScrollArea { background: transparent; border: 0; }")

        self._list_body = QFrame()
        self._list_body.setProperty("class", "mgr-list")
        self._list_body.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._list_body.setStyleSheet("background: transparent;")
        self._list_layout = QVBoxLayout(self._list_body)
        self._list_layout.setContentsMargins(8, 8, 8, 12)
        self._list_layout.setSpacing(2)
        self._list_scroll.setWidget(self._list_body)

        rl.addWidget(self._list_scroll, 1)

        return rail

    # ------------------------------------------------------------------
    # Editor wiring
    # ------------------------------------------------------------------

    def _wire_editors(self) -> None:
        for editor in (self._system_editor, self._ai_editor):
            editor.saveClicked.connect(self._on_save_clicked)
            editor.hotkeyChanged.connect(self._on_hotkey_changed)
            editor.deleteRequested.connect(self._on_delete_requested)
            editor.duplicateRequested.connect(self._on_duplicate_requested)
            editor.nameChanged.connect(self._on_name_changed)
            editor.emojiChanged.connect(self._on_emoji_changed)
            editor.enabledChanged.connect(self._on_enabled_changed)

        self._ai_editor.promptChanged.connect(self._on_prompt_changed)
        self._ai_editor.modelChanged.connect(self._on_model_changed)
        self._ai_editor.temperatureChanged.connect(self._on_temperature_changed)

    # ------------------------------------------------------------------
    # Public API (preserved surface — wired by tray_controller)
    # ------------------------------------------------------------------

    def set_config(self, config: Config) -> None:
        self._original_config = copy.deepcopy(config)
        self._working_config = copy.deepcopy(config)
        self._refresh_dirty_indicator()
        self._rebuild_list()
        if self._selected_id and (
            self._selected_id == LAUNCHER_PSEUDO_ID
            or self._find_item(self._selected_id) is not None
        ):
            self._select(self._selected_id)
        else:
            self._select(LAUNCHER_PSEUDO_ID)

    def present(self) -> None:
        self.adjustSize()
        self.resize(CARD_WIDTH + OUTER_PADDING * 2, CARD_HEIGHT + OUTER_PADDING * 2)
        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        if screen is not None:
            geom = screen.availableGeometry()
            x = geom.x() + (geom.width() - self.width()) // 2
            y = geom.y() + (geom.height() - self.height()) // 2
            self.move(x, y)
        self.show()
        self.raise_()
        self.activateWindow()

    # ------------------------------------------------------------------
    # List rendering
    # ------------------------------------------------------------------

    def _items_by_type(self, type_: str) -> list[Item]:
        items = [it for it in self._working_config.items if it.type == type_]
        items.sort(key=lambda it: (it.order, (it.name or "").lower()))
        return items

    def _matches_filter(self, item: Item, query: str) -> bool:
        if not query:
            return True
        q = query.lower()
        parts = [item.name or ""]
        if item.prompt:
            parts.append(item.prompt)
        if item.body:
            parts.append(item.body)
        return any(q in (p or "").lower() for p in parts)

    def _matches_launcher_filter(self, query: str) -> bool:
        if not query:
            return True
        return query.lower() in "launcher (open popup)"

    def _rebuild_list(self) -> None:
        # Clear existing rows.
        while self._list_layout.count():
            child = self._list_layout.takeAt(0)
            w = child.widget()
            if w is not None:
                w.deleteLater()
            else:
                lyt = child.layout()
                if lyt is not None:
                    self._discard_layout(lyt)
        self._row_widgets.clear()

        query = self._search_text.strip().lower()
        show_system = self._active_tab in ("all", "system")
        show_ai = self._active_tab in ("all", "ai")
        show_snip = self._active_tab in ("all", "snippet")

        # SYSTEM group (square dot per JSX) — always includes the launcher
        # pseudo-row at the top.
        if show_system:
            self._add_group_header("System", COLOR.text_3, dot_kind="square")
            if self._matches_launcher_filter(query):
                launcher_chip = _format_hotkey_chip(self._working_config.launcher_hotkey)
                launcher_row = LibraryRow(
                    LAUNCHER_PSEUDO_ID, "rec_launcher",
                    "Launcher (open popup)", launcher_chip,
                )
                launcher_row.rowClicked.connect(self._on_row_clicked)
                self._row_widgets[LAUNCHER_PSEUDO_ID] = launcher_row
                self._list_layout.addWidget(launcher_row)

            for item in self._items_by_type("system"):
                if not self._matches_filter(item, query):
                    continue
                self._add_item_row(item)

        # AI ACTIONS group (violet dot)
        if show_ai:
            self._add_group_header(
                "AI Actions", COLOR.violet, dot_kind="round", add_section="ai",
            )
            for item in self._items_by_type("ai"):
                if not self._matches_filter(item, query):
                    continue
                self._add_item_row(item)

        # SNIPPETS group (mint dot)
        if show_snip:
            self._add_group_header(
                "Snippets", COLOR.mint, dot_kind="round", add_section="snippet",
            )
            for item in self._items_by_type("snippet"):
                if not self._matches_filter(item, query):
                    continue
                self._add_item_row(item)

        self._list_layout.addStretch(1)

        if self._selected_id is not None and self._selected_id in self._row_widgets:
            self._row_widgets[self._selected_id].set_selected(True)

    def _add_group_header(self, title: str, dot_color: str, *,
                          dot_kind: str = "round",
                          add_section: Optional[str] = None) -> None:
        row = QFrame(self._list_body)
        row.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        row.setStyleSheet("background: transparent;")
        rl = QHBoxLayout(row)
        rl.setContentsMargins(8, 14, 8, 6)
        rl.setSpacing(8)

        dot = QLabel(row)
        dot.setFixedSize(6, 6)
        radius = "1px" if dot_kind == "square" else "3px"
        dot.setStyleSheet(f"background: {dot_color}; border-radius: {radius};")
        rl.addWidget(dot, 0, Qt.AlignmentFlag.AlignVCenter)

        lbl = QLabel(title, row)
        lbl.setProperty("class", "mgr-grp")
        rl.addWidget(lbl)

        rl.addStretch(1)

        if add_section is not None:
            add_btn = QPushButton(row)
            add_btn.setProperty("class", "mgr-add")
            add_btn.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            add_btn.setIcon(icon("plus", COLOR.text_2, 12))
            add_btn.setIconSize(icon_size(12))
            add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            add_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            add_btn.setToolTip(f"Add {title.lower()}")
            add_btn.clicked.connect(
                lambda _checked=False, s=add_section: self._on_add_clicked(s)
            )
            rl.addWidget(add_btn)

        self._list_layout.addWidget(row)

    def _add_item_row(self, item: Item) -> None:
        chip = _format_hotkey_chip(item.hotkey)
        row = LibraryRow(item.id, _icon_for_item(item),
                         item.name or "(unnamed)", chip)
        row.rowClicked.connect(self._on_row_clicked)
        self._row_widgets[item.id] = row
        self._list_layout.addWidget(row)

    def _discard_layout(self, lyt) -> None:
        while lyt.count():
            child = lyt.takeAt(0)
            w = child.widget()
            if w is not None:
                w.deleteLater()
            else:
                sub = child.layout()
                if sub is not None:
                    self._discard_layout(sub)

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------

    def _select_initial(self) -> None:
        self._select(LAUNCHER_PSEUDO_ID)

    def _select(self, item_id: str) -> None:
        if self._selected_id is not None and self._selected_id in self._row_widgets:
            self._row_widgets[self._selected_id].set_selected(False)
        self._selected_id = item_id
        if item_id in self._row_widgets:
            self._row_widgets[item_id].set_selected(True)

        if item_id == LAUNCHER_PSEUDO_ID:
            self._system_editor.populate_launcher(self._working_config.launcher_hotkey)
            self._stack.setCurrentIndex(self.IDX_SYSTEM)
            self._refresh_warning_banner(self._system_editor)
            return

        item = self._find_item(item_id)
        if item is None:
            self._stack.setCurrentIndex(self.IDX_EMPTY)
            return

        if item.type == "system":
            self._system_editor.populate_system(item)
            self._stack.setCurrentIndex(self.IDX_SYSTEM)
            self._refresh_warning_banner(self._system_editor)
        elif item.type == "ai":
            self._ai_editor.populate(item)
            self._stack.setCurrentIndex(self.IDX_AI)
            self._refresh_warning_banner(self._ai_editor)
        else:  # snippet
            self._system_editor.populate_snippet(item)
            self._stack.setCurrentIndex(self.IDX_SYSTEM)
            self._refresh_warning_banner(self._system_editor)

    def _find_item(self, item_id: str) -> Optional[Item]:
        for it in self._working_config.items:
            if it.id == item_id:
                return it
        return None

    # ------------------------------------------------------------------
    # Slot handlers
    # ------------------------------------------------------------------

    def _on_search_changed(self, text: str) -> None:
        self._search_text = text or ""
        self._rebuild_list()

    def _on_tab_changed(self, key: str) -> None:
        self._active_tab = key
        for k, btn in self._tab_buttons.items():
            btn.setProperty("on", "true" if k == key else "false")
            _repolish(btn)
        self._rebuild_list()

    def _on_row_clicked(self, item_id: str) -> None:
        self._select(item_id)

    def _on_add_clicked(self, section: str) -> None:
        name, ok = QInputDialog.getText(
            self, "New item", "Name:", QLineEdit.EchoMode.Normal,
            "Untitled action" if section == "ai" else "Untitled snippet",
        )
        if not ok:
            return
        name = (name or "").strip() or (
            "Untitled action" if section == "ai" else "Untitled snippet"
        )

        max_order = max(
            (it.order for it in self._working_config.items),
            default=-1,
        )
        if section == "ai":
            new_item = Item(
                id=new_item_id("ai"),
                type="ai",
                name=name,
                emoji="✨",
                hotkey="",
                enabled=True,
                order=max_order + 1,
                deletable=True,
                prompt="",
                model="",
                temperature=0.2,
            )
        else:
            new_item = Item(
                id=new_item_id("sn"),
                type="snippet",
                name=name,
                emoji="\U0001F4CB",
                hotkey="",
                enabled=True,
                order=max_order + 1,
                deletable=True,
                kind="text",
                body="",
                behavior="replace",
            )
        self._working_config.items.append(new_item)
        self._refresh_dirty_indicator()
        self._rebuild_list()
        self._select(new_item.id)

    def _on_delete_requested(self, item_id: str) -> None:
        item = self._find_item(item_id)
        if item is None or not item.deletable:
            return
        self._working_config.items = [
            it for it in self._working_config.items if it.id != item_id
        ]
        self._refresh_dirty_indicator()
        if self._selected_id == item_id:
            self._selected_id = LAUNCHER_PSEUDO_ID
        self._rebuild_list()
        if self._selected_id == LAUNCHER_PSEUDO_ID:
            self._select(LAUNCHER_PSEUDO_ID)

    def _on_duplicate_requested(self, item_id: str) -> None:
        item = self._find_item(item_id)
        if item is None or not item.deletable:
            return
        max_order = max(
            (it.order for it in self._working_config.items), default=-1
        )
        prefix = "ai" if item.type == "ai" else "sn"
        clone = Item(
            id=new_item_id(prefix),
            type=item.type,
            name=f"{item.name} (copy)",
            emoji=item.emoji,
            hotkey="",  # don't duplicate hotkey -> would conflict
            enabled=item.enabled,
            order=max_order + 1,
            deletable=True,
            subtype=item.subtype,
            prompt=item.prompt,
            model=item.model,
            temperature=item.temperature,
            kind=item.kind,
            body=item.body,
            behavior=item.behavior,
        )
        self._working_config.items.append(clone)
        self._refresh_dirty_indicator()
        self._rebuild_list()
        self._select(clone.id)

    def _on_name_changed(self, item_id: str, name: str) -> None:
        if item_id == LAUNCHER_PSEUDO_ID:
            return
        item = self._find_item(item_id)
        if item is None or item.type == "system":
            return
        item.name = name
        # Cheap rebuild to reflect the name in the rail.
        self._rebuild_list()
        self._refresh_dirty_indicator()

    def _on_emoji_changed(self, item_id: str, emoji: str) -> None:
        item = self._find_item(item_id)
        if item is None or item.type == "system":
            return
        item.emoji = emoji
        self._rebuild_list()
        self._refresh_dirty_indicator()

    def _on_enabled_changed(self, item_id: str, enabled: bool) -> None:
        item = self._find_item(item_id)
        if item is None:
            return
        item.enabled = bool(enabled)
        self._refresh_dirty_indicator()

    def _on_hotkey_changed(self, item_id: str, value: str) -> None:
        if item_id == LAUNCHER_PSEUDO_ID:
            self._working_config.launcher_hotkey = value
        else:
            item = self._find_item(item_id)
            if item is None:
                return
            item.hotkey = value
        self._refresh_dirty_indicator()
        self._rebuild_list()
        if self._selected_id is not None and self._selected_id in self._row_widgets:
            self._row_widgets[self._selected_id].set_selected(True)
        editor = self._current_editor()
        if editor is not None:
            self._refresh_warning_banner(editor)

    def _on_prompt_changed(self, item_id: str, prompt: str) -> None:
        item = self._find_item(item_id)
        if item is None or item.type != "ai":
            return
        item.prompt = prompt
        self._refresh_dirty_indicator()

    def _on_model_changed(self, item_id: str, model: str) -> None:
        item = self._find_item(item_id)
        if item is None or item.type != "ai":
            return
        item.model = model
        self._refresh_dirty_indicator()

    def _on_temperature_changed(self, item_id: str, value: float) -> None:
        item = self._find_item(item_id)
        if item is None or item.type != "ai":
            return
        item.temperature = float(value)
        self._refresh_dirty_indicator()

    # ------------------------------------------------------------------
    # Save / validation
    # ------------------------------------------------------------------

    def _hotkey_index(self) -> dict[str, list[str]]:
        """Returns ``hotkey -> list of owner ids (or LAUNCHER_PSEUDO_ID)``."""
        index: dict[str, list[str]] = {}
        if self._working_config.launcher_hotkey:
            index.setdefault(self._working_config.launcher_hotkey, []).append(
                LAUNCHER_PSEUDO_ID
            )
        for it in self._working_config.items:
            if it.hotkey:
                index.setdefault(it.hotkey, []).append(it.id)
        return index

    def _label_for_owner(self, owner_id: str) -> str:
        if owner_id == LAUNCHER_PSEUDO_ID:
            return "Launcher"
        it = self._find_item(owner_id)
        return it.name if it is not None else owner_id

    def _detect_conflict(self, focus_owner: str) -> Optional[str]:
        index = self._hotkey_index()
        if focus_owner == LAUNCHER_PSEUDO_ID:
            focus_hotkey = self._working_config.launcher_hotkey or ""
        else:
            it = self._find_item(focus_owner)
            focus_hotkey = (it.hotkey if it is not None else "") or ""

        if focus_hotkey and len(index.get(focus_hotkey, [])) > 1:
            others = [oid for oid in index[focus_hotkey] if oid != focus_owner]
            other_label = self._label_for_owner(others[0]) if others else "another item"
            return (
                f"⚠  {self._render_chord(focus_hotkey)} is also assigned to "
                f"'{other_label}'. Resolve conflict before saving."
            )

        for chord, owners in index.items():
            if len(owners) > 1:
                a = self._label_for_owner(owners[0])
                b = self._label_for_owner(owners[1])
                return (
                    f"⚠  {self._render_chord(chord)} is assigned to "
                    f"both '{a}' and '{b}'. Resolve conflict before saving."
                )
        return None

    def _render_chord(self, chord: str) -> str:
        return "+".join(_humanize_chord(chord)) or "—"

    def _current_editor(self) -> Optional[_EditorBase]:
        idx = self._stack.currentIndex()
        if idx == self.IDX_SYSTEM:
            return self._system_editor
        if idx == self.IDX_AI:
            return self._ai_editor
        return None

    def _refresh_warning_banner(self, editor: _EditorBase) -> None:
        owner = editor.current_id() or self._selected_id or ""
        if not owner:
            editor.set_warning("")
            return
        msg = self._detect_conflict(owner)
        editor.set_warning(msg or "")

    def _on_save_clicked(self) -> None:
        # Hard gate: no duplicate hotkeys may be saved.
        index = self._hotkey_index()
        conflicts = [(c, o) for c, o in index.items() if len(o) > 1]
        if conflicts:
            chord, owners = conflicts[0]
            a = self._label_for_owner(owners[0])
            b = self._label_for_owner(owners[1])
            msg = (
                f"⚠  {self._render_chord(chord)} is assigned to both "
                f"'{a}' and '{b}'. Resolve conflict before saving."
            )
            editor = self._current_editor()
            if editor is not None:
                editor.set_warning(msg)
            return

        try:
            save_config(self._config_path, self._working_config)
        except Exception as exc:
            editor = self._current_editor()
            if editor is not None:
                editor.set_warning(f"⚠  Could not save: {exc}")
            return

        self._original_config = copy.deepcopy(self._working_config)
        self._refresh_dirty_indicator()
        editor = self._current_editor()
        if editor is not None:
            editor.set_warning("")
            editor.trigger_save_flash()
        self.configChanged.emit(self._working_config)

    def _refresh_dirty_indicator(self) -> None:
        dirty = self._configs_differ(self._working_config, self._original_config)
        self._dirty_lbl.setVisible(dirty)

    @staticmethod
    def _configs_differ(a: Config, b: Config) -> bool:
        if a.version != b.version or a.launcher_hotkey != b.launcher_hotkey:
            return True
        if len(a.items) != len(b.items):
            return True
        by_id_b = {it.id: it for it in b.items}
        for it_a in a.items:
            it_b = by_id_b.get(it_a.id)
            if it_b is None:
                return True
            for field_name in (
                "type", "name", "emoji", "hotkey", "enabled", "order", "deletable",
                "subtype", "prompt", "model", "temperature", "kind", "body", "behavior",
            ):
                if getattr(it_a, field_name) != getattr(it_b, field_name):
                    return True
        return False

    # ------------------------------------------------------------------
    # Event handling: drag + close
    # ------------------------------------------------------------------

    def _on_close_clicked(self) -> None:
        self.closeRequested.emit()
        self.hide()

    def closeEvent(self, event):
        # Don't actually destroy; just hide so the next present() reuses state.
        self.closeRequested.emit()
        event.ignore()
        self.hide()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self._on_close_clicked()
            event.accept()
            return
        super().keyPressEvent(event)

    def eventFilter(self, obj, event):
        if obj is self._titlebar:
            et = event.type()
            if et == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                return True
            if et == QEvent.Type.MouseMove and event.buttons() & Qt.MouseButton.LeftButton:
                if self._drag_pos is not None:
                    self.move(event.globalPosition().toPoint() - self._drag_pos)
                    return True
            if et == QEvent.Type.MouseButtonRelease:
                self._drag_pos = None
        return super().eventFilter(obj, event)


__all__ = ["ManagerWindow"]
