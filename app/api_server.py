"""FastAPI + uvicorn HTTP server that exposes every launcher shortcut over REST.

Lets a GPU-less guest VM (or any remote process) invoke transcription, grammar
fix, AI actions, and snippets on the host machine. Routes are keyed by `slot`
(see `effective_slot(item)` in `actions_config`).

The host's tray controller owns an `APIServer` instance and calls `start()` /
`stop()` during its own lifecycle. `get_config` is invoked per-request so the
slot index always reflects the latest in-memory config — no stale state after
a manager save.
"""

from __future__ import annotations

import logging
import os
import shutil
import threading
import time
import traceback
from pathlib import Path
from typing import Callable, Dict, Optional

import uvicorn
from fastapi import Depends, FastAPI, File, Header, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .actions_config import Config, Item, effective_slot
from .clipboard_action_worker import run_action
from .grammar_online_client import fix_grammar
from .local_whisper_client import transcribe_offline, transcribe_offline_path
from .respeaker_client import respeak
from .whisper_client import transcribe_online
from .youtube_audio_worker import download_youtube


log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class HealthOut(BaseModel):
    ok: bool = True
    version: int = 1


class ItemListEntry(BaseModel):
    id: str
    slot: str
    type: str
    name: str
    emoji: str
    enabled: bool


class TextIn(BaseModel):
    text: str


class UrlIn(BaseModel):
    url: str


class AIRequestIn(BaseModel):
    text: str
    model: Optional[str] = None
    temperature: Optional[float] = None


class TextOut(BaseModel):
    text: str


class UrlOut(BaseModel):
    url: str


class TitledTextOut(BaseModel):
    text: str
    title: str


class ErrorOut(BaseModel):
    error: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_token_dep(token: str):
    """Bearer-token dependency factory. If `token` is empty, the check is a no-op."""

    def _check(authorization: str = Header(default="")) -> None:
        if not token:
            return
        if not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="missing bearer token")
        if authorization[7:] != token:
            raise HTTPException(status_code=401, detail="invalid token")

    return _check


def _build_slot_index(cfg: Config) -> Dict[str, Item]:
    """Build slot -> Item, preferring the lowest-`order` item on duplicates.

    Logs a warning each time a duplicate is detected so misconfiguration is
    visible in the host's log stream. (Idempotent — fine to re-log per request.)
    """
    sorted_items = sorted(cfg.items, key=lambda it: it.order)
    index: Dict[str, Item] = {}
    for it in sorted_items:
        slot = effective_slot(it)
        if slot in index:
            log.warning(
                "Duplicate slot %r — keeping %r (order=%d), ignoring %r (order=%d)",
                slot,
                index[slot].id,
                index[slot].order,
                it.id,
                it.order,
            )
            continue
        index[slot] = it
    return index


def _server_error(exc: BaseException) -> JSONResponse:
    """Wrap an unexpected exception in a 500 with a generic message and log it."""
    log.error("Unhandled API error: %s\n%s", exc, traceback.format_exc())
    return JSONResponse(status_code=500, content={"error": "internal server error"})


# ---------------------------------------------------------------------------
# APIServer
# ---------------------------------------------------------------------------


