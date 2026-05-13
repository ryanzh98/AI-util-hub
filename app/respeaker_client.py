"""TTS + RVC voice re-speaker: pure helper + Qt worker wrapper.

Takes a transcript string, runs it through edge-tts to produce a neutral WAV,
then through an RVC voice-conversion model to clone the target voice, and
returns the path to the resulting WAV. The Qt worker wraps `respeak()` and
plays the WAV through the system speakers via sounddevice.

Configuration is read from environment (with sensible defaults):
    RESPEAKER_MODEL_PATH    .pth file of the RVC voice model
    RESPEAKER_INDEX_PATH    .index file (optional but strongly recommended)
    RESPEAKER_BASE_VOICE    edge-tts voice name (e.g. en-US-JennyNeural)
    RESPEAKER_PITCH         semitone shift, -12..+12 (default 0)
    RESPEAKER_INDEX_RATE    accent-mix strength 0.0..1.0 (default 0.75)
    RESPEAKER_DEVICE        torch device string, e.g. "cuda:0" or "cpu"
    RESPEAKER_F0_METHOD     pitch extraction, default "rmvpe"
"""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Callable, Optional

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot


def _project_root() -> Path:
    from .paths import app_base_dir
    return app_base_dir()


def _default(name: str, fallback: str) -> str:
    raw = os.environ.get(name, "").strip()
    return raw if raw else fallback


_DEFAULT_MODEL = "models/respeaker/voice.pth"
_DEFAULT_INDEX = "models/respeaker/voice.index"
_DEFAULT_BASE_VOICE = "en-US-JennyNeural"
_DEFAULT_DEVICE = "cuda:0"
_DEFAULT_F0_METHOD = "rmvpe"
_DEFAULT_PITCH = 0
_DEFAULT_INDEX_RATE = 0.75


_ENGINE = None  # type: ignore[var-annotated]
_ENGINE_KEY: tuple[str, str, str, str] | None = None  # (model, index, device, f0_method)
_LOAD_LOCK = threading.Lock()
_INFER_LOCK = threading.Lock()


def _drop_engine() -> None:
    """Release the cached engine and free GPU memory if possible.

    Must be called under `_LOAD_LOCK`.
    """
    global _ENGINE, _ENGINE_KEY
    _ENGINE = None
    _ENGINE_KEY = None
    try:
        import gc
        gc.collect()
    except Exception:
        pass
    try:
        import torch  # type: ignore[import-not-found]
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass


def _resolve_path(value: str) -> str:
    p = Path(value)
    if not p.is_absolute():
        p = _project_root() / p
    return str(p)


def resolve_output_dir() -> Path:
    """Where generated WAVs land.

    Reads RESPEAKER_OUTPUT_DIR; falls back to <project>/audio_output. Relative
    paths resolve against the project root so users can drop a short value in
    .env without surprises. Creates the directory if missing.
    """
    raw = os.environ.get("RESPEAKER_OUTPUT_DIR", "").strip()
    d = Path(raw) if raw else _project_root() / "audio_output"
    if not d.is_absolute():
        d = _project_root() / d
    d.mkdir(parents=True, exist_ok=True)
    return d


_DLL_DIR_HANDLE = None  # keep alive — handle GC = directory removed from search


def _ensure_conda_dlls_visible() -> None:
    """Add the conda env's Library/bin to Python's DLL search path.

    Needed for stdlib + sub-deps that link against conda-provided DLLs:
      - liblzma.dll (Python's `_lzma` → librosa → tts-with-rvc)
      - libsqlite3.dll, etc.

    Critically uses `os.add_dll_directory` instead of mutating PATH. PATH
    mutation breaks PyQt6 because Qt's runtime LoadLibrary calls (e.g. for
    OpenSSL) use the standard search order which DOES include PATH, and
    conda's libcrypto can have different exports than Qt's bundled one.
    `add_dll_directory` is process-local and only affects extension loading.

    Called lazily — only when the respeaker engine is about to load — so we
    don't add this path until AFTER PyQt6 has fully initialized. That way
    PyQt6's `Qt6/bin` is first in the USER_DIRS list and wins for any name
    collision (libssl, libcrypto, icu, etc.).
    """
    global _DLL_DIR_HANDLE
    if _DLL_DIR_HANDLE is not None:
        return
    import sys as _sys
    lib_bin = Path(_sys.prefix) / "Library" / "bin"
    if not lib_bin.is_dir():
        return
    try:
        _DLL_DIR_HANDLE = os.add_dll_directory(str(lib_bin))
    except (OSError, AttributeError):
        pass


