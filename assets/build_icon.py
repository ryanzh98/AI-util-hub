"""Render tray_source.svg → app_icon.ico (multi-size). Optional rebuild helper.

NOTE: app_icon.ico in this directory was supplied directly (not regenerated
from tray_source.svg) and the SVG no longer matches the binary icon shipped
with the app. Running this script WILL overwrite app_icon.ico with the
SVG-rendered version. Only run it if you intend to redesign via SVG.
"""
import sys
from pathlib import Path

ASSETS = Path(__file__).resolve().parent
SVG = ASSETS / "tray_source.svg"
ICO = ASSETS / "app_icon.ico"
TINT = "#E7EAF0"


def main() -> int:
    from PyQt6.QtCore import QByteArray, Qt
    from PyQt6.QtGui import QImage, QPainter
    from PyQt6.QtSvg import QSvgRenderer
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication(sys.argv)  # noqa: F841

    svg_text = SVG.read_text(encoding="utf-8").replace("currentColor", TINT)
    renderer = QSvgRenderer(QByteArray(svg_text.encode("utf-8")))

    images = []
    for size in (16, 32, 48, 64, 256):
        img = QImage(size, size, QImage.Format.Format_ARGB32)
        img.fill(Qt.GlobalColor.transparent)
        painter = QPainter(img)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        renderer.render(painter)
        painter.end()
        images.append(img)

    try:
        from PIL import Image
    except ImportError:
        print("Pillow is required to write multi-size .ico", file=sys.stderr)
        return 2

    pil_images = []
    for q in images:
        q = q.convertToFormat(QImage.Format.Format_RGBA8888)
        ptr = q.bits()
        ptr.setsize(q.sizeInBytes())
        buf = bytes(ptr)
        pil = Image.frombuffer("RGBA", (q.width(), q.height()), buf, "raw", "RGBA", 0, 1)
        pil_images.append(pil)

    pil_images[0].save(
        ICO,
        format="ICO",
        sizes=[(im.width, im.height) for im in pil_images],
        append_images=pil_images[1:],
    )
    print(f"Wrote {ICO}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
