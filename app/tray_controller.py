import os
import re
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QObject, Qt, QThread, QUrl, pyqtSignal
from PyQt6.QtGui import QAction, QDesktopServices, QGuiApplication, QIcon
from PyQt6.QtNetwork import QLocalServer, QLocalSocket
from PyQt6.QtWidgets import QApplication, QInputDialog, QMenu, QSystemTrayIcon

from .actions_config import (
    Config,
    Item,
    default_config,
    default_config_path,
    find_item,
    load_config,
    save_config,
)
from .api_server import APIServer
from .clipboard_action_worker import ClipboardActionWorker
from .grammar_online_client import OnlineGrammarFixWorker
from .hotkey_manager import HotkeyManager
from .launcher_window import LauncherWindow
from .local_whisper_client import LocalTranscriptionWorker
from .manager_window import ManagerWindow
from .recorder_window import RecorderWindow
from .respeaker_client import RespeakerWorker
from .startup_manager import ensure_start_menu_shortcut, ensure_startup_shortcut
from .tts_window import TtsWindow
from .whisper_client import TranscriptionWorker
from .youtube_audio_worker import YoutubeAudioWorker
from .youtube_window import YoutubeWindow

SINGLETON_KEY = "VoiceDetection:singleton"
APP_NAME = "Shortcut"

MODE_ONLINE = "online"
MODE_OFFLINE = "offline"
MODE_RESPEAKER = "respeaker"


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _tray_icon() -> QIcon:
    from .paths import bundled_data_dir
    ico = bundled_data_dir() / "assets" / "app_icon.ico"
    if ico.exists():
        qi = QIcon(str(ico))
        if not qi.isNull():
            return qi
    return QIcon()


def already_running() -> bool:
    sock = QLocalSocket()
    sock.connectToServer(SINGLETON_KEY)
    if sock.waitForConnected(150):
        sock.disconnectFromServer()
        return True
    return False


def _format_hotkey(raw: str) -> str:
    if not raw:
        return "—"
    parts = raw.split("+")
    out = []
    for p in parts:
        token = p.strip("<>").lower()
        out.append({"ctrl": "Ctrl", "alt": "Alt", "shift": "Shift", "cmd": "Win",
                    "space": "Space", "enter": "Enter", "tab": "Tab"}.get(token, token.upper()))
    return "+".join(out)