def _ensure_ffmpeg_on_path() -> None:
    """Make sure a binary literally named `ffmpeg.exe` is findable on PATH.

    tts-with-rvc -> ffmpeg-python spawns `subprocess.Popen(["ffmpeg", ...])`,
    which on Windows requires the binary to be named exactly `ffmpeg.exe` and
    sit in a directory on PATH. imageio-ffmpeg ships its binary as
    `ffmpeg-win-x86_64-v7.1.exe`, so dropping its dir on PATH is not enough —
    we materialize a shim copy named `ffmpeg.exe` in a project-local bin dir.
    """
    try:
        import imageio_ffmpeg
    except ImportError:
        return  # caller will hit a clearer error from tts-with-rvc
    try:
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return

    shim_dir = _project_root() / "bin"
    shim_dir.mkdir(parents=True, exist_ok=True)
    shim = shim_dir / "ffmpeg.exe"

    src = Path(ffmpeg_exe)
    needs_copy = (
        not shim.exists()
        or shim.stat().st_size != src.stat().st_size
    )
    if needs_copy:
        try:
            import shutil as _shutil
            _shutil.copy2(src, shim)
        except OSError:
            pass

    shim_dir_str = str(shim_dir)
    existing = os.environ.get("PATH", "")
    if shim_dir_str.lower() in existing.lower():
        return
    os.environ["PATH"] = shim_dir_str + os.pathsep + existing


def _load_engine(
    status_cb: Optional[Callable[[str], None]] = None,
    model_path: Optional[str] = None,
    index_path: Optional[str] = None,
    f0_method: Optional[str] = None,
):
    """Lazy-load TTS_RVC, replacing the cached engine on voice/f0 change.

    `model_path` / `index_path` / `f0_method` are part of the engine's
    construction signature in `tts_with_rvc.TTS_RVC` — changing any of them
    forces a new engine instance. We keep a single resident engine and
    drop it on key change to bound VRAM.

    `base_voice` is intentionally *not* in the cache key — it can be
    swapped cheaply on an existing engine via `engine.set_voice()` (see
    `respeak()`), so the user can switch language per-call without paying
    a model-reload.

    When any argument is None, falls back to the env-configured default
    (preserving pre-picker behaviour for HTTP API callers).

    Holds `_LOAD_LOCK` while loading.
    """
    global _ENGINE, _ENGINE_KEY

    with _LOAD_LOCK:
        resolved_model = _resolve_path(
            model_path if model_path else _default("RESPEAKER_MODEL_PATH", _DEFAULT_MODEL)
        )
        resolved_index = _resolve_path(
            index_path if index_path else _default("RESPEAKER_INDEX_PATH", _DEFAULT_INDEX)
        )
        device = _default("RESPEAKER_DEVICE", _DEFAULT_DEVICE)
        resolved_f0 = (f0_method or "").strip() or _default("RESPEAKER_F0_METHOD", _DEFAULT_F0_METHOD)
        key = (resolved_model, resolved_index, device, resolved_f0)

        if _ENGINE is not None and _ENGINE_KEY == key:
            return _ENGINE

        if _ENGINE is not None:
            if status_cb is not None:
                status_cb("Switching voice model…")
            _drop_engine()

        # Add the env's Library/bin to Python's DLL search BEFORE importing
        # tts_with_rvc — librosa (transitive dep) imports lzma, which loads
        # liblzma.dll from that dir. Without this, `import tts_with_rvc`
        # fails with "DLL load failed while importing _lzma" on conda envs
        # that don't activate via `conda activate` (we run pythonw directly).
        _ensure_conda_dlls_visible()
        # Make ffmpeg subprocess findable for tts-with-rvc's audio loader.
        _ensure_ffmpeg_on_path()

        try:
            from tts_with_rvc import TTS_RVC
        except ImportError as e:
            raise RuntimeError(
                f"tts-with-rvc not installed ({e}). Run: pip install tts-with-rvc"
            )

        base_voice = _default("RESPEAKER_BASE_VOICE", _DEFAULT_BASE_VOICE)

        if not Path(resolved_model).exists():
            raise RuntimeError(
                f"RVC model not found at {resolved_model}. "
                f"Set RESPEAKER_MODEL_PATH in .env or place a .pth or .ckpt file there."
            )

        tmp_dir = _project_root() / "audio_temp"
        out_dir = resolve_output_dir()
        tmp_dir.mkdir(parents=True, exist_ok=True)

        if status_cb is not None:
            status_cb(f"Loading voice model ({device}, {resolved_f0})…")

        try:
            engine = TTS_RVC(
                model_path=resolved_model,
                index_path=resolved_index if Path(resolved_index).exists() else "",
                device=device,
                f0_method=resolved_f0,
                tmp_directory=str(tmp_dir),
                output_directory=str(out_dir),
            )
            engine.set_voice(base_voice)
        except Exception as e:
            if device.startswith("cuda"):
                if status_cb is not None:
                    status_cb(f"GPU init failed ({e}); falling back to CPU.")
                try:
                    engine = TTS_RVC(
                        model_path=resolved_model,
                        index_path=resolved_index if Path(resolved_index).exists() else "",
                        device="cpu",
                        f0_method=resolved_f0,
                        tmp_directory=str(tmp_dir),
                        output_directory=str(out_dir),
                    )
                    engine.set_voice(base_voice)
                    # Re-key the cache with the device we actually used.
                    key = (resolved_model, resolved_index, "cpu", resolved_f0)
                except Exception as e2:
                    raise RuntimeError(f"Re-speaker model load failed: {e2}")
            else:
                raise RuntimeError(f"Re-speaker model load failed: {e}")

        _ENGINE = engine
        _ENGINE_KEY = key
        return engine


