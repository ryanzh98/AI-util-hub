import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import Callable, Optional, Tuple

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

from .paths import app_base_dir


# Substrings yt-dlp's error message contains when YouTube blocks the request
# behind their "are you a bot?" gate. Case-insensitive match.
_BOT_DETECTION_SIGNALS = (
    "sign in to confirm",
    "not a bot",
    "confirm you're not a bot",
)

# Substrings yt-dlp emits when Chrome's cookie DB is locked by a running
# Chrome process, or when Chrome 127+ app-bound-encrypted (v20) cookies can't
# be decrypted. Both surface as "use cookies.txt instead" situations.
_COOKIE_EXTRACTION_FAILURES = (
    "could not copy chrome cookie database",
    "failed to decrypt with dpapi",
    "could not copy",  # generic copy-failure fallback for other chromium browsers
)


def _ensure_bin_on_path() -> None:
    """Prepend `<app>/bin` to PATH so yt-dlp can find bundled helpers.

    yt-dlp spawns subprocesses for ffmpeg (post-processing) and for the
    JavaScript runtime that solves YouTube's n-challenge — both look up the
    executable by name on PATH. We drop `deno.exe` and `ffmpeg.exe` into
    `bin/` so the feature works without a system-wide install.
    """
    bin_dir = app_base_dir() / "bin"
    if not bin_dir.is_dir():
        return
    bin_str = str(bin_dir)
    existing = os.environ.get("PATH", "")
    if bin_str.lower() in existing.lower():
        return
    os.environ["PATH"] = bin_str + os.pathsep + existing


def _default_cookies_file() -> Path:
    """Where the app looks for a manually-exported Netscape cookies.txt.

    Use a Chrome extension like "Get cookies.txt LOCALLY" to export your
    youtube.com cookies and save the file at this path. Reading cookies via
    `cookiesfrombrowser` fails when Chrome is running (file lock) and on
    Chrome 127+ where new cookies use app-bound encryption that can't be
    decrypted outside the Chrome process.
    """
    return app_base_dir() / "secrets" / "youtube_cookies.txt"


class YoutubeBotDetectedError(RuntimeError):
    """Raised when yt-dlp's failure looks like YouTube's bot-detection gate.

    Caller should prompt the user for a browser to extract cookies from,
    persist the choice via `YOUTUBE_COOKIE_BROWSER`, and retry.
    """
    pass


def _is_bot_detection(msg: str) -> bool:
    lower = (msg or "").lower()
    return any(s in lower for s in _BOT_DETECTION_SIGNALS)


def _is_cookie_extraction_failure(msg: str) -> bool:
    lower = (msg or "").lower()
    return any(s in lower for s in _COOKIE_EXTRACTION_FAILURES)


def _resolve_cookies_file() -> Optional[Path]:
    """Return the cookies.txt path the user wants us to use, if any.

    Precedence: `YOUTUBE_COOKIES_FILE` env var (if set and exists) > the
    default `<app>/secrets/youtube_cookies.txt` (if exists). Returns None
    when no usable file is found.
    """
    override = (os.environ.get("YOUTUBE_COOKIES_FILE") or "").strip().strip('"').strip("'")
    if override:
        p = Path(override).expanduser()
        if not p.is_absolute():
            p = app_base_dir() / p
        if p.is_file():
            return p
    default = _default_cookies_file()
    if default.is_file():
        return default
    return None


