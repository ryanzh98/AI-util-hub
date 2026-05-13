"""Frameless launcher popup window.

Triggered by the global launcher hotkey (Ctrl+Alt+0 by default). Shows all
configured actions in a single-glance, three-section grid (System, AI Actions,
Snippets). Users either click a tile, press Enter on the focused one, or use
Ctrl+1..9 as quick keys.

Public surface:
    LauncherWindow(config)
    LauncherWindow.set_config(config)
    LauncherWindow.present()
    LauncherWindow.set_running(item_id | None)
    LauncherWindow.show_toast(kind, title, desc, duration_ms)

    Signals: fireRequested(str), manageRequested(), closeRequested()
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PyQt6.QtCore import (
    QEvent,
    QPoint,
    Qt,
    QTimer,
    pyqtSignal,
)
from PyQt6.QtGui import QCursor, QGuiApplication, QKeyEvent
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from design import COLOR, FONT, RADIUS

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .actions_config import Config, Item


CARD_WIDTH = 640
OUTER_PADDING = 0
GRID_COLUMNS = 4
TILE_SPACING = 6
MIN_BODY_HEIGHT = 220
MAX_BODY_HEIGHT = 520


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tile_class_for(item: "Item") -> str:
    """Map an Item to one of the QSS tile variant strings."""
    if item.type == "snippet":
        if (item.kind or "").lower() == "url":
            return "tile url"
        return "tile snip"
    # system and ai both use the violet (ai) accent
    return "tile ai"


def _type_glyph_for(klass: str) -> str:
    if "ai" in klass.split():
        return "✨"  # sparkles
    if "url" in klass.split():
        return "\U0001F517"  # link
    return "\U0001F4CB"  # clipboard


def _repolish(w: QWidget) -> None:
    """Re-evaluate stylesheet rules after changing a dynamic property."""
    style = w.style()
    style.unpolish(w)
    style.polish(w)
    w.update()


# ---------------------------------------------------------------------------
# Tile
# ---------------------------------------------------------------------------

class Tile(QPushButton):
    """A single action tile inside the launcher grid."""

    tileClicked = pyqtSignal(str)  # emits item.id

    def __init__(self, item: "Item", position: int, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._item_id = item.id
        self._position = position  # 1-indexed across all visible tiles

        self.setObjectName("tile")
        self.setProperty("class", _tile_class_for(item))
        self.setProperty("focused", False)
        self.setProperty("running", False)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(78)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # keyboard nav driven by parent

        layout = QVBoxLayout(self)
        layout.setContentsMargins(11, 10, 11, 10)
        layout.setSpacing(0)

        # Row 0: position chip (top-right)
        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(0)
        top_row.addStretch(1)
        self._kbd_label = QLabel(str(position) if position <= 9 else "")
        self._kbd_label.setProperty("class", "tile-kbd")
        self._kbd_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._kbd_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        if position > 9:
            self._kbd_label.setVisible(False)
        top_row.addWidget(self._kbd_label)
        layout.addLayout(top_row)

        layout.addStretch(1)

        # Bottom rows: emoji + name + type glyph
        bottom_row = QHBoxLayout()
        bottom_row.setContentsMargins(0, 0, 0, 0)
        bottom_row.setSpacing(8)

        name_block = QVBoxLayout()
        name_block.setContentsMargins(0, 0, 0, 0)
        name_block.setSpacing(2)

        emoji_label = QLabel(item.emoji or "")
        emoji_label.setProperty("class", "tile-emoji")
        emoji_label.setStyleSheet(f"font-size: {FONT.size_xl + 1}px;")
        emoji_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        name_block.addWidget(emoji_label)

        name_label = QLabel(item.name or "")
        name_label.setProperty("class", "tile-name")
        name_label.setStyleSheet(
            f"font-size: {FONT.size_xs + 1}px; color: {COLOR.text_1};"
        )
        name_label.setWordWrap(False)
        name_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        # Elide manually since QLabel doesn't elide by default in a button.
        name_label.setMinimumWidth(0)
        name_block.addWidget(name_label)

        bottom_row.addLayout(name_block, 1)

        # Type indicator glyph in the corner
        type_label = QLabel(_type_glyph_for(self.property("class") or ""))
        type_label.setProperty("class", "tile-type")
        type_label.setStyleSheet(f"font-size: 11px; color: {COLOR.text_3};")
        type_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom)
        type_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        bottom_row.addWidget(type_label, 0, Qt.AlignmentFlag.AlignBottom)

        layout.addLayout(bottom_row)

        self.clicked.connect(self._on_clicked)

    @property
    def item_id(self) -> str:
        return self._item_id

    @property
    def position(self) -> int:
        return self._position

    def set_focused(self, focused: bool) -> None:
        self.setProperty("focused", "true" if focused else "false")
        _repolish(self)

    def set_running(self, running: bool) -> None:
        self.setProperty("running", "true" if running else "false")
        _repolish(self)

    def _on_clicked(self) -> None:
        self.tileClicked.emit(self._item_id)


# ---------------------------------------------------------------------------
# Toast
# ---------------------------------------------------------------------------

class Toast(QFrame):
    """Auto-dismissing notification rendered at the bottom-right of the card."""

    _ICONS = {
        "ok": "✓",
        "run": "◌",
        "warn": "⚠",
        "err": "✕",
    }

    def __init__(self, kind: str, title: str, desc: str, parent: QWidget):
        super().__init__(parent)
        kind = kind if kind in self._ICONS else "ok"
        self.setProperty("class", f"toast {kind}")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFrameShape(QFrame.Shape.NoFrame)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 12, 10)
        layout.setSpacing(10)

        ic = QLabel(self._ICONS[kind])
        ic.setProperty("class", "toast-ic")
        ic.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ic.setFixedSize(22, 22)
        layout.addWidget(ic, 0, Qt.AlignmentFlag.AlignTop)

        body = QVBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(2)

        title_lbl = QLabel(title)
        title_lbl.setProperty("class", "toast-title")
        body.addWidget(title_lbl)

        desc_lbl = QLabel(desc)
        desc_lbl.setProperty("class", "toast-desc")
        desc_lbl.setWordWrap(True)
        body.addWidget(desc_lbl)

        layout.addLayout(body, 1)
        self.adjustSize()


# ---------------------------------------------------------------------------
# Launcher window
# ---------------------------------------------------------------------------

class LauncherWindow(QWidget):
    fireRequested = pyqtSignal(str)
    manageRequested = pyqtSignal()
    closeRequested = pyqtSignal()

    def __init__(self, config: "Config", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)

        self._config: "Config" = config
        self._visible: list["Item"] = []
        self._tiles: list[Tile] = []
        self._focus_idx = 0
        self._running_id: Optional[str] = None
        self._drag_pos: Optional[QPoint] = None
        self._toast: Optional[Toast] = None
        self._toast_timer = QTimer(self)
        self._toast_timer.setSingleShot(True)
        self._toast_timer.timeout.connect(self._dismiss_toast)

        self._build_chrome()
        self._populate()

    # ── chrome construction ───────────────────────────────────

    def _build_chrome(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(OUTER_PADDING, OUTER_PADDING, OUTER_PADDING, OUTER_PADDING)
        outer.setSpacing(0)

        self._card = QFrame(self)
        self._card.setObjectName("popupCard")
        self._card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._card.setMinimumWidth(CARD_WIDTH)
        outer.addWidget(self._card)

        card_layout = QVBoxLayout(self._card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        self._header = self._build_header()
        card_layout.addWidget(self._header)

        self._scroll = QScrollArea(self._card)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._scroll.setStyleSheet("QScrollArea { background: transparent; border: 0; }")

        self._body = QWidget()
        self._body.setObjectName("popupBody")
        self._body_layout = QVBoxLayout(self._body)
        self._body_layout.setContentsMargins(14, 12, 14, 10)
        self._body_layout.setSpacing(12)
        self._scroll.setWidget(self._body)
        self._scroll.setMinimumHeight(MIN_BODY_HEIGHT)
        self._scroll.setMaximumHeight(MAX_BODY_HEIGHT)

        card_layout.addWidget(self._scroll, 1)

        self._footer = self._build_footer()
        card_layout.addWidget(self._footer)

        # Toast layer is a child of the card so positioning is straightforward.
        self._toast_holder = QWidget(self._card)
        self._toast_holder.setObjectName("toastStack")
        self._toast_holder.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._toast_holder.hide()

        # Drag the header to move the window.
        self._header.installEventFilter(self)

    def _build_header(self) -> QWidget:
        header = QWidget(self._card)
        header.setObjectName("popupHeader")
        header.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        header.setCursor(Qt.CursorShape.SizeAllCursor)

        row = QHBoxLayout(header)
        row.setContentsMargins(14, 10, 12, 10)
        row.setSpacing(10)

        # Brand block: violet square + "Shortcut" label.
        brand_mark = QLabel("✓")
        brand_mark.setProperty("class", "brand-mark")
        brand_mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand_mark.setFixedSize(22, 22)
        row.addWidget(brand_mark)

        brand_lbl = QLabel("Shortcut")
        brand_lbl.setProperty("class", "brand")
        row.addWidget(brand_lbl)

        # Search field
        search_wrap = QFrame(header)
        search_wrap.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        search_wrap.setStyleSheet("background: transparent; border: 0;")
        search_lyt = QHBoxLayout(search_wrap)
        search_lyt.setContentsMargins(0, 0, 0, 0)
        search_lyt.setSpacing(0)

        self._search = QLineEdit(search_wrap)
        self._search.setProperty("class", "search")
        self._search.setPlaceholderText("Search actions and snippets…")
        self._search.setClearButtonEnabled(False)
        self._search.textChanged.connect(self._on_search_changed)
        self._search.installEventFilter(self)
        search_lyt.addWidget(self._search, 1)

        row.addWidget(search_wrap, 1)

        # Hotkey hint chips
        hint_row = QHBoxLayout()
        hint_row.setContentsMargins(0, 0, 0, 0)
        hint_row.setSpacing(3)
        for key in ("Ctrl", "Alt", "0"):
            chip = QLabel(key)
            chip.setProperty("class", "kbd")
            chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
            hint_row.addWidget(chip)
        row.addLayout(hint_row)

        # Manage button (gear)
        manage_btn = QPushButton("⚙")
        manage_btn.setProperty("class", "icon-btn")
        manage_btn.setToolTip("Manage")
        manage_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        manage_btn.setFixedSize(28, 28)
        manage_btn.clicked.connect(self.manageRequested.emit)
        row.addWidget(manage_btn)

        # Close button
        close_btn = QPushButton("✕")
        close_btn.setProperty("class", "icon-btn")
        close_btn.setToolTip("Close (Esc)")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setFixedSize(28, 28)
        close_btn.clicked.connect(self._on_close_clicked)
        row.addWidget(close_btn)

        return header

    def _build_footer(self) -> QWidget:
        footer = QWidget(self._card)
        footer.setObjectName("popupFooter")
        footer.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        row = QHBoxLayout(footer)
        row.setContentsMargins(14, 8, 12, 8)
        row.setSpacing(14)

        def hint(text_pairs: list[tuple[str, str]]) -> QWidget:
            wrap = QWidget(footer)
            lyt = QHBoxLayout(wrap)
            lyt.setContentsMargins(0, 0, 0, 0)
            lyt.setSpacing(5)
            for kind, value in text_pairs:
                lbl = QLabel(value)
                if kind == "kbd":
                    lbl.setProperty("class", "kbd")
                    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                else:
                    lbl.setProperty("class", "pop-ft-hint")
                lyt.addWidget(lbl)
            return wrap

        row.addWidget(hint([("kbd", "↵"), ("txt", "Run")]))
        row.addWidget(hint([("kbd", "Ctrl"), ("kbd", "1–9"), ("txt", "Quick")]))
        row.addWidget(hint([("kbd", "↑↓←→"), ("txt", "Navigate")]))
        row.addStretch(1)

        self._manage_link = QPushButton("⚙  Manage")
        self._manage_link.setProperty("class", "manage")
        self._manage_link.setCursor(Qt.CursorShape.PointingHandCursor)
        self._manage_link.clicked.connect(self.manageRequested.emit)
        row.addWidget(self._manage_link)

        return footer

    # ── data / population ─────────────────────────────────────

    def set_config(self, config: "Config") -> None:
        self._config = config
        self._populate()

    def _items_of(self, type_: str) -> list["Item"]:
        items = [it for it in self._config.items if it.type == type_ and it.enabled]
        items.sort(key=lambda it: (it.order, it.name.lower()))
        return items

    def _matches(self, item: "Item", query: str) -> bool:
        if not query:
            return True
        haystack_parts = [item.name or ""]
        if item.type == "ai" and item.prompt:
            haystack_parts.append(item.prompt)
        if item.type == "snippet" and item.body:
            haystack_parts.append(item.body)
        return any(query in (p or "").lower() for p in haystack_parts)

    def _populate(self) -> None:
        # Clear existing body.
        while self._body_layout.count():
            child = self._body_layout.takeAt(0)
            w = child.widget()
            if w is not None:
                w.deleteLater()
            else:
                lyt = child.layout()
                if lyt is not None:
                    self._discard_layout(lyt)
        self._tiles = []
        self._visible = []

        query = (self._search.text() if hasattr(self, "_search") else "").strip().lower()

        system_items = [it for it in self._items_of("system") if self._matches(it, query)]
        ai_items = [it for it in self._items_of("ai") if self._matches(it, query)]
        snippet_items = [it for it in self._items_of("snippet") if self._matches(it, query)]

        self._visible = system_items + ai_items + snippet_items

        # Render sections — System is always shown (system items are seeded).
        position = 1
        position = self._add_section("SYSTEM", "ai-dot", system_items, position, hide_when_empty=False)
        position = self._add_section("AI ACTIONS", "ai-dot", ai_items, position, hide_when_empty=bool(query))
        position = self._add_section("SNIPPETS", "sn-dot", snippet_items, position, hide_when_empty=bool(query))

        if not self._visible:
            label = QLabel("No matches" if query else "No actions available")
            label.setStyleSheet(
                f"color: {COLOR.text_3}; font-size: {FONT.size_sm}px; padding: 24px 4px;"
            )
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._body_layout.addWidget(label)

        self._body_layout.addStretch(1)

        # Reset focus
        self._focus_idx = 0
        self._refresh_focus()

        # Restore running state if the running id is still visible.
        if self._running_id is not None:
            self._apply_running_state()

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

    def _add_section(
        self,
        title: str,
        dot_class: str,
        items: list["Item"],
        start_position: int,
        hide_when_empty: bool,
    ) -> int:
        if not items and hide_when_empty:
            return start_position

        # Section header
        header_row = QHBoxLayout()
        header_row.setContentsMargins(2, 0, 2, 6)
        header_row.setSpacing(8)

        dot = QLabel()
        dot.setProperty("class", dot_class)
        dot.setFixedSize(6, 6)
        header_row.addWidget(dot, 0, Qt.AlignmentFlag.AlignVCenter)

        lbl = QLabel(title)
        lbl.setProperty("class", "section-hd-lbl")
        header_row.addWidget(lbl)

        header_row.addStretch(1)

        count = QLabel(str(len(items)))
        count.setProperty("class", "section-hd-count")
        header_row.addWidget(count)

        section_wrap = QWidget(self._body)
        section_wrap_layout = QVBoxLayout(section_wrap)
        section_wrap_layout.setContentsMargins(0, 0, 0, 0)
        section_wrap_layout.setSpacing(0)
        section_wrap_layout.addLayout(header_row)

        if items:
            grid_wrap = QWidget(section_wrap)
            grid = QGridLayout(grid_wrap)
            grid.setContentsMargins(0, 0, 0, 0)
            grid.setSpacing(TILE_SPACING)
            for col in range(GRID_COLUMNS):
                grid.setColumnStretch(col, 1)

            for idx, item in enumerate(items):
                position = start_position + idx
                tile = Tile(item, position, grid_wrap)
                tile.tileClicked.connect(self._on_tile_clicked)
                row = idx // GRID_COLUMNS
                col = idx % GRID_COLUMNS
                grid.addWidget(tile, row, col)
                self._tiles.append(tile)

            section_wrap_layout.addWidget(grid_wrap)
        else:
            empty_lbl = QLabel("Nothing here yet — click Manage to add")
            empty_lbl.setStyleSheet(
                f"color: {COLOR.text_3}; font-size: {FONT.size_sm}px; padding: 10px 4px;"
            )
            section_wrap_layout.addWidget(empty_lbl)

        self._body_layout.addWidget(section_wrap)
        return start_position + len(items)

    # ── presentation ──────────────────────────────────────────

    def present(self) -> None:
        # Size before positioning.
        self.adjustSize()
        width = self._card.sizeHint().width() + OUTER_PADDING * 2
        # Body sizing is dynamic; cap below MAX_BODY_HEIGHT.
        height = self.sizeHint().height()
        self.resize(max(width, CARD_WIDTH + OUTER_PADDING * 2), height)

        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        if screen is not None:
            geom = screen.availableGeometry()
            x = geom.x() + (geom.width() - self.width()) // 2
            y = geom.y() + max(int(geom.height() * 0.22), 40)
            self.move(x, y)

        self.show()
        self.raise_()
        self.activateWindow()
        self._search.clear()
        self._search.setFocus(Qt.FocusReason.OtherFocusReason)

    def set_running(self, item_id: Optional[str]) -> None:
        self._running_id = item_id
        self._apply_running_state()

    def _apply_running_state(self) -> None:
        for tile in self._tiles:
            tile.set_running(tile.item_id == self._running_id)

    def show_toast(self, kind: str, title: str, desc: str, duration_ms: int = 4000) -> None:
        self._dismiss_toast()

        toast = Toast(kind, title, desc, self._card)
        toast.show()
        toast.adjustSize()

        self._toast = toast
        self._position_toast()

        if duration_ms > 0:
            self._toast_timer.start(duration_ms)

    def _dismiss_toast(self) -> None:
        self._toast_timer.stop()
        if self._toast is not None:
            self._toast.hide()
            self._toast.deleteLater()
            self._toast = None

    def _position_toast(self) -> None:
        if self._toast is None:
            return
        margin = 16
        card_w = self._card.width()
        card_h = self._card.height()
        tw = self._toast.width()
        th = self._toast.height()
        x = max(margin, card_w - tw - margin)
        y = max(margin, card_h - th - margin - self._footer.height())
        self._toast.move(x, y)

    # ── events ────────────────────────────────────────────────

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_toast()

    def closeEvent(self, event):
        self._dismiss_toast()
        super().closeEvent(event)

    def hideEvent(self, event):
        self._dismiss_toast()
        self._running_id = None
        super().hideEvent(event)

    def _on_search_changed(self, _text: str) -> None:
        self._populate()

    def _on_close_clicked(self) -> None:
        self.closeRequested.emit()
        self.hide()

    def _on_tile_clicked(self, item_id: str) -> None:
        self.fireRequested.emit(item_id)

    # Keyboard navigation handled by intercepting events both globally
    # (keyPressEvent) and on the search field (eventFilter).
    def keyPressEvent(self, event: QKeyEvent):
        if self._handle_navigation(event):
            event.accept()
            return
        super().keyPressEvent(event)

    def eventFilter(self, obj, event):
        et = event.type()
        if obj is self._header:
            if et == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                return True
            if et == QEvent.Type.MouseMove and event.buttons() & Qt.MouseButton.LeftButton:
                if self._drag_pos is not None:
                    self.move(event.globalPosition().toPoint() - self._drag_pos)
                    return True
            if et == QEvent.Type.MouseButtonRelease:
                self._drag_pos = None

        if obj is self._search and et == QEvent.Type.KeyPress:
            if self._handle_navigation(event):
                return True

        return super().eventFilter(obj, event)

    def _handle_navigation(self, event: QKeyEvent) -> bool:
        key = event.key()
        mods = event.modifiers()

        if key == Qt.Key.Key_Escape:
            self.closeRequested.emit()
            self.hide()
            return True

        # Ctrl+1..9 quick keys.
        if mods & Qt.KeyboardModifier.ControlModifier and Qt.Key.Key_1 <= key <= Qt.Key.Key_9:
            idx = key - Qt.Key.Key_1
            if 0 <= idx < len(self._visible):
                self._fire(self._visible[idx])
                return True
            return True

        if not self._visible:
            return False

        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            target = self._visible[self._focus_idx] if 0 <= self._focus_idx < len(self._visible) else None
            if target is not None:
                self._fire(target)
            return True

        if key == Qt.Key.Key_Right:
            self._move_focus(1)
            return True
        if key == Qt.Key.Key_Left:
            self._move_focus(-1)
            return True
        if key == Qt.Key.Key_Down:
            self._move_focus(GRID_COLUMNS)
            return True
        if key == Qt.Key.Key_Up:
            self._move_focus(-GRID_COLUMNS)
            return True

        return False

    def _move_focus(self, delta: int) -> None:
        if not self._visible:
            return
        new_idx = self._focus_idx + delta
        new_idx = max(0, min(len(self._visible) - 1, new_idx))
        if new_idx == self._focus_idx:
            return
        self._focus_idx = new_idx
        self._refresh_focus()

    def _refresh_focus(self) -> None:
        for i, tile in enumerate(self._tiles):
            tile.set_focused(i == self._focus_idx)

    def _fire(self, item: "Item") -> None:
        self.fireRequested.emit(item.id)
