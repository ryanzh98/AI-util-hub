from PyQt6.QtCore import QByteArray, QSize, Qt
from PyQt6.QtGui import QIcon, QImage, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer

# ── existing icons (do not modify) ──────────────────────────────────────────

SVG_MIC = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" x2="12" y1="19" y2="22"/></svg>"""

SVG_PAUSE = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="6" y="4" width="4" height="16" rx="1"/><rect x="14" y="4" width="4" height="16" rx="1"/></svg>"""

SVG_PLAY = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="6 3 20 12 6 21 6 3"/></svg>"""

SVG_STOP = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="6" y="6" width="12" height="12" rx="2"/></svg>"""

SVG_CLOSE = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>"""

SVG_X = SVG_CLOSE

# ── header / chrome ─────────────────────────────────────────────────────────

SVG_SEARCH = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/></svg>"""

SVG_GEAR = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 11-2.83 2.83l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 11-4 0v-.09a1.65 1.65 0 00-1-1.51 1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 11-2.83-2.83l.06-.06a1.65 1.65 0 00.33-1.82 1.65 1.65 0 00-1.51-1H3a2 2 0 110-4h.09a1.65 1.65 0 001.51-1 1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 112.83-2.83l.06.06a1.65 1.65 0 001.82.33H9a1.65 1.65 0 001-1.51V3a2 2 0 114 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 112.83 2.83l-.06.06a1.65 1.65 0 00-.33 1.82V9a1.65 1.65 0 001.51 1H21a2 2 0 110 4h-.09a1.65 1.65 0 00-1.51 1z"/></svg>"""

SVG_PIN = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 17v5"/><path d="M9 11V4h6v7l3 3v2H6v-2l3-3z"/></svg>"""

SVG_WINDOW = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="6" y="3" width="15" height="15" rx="2"/><path d="M3 6v13a2 2 0 002 2h13"/></svg>"""

# ── chevrons / carets / arrows ──────────────────────────────────────────────

SVG_CHEV_DOWN = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9l6 6 6-6"/></svg>"""

SVG_CHEV_RIGHT = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 6l6 6-6 6"/></svg>"""

SVG_CARET_DOWN = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"><path d="M7 10l5 5 5-5z"/></svg>"""

SVG_TRI_RIGHT = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"><path d="M9 6l8 6-8 6z"/></svg>"""

SVG_CHEV_UP = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M6 15l6-6 6 6"/></svg>"""

SVG_CHEV_DOWN_SMALL = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9l6 6 6-6"/></svg>"""

# ── list / view / sort controls ─────────────────────────────────────────────

SVG_SORT = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M7 4v16M3 8l4-4 4 4"/><path d="M17 20V4M13 16l4 4 4-4"/></svg>"""

SVG_VIEW_GRID = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="4" width="7" height="7" rx="1.4"/><rect x="13" y="4" width="7" height="7" rx="1.4"/><rect x="4" y="13" width="7" height="7" rx="1.4"/><rect x="13" y="13" width="7" height="7" rx="1.4"/></svg>"""

SVG_VIEW_LIST = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 6h4M4 12h4M4 18h4"/><path d="M11 6h9M11 12h9M11 18h9"/></svg>"""

# ── file / action chrome ────────────────────────────────────────────────────

SVG_PLUS = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>"""

SVG_SAVE = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21H5a2 2 0 01-2-2V5a2 2 0 012-2h11l5 5v11a2 2 0 01-2 2z"/><path d="M17 21v-8H7v8M7 3v5h8"/></svg>"""

SVG_FOLDER = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7a2 2 0 012-2h4l2 3h8a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2V7z"/></svg>"""

SVG_PLAY_LINE = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M8 5l11 7-11 7V5z"/></svg>"""

SVG_PASTE = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="8" y="3" width="8" height="4" rx="1"/><path d="M16 5h2a2 2 0 012 2v12a2 2 0 01-2 2H6a2 2 0 01-2-2V7a2 2 0 012-2h2"/><path d="M9 13h6M9 17h4"/></svg>"""

# ── action-tile glyphs ──────────────────────────────────────────────────────

SVG_MIC_SOLID = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"><path d="M12 14a3 3 0 003-3V6a3 3 0 10-6 0v5a3 3 0 003 3z"/><path d="M19 11a1 1 0 10-2 0 5 5 0 11-10 0 1 1 0 10-2 0 7 7 0 006 6.92V20H8a1 1 0 100 2h8a1 1 0 100-2h-3v-2.08A7 7 0 0019 11z"/></svg>"""

SVG_MIC_OUTLINE = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0014 0M12 18v4M9 22h6"/></svg>"""

SVG_SPARK = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2.5l1.6 4.4a3 3 0 001.8 1.8L19.5 10.5l-4.4 1.6a3 3 0 00-1.8 1.8L11.7 18l-1.6-4.4a3 3 0 00-1.8-1.8L4.5 10.5l4.4-1.6a3 3 0 001.8-1.8L12 2.5z"/><path d="M19 15l.7 1.9.2.5.5.2L22 18.2l-1.6.7-.5.2-.2.5L19 21.4 18.3 19.5l-.2-.5-.5-.2L16 18.2l1.6-.7.5-.2.2-.5L19 15z" opacity="0.85"/></svg>"""