def _env_int(name: str, fallback: int) -> int:
    try:
        return int(_default(name, str(fallback)))
    except ValueError:
        return fallback


def _env_float(name: str, fallback: float) -> float:
    try:
        return float(_default(name, str(fallback)))
    except ValueError:
        return fallback


def respeak(
    text: str,
    status_cb: Optional[Callable[[str], None]] = None,
    model_path: Optional[str] = None,
    index_path: Optional[str] = None,
    settings: Optional[dict] = None,
) -> str:
    """Synthesize `text` in the target voice and return absolute WAV path.

    Pass `model_path`/`index_path` to use a specific RVC voice; `settings`
    overrides per-call TTS+RVC parameters from the popup UI. Keys:

        base_voice          Edge TTS voice id (controls language)
        rvc_pitch           int semitone shift
        rvc_index_rate      float 0..1
        rvc_f0_method       str — forces engine rebuild if it changes
        rvc_filter_radius   int >=3
        rvc_protect         float 0..0.5
        rvc_rms_mix_rate    float 0..1

    Any omitted/None value falls back to the env default so existing
    callers (e.g. the HTTP API) keep working unchanged.

    Raises RuntimeError on any failure. Safe to call from any thread —
    inference is serialized on `_INFER_LOCK`.
    """
    if not text or not text.strip():
        raise RuntimeError("Empty text passed to respeak()")

    s = settings or {}
    f0_method = s.get("rvc_f0_method") or None  # None → env default in _load_engine
    base_voice = s.get("base_voice") or _default("RESPEAKER_BASE_VOICE", _DEFAULT_BASE_VOICE)

    engine = _load_engine(
        status_cb,
        model_path=model_path,
        index_path=index_path,
        f0_method=f0_method,
    )

    pitch = int(s["rvc_pitch"]) if s.get("rvc_pitch") is not None else _env_int("RESPEAKER_PITCH", _DEFAULT_PITCH)
    index_rate = float(s["rvc_index_rate"]) if s.get("rvc_index_rate") is not None else _env_float("RESPEAKER_INDEX_RATE", _DEFAULT_INDEX_RATE)
    filter_radius = int(s.get("rvc_filter_radius") or 3)
    protect = float(s["rvc_protect"]) if s.get("rvc_protect") is not None else 0.33
    rms_mix_rate = float(s["rvc_rms_mix_rate"]) if s.get("rvc_rms_mix_rate") is not None else 0.5

    if status_cb is not None:
        status_cb("Synthesizing voice…")

    try:
        with _INFER_LOCK:
            # Base voice switch is cheap (no engine rebuild) so apply per-call
            # for language switches. Done inside _INFER_LOCK so a concurrent
            # call can't change the voice between set_voice() and engine().
            try:
                engine.set_voice(base_voice)
            except Exception:
                pass  # unknown voice ID — fall through with prior voice.
            path = engine(
                text=text,
                pitch=pitch,
                index_rate=index_rate,
                filter_radius=filter_radius,
                protect=protect,
                rms_mix_rate=rms_mix_rate,
            )
    except Exception as e:
        import sys, traceback
        # Dump full stack to stderr (captured by main.py's crash.log handler)
        # so we can diagnose tts-with-rvc internals rather than just the
        # one-line repr.
        try:
            traceback.print_exc(file=sys.stderr)
        except Exception:
            pass
        raise RuntimeError(f"Voice synthesis failed: {type(e).__name__}: {e}")

    if not path or not Path(path).exists():
        raise RuntimeError("Voice synthesis produced no output file")

    return str(Path(path).resolve())


