"""Frameless launcher popup window — "AI Util Hub".

Triggered by the global launcher hotkey (Ctrl+Alt+0 by default). Shows all
configured actions in a single-glance window with three collapsible sections
(System, AI Actions, Snippets). Users either click a tile, press Enter on the
focused one, or use Ctrl+1..9 as quick keys.

Public surface (preserved — tray_controller depends on these):
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

from design import COLOR, FONT
from design.icons import icon, icon_size

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .actions_config import Config, Item


CARD_WIDTH = 820
OUTER_PADDING = 0
GRID_COLUMNS = 4
TILE_SPACING = 8
MIN_BODY_HEIGHT = 220
MAX_BODY_HEIGHT = 600


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Map Item.subtype → registered icon name (see design/icons.py).
_SUBTYPE_ICON = {
    "voice_online":     "mic_solid",
    "voice_offline":    "mic_outline",
    "grammar":          "spark",
    "youtube":          "youtube",
    "voice_respeaker":  "head_voice",
    "voice_tts":        "type_voice",
}


def _icon_for(item: "Item") -> str:
    """Return the icon name to use for a given Item."""
    if item.subtype and item.subtype in _SUBTYPE_ICON:
        return _SUBTYPE_ICON[item.subtype]
    if item.type == "ai":
        return "id_card"
    if item.type == "snippet":
        return "clipboard"
    return "spark"


def _humanize_hotkey(hk: str) -> list[str]:
    """`'<ctrl>+<alt>+1'` → `['Ctrl', 'Alt', '1']`."""
    if not hk:
        return []
    parts = [p.strip().strip("<>") for p in hk.split("+")]
    out: list[str] = []
    for p in parts:
        if not p:
            continue
        low = p.lower()
        if low in ("ctrl", "alt", "shift", "win", "meta", "cmd"):
            out.append(p[:1].upper() + p[1:].lower())
        elif len(p) == 1:
            out.append(p.upper())
        else:
            out.append(p.title())
    return out


def _repolish(w: QWidget) -> None:
    """Re-evaluate stylesheet rules after changing a dynamic property."""
    style = w.style()
    style.unpolish(w)
    style.polish(w)
    w.update()


def _make_kbd(text: str, *, small: bool = True, parent: Optional[QWidget] = None) -> QLabel:
    """Create a `.kbd` (and optionally `.kbd.sm`) chip label."""
    lbl = QLabel(text, parent)
    cls = "kbd sm" if small else "kbd"
    lbl.setProperty("class", cls)
    lbl.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return lbl


def _make_icon_label(svg_name: str, color: str, size: int, parent: Optional[QWidget] = None) -> QLabel:
    """Create a QLabel that renders the named SVG icon as a tinted pixmap."""
    lbl = QLabel(parent)
    lbl.setPixmap(icon(svg_name, color, size).pixmap(icon_size(size)))
    lbl.setFixedSize(size, size)
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
    return lbl


# ---------------------------------------------------------------------------
# Tile (grid view)
# ---------------------------------------------------------------------------

class Tile(QPushButton):
    """A single action tile inside the launcher grid."""

    tileClicked = pyqtSignal(str)  # emits item.id

    def __init__(self, item: "Item", position: int, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._item_id = item.id
        self._position = position  # 1-indexed across all visible tiles

        self.setProperty("class", "tile")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setProperty("focused", "false")
        self.setProperty("running", "false")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(114)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # keyboard nav driven by parent

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        # Top row: position chip pinned to the right.
        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(0)
        top_row.addStretch(1)
        if position <= 9:
            num_chip = QLabel(str(position))
            num_chip.setProperty("class", "tile-num")
            num_chip.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            num_chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
            num_chip.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            top_row.addWidget(num_chip)
        layout.addLayout(top_row)

        # Center column: icon + name.
        icon_lbl = _make_icon_label(_icon_for(item), COLOR.violet, 22, self)
        layout.addWidget(icon_lbl, 0, Qt.AlignmentFlag.AlignHCenter)

        name_lbl = QLabel(item.name or "")
        name_lbl.setProperty("class", "tile-name")
        name_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        name_lbl.setWordWrap(False)
        name_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        name_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        # Allow Qt to elide if needed.
        name_lbl.setTextFormat(Qt.TextFormat.PlainText)
        name_lbl.setMaximumWidth(16777215)
        layout.addWidget(name_lbl, 0, Qt.AlignmentFlag.AlignHCenter)

        layout.addStretch(1)

        # Bottom row: hotkey chord chips.
        chord = QFrame(self)
        chord.setProperty("class", "tile-chord")
        chord.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        chord_lyt = QHBoxLayout(chord)
        chord_lyt.setContentsMargins(0, 0, 0, 0)
        chord_lyt.setSpacing(3)
        keys = _humanize_hotkey(item.hotkey or "")
        if keys:
            for k in keys:
                kbd = _make_kbd(k, small=True, parent=chord)
                kbd.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
                chord_lyt.addWidget(kbd, 1)
        else:
            # placeholder spacer keeps the bottom of the tile aligned even
            # when no hotkey is bound
            chord_lyt.addStretch(1)
        layout.addWidget(chord)

        self.clicked.connect(self._on_clicked)

    @property
    def item_id(self) -> str:
        return self._item_id

    @property
    def position(self) -> int:
        return self._position

    def set_focused(self, focused: bool) -> None:
        self.setProperty("focused", "true" if focused else "false")
        # Toggle the modern `is-focused` class too so the new selectors fire.
        cls = self.property("class") or "tile"
        parts = [p for p in str(cls).split() if p != "is-focused"]
        if focused:
            parts.append("is-focused")
        self.setProperty("class", " ".join(parts))
        _repolish(self)

    def set_running(self, running: bool) -> None:
        self.setProperty("running", "true" if running else "false")
        _repolish(self)

    def _on_clicked(self) -> None:
        self.tileClicked.emit(self._item_id)


# ---------------------------------------------------------------------------
# Row (list view)
# ---------------------------------------------------------------------------

class Row(QPushButton):
    """A single action row inside the launcher list view."""

    rowClicked = pyqtSignal(str)  # emits item.id

    def __init__(self, item: "Item", position: int, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._item_id = item.id
        self._position = position

        self.setProperty("class", "row")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setProperty("focused", "false")
        self.setProperty("running", "false")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(38)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        lyt = QHBoxLayout(self)
        lyt.setContentsMargins(12, 6, 12, 6)
        lyt.setSpacing(12)

        icon_lbl = _make_icon_label(_icon_for(item), COLOR.violet, 18, self)
        icon_lbl.setProperty("class", "row-icon")
        lyt.addWidget(icon_lbl, 0, Qt.AlignmentFlag.AlignVCenter)

        divider = QFrame(self)
        divider.setProperty("class", "row-divider")
        divider.setFrameShape(QFrame.Shape.VLine)
        divider.setFixedWidth(1)
        divider.setFixedHeight(16)
        lyt.addWidget(divider, 0, Qt.AlignmentFlag.AlignVCenter)

        name_lbl = QLabel(item.name or "")
        name_lbl.setProperty("class", "row-name")
        name_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        name_lbl.setWordWrap(False)
        lyt.addWidget(name_lbl, 1)

        chord = QFrame(self)
        chord.setProperty("class", "row-chord")
        chord.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        chord_lyt = QHBoxLayout(chord)
        chord_lyt.setContentsMargins(0, 0, 0, 0)
        chord_lyt.setSpacing(3)
        for k in _humanize_hotkey(item.hotkey or ""):
            kbd = _make_kbd(k, small=True, parent=chord)
            kbd.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            chord_lyt.addWidget(kbd)
        lyt.addWidget(chord, 0, Qt.AlignmentFlag.AlignVCenter)

        self.clicked.connect(self._on_clicked)

    @property
    def item_id(self) -> str:
        return self._item_id

    @property
    def position(self) -> int:
        return self._position

    def set_focused(self, focused: bool) -> None:
        self.setProperty("focused", "true" if focused else "false")
        cls = self.property("class") or "row"
        parts = [p for p in str(cls).split() if p != "is-focused"]
        if focused:
            parts.append("is-focused")
        self.setProperty("class", " ".join(parts))
        _repolish(self)

    def set_running(self, running: bool) -> None:
        self.setProperty("running", "true" if running else "false")
        _repolish(self)

    def _on_clicked(self) -> None:
        self.rowClicked.emit(self._item_id)


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

    BRAND_TITLE = "AI Util Hub"

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
        self._cells: list[QWidget] = []  # list of Tile or Row, in visible order
        self._focus_idx = 0
        self._running_id: Optional[str] = None
        self._drag_pos: Optional[QPoint] = None
        self._toast: Optional[Toast] = None
        self._toast_timer = QTimer(self)
        self._toast_timer.setSingleShot(True)
        self._toast_timer.timeout.connect(self._dismiss_toast)

        # View state — memory-only this round.
        self._view: str = "grid"  # "grid" | "list"

        # Per-section open/closed state (memory-only).
        self._section_open: dict[str, bool] = {
            "system": True,
            "ai": True,
            "snippet": True,
        }

        self._build_chrome()
        self._populate()

    # ── chrome construction ───────────────────────────────────

    def _build_chrome(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(OUTER_PADDING, OUTER_PADDING, OUTER_PADDING, OUTER_PADDING)
        outer.setSpacing(0)

        self._card = QFrame(self)
        self._card.setObjectName("popupCard")
        # Apply the new `.win` class so the modern QSS selectors target this card.
        self._card.setProperty("class", "win")
        self._card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._card.setMinimumWidth(CARD_WIDTH)
        outer.addWidget(self._card)

        card_layout = QVBoxLayout(self._card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        # Row 1 — header (brand + chrome buttons), drag region.
        self._header = self._build_header()
        card_layout.addWidget(self._header)

        # Row 2 — search + view toggle.
        self._search_row = self._build_search_row()
        card_layout.addWidget(self._search_row)

        # Body (scrollable sections).
        self._scroll = QScrollArea(self._card)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._scroll.setStyleSheet("QScrollArea { background: transparent; border: 0; }")

        self._body = QWidget()
        self._body.setObjectName("popupBody")
        self._body.setProperty("class", "win-body")
        self._body.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._body_layout = QVBoxLayout(self._body)
        self._body_layout.setContentsMargins(16, 4, 16, 14)
        self._body_layout.setSpacing(0)  # sections own their own top margin
        self._scroll.setWidget(self._body)
        self._scroll.setMinimumHeight(MIN_BODY_HEIGHT)
        self._scroll.setMaximumHeight(MAX_BODY_HEIGHT)

        card_layout.addWidget(self._scroll, 1)

        # Footer.
        self._footer = self._build_footer()
        card_layout.addWidget(self._footer)

        # Toast holder.
        self._toast_holder = QWidget(self._card)
        self._toast_holder.setObjectName("toastStack")
        self._toast_holder.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._toast_holder.hide()

        # Header is the drag handle.
        self._header.installEventFilter(self)

    # ── Row 1: brand + chrome buttons ─────────────────────────

    def _build_header(self) -> QWidget:
        header = QFrame(self._card)
        header.setObjectName("popupHeader")
        header.setProperty("class", "win-hd")
        header.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        header.setCursor(Qt.CursorShape.SizeAllCursor)

        row = QHBoxLayout(header)
        row.setContentsMargins(16, 14, 12, 10)
        row.setSpacing(10)

        # Brand mark — gradient circle containing the mic-solid glyph.
        brand_mark = QFrame(header)
        brand_mark.setProperty("class", "brand-mark")
        brand_mark.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        brand_mark.setFixedSize(26, 26)
        bm_lyt = QHBoxLayout(brand_mark)
        bm_lyt.setContentsMargins(0, 0, 0, 0)
        bm_lyt.setSpacing(0)
        glyph = QLabel(brand_mark)
        glyph.setPixmap(icon("mic_solid", "#FFFFFF", 13).pixmap(icon_size(13)))
        glyph.setAlignment(Qt.AlignmentFlag.AlignCenter)
        glyph.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        bm_lyt.addWidget(glyph, 0, Qt.AlignmentFlag.AlignCenter)
        row.addWidget(brand_mark, 0, Qt.AlignmentFlag.AlignVCenter)

        brand_lbl = QLabel(self.BRAND_TITLE, header)
        brand_lbl.setProperty("class", "brand-title")
        row.addWidget(brand_lbl, 0, Qt.AlignmentFlag.AlignVCenter)

        row.addStretch(1)

        # Chrome buttons. Use icon QIcons (already tinted by SVG_*).
        def _icon_btn(svg_name: str, tooltip: str, *, close: bool = False) -> QPushButton:
            btn = QPushButton(header)
            cls = "icon-btn close" if close else "icon-btn"
            btn.setProperty("class", cls)
            btn.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            btn.setIcon(icon(svg_name, COLOR.text_2, 14))
            btn.setIconSize(icon_size(14))
            btn.setFixedSize(28, 28)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(tooltip)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            return btn

        gear_btn = _icon_btn("gear", "Settings")
        gear_btn.clicked.connect(self.manageRequested.emit)
        row.addWidget(gear_btn)

        pin_btn = _icon_btn("pin", "Pin")
        # No-op stub for now; tooltip only.
        row.addWidget(pin_btn)

        win_btn = _icon_btn("window", "Open as window")
        # No-op stub for now; tooltip only.
        row.addWidget(win_btn)

        close_btn = _icon_btn("close", "Close (Esc)", close=True)
        close_btn.clicked.connect(self._on_close_clicked)
        row.addWidget(close_btn)

        return header

    # ── Row 2: search + view toggle ───────────────────────────

    def _build_search_row(self) -> QWidget:
        wrap = QFrame(self._card)
        wrap.setProperty("class", "search-row")
        wrap.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        row = QHBoxLayout(wrap)
        row.setContentsMargins(16, 4, 16, 14)
        row.setSpacing(0)

        # The .search container holds the icon, input, and view toggle so the
        # whole row visually reads as one rounded chip (matching the JSX).
        search = QFrame(wrap)
        search.setProperty("class", "search")
        search.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        search.setMinimumHeight(36)
        search.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        # Override the default left-padding from the QLineEdit selector — we
        # render our own leading icon as a sibling.
        search.setStyleSheet(
            "QFrame[class~=\"search\"] { padding: 0; }"
        )

        s_lyt = QHBoxLayout(search)
        s_lyt.setContentsMargins(11, 0, 6, 0)
        s_lyt.setSpacing(8)

        search_icon = _make_icon_label("search", COLOR.text_3, 14, search)
        search_icon.setProperty("class", "search-icon")
        s_lyt.addWidget(search_icon, 0, Qt.AlignmentFlag.AlignVCenter)

        self._search = QLineEdit(search)
        # Don't tag with `class~=search` — that selector applies a 36px
        # bordered surface; we want a flat input inside the bordered frame.
        self._search.setProperty("class", "search-input")
        self._search.setStyleSheet(
            f"QLineEdit {{ background: transparent; border: 0; color: {COLOR.text_1}; "
            f"font-family: {FONT.sans}; font-size: 12px; padding: 0; }}"
        )
        self._search.setPlaceholderText("Search actions and snippets…")
        self._search.setClearButtonEnabled(False)
        self._search.textChanged.connect(self._on_search_changed)
        self._search.installEventFilter(self)
        s_lyt.addWidget(self._search, 1)

        # View toggle (sort / list / grid) — pinned to the right inside .search
        toggle = QFrame(search)
        toggle.setProperty("class", "view-toggle")
        toggle.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        toggle.setFixedHeight(22)
        t_lyt = QHBoxLayout(toggle)
        t_lyt.setContentsMargins(8, 0, 0, 0)
        t_lyt.setSpacing(2)

        def _toggle_btn(svg_name: str, tooltip: str) -> QPushButton:
            b = QPushButton(toggle)
            b.setProperty("class", "view-toggle-btn")
            b.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            b.setIcon(icon(svg_name, COLOR.text_3, 13))
            b.setIconSize(icon_size(13))
            b.setFixedSize(22, 22)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setToolTip(tooltip)
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            b.setProperty("on", "false")
            return b

        self._sort_btn = _toggle_btn("sort", "Sort")
        # Sort is a no-op stub for now.
        t_lyt.addWidget(self._sort_btn)

        self._list_btn = _toggle_btn("view_list", "List view")
        self._list_btn.clicked.connect(lambda: self._set_view("list"))
        t_lyt.addWidget(self._list_btn)

        self._grid_btn = _toggle_btn("view_grid", "Grid view")
        self._grid_btn.clicked.connect(lambda: self._set_view("grid"))
        t_lyt.addWidget(self._grid_btn)

        s_lyt.addWidget(toggle, 0, Qt.AlignmentFlag.AlignVCenter)

        row.addWidget(search, 1)

        self._refresh_view_toggle()
        return wrap

    def _refresh_view_toggle(self) -> None:
        """Sync the on/off state of the view-toggle buttons to `self._view`."""
        for btn, kind in (
            (self._list_btn, "list"),
            (self._grid_btn, "grid"),
        ):
            on = self._view == kind
            btn.setProperty("on", "true" if on else "false")
            tint = COLOR.violet if on else COLOR.text_3
            icon_name = "view_list" if kind == "list" else "view_grid"
            btn.setIcon(icon(icon_name, tint, 13))
            _repolish(btn)

    def _set_view(self, view: str) -> None:
        if view not in ("grid", "list") or view == self._view:
            return
        self._view = view
        self._refresh_view_toggle()
        self._populate()

    # ── Footer ────────────────────────────────────────────────

    def _build_footer(self) -> QWidget:
        footer = QFrame(self._card)
        footer.setObjectName("popupFooter")
        footer.setProperty("class", "win-ft")
        footer.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        row = QHBoxLayout(footer)
        row.setContentsMargins(16, 11, 16, 12)
        row.setSpacing(10)

        # Left: "Run: ↵"
        left = QFrame(footer)
        left.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        left.setStyleSheet("background: transparent;")
        left_lyt = QHBoxLayout(left)
        left_lyt.setContentsMargins(0, 0, 0, 0)
        left_lyt.setSpacing(5)
        run_lbl = QLabel("Run:", left)
        run_lbl.setProperty("class", "win-ft-hint")
        run_lbl.setStyleSheet(f"color: {COLOR.text_3}; font-size: 11px;")
        left_lyt.addWidget(run_lbl, 0, Qt.AlignmentFlag.AlignVCenter)
        left_lyt.addWidget(_make_kbd("↵", small=False, parent=left), 0, Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(left, 0, Qt.AlignmentFlag.AlignVCenter)

        row.addStretch(1)

        # Right: "Browser: <chord>"
        self._browser_hint = QFrame(footer)
        self._browser_hint.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._browser_hint.setStyleSheet("background: transparent;")
        self._browser_hint_lyt = QHBoxLayout(self._browser_hint)
        self._browser_hint_lyt.setContentsMargins(0, 0, 0, 0)
        self._browser_hint_lyt.setSpacing(5)
        self._refresh_browser_hint()
        row.addWidget(self._browser_hint, 0, Qt.AlignmentFlag.AlignVCenter)

        return footer

    def _refresh_browser_hint(self) -> None:
        # Clear current chips.
        while self._browser_hint_lyt.count():
            child = self._browser_hint_lyt.takeAt(0)
            w = child.widget()
            if w is not None:
                w.deleteLater()
        browser_lbl = QLabel("Browser:", self._browser_hint)
        browser_lbl.setProperty("class", "win-ft-hint")
        browser_lbl.setStyleSheet(f"color: {COLOR.text_3}; font-size: 11px;")
        self._browser_hint_lyt.addWidget(browser_lbl, 0, Qt.AlignmentFlag.AlignVCenter)
        for k in _humanize_hotkey(getattr(self._config, "launcher_hotkey", "") or ""):
            self._browser_hint_lyt.addWidget(
                _make_kbd(k, small=False, parent=self._browser_hint),
                0,
                Qt.AlignmentFlag.AlignVCenter,
            )

    # ── data / population ─────────────────────────────────────

    def set_config(self, config: "Config") -> None:
        self._config = config
        self._refresh_browser_hint()
        self._populate()

    def _items_of(self, type_: str) -> list["Item"]:
        items = [it for it in self._config.items if it.type == type_ and it.enabled]
        items.sort(key=lambda it: (it.order, (it.name or "").lower()))
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
        self._cells = []
        self._visible = []

        query = (self._search.text() if hasattr(self, "_search") else "").strip().lower()

        system_items = [it for it in self._items_of("system") if self._matches(it, query)]
        ai_items = [it for it in self._items_of("ai") if self._matches(it, query)]
        snippet_items = [it for it in self._items_of("snippet") if self._matches(it, query)]

        self._visible = system_items + ai_items + snippet_items

        # Render sections.
        position = 1
        position = self._add_section(
            "SYSTEM", "violet", "system", system_items, position,
            hide_when_empty=False,
        )
        position = self._add_section(
            "AI ACTIONS", "violet", "ai", ai_items, position,
            hide_when_empty=bool(query),
        )
        position = self._add_section(
            "SNIPPETS", "mint", "snippet", snippet_items, position,
            hide_when_empty=bool(query),
        )

        if not self._visible:
            label = QLabel("No matches" if query else "No actions available")
            label.setStyleSheet(
                f"color: {COLOR.text_3}; font-size: 12px; padding: 24px 4px;"
            )
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._body_layout.addWidget(label)

        self._body_layout.addStretch(1)

        # Reset focus to the first visible cell.
        self._focus_idx = 0
        self._refresh_focus()

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
        dot_color: str,
        section_key: str,
        items: list["Item"],
        start_position: int,
        hide_when_empty: bool,
    ) -> int:
        if not items and hide_when_empty:
            return start_position

        is_open = self._section_open.get(section_key, True)

        section = QFrame(self._body)
        section.setProperty("class", "section")
        section.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        section_lyt = QVBoxLayout(section)
        # The CSS gives sections an 18px top margin (2px for the very first).
        is_first = self._body_layout.count() == 0
        section_lyt.setContentsMargins(0, 2 if is_first else 18, 0, 0)
        section_lyt.setSpacing(0)

        # Section header (clickable to collapse/expand).
        header = QFrame(section)
        header.setProperty("class", "section-hd")
        header.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        header.setCursor(Qt.CursorShape.PointingHandCursor)
        header_lyt = QHBoxLayout(header)
        header_lyt.setContentsMargins(2, 0, 2, 11)
        header_lyt.setSpacing(8)

        chev = _make_icon_label(
            "chev_down" if is_open else "chev_right",
            COLOR.text_3, 12, header,
        )
        chev.setProperty("class", "chev")
        header_lyt.addWidget(chev, 0, Qt.AlignmentFlag.AlignVCenter)

        dot = QLabel(header)
        dot.setProperty("class", f"dot {dot_color}")
        dot.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        dot.setFixedSize(6, 6)
        header_lyt.addWidget(dot, 0, Qt.AlignmentFlag.AlignVCenter)

        lbl = QLabel(title, header)
        lbl.setProperty("class", "section-hd-lbl")
        header_lyt.addWidget(lbl, 0, Qt.AlignmentFlag.AlignVCenter)

        rule = QFrame(header)
        rule.setProperty("class", "rule")
        rule.setFrameShape(QFrame.Shape.HLine)
        rule.setFixedHeight(1)
        rule.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        header_lyt.addWidget(rule, 1, Qt.AlignmentFlag.AlignVCenter)

        # Wire up collapse/expand on header click.
        def _toggle(_evt=None, key=section_key):
            self._section_open[key] = not self._section_open.get(key, True)
            self._populate()
        header.mousePressEvent = lambda _e, k=section_key: _toggle(k)  # type: ignore[assignment]

        section_lyt.addWidget(header)

        if is_open:
            if not items:
                empty = QLabel(
                    "Nothing here yet — click Manage to add", section,
                )
                empty.setProperty("class", "section-empty")
                empty.setStyleSheet(
                    f"color: {COLOR.text_3}; font-size: 11px; padding: 0 4px 4px;"
                )
                section_lyt.addWidget(empty)
            elif self._view == "grid":
                grid_wrap = QFrame(section)
                grid_wrap.setProperty("class", "tile-grid")
                grid_wrap.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
                grid = QGridLayout(grid_wrap)
                grid.setContentsMargins(0, 0, 0, 0)
                grid.setSpacing(TILE_SPACING)
                for col in range(GRID_COLUMNS):
                    grid.setColumnStretch(col, 1)
                for idx, item in enumerate(items):
                    pos = start_position + idx
                    tile = Tile(item, pos, grid_wrap)
                    tile.tileClicked.connect(self._on_cell_clicked)
                    r = idx // GRID_COLUMNS
                    c = idx % GRID_COLUMNS
                    grid.addWidget(tile, r, c)
                    self._cells.append(tile)
                section_lyt.addWidget(grid_wrap)
            else:  # list view
                list_wrap = QFrame(section)
                list_wrap.setProperty("class", "tile-list")
                list_wrap.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
                list_lyt = QVBoxLayout(list_wrap)
                list_lyt.setContentsMargins(0, 0, 0, 0)
                list_lyt.setSpacing(2)
                for idx, item in enumerate(items):
                    pos = start_position + idx
                    row_w = Row(item, pos, list_wrap)
                    row_w.rowClicked.connect(self._on_cell_clicked)
                    list_lyt.addWidget(row_w)
                    self._cells.append(row_w)
                section_lyt.addWidget(list_wrap)

        self._body_layout.addWidget(section)
        return start_position + len(items) if is_open else start_position

    # ── presentation ──────────────────────────────────────────

    def present(self) -> None:
        self.adjustSize()
        width = self._card.sizeHint().width() + OUTER_PADDING * 2
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
        for cell in self._cells:
            try:
                cell.set_running(cell.item_id == self._running_id)
            except AttributeError:
                pass

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

    def _on_cell_clicked(self, item_id: str) -> None:
        self.fireRequested.emit(item_id)

    # Keyboard navigation handled both globally (keyPressEvent) and on the
    # search field (eventFilter) so the user can navigate without leaving
    # the input.
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

        # Ctrl+1..9 quick keys — fire by visible position.
        if mods & Qt.KeyboardModifier.ControlModifier and Qt.Key.Key_1 <= key <= Qt.Key.Key_9:
            idx = key - Qt.Key.Key_1
            if 0 <= idx < len(self._visible):
                self._fire(self._visible[idx])
            return True

        if not self._visible:
            return False

        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            target = (
                self._visible[self._focus_idx]
                if 0 <= self._focus_idx < len(self._visible)
                else None
            )
            if target is not None:
                self._fire(target)
            return True

        cols = GRID_COLUMNS if self._view == "grid" else 1
        if key == Qt.Key.Key_Right:
            if self._view == "grid":
                self._move_focus(1)
            return True
        if key == Qt.Key.Key_Left:
            if self._view == "grid":
                self._move_focus(-1)
            return True
        if key == Qt.Key.Key_Down:
            self._move_focus(cols)
            return True
        if key == Qt.Key.Key_Up:
            self._move_focus(-cols)
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
        for i, cell in enumerate(self._cells):
            try:
                cell.set_focused(i == self._focus_idx)
            except AttributeError:
                pass

    def _fire(self, item: "Item") -> None:
        self.fireRequested.emit(item.id)
