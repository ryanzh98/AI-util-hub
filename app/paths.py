"""Path helpers that behave correctly when frozen by PyInstaller.

When running from source, the "base directory" is the project root (parent of
the `app/` package). When running from a PyInstaller bundle, it's the
directory containing the .exe — that's where the friend drops `.env`,
`clipboard_actions.json`, and the `models/` folder.
"""

from __future__ import annotations

import sys
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def app_base_dir() -> Path:
    """Where to look for external config + model files."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def bundled_data_dir() -> Path:
    """Where bundled read-only assets (icons, etc.) live.

    In a PyInstaller bundle this is `sys._MEIPASS` (one-file extraction dir
    or the `_internal/` folder for one-folder mode). In source mode it's the
    project root, same as `app_base_dir()`.
    """
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return Path(__file__).resolve().parent.parent