def download_youtube(
    url: str,
    status_cb: Optional[Callable[[str], None]] = None,
) -> Tuple[Path, str]:
    """Download audio from a YouTube URL synchronously.

    Returns (audio_path, title). Raises RuntimeError with the same messages the
    Qt slot historically emits via `failed`. Does NOT delete the downloaded file
    on success — caller owns cleanup. On failure, the temp dir is removed.

    Cookie precedence (first match wins):
      1. `YOUTUBE_COOKIES_FILE` — path to a Netscape cookies.txt (manual export).
      2. `<app>/secrets/youtube_cookies.txt` — same format, default location.
      3. `YOUTUBE_COOKIE_BROWSER` — yt-dlp pulls live cookies from this browser
         (e.g. "chrome", "edge"). Fails on Windows when Chrome is running
         (file lock) or when cookies use Chrome 127+ app-bound encryption,
         in which case we transparently fall back to (1)/(2) if available.
    """

    def _emit(msg: str) -> None:
        if status_cb is not None:
            status_cb(msg)

    _ensure_bin_on_path()

    try:
        import yt_dlp
    except ImportError as e:
        raise RuntimeError(
            f"yt-dlp not installed ({e}). Run: pip install -r requirements.txt"
        )

    tmp_dir = Path(tempfile.mkdtemp(prefix="vd_yt_"))
    last_status_ts = [0.0]
    _emit("Starting download…")

    def hook(d: dict) -> None:
        status = d.get("status")
        if status == "downloading":
            now = time.monotonic()
            if now - last_status_ts[0] < 0.25:
                return
            last_status_ts[0] = now
            downloaded = d.get("downloaded_bytes") or 0
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            if total:
                pct = (downloaded / total) * 100.0
                _emit(f"Downloading… {pct:.0f}%")
            else:
                mb = downloaded / (1024 * 1024)
                _emit(f"Downloading… {mb:.1f} MB")
        elif status == "finished":
            _emit("Download complete, preparing audio…")

    base_opts = {
        "format": "bestaudio/best",
        "outtmpl": str(tmp_dir / "%(id)s.%(ext)s"),
        "noprogress": True,
        "quiet": True,
        "no_warnings": True,
        "restrictfilenames": True,
        "noplaylist": True,
        "concurrent_fragment_downloads": 4,
        "progress_hooks": [hook],
    }

    cookies_file = _resolve_cookies_file()
    browser = os.environ.get("YOUTUBE_COOKIE_BROWSER", "").strip().lower()
    profile = os.environ.get("YOUTUBE_COOKIE_PROFILE", "").strip()

    # Build attempt list: cookies.txt is preferred when available because it
    # avoids both the Chrome file-lock issue (#7271) and Chrome 127+'s
    # app-bound encryption (#10927). Fall back to live browser extraction.
    attempts: list[tuple[str, dict]] = []
    if cookies_file is not None:
        attempts.append((
            f"cookies.txt ({cookies_file.name})",
            {**base_opts, "cookiefile": str(cookies_file)},
        ))
    if browser:
        # yt-dlp expects a tuple: (browser_name, profile, keyring, container).
        browser_tuple: tuple = (browser, profile or None, None, None)
        attempts.append((
            f"{browser} cookies" + (f" / {profile}" if profile else ""),
            {**base_opts, "cookiesfrombrowser": browser_tuple},
        ))
    if not attempts:
        attempts.append(("no cookies", dict(base_opts)))

    last_err: Optional[Exception] = None
    for label, ydl_opts in attempts:
        _emit(f"Using {label}…")
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if isinstance(info, dict) and "entries" in info and info["entries"]:
                    info = info["entries"][0]
                filename = ydl.prepare_filename(info)

            audio_path = Path(filename)
            if not audio_path.exists():
                # yt-dlp sometimes rewrites the extension after merging.
                candidates = [p for p in tmp_dir.iterdir() if p.is_file()]
                if not candidates:
                    raise FileNotFoundError(
                        f"Downloaded file not found in {tmp_dir}"
                    )
                audio_path = max(candidates, key=lambda p: p.stat().st_mtime)

            title = (
                (info.get("title") if isinstance(info, dict) else None)
                or (info.get("id") if isinstance(info, dict) else None)
                or "youtube_transcript"
            )
            _emit("Audio ready, queuing transcription…")
            return audio_path, str(title)

        except Exception as e:
            last_err = e
            msg = str(e)
            # If browser cookie extraction blew up (locked DB / ABE-encrypted
            # cookies on Chrome 127+) and we still have a cookies.txt-or-other
            # attempt queued, fall through silently.
            if _is_cookie_extraction_failure(msg) and attempts.index((label, ydl_opts)) < len(attempts) - 1:
                _emit("Browser cookies unusable, falling back…")
                continue
            break

    try:
        shutil.rmtree(tmp_dir, ignore_errors=True)
    except Exception:
        pass
    msg = str(last_err) if last_err else "unknown error"
    if _is_bot_detection(msg):
        raise YoutubeBotDetectedError(msg)
    if _is_cookie_extraction_failure(msg):
        raise RuntimeError(
            "YouTube download failed: couldn't read Chrome cookies "
            "(Chrome is running, or cookies use app-bound encryption). "
            "Export your YouTube cookies to a Netscape cookies.txt — e.g. "
            "via the 'Get cookies.txt LOCALLY' Chrome extension — and save "
            f"it at {_default_cookies_file()}, then retry."
        )
    raise RuntimeError(f"YouTube download failed: {msg}")


class YoutubeAudioWorker(QObject):
    audioReady = pyqtSignal(str, str)
    failed = pyqtSignal(str)
    botDetected = pyqtSignal(str)  # carries the original URL for retry
    statusChanged = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

    @pyqtSlot(str)
    def process(self, url: str) -> None:
        try:
            path, title = download_youtube(url, status_cb=self.statusChanged.emit)
        except YoutubeBotDetectedError:
            self.botDetected.emit(url)
            return
        except RuntimeError as e:
            self.failed.emit(str(e))
            return
        except Exception as e:
            self.failed.emit(f"YouTube download failed: {e}")
            return
        self.audioReady.emit(str(path), title)
