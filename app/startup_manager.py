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
    """Recreate `lnk` if its target / args / icon drifted from current.

    The icon comparison matters: when assets/tray.ico was renamed to
    assets/app_icon.ico, existing shortcuts kept pointing at the old
    icon path. Windows then showed a stale / fallback icon in the
    taskbar and Start Menu until the .lnk was rebuilt.
    """
    if lnk is None:
        return False
    target, args = _shortcut_target_and_args()
    want_icon = str(_icon_path())
    try:
        from win32com.client import Dispatch
    except ImportError:
        return False
    if os.path.exists(lnk):
        try:
            shell = Dispatch("WScript.Shell")
            existing = shell.CreateShortcut(lnk)
            # IconLocation returns "<path>,<index>" — strip the index for the
            # comparison since we always write index 0.
            existing_icon = (existing.IconLocation or "").split(",")[0]
            if (
                existing.TargetPath == target
                and existing.Arguments == args
                and existing_icon.lower() == want_icon.lower()
            ):
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


def _user_pinned_taskbar_dir() -> Path | None:
    """Where Windows stores .lnk files for items pinned to the taskbar."""
    appdata = os.environ.get("APPDATA")
    if not appdata:
        return None
    p = (
        Path(appdata)
        / "Microsoft" / "Internet Explorer" / "Quick Launch"
        / "User Pinned" / "TaskBar"
    )
    return p if p.is_dir() else None


def refresh_taskbar_pin_icon() -> int:
    """Rewrite IconLocation on any pinned-taskbar shortcut targeting this app.

    The user pins to the taskbar separately from the Start Menu / startup
    folder shortcuts we manage — that pin's .lnk lives in its own folder
    and keeps whatever icon path was captured at pin time. After renaming
    assets/tray.ico → assets/app_icon.ico the pin's IconLocation became
    stale (pointing at a path that no longer exists) so Windows fell back
    to a generic icon.

    Returns the number of shortcuts updated. Cheap & idempotent — safe to
    call on every launch. After this fix, Windows still serves the old
    icon from its disk cache until Explorer restarts or icon cache rolls.
    """
    pin_dir = _user_pinned_taskbar_dir()
    if pin_dir is None:
        return 0
    try:
        from win32com.client import Dispatch
    except ImportError:
        return 0

    our_target, _ = _shortcut_target_and_args()
    want_icon = str(_icon_path())
    if not Path(want_icon).exists():
        return 0  # new icon missing — don't break working pins

    try:
        shell = Dispatch("WScript.Shell")
    except Exception:
        return 0

    updated = 0
    for lnk in pin_dir.glob("*.lnk"):
        try:
            existing = shell.CreateShortcut(str(lnk))
            # Only touch shortcuts that actually point at this app.
            if existing.TargetPath.lower() != our_target.lower():
                continue
            current_icon = (existing.IconLocation or "").split(",")[0]
            if current_icon.lower() == want_icon.lower():
                continue
            existing.IconLocation = want_icon
            existing.Save()
            updated += 1
        except Exception:
            continue
    return updated


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
