import faulthandler
import os
import sys
import traceback
from pathlib import Path

# In source mode this is the project root; in a frozen bundle main.py lives
# inside _MEIPASS but we want external files to live next to the .exe.
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Lazy import — must come after sys.path is set up.
from app.paths import app_base_dir  # noqa: E402

BASE = app_base_dir()

# Crash diagnostics — write Python stack to crash.log on segfault/abort + on any
# uncaught exception. Lets us see the qFatal context when pythonw eats stderr.
_CRASH_LOG = open(BASE / "crash.log", "w", buffering=1, encoding="utf-8")
faulthandler.enable(file=_CRASH_LOG)
# Redirect Python's stderr to the same file so all `traceback.print_exc()` calls
# from worker threads (e.g. respeaker_client) land here, not /dev/null.
sys.stderr = _CRASH_LOG


def _excepthook(exc_type, exc, tb):
    print("=== uncaught exception ===", file=_CRASH_LOG, flush=True)
    traceback.print_exception(exc_type, exc, tb, file=_CRASH_LOG)
    _CRASH_LOG.flush()
    sys.__excepthook__(exc_type, exc, tb)


sys.excepthook = _excepthook

from dotenv import load_dotenv  # noqa: E402

from PyQt6.QtCore import qInstallMessageHandler, QtMsgType  # noqa: E402
from PyQt6.QtGui import QIcon  # noqa: E402
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon  # noqa: E402

from app.paths import bundled_data_dir  # noqa: E402
from app.tray_controller import TrayController, already_running  # noqa: E402
from design import apply_theme  # noqa: E402


# Windows groups taskbar entries by AppUserModelID. Without this call our
# windows would be grouped under pythonw.exe's identity (and inherit its
# generic Python icon), so the user sees the wrong icon in the taskbar
# even after setWindowIcon. Must run BEFORE any window is shown.
def _set_appusermodel_id() -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "Anthropic.VoiceDetection.Shortcut.1"
        )
    except (OSError, AttributeError):
        pass


def _qt_message(msg_type, ctx, message):
    label = {
        QtMsgType.QtDebugMsg: "DEBUG",
        QtMsgType.QtInfoMsg: "INFO",
        QtMsgType.QtWarningMsg: "WARN",
        QtMsgType.QtCriticalMsg: "CRIT",
        QtMsgType.QtFatalMsg: "FATAL",
    }.get(msg_type, str(msg_type))
    where = f"{ctx.file}:{ctx.line}" if ctx and ctx.file else ""
    print(f"[Qt {label}] {message}  {where}", file=_CRASH_LOG, flush=True)


qInstallMessageHandler(_qt_message)


def main() -> int:
    load_dotenv(BASE / ".env", override=True)

    _set_appusermodel_id()

    app = QApplication(sys.argv)
    app.setApplicationName("VoiceDetection")
    app.setQuitOnLastWindowClosed(False)

    # Set the global window icon so every top-level window (recorder, TTS,
    # launcher, manager, etc.) shows the app icon in the taskbar / Alt-Tab.
    # Without this each window falls back to pythonw.exe's stock icon.
    icon_path = bundled_data_dir() / "assets" / "app_icon.ico"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    apply_theme(app)

    if not QSystemTrayIcon.isSystemTrayAvailable():
        sys.stderr.write("System tray is not available on this system.\n")
        return 1

    if already_running():
        return 0

    controller = TrayController(app)  # noqa: F841
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
