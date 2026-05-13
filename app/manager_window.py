"""Frameless dashboard window for managing the unified library of actions."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from PyQt6.QtCore import (
    QEvent,
    QPoint,
    Qt,
    QTimer,
    pyqtSignal,
)
from PyQt6.QtGui import QCursor, QGuiApplication
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from design import COLOR, FONT

from .actions_config import Config, Item, new_item_id, save_config
from .hotkey_recorder import HotkeyRecorderButton

if TYPE_CHECKING:  # pragma: no cover - typing only
    pass


# ---------------------------------------------------------------------------
# Layout constants
# ---------------------------------------------------------------------------

CARD_WIDTH = 880
CARD_HEIGHT = 580
OUTER_PADDING = 0
RAIL_WIDTH = 264

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
# Utility helpers
# ---------------------------------------------------------------------------

def _repolish(w: QWidget) -> None:
    style = w.style()
    if style is None:
        return
    style.unpolish(w)
    style.polish(w)
    w.update()


def _set_class(w: QWidget, klass: str) -> None:
    w.setProperty("class", klass)
    _repolish(w)


def _section_for(item: Item) -> str:
    if item.type == "system":
        return "system"
    if item.type == "ai":
        return "ai"
    return "snippet"


# ---------------------------------------------------------------------------
# Row widget (left rail list item)
# ---------------------------------------------------------------------------

class LibraryRow(QPushButton):
    rowClicked = pyqtSignal(str)

    def __init__(self, item_id: str, emoji: str, name: str, hotkey_chip: str,
                 type_glyph: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._item_id = item_id
        self.setProperty("class", "mgr-row")
        self.setProperty("on", "false")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(34)
        self.setText("")  # children render the row

        row = QHBoxLayout(self)
        row.setContentsMargins(8, 6, 8, 6)
        row.setSpacing(10)

        grip = QLabel("⋮⋮")
        grip.setProperty("class", "mgr-grip")
        grip.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        row.addWidget(grip)

        emoji_lbl = QLabel(emoji or "")
        emoji_lbl.setStyleSheet("font-size: 15px;")
        emoji_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        row.addWidget(emoji_lbl)

        name_lbl = QLabel(name or "")
        name_lbl.setProperty("class", "mgr-row-name")
        name_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        name_lbl.setStyleSheet(f"color: {COLOR.text_1};")
        row.addWidget(name_lbl, 1)

        self._chip = QLabel(hotkey_chip)
        self._chip.setProperty("class", "kbd")
        self._chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._chip.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        if not hotkey_chip:
            self._chip.setVisible(False)
        row.addWidget(self._chip)

        glyph = QLabel(type_glyph)
        glyph.setProperty("class", "mgr-row-meta")
        glyph.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        glyph.setStyleSheet(f"color: {COLOR.text_4};")
        row.addWidget(glyph)

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
# Editor base
# ---------------------------------------------------------------------------

class _EditorBase(QWidget):
    """Common scaffold for all three editor variants."""

    nameChanged = pyqtSignal(str, str)        # (item_id, new_name)
    emojiChanged = pyqtSignal(str, str)       # (item_id, new_emoji)
    enabledChanged = pyqtSignal(str, bool)
    hotkeyChanged = pyqtSignal(str, str)      # (item_id, new_hotkey)
    deleteRequested = pyqtSignal(str)
    duplicateRequested = pyqtSignal(str)
    # AI-specific
    promptChanged = pyqtSignal(str, str)
    modelChanged = pyqtSignal(str, str)
    temperatureChanged = pyqtSignal(str, float)
    # Snippet-specific
    bodyChanged = pyqtSignal(str, str)
    kindChanged = pyqtSignal(str, str)
    behaviorChanged = pyqtSignal(str, str)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._current_id: Optional[str] = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # --- header
        self._header = QWidget(self)
        self._header.setObjectName("managerEditHead")
        self._header.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        head = QHBoxLayout(self._header)
        head.setContentsMargins(22, 16, 22, 14)
        head.setSpacing(14)

        self._emoji_box = QLabel("")
        self._emoji_box.setProperty("class", "ed-hd-emoji")
        self._emoji_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._emoji_box.setFixedSize(48, 48)
        head.addWidget(self._emoji_box, 0, Qt.AlignmentFlag.AlignTop)

        meta_col = QVBoxLayout()
        meta_col.setContentsMargins(0, 0, 0, 0)
        meta_col.setSpacing(4)

        self._kind_lbl = QLabel("")
        self._kind_lbl.setProperty("class", "ed-hd-kind")
        meta_col.addWidget(self._kind_lbl)

        self._name_edit = QLineEdit()
        self._name_edit.setProperty("class", "ed-hd-name")
        self._name_edit.setPlaceholderText("Name…")
        self._name_edit.textEdited.connect(self._on_name_edited)
        meta_col.addWidget(self._name_edit)

        self._sub_lbl = QLabel("")
        self._sub_lbl.setProperty("class", "ed-hd-sub")
        self._sub_lbl.setWordWrap(True)
        self._sub_lbl.setStyleSheet(f"color: {COLOR.text_2};")
        meta_col.addWidget(self._sub_lbl)

        head.addLayout(meta_col, 1)

        actions_col = QHBoxLayout()
        actions_col.setContentsMargins(0, 0, 0, 0)
        actions_col.setSpacing(8)

        self._change_emoji_btn = QPushButton("Change emoji")
        self._change_emoji_btn.setProperty("class", "btn ghost")
        self._change_emoji_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._change_emoji_btn.clicked.connect(self._on_change_emoji)
        actions_col.addWidget(self._change_emoji_btn)

        self._duplicate_btn = QPushButton("Duplicate")
        self._duplicate_btn.setProperty("class", "btn ghost")
        self._duplicate_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._duplicate_btn.clicked.connect(self._on_duplicate)
        actions_col.addWidget(self._duplicate_btn)

        self._delete_btn = QPushButton("Delete")
        self._delete_btn.setProperty("class", "btn ghost danger")
        self._delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._delete_btn.clicked.connect(self._on_delete)
        actions_col.addWidget(self._delete_btn)

        head.addLayout(actions_col)
        root.addWidget(self._header)

        # --- duplicate-hotkey warning banner
        self._warn_banner = QFrame(self)
        self._warn_banner.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._warn_banner.setStyleSheet(
            "background: rgba(255,107,122,0.10);"
            "border-bottom: 1px solid rgba(255,107,122,0.30);"
        )
        warn_lyt = QHBoxLayout(self._warn_banner)
        warn_lyt.setContentsMargins(22, 8, 22, 8)
        warn_lyt.setSpacing(8)
        self._warn_label = QLabel("")
        self._warn_label.setStyleSheet(f"color: {COLOR.danger}; font-size: 12px;")
        self._warn_label.setWordWrap(True)
        warn_lyt.addWidget(self._warn_label, 1)
        self._warn_banner.hide()
        root.addWidget(self._warn_banner)

        # --- body (subclasses populate)
        self._body_scroll = QScrollArea(self)
        self._body_scroll.setWidgetResizable(True)
        self._body_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._body_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._body_scroll.setStyleSheet("QScrollArea { background: transparent; border: 0; }")

        self._body = QWidget()
        self._body.setStyleSheet(f"background: {COLOR.surface_1};")
        self._body_layout = QVBoxLayout(self._body)
        self._body_layout.setContentsMargins(22, 16, 22, 18)
        self._body_layout.setSpacing(18)
        self._body_scroll.setWidget(self._body)
        root.addWidget(self._body_scroll, 1)

        # --- footer (hotkey + save)
        self._footer = QWidget(self)
        self._footer.setObjectName("editorFooter")
        self._footer.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        ft = QHBoxLayout(self._footer)
        ft.setContentsMargins(22, 11, 22, 11)
        ft.setSpacing(10)

        ft_lbl = QLabel("Hotkey")
        ft_lbl.setProperty("class", "ed-ft-lbl")
        ft.addWidget(ft_lbl)

        self._hotkey_btn = HotkeyRecorderButton("", self._footer)
        self._hotkey_btn.captured.connect(self._on_hotkey_captured)
        self._hotkey_btn.cleared.connect(self._on_hotkey_cleared)
        ft.addWidget(self._hotkey_btn)

        ft.addStretch(1)

        self._save_btn = QPushButton("\U0001F4BE  Save")
        self._save_btn.setProperty("class", "btn primary")
        self._save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._save_btn.clicked.connect(self._on_save_clicked)
        ft.addWidget(self._save_btn)

        root.addWidget(self._footer)

        # Save-flash timer
        self._save_flash_timer = QTimer(self)
        self._save_flash_timer.setSingleShot(True)
        self._save_flash_timer.timeout.connect(self._restore_save_label)

    # Public surface ----------------------------------------------------

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
        self._save_btn.setText("Saved ✓")
        self._save_flash_timer.start(1500)

    def saveRequested(self):  # noqa: N802 (Qt-style accessor name kept lowercase)
        return self._save_signal

    # Signals via subclass overrides (we use a Qt signal proxy below)
    saveClicked = pyqtSignal()

    # Internal --------------------------------------------------------

    def _restore_save_label(self) -> None:
        self._save_btn.setText("\U0001F4BE  Save")

    def _on_save_clicked(self) -> None:
        self.saveClicked.emit()

    def _on_name_edited(self, text: str) -> None:
        if self._current_id is None:
            return
        self.nameChanged.emit(self._current_id, text)

    def _on_change_emoji(self) -> None:
        if self._current_id is None:
            return
        current = self._emoji_box.text() or ""
        new, ok = QInputDialog.getText(
            self, "Change emoji", "Emoji or character:", QLineEdit.EchoMode.Normal, current
        )
        if not ok:
            return
        new = (new or "").strip()
        if not new:
            return
        # Accept just the first grapheme-ish chunk; user is trusted.
        self._emoji_box.setText(new)
        self.emojiChanged.emit(self._current_id, new)

    def _on_duplicate(self) -> None:
        if self._current_id is None:
            return
        self.duplicateRequested.emit(self._current_id)

    def _on_delete(self) -> None:
        if self._current_id is None:
            return
        self.deleteRequested.emit(self._current_id)

    def _on_hotkey_captured(self, value: str) -> None:
        if self._current_id is None:
            return
        self.hotkeyChanged.emit(self._current_id, value)

    def _on_hotkey_cleared(self) -> None:
        if self._current_id is None:
            return
        self.hotkeyChanged.emit(self._current_id, "")

    # Subclass hooks ---------------------------------------------------

    def _clear_body(self) -> None:
        while self._body_layout.count():
            child = self._body_layout.takeAt(0)
            w = child.widget()
            if w is not None:
                w.deleteLater()
            else:
                lyt = child.layout()
                if lyt is not None:
                    self._discard_layout(lyt)

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


# ---------------------------------------------------------------------------
# Small field helper
# ---------------------------------------------------------------------------

def _make_field(label: str, control: QWidget, hint: Optional[str] = None) -> QWidget:
    wrap = QWidget()
    lyt = QVBoxLayout(wrap)
    lyt.setContentsMargins(0, 0, 0, 0)
    lyt.setSpacing(7)
    lbl = QLabel(label)
    lbl.setProperty("class", "ed-field-lbl")
    lyt.addWidget(lbl)
    lyt.addWidget(control)
    if hint:
        h = QLabel(hint)
        h.setProperty("class", "ed-field-hint")
        h.setWordWrap(True)
        lyt.addWidget(h)
    return wrap


# ---------------------------------------------------------------------------
# System editor
# ---------------------------------------------------------------------------

class SystemEditor(_EditorBase):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._name_edit.setReadOnly(True)
        self._change_emoji_btn.hide()
        self._duplicate_btn.hide()
        self._delete_btn.hide()
        self._build_body()

    def _build_body(self) -> None:
        self._clear_body()

        self._enabled_chk = QCheckBox("Enabled in popup launcher")
        self._enabled_chk.setProperty("class", "ed-check")
        self._enabled_chk.stateChanged.connect(self._on_enabled_changed)

        self._body_layout.addWidget(_make_field(
            "Status",
            self._enabled_chk,
            "Disable to hide this built-in feature from the popup tile grid. "
            "Its global hotkey will also be unbound.",
        ))
        self._body_layout.addStretch(1)

    def populate(self, item: Item) -> None:
        self._current_id = item.id
        self._emoji_box.setText(item.emoji or "")
        self._kind_lbl.setText("●  SYSTEM FEATURE")
        self._kind_lbl.setStyleSheet(f"color: {COLOR.text_3};")
        self._name_edit.setText(item.name or "")
        self._sub_lbl.setText(
            "Built-in feature. Trigger it from any window with the hotkey below, "
            "or click its tile in the launcher popup."
        )
        self._enabled_chk.blockSignals(True)
        self._enabled_chk.setChecked(bool(item.enabled))
        self._enabled_chk.blockSignals(False)
        self._hotkey_btn.setValue(item.hotkey or "")

    def _on_enabled_changed(self, state: int) -> None:
        if self._current_id is None:
            return
        self.enabledChanged.emit(self._current_id, state == Qt.CheckState.Checked.value)


# ---------------------------------------------------------------------------
# AI editor
# ---------------------------------------------------------------------------

class AIEditor(_EditorBase):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._build_body()

    def _build_body(self) -> None:
        self._clear_body()

        cols = QHBoxLayout()
        cols.setContentsMargins(0, 0, 0, 0)
        cols.setSpacing(22)

        # Left column: prompt + preview
        left = QVBoxLayout()
        left.setContentsMargins(0, 0, 0, 0)
        left.setSpacing(18)

        self._prompt_edit = QTextEdit()
        self._prompt_edit.setProperty("class", "ed-textarea ed-prompt")
        self._prompt_edit.setMinimumHeight(140)
        self._prompt_edit.textChanged.connect(self._on_prompt_changed)
        left.addWidget(_make_field(
            "Prompt",
            self._prompt_edit,
            "Sent as the system prompt. The clipboard contents are sent as the user message.",
        ))

        # Static preview block (visual nicety, not live)
        preview_frame = QFrame()
        preview_frame.setProperty("class", "ed-preview")
        preview_frame.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        pl = QVBoxLayout(preview_frame)
        pl.setContentsMargins(14, 12, 14, 14)
        pl.setSpacing(10)

        plh = QHBoxLayout()
        plh.setContentsMargins(0, 0, 0, 0)
        plh.setSpacing(8)
        dot = QLabel()
        dot.setFixedSize(6, 6)
        dot.setStyleSheet(
            f"background: {COLOR.violet}; border-radius: 3px;"
        )
        plh.addWidget(dot)
        plbl = QLabel("LIVE PREVIEW")
        plbl.setProperty("class", "ed-preview-lbl")
        plh.addWidget(plbl)
        plh.addStretch(1)
        pmute = QLabel("sample input, not a live LLM call")
        pmute.setProperty("class", "ed-preview-mute")
        plh.addWidget(pmute)
        pl.addLayout(plh)

        grid = QHBoxLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(8)

        def _cell(header: str, text: str) -> QFrame:
            cell = QFrame()
            cell.setProperty("class", "ed-preview-cell")
            cell.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            cly = QVBoxLayout(cell)
            cly.setContentsMargins(10, 10, 12, 12)
            cly.setSpacing(6)
            h = QLabel(header)
            h.setProperty("class", "ed-preview-hdcell")
            cly.addWidget(h)
            t = QLabel(text)
            t.setProperty("class", "ed-preview-text")
            t.setWordWrap(True)
            cly.addWidget(t)
            return cell

        grid.addWidget(_cell(
            "CLIPBOARD INPUT",
            "heyy can u send me that doc when u get a sec, thx",
        ), 1)
        arrow = QLabel("→")
        arrow.setProperty("class", "ed-preview-arrow")
        arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        arrow.setFixedWidth(32)
        grid.addWidget(arrow)
        grid.addWidget(_cell(
            "RESULT",
            "Hi — could you send that document over when you have a moment? Thanks.",
        ), 1)

        pl.addLayout(grid)
        left.addWidget(preview_frame)
        left.addStretch(1)

        left_wrap = QWidget()
        left_wrap.setLayout(left)
        cols.addWidget(left_wrap, 1)

        # Right column: model, temperature, enabled
        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(18)

        self._model_combo = QComboBox()
        self._model_combo.setProperty("class", "ed-input")
        self._model_combo.setEditable(True)
        for value, label in AI_MODEL_CHOICES:
            self._model_combo.addItem(label, value)
        self._model_combo.currentIndexChanged.connect(self._on_model_changed)
        self._model_combo.lineEdit().editingFinished.connect(self._on_model_text_finished)
        right.addWidget(_make_field(
            "Model",
            self._model_combo,
            "Any OpenRouter model id. Leave blank for the grammar fallback default.",
        ))

        temp_wrap = QWidget()
        temp_lyt = QVBoxLayout(temp_wrap)
        temp_lyt.setContentsMargins(0, 0, 0, 0)
        temp_lyt.setSpacing(6)
        self._temp_slider = QSlider(Qt.Orientation.Horizontal)
        self._temp_slider.setProperty("class", "ed-slider")
        self._temp_slider.setMinimum(0)
        self._temp_slider.setMaximum(20)
        self._temp_slider.setSingleStep(1)
        self._temp_slider.setPageStep(2)
        self._temp_slider.valueChanged.connect(self._on_temp_changed)
        temp_lyt.addWidget(self._temp_slider)
        marks = QHBoxLayout()
        marks.setContentsMargins(0, 0, 0, 0)
        for txt in ("0", "0.5", "1"):
            lbl = QLabel(txt)
            lbl.setStyleSheet(
                f"font-family: {FONT.mono}; font-size: 10px; color: {COLOR.text_4};"
            )
            marks.addWidget(lbl)
            if txt != "1":
                marks.addStretch(1)
        temp_lyt.addLayout(marks)

        self._temp_field_wrap = _make_field(
            "Temperature · 0.00",
            temp_wrap,
            "Lower = deterministic, higher = creative.",
        )
        right.addWidget(self._temp_field_wrap)

        self._enabled_chk = QCheckBox("Show in launcher")
        self._enabled_chk.setProperty("class", "ed-check")
        self._enabled_chk.stateChanged.connect(self._on_enabled_changed)
        right.addWidget(_make_field("Behavior", self._enabled_chk))

        right.addStretch(1)

        right_wrap = QWidget()
        right_wrap.setLayout(right)
        right_wrap.setFixedWidth(260)
        cols.addWidget(right_wrap, 0)

        self._body_layout.addLayout(cols)
        self._body_layout.addStretch(1)

    def populate(self, item: Item) -> None:
        self._current_id = item.id
        self._emoji_box.setText(item.emoji or "")
        self._kind_lbl.setText("●  AI ACTION")
        self._kind_lbl.setStyleSheet(f"color: {COLOR.violet};")
        self._name_edit.setText(item.name or "")
        self._sub_lbl.setText(
            "Runs against your clipboard contents and replaces them with the result."
        )

        self._prompt_edit.blockSignals(True)
        self._prompt_edit.setPlainText(item.prompt or "")
        self._prompt_edit.blockSignals(False)

        self._model_combo.blockSignals(True)
        target_value = (item.model or "")
        match_idx = -1
        for i in range(self._model_combo.count()):
            if self._model_combo.itemData(i) == target_value:
                match_idx = i
                break
        if match_idx >= 0:
            self._model_combo.setCurrentIndex(match_idx)
        else:
            # custom value pasted in
            self._model_combo.setEditText(target_value)
        self._model_combo.blockSignals(False)

        temp = item.temperature if item.temperature is not None else 0.2
        clamped = max(0.0, min(1.0, float(temp)))
        self._temp_slider.blockSignals(True)
        self._temp_slider.setValue(int(round(clamped * 20)))
        self._temp_slider.blockSignals(False)
        self._update_temp_label(clamped)

        self._enabled_chk.blockSignals(True)
        self._enabled_chk.setChecked(bool(item.enabled))
        self._enabled_chk.blockSignals(False)

        self._hotkey_btn.setValue(item.hotkey or "")

        self._delete_btn.setVisible(bool(item.deletable))
        self._duplicate_btn.setVisible(bool(item.deletable))
        self._change_emoji_btn.show()
        self._name_edit.setReadOnly(False)

    def _update_temp_label(self, value: float) -> None:
        # Replace the existing label inside the temperature field wrap.
        lyt = self._temp_field_wrap.layout()
        if lyt is None or lyt.count() == 0:
            return
        item = lyt.itemAt(0)
        if item is None:
            return
        w = item.widget()
        if isinstance(w, QLabel):
            w.setText(f"Temperature · {value:.2f}")

    # Slot handlers ----------------------------------------------------

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
        text = self._model_combo.lineEdit().text().strip()
        # If text matches a known label, use the data value; else treat as raw model id.
        for i in range(self._model_combo.count()):
            if self._model_combo.itemText(i) == text:
                value = self._model_combo.itemData(i)
                self.modelChanged.emit(self._current_id, str(value or ""))
                return
        self.modelChanged.emit(self._current_id, text)

    def _on_temp_changed(self, raw: int) -> None:
        value = raw / 20.0
        self._update_temp_label(value)
        if self._current_id is None:
            return
        self.temperatureChanged.emit(self._current_id, value)

    def _on_enabled_changed(self, state: int) -> None:
        if self._current_id is None:
            return
        self.enabledChanged.emit(self._current_id, state == Qt.CheckState.Checked.value)


# ---------------------------------------------------------------------------
# Snippet editor
# ---------------------------------------------------------------------------

class SnippetEditor(_EditorBase):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._build_body()

    def _build_body(self) -> None:
        self._clear_body()

        cols = QHBoxLayout()
        cols.setContentsMargins(0, 0, 0, 0)
        cols.setSpacing(22)

        # Left: body
        left = QVBoxLayout()
        left.setContentsMargins(0, 0, 0, 0)
        left.setSpacing(18)

        self._body_text = QTextEdit()
        self._body_text.setProperty("class", "ed-textarea ed-mono")
        self._body_text.setMinimumHeight(160)
        self._body_text.textChanged.connect(self._on_body_text_changed)

        self._body_url = QLineEdit()
        self._body_url.setProperty("class", "ed-input ed-mono")
        self._body_url.setPlaceholderText("https://…")
        self._body_url.textEdited.connect(self._on_body_url_edited)
        self._body_url.hide()

        self._body_field_wrap = QWidget()
        bf_lyt = QVBoxLayout(self._body_field_wrap)
        bf_lyt.setContentsMargins(0, 0, 0, 0)
        bf_lyt.setSpacing(7)
        self._body_lbl = QLabel("SNIPPET TEXT")
        self._body_lbl.setProperty("class", "ed-field-lbl")
        bf_lyt.addWidget(self._body_lbl)
        bf_lyt.addWidget(self._body_text)
        bf_lyt.addWidget(self._body_url)
        self._body_hint = QLabel("Goes straight to the clipboard.")
        self._body_hint.setProperty("class", "ed-field-hint")
        self._body_hint.setWordWrap(True)
        bf_lyt.addWidget(self._body_hint)

        left.addWidget(self._body_field_wrap)
        left.addStretch(1)

        left_wrap = QWidget()
        left_wrap.setLayout(left)
        cols.addWidget(left_wrap, 1)

        # Right: type segmented + behavior radios + enabled
        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(18)

        seg_wrap = QFrame()
        seg_wrap.setProperty("class", "ed-seg")
        seg_wrap.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        seg_lyt = QHBoxLayout(seg_wrap)
        seg_lyt.setContentsMargins(3, 3, 3, 3)
        seg_lyt.setSpacing(3)
        self._kind_text_btn = QPushButton("Text")
        self._kind_text_btn.setProperty("class", "ed-seg-btn")
        self._kind_text_btn.setProperty("on", "true")
        self._kind_text_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._kind_text_btn.clicked.connect(lambda: self._on_kind_changed("text"))
        self._kind_url_btn = QPushButton("URL")
        self._kind_url_btn.setProperty("class", "ed-seg-btn")
        self._kind_url_btn.setProperty("on", "false")
        self._kind_url_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._kind_url_btn.clicked.connect(lambda: self._on_kind_changed("url"))
        seg_lyt.addWidget(self._kind_text_btn, 1)
        seg_lyt.addWidget(self._kind_url_btn, 1)
        right.addWidget(_make_field("Type", seg_wrap))

        # Behavior radios (text-only)
        self._behavior_group = QButtonGroup(self)
        self._behavior_group.setExclusive(True)
        behavior_wrap = QWidget()
        bw_lyt = QVBoxLayout(behavior_wrap)
        bw_lyt.setContentsMargins(0, 0, 0, 0)
        bw_lyt.setSpacing(0)

        self._rb_replace = QRadioButton("Replace clipboard (default)")
        self._rb_replace.setProperty("class", "ed-radio")
        self._rb_replace.toggled.connect(lambda c: c and self._on_behavior_changed("replace"))
        bw_lyt.addWidget(self._rb_replace)

        self._rb_append = QRadioButton("Append to clipboard")
        self._rb_append.setProperty("class", "ed-radio")
        self._rb_append.toggled.connect(lambda c: c and self._on_behavior_changed("append"))
        bw_lyt.addWidget(self._rb_append)

        self._rb_autopaste = QRadioButton("Copy + auto-paste")
        self._rb_autopaste.setProperty("class", "ed-radio")
        self._rb_autopaste.toggled.connect(lambda c: c and self._on_behavior_changed("autopaste"))
        bw_lyt.addWidget(self._rb_autopaste)

        self._behavior_group.addButton(self._rb_replace)
        self._behavior_group.addButton(self._rb_append)
        self._behavior_group.addButton(self._rb_autopaste)

        self._behavior_field = _make_field("On trigger", behavior_wrap)
        right.addWidget(self._behavior_field)

        self._enabled_chk = QCheckBox("Show in launcher")
        self._enabled_chk.setProperty("class", "ed-check")
        self._enabled_chk.stateChanged.connect(self._on_enabled_changed)
        right.addWidget(_make_field("Visibility", self._enabled_chk))

        right.addStretch(1)

        right_wrap = QWidget()
        right_wrap.setLayout(right)
        right_wrap.setFixedWidth(260)
        cols.addWidget(right_wrap, 0)

        self._body_layout.addLayout(cols)
        self._body_layout.addStretch(1)

    def populate(self, item: Item) -> None:
        self._current_id = item.id
        self._emoji_box.setText(item.emoji or "")
        is_url = (item.kind or "text").lower() == "url"

        if is_url:
            self._kind_lbl.setText("●  URL SNIPPET")
            self._kind_lbl.setStyleSheet(f"color: {COLOR.url_blue};")
            self._sub_lbl.setText(
                "Opens the URL in your default browser. Doesn't touch the clipboard."
            )
        else:
            self._kind_lbl.setText("●  TEXT SNIPPET")
            self._kind_lbl.setStyleSheet(f"color: {COLOR.mint};")
            self._sub_lbl.setText(
                "Replaces the clipboard with this text. Paste it anywhere with Ctrl+V."
            )

        self._name_edit.setText(item.name or "")
        self._name_edit.setReadOnly(False)
        self._change_emoji_btn.show()
        self._duplicate_btn.setVisible(bool(item.deletable))
        self._delete_btn.setVisible(bool(item.deletable))

        # body
        if is_url:
            self._body_lbl.setText("URL")
            self._body_hint.setText("Opens in your default browser when fired.")
            self._body_text.hide()
            self._body_url.show()
            self._body_url.blockSignals(True)
            self._body_url.setText(item.body or "")
            self._body_url.blockSignals(False)
        else:
            self._body_lbl.setText("SNIPPET TEXT")
            self._body_hint.setText("Goes straight to the clipboard.")
            self._body_url.hide()
            self._body_text.show()
            self._body_text.blockSignals(True)
            self._body_text.setPlainText(item.body or "")
            self._body_text.blockSignals(False)

        # Segmented control state
        self._kind_text_btn.setProperty("on", "false" if is_url else "true")
        self._kind_url_btn.setProperty("on", "true" if is_url else "false")
        _repolish(self._kind_text_btn)
        _repolish(self._kind_url_btn)

        # Behavior radios — only meaningful for text
        self._behavior_field.setVisible(not is_url)
        behavior = (item.behavior or "replace").lower()
        for rb, key in (
            (self._rb_replace, "replace"),
            (self._rb_append, "append"),
            (self._rb_autopaste, "autopaste"),
        ):
            rb.blockSignals(True)
            rb.setChecked(behavior == key)
            rb.blockSignals(False)

        self._enabled_chk.blockSignals(True)
        self._enabled_chk.setChecked(bool(item.enabled))
        self._enabled_chk.blockSignals(False)

        self._hotkey_btn.setValue(item.hotkey or "")

    def _on_body_text_changed(self) -> None:
        if self._current_id is None:
            return
        self.bodyChanged.emit(self._current_id, self._body_text.toPlainText())

    def _on_body_url_edited(self, text: str) -> None:
        if self._current_id is None:
            return
        self.bodyChanged.emit(self._current_id, text)

    def _on_kind_changed(self, kind: str) -> None:
        if self._current_id is None:
            return
        self.kindChanged.emit(self._current_id, kind)

    def _on_behavior_changed(self, behavior: str) -> None:
        if self._current_id is None:
            return
        self.behaviorChanged.emit(self._current_id, behavior)

    def _on_enabled_changed(self, state: int) -> None:
        if self._current_id is None:
            return
        self.enabledChanged.emit(self._current_id, state == Qt.CheckState.Checked.value)


# ---------------------------------------------------------------------------
# Launcher hotkey editor (pseudo-item for the launcher itself)
# ---------------------------------------------------------------------------

class LauncherEditor(_EditorBase):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._name_edit.setReadOnly(True)
        self._change_emoji_btn.hide()
        self._duplicate_btn.hide()
        self._delete_btn.hide()
        self._build_body()

    def _build_body(self) -> None:
        self._clear_body()
        note = QLabel(
            "This is the global hotkey that opens the launcher popup from anywhere. "
            "Pick a chord with at least one of Ctrl, Alt, Shift, or Win."
        )
        note.setStyleSheet(f"color: {COLOR.text_2}; font-size: 12px;")
        note.setWordWrap(True)
        self._body_layout.addWidget(note)
        self._body_layout.addStretch(1)

    def populate(self, hotkey: str) -> None:
        self._current_id = LAUNCHER_PSEUDO_ID
        self._emoji_box.setText("▶")
        self._kind_lbl.setText("●  LAUNCHER")
        self._kind_lbl.setStyleSheet(f"color: {COLOR.violet};")
        self._name_edit.setText("Open the launcher popup")
        self._sub_lbl.setText("Global trigger — works from any window.")
        self._hotkey_btn.setValue(hotkey or "")


# ---------------------------------------------------------------------------
# Manager window
# ---------------------------------------------------------------------------

class ManagerWindow(QWidget):
    """Frameless dashboard for editing the unified action library."""

    configChanged = pyqtSignal(object)
    closeRequested = pyqtSignal()

    # Editor indices in the QStackedWidget
    IDX_EMPTY = 0
    IDX_LAUNCHER = 1
    IDX_SYSTEM = 2
    IDX_AI = 3
    IDX_SNIPPET = 4

    def __init__(self, config: Config, config_path: Path, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
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
        outer.setContentsMargins(OUTER_PADDING, OUTER_PADDING, OUTER_PADDING, OUTER_PADDING)
        outer.setSpacing(0)

        self._card = QFrame(self)
        self._card.setObjectName("managerCard")
        self._card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._card.setFixedSize(CARD_WIDTH, CARD_HEIGHT)
        outer.addWidget(self._card)

        card_lyt = QVBoxLayout(self._card)
        card_lyt.setContentsMargins(0, 0, 0, 0)
        card_lyt.setSpacing(0)

        # Titlebar
        self._titlebar = QWidget(self._card)
        self._titlebar.setObjectName("managerTitlebar")
        self._titlebar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._titlebar.setFixedHeight(44)
        self._titlebar.setCursor(Qt.CursorShape.SizeAllCursor)
        tb = QHBoxLayout(self._titlebar)
        tb.setContentsMargins(16, 0, 10, 0)
        tb.setSpacing(8)

        brand_mark = QLabel("✓")
        brand_mark.setProperty("class", "brand-mark")
        brand_mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand_mark.setFixedSize(18, 18)
        brand_mark.setStyleSheet(
            f"background: {COLOR.violet}; color: #FFFFFF; border-radius: 5px;"
            f" font-size: 11px; font-weight: 700;"
        )
        tb.addWidget(brand_mark)

        title_lbl = QLabel("Shortcut")
        title_lbl.setProperty("class", "mgr-title")
        tb.addWidget(title_lbl)

        sep = QLabel("/")
        sep.setStyleSheet(f"color: {COLOR.text_4}; margin: 0 4px;")
        tb.addWidget(sep)

        sub = QLabel("Manage Library")
        sub.setStyleSheet(f"color: {COLOR.text_2}; font-size: 12px; font-weight: 500;")
        tb.addWidget(sub)

        self._dirty_lbl = QLabel("• Unsaved changes")
        self._dirty_lbl.setStyleSheet(
            f"color: {COLOR.amber}; font-size: 11px; font-weight: 500; margin-left: 10px;"
        )
        self._dirty_lbl.hide()
        tb.addWidget(self._dirty_lbl)

        tb.addStretch(1)

        close_btn = QPushButton("✕")
        close_btn.setProperty("class", "icon-btn")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setFixedSize(28, 28)
        close_btn.clicked.connect(self._on_close_clicked)
        tb.addWidget(close_btn)

        card_lyt.addWidget(self._titlebar)
        self._titlebar.installEventFilter(self)

        # Body: rail + editor
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        card_lyt.addLayout(body, 1)

        self._rail = self._build_rail()
        body.addWidget(self._rail)

        self._edit_pane = QWidget(self._card)
        self._edit_pane.setObjectName("managerEdit")
        self._edit_pane.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        edit_lyt = QVBoxLayout(self._edit_pane)
        edit_lyt.setContentsMargins(0, 0, 0, 0)
        edit_lyt.setSpacing(0)

        self._stack = QStackedWidget(self._edit_pane)
        edit_lyt.addWidget(self._stack)

        # Index 0: empty placeholder
        empty = QWidget()
        ev = QVBoxLayout(empty)
        ev.setContentsMargins(40, 40, 40, 40)
        ev.setSpacing(8)
        ev.addStretch(1)
        ep = QLabel("Select an item from the left to edit.")
        ep.setStyleSheet(f"color: {COLOR.text_2}; font-size: 13px;")
        ep.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ev.addWidget(ep)
        ev.addStretch(1)
        self._stack.insertWidget(self.IDX_EMPTY, empty)

        # Index 1..4: real editors
        self._launcher_editor = LauncherEditor()
        self._system_editor = SystemEditor()
        self._ai_editor = AIEditor()
        self._snippet_editor = SnippetEditor()
        self._stack.insertWidget(self.IDX_LAUNCHER, self._launcher_editor)
        self._stack.insertWidget(self.IDX_SYSTEM, self._system_editor)
        self._stack.insertWidget(self.IDX_AI, self._ai_editor)
        self._stack.insertWidget(self.IDX_SNIPPET, self._snippet_editor)

        body.addWidget(self._edit_pane, 1)

    def _build_rail(self) -> QWidget:
        rail = QWidget(self._card)
        rail.setObjectName("managerRail")
        rail.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        rail.setFixedWidth(RAIL_WIDTH)
        rl = QVBoxLayout(rail)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(0)

        head = QWidget(rail)
        head.setObjectName("managerRailHead")
        head.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        hl = QVBoxLayout(head)
        hl.setContentsMargins(14, 14, 14, 10)
        hl.setSpacing(10)

        # Search field with leading icon overlay
        search_wrap = QFrame(head)
        search_wrap.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        search_wrap.setStyleSheet("background: transparent; border: 0;")
        sw = QHBoxLayout(search_wrap)
        sw.setContentsMargins(0, 0, 0, 0)
        sw.setSpacing(0)

        self._search = QLineEdit(search_wrap)
        self._search.setProperty("class", "mgr-search")
        self._search.setPlaceholderText("\U0001F50D  Search library…")
        self._search.textChanged.connect(self._on_search_changed)
        sw.addWidget(self._search, 1)
        hl.addWidget(search_wrap)

        # Tabs
        tabs = QFrame(head)
        tabs.setObjectName("managerTabs")
        tabs.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        tl = QHBoxLayout(tabs)
        tl.setContentsMargins(3, 3, 3, 3)
        tl.setSpacing(4)
        self._tab_buttons: dict[str, QPushButton] = {}
        for key, label in (("all", "All"), ("system", "System"), ("ai", "AI"), ("snippet", "Snippets")):
            btn = QPushButton(label)
            btn.setProperty("class", "mgr-tab")
            btn.setProperty("on", "true" if key == self._active_tab else "false")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _checked=False, k=key: self._on_tab_changed(k))
            tl.addWidget(btn, 1)
            self._tab_buttons[key] = btn
        hl.addWidget(tabs)

        rl.addWidget(head)

        # Scrollable list
        self._list_scroll = QScrollArea(rail)
        self._list_scroll.setWidgetResizable(True)
        self._list_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._list_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._list_scroll.setStyleSheet("QScrollArea { background: transparent; border: 0; }")

        self._list_body = QWidget()
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
        for editor in (self._launcher_editor, self._system_editor, self._ai_editor, self._snippet_editor):
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

        self._snippet_editor.bodyChanged.connect(self._on_body_changed)
        self._snippet_editor.kindChanged.connect(self._on_kind_changed)
        self._snippet_editor.behaviorChanged.connect(self._on_behavior_changed)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_config(self, config: Config) -> None:
        self._original_config = copy.deepcopy(config)
        self._working_config = copy.deepcopy(config)
        self._refresh_dirty_indicator()
        self._rebuild_list()
        # Re-select if possible
        if self._selected_id and (
            self._selected_id == LAUNCHER_PSEUDO_ID
            or self._find_item(self._selected_id) is not None
        ):
            self._select(self._selected_id)
        else:
            self._select(LAUNCHER_PSEUDO_ID)

    def present(self) -> None:
        self.adjustSize()
        # Fixed inner card; outer translucent widget gets +padding.
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

    def _format_hotkey_chip(self, hotkey: str) -> str:
        if not hotkey:
            return ""
        # Compact: just the trailing key.
        try:
            tail = hotkey.split("+")[-1].strip()
        except Exception:
            return ""
        if tail.startswith("<") and tail.endswith(">"):
            tail = tail[1:-1]
        return tail.upper()[:4]

    def _rebuild_list(self) -> None:
        # Clear
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

        # --- LAUNCHER pseudo-row (always at top, treated as system)
        if show_system:
            self._add_group_header("SYSTEM", COLOR.violet)
            # Launcher pseudo-row
            launcher_chip = self._format_hotkey_chip(self._working_config.launcher_hotkey)
            launcher_row = LibraryRow(
                LAUNCHER_PSEUDO_ID, "▶", "Launcher (open popup)",
                launcher_chip, "❖",
            )
            launcher_row.rowClicked.connect(self._on_row_clicked)
            self._row_widgets[LAUNCHER_PSEUDO_ID] = launcher_row
            self._list_layout.addWidget(launcher_row)

            for item in self._items_by_type("system"):
                if not self._matches_filter(item, query):
                    continue
                self._add_item_row(item, "✨")

        if show_ai:
            self._add_group_header("AI ACTIONS", COLOR.violet, add_section="ai")
            for item in self._items_by_type("ai"):
                if not self._matches_filter(item, query):
                    continue
                self._add_item_row(item, "✨")

        if show_snip:
            self._add_group_header("SNIPPETS", COLOR.mint, add_section="snippet")
            for item in self._items_by_type("snippet"):
                if not self._matches_filter(item, query):
                    continue
                glyph = "\U0001F517" if (item.kind or "").lower() == "url" else "\U0001F4CB"
                self._add_item_row(item, glyph)

        self._list_layout.addStretch(1)

        # Refresh selected highlight
        if self._selected_id is not None and self._selected_id in self._row_widgets:
            self._row_widgets[self._selected_id].set_selected(True)

    def _add_group_header(self, title: str, dot_color: str, add_section: Optional[str] = None) -> None:
        row = QWidget()
        rl = QHBoxLayout(row)
        rl.setContentsMargins(8, 12, 8, 6)
        rl.setSpacing(6)

        dot = QLabel()
        dot.setFixedSize(5, 5)
        dot.setStyleSheet(f"background: {dot_color}; border-radius: 2.5px;")
        rl.addWidget(dot)

        lbl = QLabel(title)
        lbl.setProperty("class", "mgr-grp")
        rl.addWidget(lbl)

        rl.addStretch(1)

        if add_section is not None:
            add_btn = QPushButton("+")
            add_btn.setProperty("class", "mgr-add")
            add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            add_btn.setFixedSize(18, 18)
            add_btn.clicked.connect(lambda _checked=False, s=add_section: self._on_add_clicked(s))
            rl.addWidget(add_btn)

        self._list_layout.addWidget(row)

    def _add_item_row(self, item: Item, type_glyph: str) -> None:
        chip = self._format_hotkey_chip(item.hotkey)
        row = LibraryRow(item.id, item.emoji or "", item.name or "(unnamed)", chip, type_glyph)
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
        # Prefer launcher row so the user knows it's editable.
        self._select(LAUNCHER_PSEUDO_ID)

    def _select(self, item_id: str) -> None:
        # Clear highlight on previous
        if self._selected_id is not None and self._selected_id in self._row_widgets:
            self._row_widgets[self._selected_id].set_selected(False)
        self._selected_id = item_id
        if item_id in self._row_widgets:
            self._row_widgets[item_id].set_selected(True)

        # Pick the editor
        if item_id == LAUNCHER_PSEUDO_ID:
            self._launcher_editor.populate(self._working_config.launcher_hotkey)
            self._stack.setCurrentIndex(self.IDX_LAUNCHER)
            self._refresh_warning_banner(self._launcher_editor)
            return

        item = self._find_item(item_id)
        if item is None:
            self._stack.setCurrentIndex(self.IDX_EMPTY)
            return

        if item.type == "system":
            self._system_editor.populate(item)
            self._stack.setCurrentIndex(self.IDX_SYSTEM)
            self._refresh_warning_banner(self._system_editor)
        elif item.type == "ai":
            self._ai_editor.populate(item)
            self._stack.setCurrentIndex(self.IDX_AI)
            self._refresh_warning_banner(self._ai_editor)
        else:
            self._snippet_editor.populate(item)
            self._stack.setCurrentIndex(self.IDX_SNIPPET)
            self._refresh_warning_banner(self._snippet_editor)

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
        emoji, ok = QInputDialog.getText(
            self, "New item", "Emoji (one character):",
            QLineEdit.EchoMode.Normal,
            "✨" if section == "ai" else "\U0001F4CB",
        )
        if not ok:
            return
        emoji = (emoji or "").strip() or ("✨" if section == "ai" else "\U0001F4CB")
        name, ok = QInputDialog.getText(
            self, "New item", "Name:", QLineEdit.EchoMode.Normal,
            "Untitled action" if section == "ai" else "Untitled snippet",
        )
        if not ok:
            return
        name = (name or "").strip() or ("Untitled action" if section == "ai" else "Untitled snippet")

        max_order = max(
            (it.order for it in self._working_config.items),
            default=-1,
        )
        if section == "ai":
            new_item = Item(
                id=new_item_id("ai"),
                type="ai",
                name=name,
                emoji=emoji,
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
                emoji=emoji,
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
        self._working_config.items = [it for it in self._working_config.items if it.id != item_id]
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
        max_order = max((it.order for it in self._working_config.items), default=-1)
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
        if item_id in self._row_widgets:
            # Cheap: rebuild the row text by full list rebuild.
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
        # Re-select to refresh the row chip highlight.
        if self._selected_id is not None and self._selected_id in self._row_widgets:
            self._row_widgets[self._selected_id].set_selected(True)
        # Immediate conflict surface
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

    def _on_body_changed(self, item_id: str, body: str) -> None:
        item = self._find_item(item_id)
        if item is None or item.type != "snippet":
            return
        item.body = body
        self._refresh_dirty_indicator()

    def _on_kind_changed(self, item_id: str, kind: str) -> None:
        item = self._find_item(item_id)
        if item is None or item.type != "snippet":
            return
        item.kind = kind
        # Re-populate so segmented control + body widget match.
        self._snippet_editor.populate(item)
        self._rebuild_list()
        self._refresh_dirty_indicator()

    def _on_behavior_changed(self, item_id: str, behavior: str) -> None:
        item = self._find_item(item_id)
        if item is None or item.type != "snippet":
            return
        item.behavior = behavior
        self._refresh_dirty_indicator()

    # ------------------------------------------------------------------
    # Save / validation
    # ------------------------------------------------------------------

    def _hotkey_index(self) -> dict[str, list[str]]:
        """Returns hotkey -> list of owner labels (id or pseudo)."""
        index: dict[str, list[str]] = {}
        if self._working_config.launcher_hotkey:
            index.setdefault(self._working_config.launcher_hotkey, []).append(LAUNCHER_PSEUDO_ID)
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
        # Find any conflict involving the focused owner first.
        focus_hotkey = None
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

        # Otherwise, surface any conflict in the config (rare on this editor).
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
        if not chord:
            return "—"
        parts = []
        for raw in chord.split("+"):
            tok = raw.strip()
            if not tok:
                continue
            if tok.startswith("<") and tok.endswith(">"):
                parts.append(tok[1:-1].capitalize())
            else:
                parts.append(tok.upper())
        return "+".join(parts)

    def _current_editor(self) -> Optional[_EditorBase]:
        idx = self._stack.currentIndex()
        if idx == self.IDX_LAUNCHER:
            return self._launcher_editor
        if idx == self.IDX_SYSTEM:
            return self._system_editor
        if idx == self.IDX_AI:
            return self._ai_editor
        if idx == self.IDX_SNIPPET:
            return self._snippet_editor
        return None

    def _refresh_warning_banner(self, editor: _EditorBase) -> None:
        owner = editor.current_id() or self._selected_id or ""
        if not owner:
            editor.set_warning("")
            return
        msg = self._detect_conflict(owner)
        editor.set_warning(msg or "")

    def _on_save_clicked(self) -> None:
        # Hard gate: no duplicate hotkeys.
        index = self._hotkey_index()
        conflicts = [(chord, owners) for chord, owners in index.items() if len(owners) > 1]
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
            # Compare every field on the dataclass.
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
        # Don't actually destroy; just hide.
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
