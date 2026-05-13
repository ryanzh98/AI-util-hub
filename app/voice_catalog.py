"""Discoverable RVC voice catalog.

The "Default" entry points at the singleton model under `models/respeaker/`
(what shipped before the picker existed). Every additional voice is a
subfolder under `Sound/` that contains a `.pth` file; the `.index` is
optional but strongly preferred for accent quality.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .paths import app_base_dir

DEFAULT_LABEL = "Default"
DEFAULT_MODEL_REL = "models/respeaker/voice.pth"
DEFAULT_INDEX_REL = "models/respeaker/voice.index"
SOUND_DIR_REL = "Sound"


@dataclass(frozen=True)
class Voice:
    label: str
    model_path: str  # absolute path; "" if missing on disk
    index_path: str  # absolute path; "" if no .index pair
    is_default: bool

    @property
    def available(self) -> bool:
        return bool(self.model_path) and Path(self.model_path).is_file()


def _default_voice() -> Voice:
    base = app_base_dir()
    model = base / DEFAULT_MODEL_REL
    index = base / DEFAULT_INDEX_REL
    return Voice(
        label=DEFAULT_LABEL,
        model_path=str(model) if model.is_file() else "",
        index_path=str(index) if index.is_file() else "",
        is_default=True,
    )


def _pick_pth(folder: Path) -> Path | None:
    candidates = sorted(
        (p for p in folder.iterdir() if p.is_file() and p.suffix.lower() == ".pth"),
        key=lambda p: p.stat().st_size,
        reverse=True,
    )
    return candidates[0] if candidates else None


def _pick_index(folder: Path) -> Path | None:
    for p in folder.iterdir():
        if p.is_file() and p.suffix.lower() == ".index":
            return p
    return None


def list_voices() -> list[Voice]:
    """Default first; one entry per Sound/<subdir> that has a .pth file.

    Picks the largest .pth in each subfolder (so e.g. `_ULTIMATE.pth` wins
    over earlier checkpoint variants). Folders with no .pth are skipped.
    """
    voices: list[Voice] = [_default_voice()]

    sound_dir = app_base_dir() / SOUND_DIR_REL
    if not sound_dir.is_dir():
        return voices

    for sub in sorted(sound_dir.iterdir(), key=lambda p: p.name.lower()):
        if not sub.is_dir():
            continue
        pth = _pick_pth(sub)
        if pth is None:
            continue
        idx = _pick_index(sub)
        voices.append(
            Voice(
                label=sub.name,
                model_path=str(pth),
                index_path=str(idx) if idx else "",
                is_default=False,
            )
        )

    return voices


def find_by_model_path(path: str | None) -> Voice | None:
    """Look up the catalog entry whose model_path matches `path`.

    Used to restore a persisted selection. Returns None if `path` is empty
    or doesn't match a current entry (e.g. the voice folder was deleted).
    """
    if not path:
        return None
    target = str(Path(path).resolve()).lower()
    for v in list_voices():
        if not v.model_path:
            continue
        if str(Path(v.model_path).resolve()).lower() == target:
            return v
    return None
