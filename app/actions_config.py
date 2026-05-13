"""JSON-backed config for the unified launcher: system actions, AI actions, snippets."""

from __future__ import annotations

import json
import os
import sys
import uuid
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Optional


@dataclass
class Item:
    id: str
    type: str
    name: str
    emoji: str
    hotkey: str = ""
    enabled: bool = True
    order: int = 0
    deletable: bool = True
    slot: Optional[str] = None
    subtype: Optional[str] = None
    prompt: Optional[str] = None
    model: Optional[str] = None
    temperature: Optional[float] = None
    kind: Optional[str] = None
    body: Optional[str] = None
    behavior: Optional[str] = None
    voice_model_path: Optional[str] = None
    voice_index_path: Optional[str] = None
    # Per-hotkey TTS+RVC overrides; None means "fall back to .env default".
    base_voice: Optional[str] = None
    rvc_pitch: Optional[int] = None
    rvc_index_rate: Optional[float] = None
    rvc_f0_method: Optional[str] = None
    rvc_filter_radius: Optional[int] = None
    rvc_protect: Optional[float] = None
    rvc_rms_mix_rate: Optional[float] = None


@dataclass
class Config:
    version: int = 1
    launcher_hotkey: str = "<ctrl>+<alt>+0"
    items: list[Item] = field(default_factory=list)


def default_config_path() -> Path:
    env = os.environ.get("CLIPBOARD_ACTIONS_PATH")
    if env:
        return Path(env)
    from .paths import app_base_dir
    return app_base_dir() / "clipboard_actions.json"


def default_config() -> Config:
    return Config(
        version=1,
        launcher_hotkey="<ctrl>+<alt>+0",
        items=[
            Item(
                id="sys-voice-online",
                type="system",
                subtype="voice_online",
                name="Voice → Clipboard (online)",
                emoji="🎤",
                hotkey="<ctrl>+<alt>+1",
                enabled=True,
                deletable=False,
                order=0,
            ),
            Item(
                id="sys-voice-offline",
                type="system",
                subtype="voice_offline",
                name="Voice → Clipboard (offline)",
                emoji="🎙️",
                hotkey="<ctrl>+<alt>+2",
                enabled=True,
                deletable=False,
                order=1,
            ),
            Item(
                id="sys-grammar",
                type="system",
                subtype="grammar",
                name="Fix grammar",
                emoji="✨",
                hotkey="<ctrl>+<alt>+3",
                enabled=True,
                deletable=False,
                order=2,
            ),
            Item(
                id="sys-youtube",
                type="system",
                subtype="youtube",
                name="YouTube transcribe",
                emoji="▶️",
                hotkey="<ctrl>+<alt>+4",
                enabled=True,
                deletable=False,
                order=3,
            ),
            Item(
                id="sys-voice-respeaker",
                type="system",
                subtype="voice_respeaker",
                name="Voice → Cloned voice playback",
                emoji="🗣️",
                hotkey="<ctrl>+<alt>+5",
                enabled=True,
                deletable=False,
                order=4,
            ),
            Item(
                id="sys-tts",
                type="system",
                subtype="voice_tts",
                name="Type → Cloned voice playback",
                emoji="⌨️",
                hotkey="<ctrl>+<alt>+6",
                enabled=True,
                deletable=False,
                order=5,
            ),
        ],
    )


def _item_from_dict(d: dict) -> Item:
    allowed = {f.name for f in fields(Item)}
    return Item(**{k: v for k, v in d.items() if k in allowed})


def load_config(path: Path) -> Config:
    if not path.exists():
        return default_config()
    try:
        with path.open("r", encoding="utf-8") as f:
            raw = json.load(f)
        version = int(raw.get("version", 1))
        launcher_hotkey = str(raw.get("launcher_hotkey", "<ctrl>+<alt>+0"))
        items_raw = raw.get("items", [])
        if not isinstance(items_raw, list):
            raise ValueError("'items' must be a list")
        items = [_item_from_dict(d) for d in items_raw if isinstance(d, dict)]
        return Config(version=version, launcher_hotkey=launcher_hotkey, items=items)
    except Exception as exc:
        print(f"[actions_config] Failed to load {path}: {exc!r}; using defaults.", file=sys.stderr)
        return default_config()


def save_config(path: Path, cfg: Config) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    payload = asdict(cfg)
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def new_item_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def find_item(cfg: Config, item_id: str) -> Optional[Item]:
    for it in cfg.items:
        if it.id == item_id:
            return it
    return None


def effective_slot(item: Item) -> str:
    """Return the slot used for HTTP routing — `item.slot` if non-empty, else `item.id`."""
    if item.slot and item.slot.strip():
        return item.slot.strip()
    return item.id