class APIServer:
    """HTTP gateway around the launcher's pure-function worker layer."""

    def __init__(self, get_config: Callable[[], Config]):
        self._get_config = get_config

        enabled_raw = os.environ.get("LAUNCHER_API_ENABLED", "1").strip()
        self._enabled = enabled_raw.lower() == "1"

        self._host = os.environ.get("LAUNCHER_API_HOST", "0.0.0.0").strip() or "0.0.0.0"

        port_raw = os.environ.get("LAUNCHER_API_PORT", "8009").strip()
        try:
            self._port = int(port_raw)
        except ValueError:
            self._port = 8009

        self._token = os.environ.get("LAUNCHER_API_TOKEN", "").strip()

        self._app: Optional[FastAPI] = None
        self._server: Optional[uvicorn.Server] = None
        self._thread: Optional[threading.Thread] = None

    # -- lifecycle ----------------------------------------------------------

    def start(self) -> None:
        if not self._enabled:
            log.info("LAUNCHER_API_ENABLED is off; API server not started.")
            return
        if self._server is not None:
            log.info("API server already running.")
            return

        self._app = self._build_app()
        config = uvicorn.Config(
            self._app,
            host=self._host,
            port=self._port,
            log_level="warning",
            access_log=False,
            log_config=None,
        )
        self._server = uvicorn.Server(config)
        self._thread = threading.Thread(
            target=self._server.run,
            daemon=True,
            name="LauncherAPIServer",
        )
        self._thread.start()

        # Wait briefly for the server to actually bind so `is_running()` and
        # `bound_url` are accurate immediately after `start()` returns.
        deadline = time.time() + 2.0
        while time.time() < deadline and not getattr(self._server, "started", False):
            time.sleep(0.05)

    def stop(self) -> None:
        if self._server is None:
            return
        self._server.should_exit = True
        if self._thread is not None:
            self._thread.join(timeout=3.0)
        self._server = None
        self._thread = None
        self._app = None

    def is_running(self) -> bool:
        return self._server is not None and getattr(self._server, "started", False)

    @property
    def bound_url(self) -> str:
        if not self.is_running():
            return ""
        return f"http://{self._host}:{self._port}"

    # -- app builder --------------------------------------------------------

    def _build_app(self) -> FastAPI:
        app = FastAPI(title="Voice Detection Launcher API", version="1")

        auth = _make_token_dep(self._token)
        get_config = self._get_config

        # ---- /healthz : auth-exempt -------------------------------------

        @app.get("/healthz", response_model=HealthOut)
        def healthz() -> HealthOut:
            return HealthOut()

        # ---- /items : authed listing ------------------------------------

        @app.get("/items", response_model=list[ItemListEntry], dependencies=[Depends(auth)])
        def list_items() -> list[ItemListEntry]:
            cfg = get_config()
            sorted_items = sorted(cfg.items, key=lambda it: it.order)
            return [
                ItemListEntry(
                    id=it.id,
                    slot=effective_slot(it),
                    type=it.type,
                    name=it.name,
                    emoji=it.emoji,
                    enabled=bool(it.enabled),
                )
                for it in sorted_items
            ]

        # ---- shared slot resolver --------------------------------------

        def _resolve_slot(slot: str):
            """Return (item, None) on hit, or (None, JSONResponse) on miss/disabled."""
            cfg = get_config()
            index = _build_slot_index(cfg)
            item = index.get(slot)
            if item is None:
                return None, JSONResponse(status_code=404, content={"error": "no such slot"})
            if not item.enabled:
                return None, JSONResponse(status_code=409, content={"error": "item disabled"})
            return item, None

        # ---- GET /slot/{slot} : snippet-only read -----------------------

        @app.get("/slot/{slot}", dependencies=[Depends(auth)])
        def slot_get(slot: str):
            item, err = _resolve_slot(slot)
            if err is not None:
                return err
            assert item is not None  # narrowing

            if item.type != "snippet":
                return JSONResponse(
                    status_code=405,
                    content={"error": "use POST for this item type"},
                )
            if (item.kind or "") == "url":
                return {"url": item.body or ""}
            return {"text": item.body or ""}

        # ---- POST /slot/{slot} : dispatch by item type ------------------

        @app.post("/slot/{slot}")
        async def slot_post(
            slot: str,
            request: Request,
            _auth: None = Depends(auth),
        ):
            item, err = _resolve_slot(slot)
            if err is not None:
                return err
            assert item is not None

            try:
                # ---- system actions ------------------------------------
                if item.type == "system":
                    subtype = item.subtype or ""

                    if subtype in ("voice_online", "voice_offline"):
                        return await _handle_voice(request, subtype)

                    if subtype == "grammar":
                        return await _handle_grammar(request)

                    if subtype == "youtube":
                        return await _handle_youtube(request)

                    if subtype == "voice_respeaker":
                        return await _handle_respeaker(request)

                    return JSONResponse(
                        status_code=400,
                        content={"error": f"unsupported system subtype: {subtype!r}"},
                    )

                # ---- AI actions ----------------------------------------
                if item.type == "ai":
                    return await _handle_ai(request, item)

                # ---- snippets ------------------------------------------
                if item.type == "snippet":
                    if (item.kind or "") == "url":
                        return {"url": item.body or ""}
                    return {"text": item.body or ""}

                return JSONResponse(
                    status_code=400,
                    content={"error": f"unsupported item type: {item.type!r}"},
                )
            except HTTPException:
                raise
            except RuntimeError as e:
                # Pure-function worker failures bubble up here.
                return JSONResponse(status_code=500, content={"error": str(e)})
            except Exception as e:
                return _server_error(e)

        # ---- handler: voice ---------------------------------------------

        async def _handle_voice(request: Request, subtype: str):
            audio_bytes = await _read_audio(request)
            if not audio_bytes:
                return JSONResponse(
                    status_code=400,
                    content={"error": "empty audio body"},
                )
            try:
                if subtype == "voice_online":
                    text = await run_in_threadpool(transcribe_online, audio_bytes)
                else:
                    text = await run_in_threadpool(transcribe_offline, audio_bytes)
            except RuntimeError as e:
                return JSONResponse(status_code=500, content={"error": str(e)})
            except Exception as e:
                return _server_error(e)
            return {"text": text}

        # ---- handler: grammar -------------------------------------------

        async def _handle_grammar(request: Request):
            req = await _parse_json_model(request, TextIn)
            try:
                fixed = await run_in_threadpool(fix_grammar, req.text)
            except RuntimeError as e:
                return JSONResponse(status_code=500, content={"error": str(e)})
            except Exception as e:
                return _server_error(e)
            return {"text": fixed}

        # ---- handler: respeaker -----------------------------------------

        async def _handle_respeaker(request: Request):
            from fastapi.responses import FileResponse
            req = await _parse_json_model(request, TextIn)
            try:
                wav_path = await run_in_threadpool(respeak, req.text)
            except RuntimeError as e:
                return JSONResponse(status_code=500, content={"error": str(e)})
            except Exception as e:
                return _server_error(e)
            return FileResponse(wav_path, media_type="audio/wav",
                                filename=Path(wav_path).name)

        # ---- handler: youtube -------------------------------------------

        async def _handle_youtube(request: Request):
            req = await _parse_json_model(request, UrlIn)
            try:
                path, title = await run_in_threadpool(download_youtube, req.url)
            except RuntimeError as e:
                return JSONResponse(status_code=500, content={"error": str(e)})
            except Exception as e:
                return _server_error(e)

            path_str = str(path)
            try:
                try:
                    text = await run_in_threadpool(transcribe_offline_path, path_str)
                except RuntimeError as e:
                    return JSONResponse(status_code=500, content={"error": str(e)})
                except Exception as e:
                    return _server_error(e)
                return {"text": text, "title": title}
            finally:
                # `transcribe_offline_path` already cleans up on its own, but
                # we belt-and-suspenders here in case it raised before the
                # finally block ran (e.g. model load failure pre-removal).
                try:
                    p = Path(path_str)
                    if p.exists():
                        try:
                            p.unlink()
                        except OSError:
                            pass
                    if p.parent.name.startswith("vd_yt_") and p.parent.exists():
                        shutil.rmtree(p.parent, ignore_errors=True)
                except Exception:
                    pass

        # ---- handler: AI action -----------------------------------------

        async def _handle_ai(request: Request, item: Item):
            req = await _parse_json_model(request, AIRequestIn)

            override_model = (req.model or "").strip() if req.model else ""
            model = override_model or (item.model or "")

            if req.temperature is not None:
                temperature = float(req.temperature)
            elif item.temperature is not None:
                temperature = float(item.temperature)
            else:
                temperature = 0.2

            prompt = item.prompt or ""

            try:
                result = await run_in_threadpool(
                    run_action, prompt, model, temperature, req.text
                )
            except RuntimeError as e:
                return JSONResponse(status_code=500, content={"error": str(e)})
            except Exception as e:
                return _server_error(e)
            return {"text": result}

        return app


# ---------------------------------------------------------------------------
# Request body helpers (module-level so they're easy to test/reuse)
# ---------------------------------------------------------------------------


async def _read_audio(request: Request) -> bytes:
    """Read audio from raw `audio/wav` body or a multipart `audio` field.

    Returns the raw bytes (possibly empty). Caller decides what to do with
    empty input.
    """
    content_type = (request.headers.get("content-type") or "").lower()
    if content_type.startswith("multipart/form-data"):
        form = await request.form()
        upload = form.get("audio")
        if isinstance(upload, UploadFile):
            return await upload.read()
        if isinstance(upload, (bytes, bytearray)):
            return bytes(upload)
        if isinstance(upload, str):
            return upload.encode("utf-8", errors="ignore")
        return b""
    return await request.body()


async def _parse_json_model(request: Request, model_cls):
    """Parse the request body as JSON into `model_cls`, raising 422 on failure."""
    try:
        payload = await request.json()
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"invalid JSON body: {e}")
    try:
        return model_cls(**(payload or {}))
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"invalid request body: {e}")