def play_wav(wav_path: str) -> None:
    """Play a WAV file through the default output device. Blocks until done.

    Raises RuntimeError on failure. Loads soundfile + sounddevice lazily so the
    process can start without them when not in use.
    """
    try:
        import soundfile as sf
        import sounddevice as sd
    except ImportError as e:
        raise RuntimeError(f"Audio playback deps missing ({e})")

    try:
        data, samplerate = sf.read(wav_path, dtype="float32")
    except Exception as e:
        raise RuntimeError(f"Failed to read WAV {wav_path}: {e}")

    try:
        sd.play(data, samplerate)
        sd.wait()
    except Exception as e:
        raise RuntimeError(f"Audio playback failed: {e}")


class RespeakerWorker(QObject):
    done = pyqtSignal(str)  # emits the played WAV path
    failed = pyqtSignal(str)
    statusChanged = pyqtSignal(str)

    @pyqtSlot(str)
    def speak(self, text: str) -> None:
        self._run(text, "", "", {})

    @pyqtSlot(str, str, str)
    def speakWithVoice(self, text: str, model_path: str, index_path: str) -> None:
        self._run(text, model_path, index_path, {})

    @pyqtSlot(str, str, str, dict)
    def speakWithSettings(
        self,
        text: str,
        model_path: str,
        index_path: str,
        settings: dict,
    ) -> None:
        self._run(text, model_path, index_path, settings)

    @pyqtSlot(str)
    def replayWav(self, wav_path: str) -> None:
        """Re-play an already-generated WAV without re-synthesizing.

        Reuses the same done/failed signals so the controller's busy-gate and
        status plumbing don't need a separate code path.
        """
        if not wav_path or not Path(wav_path).exists():
            self.failed.emit(f"WAV not found: {wav_path}")
            return
        try:
            self.statusChanged.emit("Playing…")
            play_wav(wav_path)
        except RuntimeError as e:
            self.failed.emit(str(e))
            return
        self.done.emit(wav_path)

    def _run(self, text: str, model_path: str, index_path: str, settings: dict) -> None:
        try:
            wav_path = respeak(
                text,
                status_cb=self.statusChanged.emit,
                model_path=model_path or None,
                index_path=index_path or None,
                settings=settings or None,
            )
        except RuntimeError as e:
            self.failed.emit(str(e))
            return
        try:
            self.statusChanged.emit("Playing…")
            play_wav(wav_path)
        except RuntimeError as e:
            self.failed.emit(str(e))
            return
        self.done.emit(wav_path)
