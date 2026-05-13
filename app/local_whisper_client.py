import importlib
import os
import shutil
import sys
import tempfile
import threading
from pathlib import Path
from typing import Callable, Optional

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

DEFAULT_MODEL = "large-v3-turbo"

_CUDA_DLL_HANDLES: list = []
_PRELOADED_DLLS: list = []


def _nvidia_bin_dirs() -> list[str]:
    dirs: list[str] = []
    for pkg in ("nvidia.cudnn", "nvidia.cublas", "nvidia.cuda_nvrtc"):
        try:
            mod = importlib.import_module(pkg)
        except ImportError:
            continue
        roots = list(getattr(mod, "__path__", []) or [])
        if getattr(mod, "__file__", None):
            roots.append(os.path.dirname(mod.__file__))
        for root in roots:
            bin_dir = os.path.join(root, "bin")
            if os.path.isdir(bin_dir):
                dirs.append(bin_dir)
    return dirs


def _register_cuda_dll_dirs() -> None:
    """Pre-resolve cuDNN/cuBLAS/NVRTC DLLs shipped by the `nvidia-*-cu12` wheels.

    ctranslate2 lazy-loads these at inference time via plain `LoadLibraryA`,
    which on Windows ignores `os.add_dll_directory`. We do two things:

    1. Register each bin dir via `os.add_dll_directory` (covers static deps).
    2. Pre-load every DLL via `ctypes.WinDLL` so the Windows loader finds them
       by name in its already-resolved-modules table when ctranslate2 asks.

    Two passes for the pre-load handle intra-bundle dependency order
    (e.g. cuBLAS depends on cuBLAS-Lt; some cuDNN engines depend on others).
    """
    if sys.platform != "win32":
        return
    if _PRELOADED_DLLS:
        return

    bin_dirs = _nvidia_bin_dirs()

    for bin_dir in bin_dirs:
        try:
            _CUDA_DLL_HANDLES.append(os.add_dll_directory(bin_dir))
        except (OSError, AttributeError):
            pass

    import ctypes
    for _ in range(2):
        for bin_dir in bin_dirs:
            try:
                names = os.listdir(bin_dir)
            except OSError:
                continue
            for fname in names:
                if not fname.lower().endswith(".dll"):
                    continue
                full = os.path.join(bin_dir, fname)
                try:
                    _PRELOADED_DLLS.append(ctypes.WinDLL(full))
                except OSError:
                    pass


def _detect_cuda() -> bool:
    try:
        import ctranslate2
    except ImportError:
        return False
    try:
        return ctranslate2.get_cuda_device_count() > 0
    except Exception:
        return False


# Module-level singleton state. The faster-whisper WhisperModel is heavy and
# not safe for concurrent transcription calls; we hoist it to module scope so
# both the Qt-slot caller and the HTTP API workers share one instance.
#   _LOAD_LOCK  serializes the first-time load (prevents duplicate downloads).
#   _MODEL_LOCK serializes inference (model.transcribe is not thread-safe).
_MODEL = None  # type: ignore[var-annotated]
_DEVICE: Optional[str] = None
_COMPUTE_TYPE: Optional[str] = None
_LOAD_LOCK = threading.Lock()
_MODEL_LOCK = threading.Lock()


