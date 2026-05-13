from PyQt6.QtCore import QByteArray, QSize, Qt
from PyQt6.QtGui import QIcon, QImage, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer

SVG_MIC = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" x2="12" y1="19" y2="22"/></svg>"""

SVG_PAUSE = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="6" y="4" width="4" height="16" rx="1"/><rect x="14" y="4" width="4" height="16" rx="1"/></svg>"""

SVG_PLAY = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="6 3 20 12 6 21 6 3"/></svg>"""

SVG_STOP = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="6" y="6" width="12" height="12" rx="2"/></svg>"""

SVG_CLOSE = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>"""

SVG_X = SVG_CLOSE

_ICONS = {
    "mic": SVG_MIC,
    "pause": SVG_PAUSE,
    "play": SVG_PLAY,
    "stop": SVG_STOP,
    "close": SVG_CLOSE,
    "x": SVG_X,
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