SVG_YOUTUBE = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"><path d="M21.6 7.2a2.7 2.7 0 00-1.9-1.9C18 5 12 5 12 5s-6 0-7.7.4A2.7 2.7 0 002.4 7.2 28 28 0 002 12c0 1.5.1 3.1.4 4.8a2.7 2.7 0 001.9 1.9c1.7.3 7.7.3 7.7.3s6 0 7.7-.3a2.7 2.7 0 001.9-1.9c.3-1.7.4-3.3.4-4.8 0-1.6-.1-3.2-.4-4.8z"/><path d="M10 15.5l5-3.5-5-3.5v7z" fill="#0B0B10"/></svg>"""

SVG_HEAD_VOICE = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"><path d="M14 3.6a8 8 0 00-9 7.4v3a2 2 0 002 2h1v3a2 2 0 002 2h2v-7H8v-3a6 6 0 0112 0v3a2 2 0 01-2 2v3a4 4 0 01-4 4h-1v1h1a5 5 0 005-5v-2.2A4 4 0 0020 14v-3a8 8 0 00-6-7.4z" opacity="0.95"/><path d="M19.5 9c.9.6 1.5 1.7 1.5 3s-.6 2.4-1.5 3" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/><path d="M21.5 7.5c1.5 1 2.5 2.6 2.5 4.5s-1 3.5-2.5 4.5" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" opacity="0.65"/></svg>"""

SVG_TYPE_VOICE = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="6" width="14" height="12" rx="2.2"/><path d="M8 11h4M8 14h6"/><path d="M18 9c1.8.6 3 2.2 3 4s-1.2 3.4-3 4"/></svg>"""

SVG_ID_CARD = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="2.5" y="5" width="19" height="14" rx="2"/><circle cx="9" cy="12" r="2.4"/><path d="M5.5 17c.5-1.6 2-2.5 3.5-2.5s3 .9 3.5 2.5"/><path d="M14.5 10h4M14.5 13h3"/></svg>"""

SVG_CLIPBOARD = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="8" y="3" width="8" height="4" rx="1"/><path d="M16 5h2a2 2 0 012 2v12a2 2 0 01-2 2H6a2 2 0 01-2-2V7a2 2 0 012-2h2"/></svg>"""

SVG_TRANSCRIPT = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="3" width="16" height="18" rx="2"/><path d="M8 8h8M8 12h8M8 16h5"/></svg>"""

SVG_REC_LAUNCHER = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l5 5L20 7"/></svg>"""

SVG_MANAGE = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18M3 12h18M3 18h18"/></svg>"""

SVG_REFRESH = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 0115.5-6.3L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 01-15.5 6.3L3 16"/><path d="M3 21v-5h5"/></svg>"""


_ICONS = {
    # existing
    "mic": SVG_MIC,
    "pause": SVG_PAUSE,
    "play": SVG_PLAY,
    "stop": SVG_STOP,
    "close": SVG_CLOSE,
    "x": SVG_X,
    # header / chrome
    "search": SVG_SEARCH,
    "gear": SVG_GEAR,
    "pin": SVG_PIN,
    "window": SVG_WINDOW,
    # chevrons / carets / arrows
    "chev_down": SVG_CHEV_DOWN,
    "chev_right": SVG_CHEV_RIGHT,
    "caret_down": SVG_CARET_DOWN,
    "tri_right": SVG_TRI_RIGHT,
    "chev_up": SVG_CHEV_UP,
    "chev_down_small": SVG_CHEV_DOWN_SMALL,
    # list / view / sort
    "sort": SVG_SORT,
    "view_grid": SVG_VIEW_GRID,
    "view_list": SVG_VIEW_LIST,
    # file / action chrome
    "plus": SVG_PLUS,
    "save": SVG_SAVE,
    "folder": SVG_FOLDER,
    "play_line": SVG_PLAY_LINE,
    "paste": SVG_PASTE,
    # action-tile glyphs
    "mic_solid": SVG_MIC_SOLID,
    "mic_outline": SVG_MIC_OUTLINE,
    "spark": SVG_SPARK,
    "youtube": SVG_YOUTUBE,
    "head_voice": SVG_HEAD_VOICE,
    "type_voice": SVG_TYPE_VOICE,
    "id_card": SVG_ID_CARD,
    "clipboard": SVG_CLIPBOARD,
    "transcript": SVG_TRANSCRIPT,
    "rec_launcher": SVG_REC_LAUNCHER,
    "manage": SVG_MANAGE,
    "refresh": SVG_REFRESH,
}


def _render_pixmap(svg_text: str, color: str, size: int) -> QPixmap:
    tinted = svg_text.replace("currentColor", color)
    renderer = QSvgRenderer(QByteArray(tinted.encode("utf-8")))
    img = QImage(size, size, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    painter = QPainter(img)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    renderer.render(painter)
    painter.end()
    return QPixmap.fromImage(img)


def icon(name: str, color: str, size: int = 24) -> QIcon:
    if name not in _ICONS:
        raise KeyError(f"Unknown icon: {name}")
    pix = _render_pixmap(_ICONS[name], color, size)
    qi = QIcon(pix)
    return qi


def icon_size(px: int) -> QSize:
    return QSize(px, px)