def _load_model(status_cb: Optional[Callable[[str], None]] = None):
    """Lazy-load the shared WhisperModel singleton with CUDA→CPU fallback.

    Raises RuntimeError on failure. `status_cb`, if provided, receives
    human-readable progress strings (same wording the Qt slot used to emit
    via statusChanged).
    """
    global _MODEL, _DEVICE, _COMPUTE_TYPE

    with _LOAD_LOCK:
        if _MODEL is not None:
            return _MODEL

        # Torch's bundled CUDA DLLs (in torch/lib/) handle cuBLAS/cuDNN/NVRTC
        # for the whole process — ctranslate2 picks them up automatically once
        # torch is imported. We deliberately do NOT preload the nvidia-*-cu12
        # pip-package DLLs: those install at different patch versions than
        # torch's bundle (cuBLAS 12.9 vs 12.8, cuDNN 9.22 vs torch's 9.x) and
        # mixing them causes "Entry Point Not Found" errors on cudnn_engines_*.
        try:
            from faster_whisper import WhisperModel
        except ImportError as e:
            raise RuntimeError(
                f"faster-whisper not installed ({e}). Run: pip install -r requirements.txt"
            )

        model_name = os.environ.get("WHISPER_LOCAL_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL

        cuda_ok = _detect_cuda()
        device = "cuda" if cuda_ok else "cpu"
        compute_type = "float16" if cuda_ok else "int8"

        if status_cb is not None:
            status_cb(f"Loading {model_name} ({device}/{compute_type})…")

        try:
            model = WhisperModel(model_name, device=device, compute_type=compute_type)
            _MODEL = model
            _DEVICE = device
            _COMPUTE_TYPE = compute_type
            return model
        except Exception as e:
            if device == "cuda":
                try:
                    model = WhisperModel(model_name, device="cpu", compute_type="int8")
                    _MODEL = model
                    _DEVICE = "cpu"
                    _COMPUTE_TYPE = "int8"
                    if status_cb is not None:
                        status_cb(f"GPU init failed ({e}); using CPU/int8.")
                    return model
                except Exception as e2:
                    raise RuntimeError(f"Local model load failed: {e2}")
            raise RuntimeError(f"Local model load failed: {e}")


def _transcribe_constrained(model, source: str) -> str:
    """Run inference on `source`. If the detected language is outside the
    allowed list, retry pinned to the best-probability allowed language.
    Caller must hold `_MODEL_LOCK`.
    """
    initial_prompt = os.environ.get("WHISPER_INITIAL_PROMPT", "").strip()
    langs = os.environ.get("WHISPER_LANGUAGES", "en,zh").strip().lower()
    allowed = [l.strip() for l in langs.split(",") if l.strip()] or None
    pinned = allowed[0] if allowed and len(allowed) == 1 else None

    segments, info = model.transcribe(
        source,
        beam_size=5,
        vad_filter=True,
        language=pinned,
        initial_prompt=initial_prompt or None,
    )
    seg_list = list(segments)

    if allowed and len(allowed) > 1 and info.language not in allowed:
        probs = dict(getattr(info, "all_language_probs", None) or [])
        best = max(allowed, key=lambda l: probs.get(l, 0.0))
        segments, _info = model.transcribe(
            source,
            beam_size=5,
            vad_filter=True,
            language=best,
            initial_prompt=initial_prompt or None,
        )
        seg_list = list(segments)

    return "".join(seg.text for seg in seg_list).strip()


def transcribe_offline(
    audio: bytes,
    status_cb: Optional[Callable[[str], None]] = None,
) -> str:
    """Synchronously transcribe in-memory audio bytes.

    Raises RuntimeError with one of the standardized messages on failure.
    Safe to call from any thread; inference is serialized on `_MODEL_LOCK`.
    """
    if not audio:
        raise RuntimeError("Recording too short")

    model = _load_model(status_cb)

    tmp_path: Optional[str] = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(audio)
            tmp_path = f.name

        try:
            with _MODEL_LOCK:
                text = _transcribe_constrained(model, tmp_path)
        except Exception as e:
            raise RuntimeError(f"Local transcription failed: {e}")

        if not text:
            raise RuntimeError("Local Whisper returned empty transcript")
        return text
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def transcribe_offline_path(
    audio_path: str,
    status_cb: Optional[Callable[[str], None]] = None,
) -> str:
    """Synchronously transcribe an on-disk audio file.

    Cleans up the input file and any `vd_yt_*` parent temp dir on exit,
    matching the historical YouTube-pipeline behavior. Raises RuntimeError
    on failure. Safe to call from any thread.
    """
    model = _load_model(status_cb)

    try:
        try:
            with _MODEL_LOCK:
                text = _transcribe_constrained(model, audio_path)
        except Exception as e:
            raise RuntimeError(f"Local transcription failed: {e}")

        if not text:
            raise RuntimeError("Local Whisper returned empty transcript")
        return text
    finally:
        try:
            p = Path(audio_path)
            if p.exists():
                p.unlink()
            if p.parent.name.startswith("vd_yt_"):
                shutil.rmtree(p.parent, ignore_errors=True)
        except Exception:
            pass


class LocalTranscriptionWorker(QObject):
    done = pyqtSignal(str)
    doneWithTitle = pyqtSignal(str, str)
    failed = pyqtSignal(str)
    statusChanged = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

    @pyqtSlot(bytes)
    def transcribe(self, audio_bytes: bytes) -> None:
        try:
            text = transcribe_offline(audio_bytes, status_cb=self.statusChanged.emit)
        except RuntimeError as e:
            self.failed.emit(str(e))
            return
        self.done.emit(text)

    @pyqtSlot(str, str)
    def transcribe_path(self, audio_path: str, title: str = "") -> None:
        try:
            text = transcribe_offline_path(audio_path, status_cb=self.statusChanged.emit)
        except RuntimeError as e:
            self.failed.emit(str(e))
            return
        self.doneWithTitle.emit(text, title)