class TrayController(QObject):
    transcribeOnlineRequested = pyqtSignal(bytes)
    transcribeOfflineRequested = pyqtSignal(bytes)
    fixGrammarRequested = pyqtSignal(str)
    youtubeRequested = pyqtSignal(str)
    clipboardActionRequested = pyqtSignal(str, str, float, str)
    respeakRequested = pyqtSignal(str, str, str, dict)  # text, model_path, index_path, settings
    replayRequested = pyqtSignal(str)  # absolute WAV path to re-play

    def __init__(self, app: QApplication):
        super().__init__()
        self._app = app

        QLocalServer.removeServer(SINGLETON_KEY)
        self._server = QLocalServer(self)
        self._server.listen(SINGLETON_KEY)

        self._config_path = default_config_path()
        self._config = load_config(self._config_path)
        if not self._config_path.exists():
            try:
                save_config(self._config_path, self._config)
            except Exception:
                pass

        self._tray = QSystemTrayIcon(_tray_icon(), self)
        self._tray.activated.connect(self._on_tray_activated)
        self._build_menu()
        self._refresh_tooltip()
        self._tray.show()

        self._window: RecorderWindow | None = None
        self._pending_mode: str = MODE_ONLINE
        self._yt_window: YoutubeWindow | None = None
        self._yt_busy: bool = False
        self._action_busy: bool = False
        self._action_busy_id: str | None = None
        self._launcher: LauncherWindow | None = None
        self._manager: ManagerWindow | None = None
        self._tts_window: TtsWindow | None = None

        self._hotkey = HotkeyManager(self)
        self._hotkey.fired.connect(self._on_hotkey_fired, Qt.ConnectionType.QueuedConnection)
        self._hotkey.error.connect(self._on_hotkey_error, Qt.ConnectionType.QueuedConnection)
        self._hotkey.rebind(self._config.items, self._config.launcher_hotkey)
        self._hotkey.start()

        self._tx_thread = QThread(self)
        self._tx_worker = TranscriptionWorker()
        self._tx_worker.moveToThread(self._tx_thread)
        self.transcribeOnlineRequested.connect(self._tx_worker.transcribe)
        self._tx_worker.done.connect(self._on_transcript_done)
        self._tx_worker.failed.connect(self._on_transcript_failed)
        self._tx_thread.start()

        self._local_thread = QThread(self)
        self._local_worker = LocalTranscriptionWorker()
        self._local_worker.moveToThread(self._local_thread)
        self.transcribeOfflineRequested.connect(self._local_worker.transcribe)
        self._local_worker.done.connect(self._on_transcript_done)
        self._local_worker.failed.connect(self._on_transcript_failed)
        self._local_worker.statusChanged.connect(self._on_local_status)
        self._local_thread.start()

        self._grammar_thread = QThread(self)
        self._grammar_worker = OnlineGrammarFixWorker()
        self._grammar_worker.moveToThread(self._grammar_thread)
        self.fixGrammarRequested.connect(self._grammar_worker.fix)
        self._grammar_worker.done.connect(self._on_grammar_done)
        self._grammar_worker.failed.connect(self._on_grammar_failed)
        self._grammar_thread.start()

        self._yt_thread = QThread(self)
        self._yt_worker = YoutubeAudioWorker()
        self._yt_worker.moveToThread(self._yt_thread)
        self.youtubeRequested.connect(self._yt_worker.process)
        self._yt_worker.audioReady.connect(self._local_worker.transcribe_path)
        self._yt_worker.failed.connect(self._on_youtube_failed)
        self._yt_worker.botDetected.connect(self._on_youtube_bot_detected)
        self._yt_worker.statusChanged.connect(self._on_local_status)
        self._local_worker.doneWithTitle.connect(self._on_youtube_transcript_done)
        self._yt_thread.start()

        self._action_thread = QThread(self)
        self._action_worker = ClipboardActionWorker()
        self._action_worker.moveToThread(self._action_thread)
        self.clipboardActionRequested.connect(self._action_worker.run)
        self._action_worker.done.connect(self._on_action_done)
        self._action_worker.failed.connect(self._on_action_failed)
        self._action_thread.start()

        self._respeaker_thread = QThread(self)
        self._respeaker_worker = RespeakerWorker()
        self._respeaker_worker.moveToThread(self._respeaker_thread)
        self.respeakRequested.connect(self._respeaker_worker.speakWithSettings)
        self.replayRequested.connect(self._respeaker_worker.replayWav)
        self._respeaker_worker.done.connect(self._on_respeak_done)
        self._respeaker_worker.failed.connect(self._on_respeak_failed)
        self._respeaker_worker.statusChanged.connect(self._on_local_status)
        self._respeaker_thread.start()
        self._respeak_busy: bool = False

        self._api = APIServer(lambda: self._config)
        try:
            self._api.start()
        except Exception as e:
            self._toast(f"API server failed to start: {e}",
                        QSystemTrayIcon.MessageIcon.Warning, title="HTTP API")

        ensure_startup_shortcut()
        ensure_start_menu_shortcut()

        if self._tray.supportsMessages():
            api_line = (f" · API on {self._api.bound_url}"
                        if self._api.is_running() else "")
            self._tray.showMessage(
                APP_NAME,
                f"Open the launcher with {_format_hotkey(self._config.launcher_hotkey)}. "
                f"Manage shortcuts from the tray menu.{api_line}",
                _tray_icon(),
                3500,
            )

    # ── menu / tooltip ──────────────────────────────────────────

    def _build_menu(self) -> None:
        menu = QMenu()
        launcher_action = QAction(
            f"Open launcher ({_format_hotkey(self._config.launcher_hotkey)})", menu
        )
        launcher_action.triggered.connect(self._open_launcher)
        menu.addAction(launcher_action)

        manage_action = QAction("Manage shortcuts…", menu)
        manage_action.triggered.connect(self._open_manager)
        menu.addAction(manage_action)

        menu.addSeparator()

        startup_action = QAction("Re-add to startup", menu)
        startup_action.triggered.connect(lambda: ensure_startup_shortcut())
        menu.addAction(startup_action)

        menu.addSeparator()

        quit_action = QAction("Quit", menu)
        quit_action.triggered.connect(self.shutdown)
        menu.addAction(quit_action)

        self._tray.setContextMenu(menu)

    def _refresh_tooltip(self) -> None:
        parts = [f"{APP_NAME} — {_format_hotkey(self._config.launcher_hotkey)} (launcher)"]
        for it in sorted(self._config.items, key=lambda i: i.order):
            if it.enabled and it.hotkey:
                parts.append(f"{_format_hotkey(it.hotkey)} {it.name}")
        self._tray.setToolTip(" · ".join(parts[:5]))

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self._open_launcher()

    # ── hotkey dispatch ─────────────────────────────────────────

    def _on_hotkey_fired(self, item_id: str) -> None:
        if item_id == HotkeyManager.LAUNCHER_ID:
            self._open_launcher()
            return
        item = find_item(self._config, item_id)
        if item is None or not item.enabled:
            return
        self._dispatch(item)

    def _on_hotkey_error(self, msg: str) -> None:
        if self._tray.supportsMessages():
            self._tray.showMessage(
                APP_NAME, msg, QSystemTrayIcon.MessageIcon.Warning, 5000
            )

    # ── launcher ────────────────────────────────────────────────

    def _open_launcher(self) -> None:
        if self._launcher is None:
            self._launcher = LauncherWindow(self._config)
            self._launcher.fireRequested.connect(self._on_launcher_fire)
            self._launcher.manageRequested.connect(self._open_manager)
            self._launcher.closeRequested.connect(self._on_launcher_close)
        self._launcher.set_config(self._config)
        self._launcher.present()

    def _on_launcher_fire(self, item_id: str) -> None:
        item = find_item(self._config, item_id)
        if item is None or not item.enabled:
            return
        self._dispatch(item)

    def _on_launcher_close(self) -> None:
        if self._launcher is not None:
            self._launcher.hide()

    # ── manager ─────────────────────────────────────────────────

    def _open_manager(self) -> None:
        if self._launcher is not None:
            self._launcher.hide()
        if self._manager is None:
            self._manager = ManagerWindow(self._config, self._config_path)
            self._manager.configChanged.connect(self._on_config_changed)
            self._manager.closeRequested.connect(self._on_manager_close)
        else:
            self._manager.set_config(self._config)
        self._manager.present()

    def _on_manager_close(self) -> None:
        if self._manager is not None:
            self._manager.hide()

    def _on_config_changed(self, new_config: Config) -> None:
        self._config = new_config
        self._hotkey.rebind(self._config.items, self._config.launcher_hotkey)
        if self._launcher is not None:
            self._launcher.set_config(self._config)
        self._build_menu()
        self._refresh_tooltip()

    # ── dispatch table ──────────────────────────────────────────

    def _dispatch(self, item: Item) -> None:
        if item.type == "system":
            sub = item.subtype or ""
            if sub == "voice_online":
                self._open_recorder(MODE_ONLINE)
            elif sub == "voice_offline":
                self._open_recorder(MODE_OFFLINE)
            elif sub == "voice_respeaker":
                if self._respeak_busy:
                    self._toast("Voice playback already running. Wait for it to finish.",
                                QSystemTrayIcon.MessageIcon.Warning, title="Re-speaker")
                    return
                self._open_recorder(MODE_RESPEAKER)
            elif sub == "voice_tts":
                self._open_tts_window()
            elif sub == "grammar":
                self._fire_grammar()
            elif sub == "youtube":
                self._open_youtube_input()
            return

        if item.type == "ai":
            self._fire_ai_action(item)
            return

        if item.type == "snippet":
            self._fire_snippet(item)
            return

    # ── system: recorder ────────────────────────────────────────

    def _open_recorder(self, mode: str) -> None:
        if self._window is not None:
            if self._window.isVisible():
                self._window.raise_()
                self._window.activateWindow()
            return
        self._pending_mode = mode
        self._window = RecorderWindow()
        self._window.recordingStopped.connect(self._on_recording_stopped)
        self._window.recordingCancelled.connect(self._on_recording_cancelled)
        self._window.destroyed.connect(self._on_window_destroyed)
        if mode == MODE_RESPEAKER:
            it = find_item(self._config, "sys-voice-respeaker")
            self._window.set_voice_by_model_path(it.voice_model_path if it else None)
            self._window.set_voice_settings(_item_voice_settings(it))
            self._window.voiceChanged.connect(
                lambda label, mp, ip: self._on_voice_changed("sys-voice-respeaker", mp, ip)
            )
            self._window.voiceSettingsChanged.connect(
                lambda d: self._on_voice_settings_changed("sys-voice-respeaker", d)
            )
            # Recorder's Replay button uses the same plumbing as TTS's:
            # forward to the worker's replayWav slot via the existing
            # replayRequested signal so we don't need a parallel pipeline.
            self._window.replayRequested.connect(self._on_recorder_replay_requested)
        self._window.present(mode=mode)

    def _on_window_destroyed(self, *_args) -> None:
        self._window = None

    def _on_recording_stopped(self, audio: bytes) -> None:
        # In respeaker mode the window stays open through TRANSCRIBING → DONE
        # so the user can hit Replay / Save after the cloned voice plays.
        # Online + offline modes have no follow-up, so shut down immediately.
        if self._pending_mode != MODE_RESPEAKER and self._window is not None:
            try:
                self._window.shutdown()
            except Exception:
                pass
        if not audio:
            # If we kept the window open for respeaker mode, close it now
            # since there's nothing to transcribe.
            if self._window is not None:
                try:
                    self._window.shutdown()
                except Exception:
                    pass
            self._toast("Recording too short", QSystemTrayIcon.MessageIcon.Warning)
            return
        self._refresh_tooltip()
        if self._pending_mode in (MODE_OFFLINE, MODE_RESPEAKER):
            self.transcribeOfflineRequested.emit(audio)
        else:
            self.transcribeOnlineRequested.emit(audio)

    def _on_recording_cancelled(self) -> None:
        if self._window is not None:
            try:
                self._window.shutdown()
            except Exception:
                pass

    def _on_transcript_done(self, text: str) -> None:
        self._refresh_tooltip()
        if self._pending_mode == MODE_RESPEAKER:
            self._respeak_busy = True
            self._toast(f"Heard: {_preview(text, 60)}", title="Re-speaker")
            it = find_item(self._config, "sys-voice-respeaker")
            mp = (it.voice_model_path or "") if it else ""
            ip = (it.voice_index_path or "") if it else ""
            self.respeakRequested.emit(text, mp, ip, _item_voice_settings(it))
            return
        QGuiApplication.clipboard().setText(text)
        self._toast(_preview(text), title="Transcript copied")

    def _on_transcript_failed(self, msg: str) -> None:
        self._refresh_tooltip()
        # In respeaker mode the recorder window stayed open through
        # transcription; close it on failure so the user isn't trapped.
        if self._window is not None and self._window.isVisible():
            try:
                self._window.shutdown()
            except Exception:
                pass
        self._toast(msg, QSystemTrayIcon.MessageIcon.Critical, title="Transcription failed")

    def _on_respeak_done(self, wav_path: str) -> None:
        self._respeak_busy = False
        self._refresh_tooltip()
        if self._tts_window is not None and self._tts_window.isVisible():
            self._tts_window.set_last_wav(wav_path)
            self._tts_window.set_busy(False, "Done. Type more to convert again.")
        # Ctrl+Alt+5 keeps its window open through DONE so the user can
        # replay / save — flip it into DONE state now.
        if self._window is not None and self._window.isVisible():
            try:
                self._window.set_done(wav_path)
            except Exception:
                pass

    def _on_recorder_replay_requested(self, wav_path: str) -> None:
        """Bridge the recorder's Replay button → existing replay pipeline."""
        if self._respeak_busy:
            return
        self._respeak_busy = True
        self.replayRequested.emit(wav_path)

    def _on_respeak_failed(self, msg: str) -> None:
        self._respeak_busy = False
        self._refresh_tooltip()
        if self._tts_window is not None and self._tts_window.isVisible():
            self._tts_window.set_busy(False, f"Failed: {msg}")
        # Recorder window (Ctrl+Alt+5 respeaker mode) is stuck in
        # TRANSCRIBING — close it so the user isn't trapped. The toast
        # below carries the error context.
        if self._window is not None and self._window.isVisible():
            try:
                self._window.shutdown()
            except Exception:
                pass
        self._toast(msg, QSystemTrayIcon.MessageIcon.Critical, title="Re-speaker failed")

    # ── TTS window (Ctrl+Alt+6) ─────────────────────────────────

    def _open_tts_window(self) -> None:
        if self._tts_window is None:
            self._tts_window = TtsWindow()
            self._tts_window.textSubmitted.connect(self._on_tts_text_submitted)
            self._tts_window.replayRequested.connect(self._on_tts_replay_requested)
            self._tts_window.voiceChanged.connect(
                lambda label, mp, ip: self._on_voice_changed("sys-tts", mp, ip)
            )
            self._tts_window.voiceSettingsChanged.connect(
                lambda d: self._on_voice_settings_changed("sys-tts", d)
            )
            self._tts_window.closeRequested.connect(lambda: None)
        it = find_item(self._config, "sys-tts")
        self._tts_window.set_voice_by_model_path(it.voice_model_path if it else None)
        self._tts_window.set_voice_settings(_item_voice_settings(it))
        self._tts_window.present()

    def _on_voice_changed(self, item_id: str, model_path: str, index_path: str) -> None:
        it = find_item(self._config, item_id)
        if it is None:
            return
        it.voice_model_path = model_path or None
        it.voice_index_path = index_path or None
        try:
            save_config(self._config_path, self._config)
        except Exception as e:
            self._toast(f"Could not save voice selection: {e}",
                        QSystemTrayIcon.MessageIcon.Warning, title="Voice picker")

    def _on_voice_settings_changed(self, item_id: str, settings: dict) -> None:
        """Merge advanced TTS+RVC settings from the popup into the Item."""
        it = find_item(self._config, item_id)
        if it is None:
            return
        for key, value in settings.items():
            if hasattr(it, key):
                setattr(it, key, value)
        try:
            save_config(self._config_path, self._config)
        except Exception as e:
            self._toast(f"Could not save voice settings: {e}",
                        QSystemTrayIcon.MessageIcon.Warning, title="Voice settings")

    def _on_tts_text_submitted(self, text: str) -> None:
        if self._respeak_busy:
            if self._tts_window is not None:
                self._tts_window.set_busy(True, "Another voice job is running…")
            return
        self._respeak_busy = True
        it = find_item(self._config, "sys-tts")
        mp = (it.voice_model_path or "") if it else ""
        ip = (it.voice_index_path or "") if it else ""
        self.respeakRequested.emit(text, mp, ip, _item_voice_settings(it))

    def _on_tts_replay_requested(self, wav_path: str) -> None:
        if self._respeak_busy:
            if self._tts_window is not None:
                self._tts_window.set_busy(True, "Another voice job is running…")
            return
        self._respeak_busy = True
        self.replayRequested.emit(wav_path)

    def _on_local_status(self, msg: str) -> None:
        self._tray.setToolTip(f"{APP_NAME} — {msg}")

    # ── system: grammar ─────────────────────────────────────────

    def _fire_grammar(self) -> None:
        text = QGuiApplication.clipboard().text()
        if not text or not text.strip():
            self._toast("Clipboard is empty", QSystemTrayIcon.MessageIcon.Warning,
                        title="Fix grammar")
            return
        self._toast(f"Fixing: {_preview(text, 60)}", title="Grammar fix in progress",
                    duration=3000)
        self.fixGrammarRequested.emit(text)

    def _on_grammar_done(self, text: str) -> None:
        self._refresh_tooltip()
        QGuiApplication.clipboard().setText(text)
        self._toast(_preview(text), title="Grammar fixed")

    def _on_grammar_failed(self, msg: str) -> None:
        self._refresh_tooltip()
        self._toast(msg, QSystemTrayIcon.MessageIcon.Critical, title="Grammar fix failed")

    # ── system: youtube ─────────────────────────────────────────

    def _open_youtube_input(self) -> None:
        if self._yt_busy:
            self._toast("A YouTube transcription is already running. Wait for it to finish.",
                        QSystemTrayIcon.MessageIcon.Warning, title="YouTube")
            return
        if self._yt_window is not None and self._yt_window.isVisible():
            self._yt_window.raise_()
            self._yt_window.activateWindow()
            return
        self._yt_window = YoutubeWindow()
        self._yt_window.urlSubmitted.connect(self._on_youtube_url_submitted)
        self._yt_window.cancelled.connect(lambda: None)
        self._yt_window.destroyed.connect(self._on_yt_window_destroyed)
        self._yt_window.present()

    def _on_yt_window_destroyed(self, *_args) -> None:
        self._yt_window = None

    def _on_youtube_url_submitted(self, url: str) -> None:
        self._yt_busy = True
        self._toast("Starting YouTube transcription…", title="YouTube")
        self.youtubeRequested.emit(url)

    def _on_youtube_transcript_done(self, text: str, title: str) -> None:
        self._yt_busy = False
        self._refresh_tooltip()
        QGuiApplication.clipboard().setText(text)
        saved = self._save_youtube_transcript(text, title)
        body = f"Copied + saved → {saved.name}" if saved else "Copied to clipboard"
        self._toast(body, title="YouTube transcript")

    def _on_youtube_failed(self, msg: str) -> None:
        self._yt_busy = False
        self._refresh_tooltip()
        self._toast(msg, QSystemTrayIcon.MessageIcon.Critical, title="YouTube transcribe failed")

    def _on_youtube_bot_detected(self, url: str) -> None:
        """YouTube blocked us. Ask the user which browser they're signed into."""
        self._yt_busy = False
        self._refresh_tooltip()

        browsers = ["chrome", "edge", "firefox", "brave", "opera", "vivaldi"]
        prior = (os.environ.get("YOUTUBE_COOKIE_BROWSER", "").strip().lower()
                 or "chrome")
        try:
            default_idx = browsers.index(prior)
        except ValueError:
            default_idx = 0

        choice, ok = QInputDialog.getItem(
            None,
            "YouTube wants cookies",
            "YouTube blocked the download (\"Sign in to confirm you're not a bot\").\n\n"
            "Pick a browser where you are signed into YouTube — the app will\n"
            "pull cookies from it and retry. The choice is saved for next time.",
            browsers,
            default_idx,
            False,
        )
        if not ok or not choice:
            self._toast("YouTube transcribe cancelled.",
                        QSystemTrayIcon.MessageIcon.Warning, title="YouTube")
            return

        choice = choice.strip().lower()
        os.environ["YOUTUBE_COOKIE_BROWSER"] = choice
        self._persist_env_var("YOUTUBE_COOKIE_BROWSER", choice)

        self._yt_busy = True
        self._toast(f"Retrying with {choice} cookies…", title="YouTube")
        self.youtubeRequested.emit(url)

    def _persist_env_var(self, key: str, value: str) -> None:
        """Write/update KEY=value in the .env file next to the app.

        Best-effort — silently no-ops if .env is unwritable.
        """
        from .paths import app_base_dir
        env_path = app_base_dir() / ".env"
        try:
            lines: list[str] = []
            if env_path.exists():
                with env_path.open("r", encoding="utf-8") as f:
                    lines = f.read().splitlines()
            found = False
            for i, line in enumerate(lines):
                stripped = line.lstrip()
                if stripped.startswith(f"{key}=") or stripped.startswith(f"#{key}="):
                    lines[i] = f"{key}={value}"
                    found = True
                    break
            if not found:
                lines.append(f"{key}={value}")
            with env_path.open("w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
        except Exception:
            pass

    def _save_youtube_transcript(self, text: str, title: str) -> Path | None:
        try:
            out_dir = Path(os.environ.get(
                "YOUTUBE_TRANSCRIPT_DIR",
                str(Path.home() / "Documents" / "voice_detection" / "youtube"),
            ))
            out_dir.mkdir(parents=True, exist_ok=True)
            safe = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", (title or "youtube_transcript"))
            safe = safe.strip(" .")[:120] or "youtube_transcript"
            ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
            p = out_dir / f"{safe}_{ts}.txt"
            p.write_text(text, encoding="utf-8")
            return p
        except Exception:
            return None

    # ── AI Action ───────────────────────────────────────────────

    def _fire_ai_action(self, item: Item) -> None:
        if self._action_busy:
            self._toast("An action is already running", QSystemTrayIcon.MessageIcon.Warning,
                        title=item.name)
            return
        text = QGuiApplication.clipboard().text()
        if not text or not text.strip():
            self._toast("Clipboard is empty", QSystemTrayIcon.MessageIcon.Warning,
                        title=item.name)
            return
        if not item.prompt or not item.prompt.strip():
            self._toast("This action has no prompt configured",
                        QSystemTrayIcon.MessageIcon.Warning, title=item.name)
            return
        self._action_busy = True
        self._action_busy_id = item.id
        if self._launcher is not None and self._launcher.isVisible():
            self._launcher.set_running(item.id)
        self._toast(f"{item.emoji} {item.name} — running…", title="Action")
        self.clipboardActionRequested.emit(
            item.prompt,
            (item.model or ""),
            float(item.temperature if item.temperature is not None else 0.2),
            text,
        )

    def _on_action_done(self, text: str) -> None:
        self._action_busy = False
        self._action_busy_id = None
        if self._launcher is not None:
            self._launcher.set_running(None)
        QGuiApplication.clipboard().setText(text)
        self._toast(_preview(text), title="Action result copied")

    def _on_action_failed(self, msg: str) -> None:
        self._action_busy = False
        self._action_busy_id = None
        if self._launcher is not None:
            self._launcher.set_running(None)
        self._toast(msg, QSystemTrayIcon.MessageIcon.Critical, title="Action failed")

    # ── Snippets ────────────────────────────────────────────────

    def _fire_snippet(self, item: Item) -> None:
        if item.kind == "url":
            url = (item.body or "").strip()
            if not url:
                self._toast("Snippet has no URL", QSystemTrayIcon.MessageIcon.Warning,
                            title=item.name)
                return
            QDesktopServices.openUrl(QUrl(url))
            self._toast(f"Opened {url}", title=item.name)
            return

        body = item.body or ""
        cb = QGuiApplication.clipboard()
        if item.behavior == "append":
            current = cb.text() or ""
            cb.setText(current + body)
        else:
            cb.setText(body)
        self._toast(_preview(body) if body else "(empty)", title=f"{item.emoji} {item.name}")

    # ── helpers ─────────────────────────────────────────────────

    def _toast(
        self,
        body: str,
        kind: QSystemTrayIcon.MessageIcon = QSystemTrayIcon.MessageIcon.Information,
        title: str = APP_NAME,
        duration: int = 4000,
    ) -> None:
        if self._tray.supportsMessages():
            self._tray.showMessage(title, body, kind, duration)

    def shutdown(self) -> None:
        try:
            self._hotkey.stop()
        except Exception:
            pass
        try:
            self._api.stop()
        except Exception:
            pass
        for w in (self._window, self._yt_window, self._launcher, self._manager, self._tts_window):
            if w is not None:
                try:
                    if hasattr(w, "shutdown"):
                        w.shutdown()
                    w.close()
                except Exception:
                    pass
        for t in (self._tx_thread, self._local_thread, self._grammar_thread,
                  self._yt_thread, self._action_thread, self._respeaker_thread):
            t.quit()
            t.wait(2000)
        self._tray.hide()
        self._app.quit()


def _preview(text: str, n: int = 80) -> str:
    if text is None:
        return ""
    s = text.strip()
    return s if len(s) <= n else s[:n].rstrip() + "…"


_VOICE_SETTING_FIELDS = (
    "base_voice",
    "rvc_pitch",
    "rvc_index_rate",
    "rvc_f0_method",
    "rvc_filter_radius",
    "rvc_protect",
    "rvc_rms_mix_rate",
    "playback_device_1",
    "playback_device_2",
)


def _item_voice_settings(item: Item | None) -> dict:
    """Snapshot the per-hotkey TTS+RVC overrides from an Item.

    Returns only keys whose value is non-None — the engine falls back to
    its env-configured defaults for anything omitted.
    """
    if item is None:
        return {}
    out: dict = {}
    for k in _VOICE_SETTING_FIELDS:
        v = getattr(item, k, None)
        if v is not None:
            out[k] = v
    return out
