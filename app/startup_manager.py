import os
import sys
from pathlib import Path

from .paths import app_base_dir, bundled_data_dir, is_frozen

SHORTCUT_NAME = "VoiceDetection.lnk"
START_MENU_NAME = "Voice Detection.lnk"


def _main_script() -> Path:
    return Path(__file__).resolve().parent.parent / "main.py"


def _icon_path() -> Path:
    return bundled_data_dir() / "assets" / "app_icon.ico"


def _pythonw_executable() -> str:
    exe = Path(sys.executable)
    pythonw = exe.with_name("pythonw.exe")
    if pythonw.exists():
        return str(pythonw)
    return str(exe)


def _shortcut_target_and_args() -> tuple[str, str]:
    """Return (target, args) tuple for the auto-created shortcuts.

    Frozen mode points the shortcut directly at the .exe; source mode launches
    pythonw -s main.py.
    """
    if is_frozen():
        return str(Path(sys.executable).resolve()), ""
    return _pythonw_executable(), f'-s "{_main_script()}"'


def _shortcut_path() -> str | None:
    try:
        import winshell
    except ImportError:
        return None
    return os.path.join(winshell.startup(), SHORTCUT_NAME)


def _start_menu_path() -> str | None:
    try:
        import winshell
    except ImportError:
        return None
    return os.path.join(winshell.programs(), START_MENU_NAME)


def _write_shortcut(lnk: str) -> bool:
    try:
        from win32com.client import Dispatch
    except ImportError:
        return False

    target, args = _shortcut_target_and_args()
    icon = str(_icon_path())
    workdir = str(app_base_dir())

    try:
        shell = Dispatch("WScript.Shell")
        s = shell.CreateShortcut(lnk)
        s.TargetPath = target
        s.Arguments = args
        s.WorkingDirectory = workdir
        if os.path.exists(icon):
            s.IconLocation = icon
        s.Description = "Voice Detection — Ctrl+Alt+1"
        s.Save()
        return True
    except Exception:
        return False


def _refresh_if_drifted(lnk: str) -> bool:
    """Recreate `lnk` if it's missing or its target/args drifted from current."""
    if lnk is None:
        return False
    target, args = _shortcut_target_and_args()
    try:
        from win32com.client import Dispatch
    except ImportError:
        return False
    if os.path.exists(lnk):
        try:
            shell = Dispatch("WScript.Shell")
            existing = shell.CreateShortcut(lnk)
            if existing.TargetPath == target and existing.Arguments == args:
                return True
        except Exception:
            pass
    return _write_shortcut(lnk)


def ensure_startup_shortcut() -> bool:
    """Create or refresh the Windows startup-folder shortcut."""
    return _refresh_if_drifted(_shortcut_path())


def ensure_start_menu_shortcut() -> bool:
    """Create or refresh the Start Menu shortcut so the user can launch manually."""
    return _refresh_if_drifted(_start_menu_path())


def remove_startup_shortcut() -> bool:
    lnk = _shortcut_path()
    if lnk is None:
        return False
    try:
        if os.path.exists(lnk):
            os.unlink(lnk)
        return True
    except OSError:
        return False


def remove_start_menu_shortcut() -> bool:
    lnk = _start_menu_path()
    if lnk is None:
        return False
    try:
        if os.path.exists(lnk):
            os.unlink(lnk)
        return True
    except OSError:
        return False
