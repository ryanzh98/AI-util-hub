"""Pre-warm offline-feature model caches so the first hotkey fire is instant.

Run from `install_and_run.ps1` after the conda env + deps + voice.pth are in
place. The two caches we materialize here:

1. faster-whisper snapshot (default `large-v3-turbo`, ~1.5 GB) -> HF hub cache.
2. RVC pretrains `hubert_base.pt` + `rmvpe.pt` (~370 MB) -> project root.
   tts-with-rvc writes these to CWD on first inference, not to HF cache.

Best-effort: any failure prints to stdout and exits 0 so the installer keeps
going. Worst case, the user pays the one-time download on first hotkey fire
(the pre-existing behaviour).
"""
from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _log(msg: str) -> None:
    print(msg, flush=True)


def _torch_cuda_ok() -> bool:
    try:
        import torch
        return bool(torch.cuda.is_available())
    except Exception:
        return False


def warm_faster_whisper() -> bool:
    """Construct WhisperModel once. Internal HF cache check makes this a no-op
    on re-runs (~1s) and a 1.5 GB download on first install."""
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        _log(f"  [whisper] import failed: {exc}")
        return False

    model_name = os.environ.get("WHISPER_LOCAL_MODEL", "").strip() or "large-v3-turbo"
    device, compute = ("cuda", "float16") if _torch_cuda_ok() else ("cpu", "int8")
    _log(f"  [whisper] caching {model_name} ({device}/{compute})...")
    try:
        WhisperModel(model_name, device=device, compute_type=compute)
    except Exception as exc:
        if device == "cuda":
            _log(f"  [whisper] CUDA load failed ({exc!r}); retrying on CPU...")
            try:
                WhisperModel(model_name, device="cpu", compute_type="int8")
            except Exception as exc2:
                _log(f"  [whisper] CPU fallback also failed: {exc2!r}")
                return False
        else:
            _log(f"  [whisper] warm-up failed: {exc!r}")
            return False
    _log(f"  [whisper] OK ({model_name} cached).")
    return True


def warm_rvc() -> bool:
    """Load TTS_RVC + run a 1-token dummy synthesis to force HuBERT/RMVPE
    download. Skips the expensive bit if both pretrain .pt files already
    exist at project root (where tts-with-rvc puts them)."""
    voice_pth = ROOT / "models" / "respeaker" / "voice.pth"
    if not voice_pth.exists():
        _log(f"  [rvc] {voice_pth.relative_to(ROOT)} missing; skipping. "
             "Drop a .pth there to enable voice cloning.")
        return False

    hubert = ROOT / "hubert_base.pt"
    rmvpe = ROOT / "rmvpe.pt"
    if hubert.exists() and rmvpe.exists():
        _log("  [rvc] hubert_base.pt + rmvpe.pt already present; pretrain cache OK.")
        return True

    # Pull .env so RESPEAKER_DEVICE etc. match runtime behaviour.
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env", override=False)
    except Exception:
        pass

    # GPU-first per user preference; respeaker_client._load_engine has its own
    # CUDA -> CPU fallback if the GPU init explodes.
    if not _torch_cuda_ok():
        os.environ["RESPEAKER_DEVICE"] = "cpu"
        _log("  [rvc] CUDA unavailable; pre-warm will run on CPU (slower one-time cost).")

    try:
        from app.respeaker_client import _load_engine
    except ImportError as exc:
        _log(f"  [rvc] import failed: {exc}")
        return False

    _log("  [rvc] loading engine (downloads HuBERT + RMVPE, ~370 MB on first install)...")
    try:
        engine = _load_engine(status_cb=lambda m: _log(f"  [rvc] {m}"))
    except Exception as exc:
        _log(f"  [rvc] engine load failed: {exc!r}")
        traceback.print_exc()
        return False

    _log("  [rvc] running 1-token dummy synthesis to flush pretrain downloads...")
    try:
        out_wav = engine(
            text="ok",
            pitch=0,
            index_rate=0.75,
            filter_radius=3,
            protect=0.33,
            rms_mix_rate=0.5,
        )
        if out_wav and Path(out_wav).exists():
            try:
                Path(out_wav).unlink()
            except OSError:
                pass
    except Exception as exc:
        _log(f"  [rvc] dummy synthesis failed: {exc!r} (engine cached; pretrains may need first-fire download).")
        return True

    _log("  [rvc] OK (engine + pretrains cached).")
    return True


def main() -> int:
    _log("Pre-warming offline-feature caches (one-time on first install)...")
    whisper_ok = warm_faster_whisper()
    rvc_ok = warm_rvc()
    if whisper_ok and rvc_ok:
        _log("All offline models cached. First hotkey fire will be instant.")
    else:
        _log("Pre-warm partial. Failed models will lazy-download on first hotkey fire.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
