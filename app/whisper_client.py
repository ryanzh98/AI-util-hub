"""OpenAI Whisper transcription: pure helper + Qt worker wrapper."""

import os
import tempfile

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot


def transcribe_online(audio: bytes) -> str:
    if not audio:
        raise RuntimeError("Recording too short")

    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key or api_key == "sk-replace-me":
        raise RuntimeError("OPENAI_API_KEY is not set in .env")

    try:
        from openai import OpenAI
    except ImportError as e:
        raise RuntimeError(f"openai package missing: {e}")

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(audio)
            tmp_path = f.name

        prompt = os.environ.get("WHISPER_INITIAL_PROMPT", "").strip()
        client = OpenAI(api_key=api_key, timeout=30.0)
        try:
            with open(tmp_path, "rb") as fh:
                kwargs = {"model": "whisper-1", "file": fh}
                if prompt:
                    kwargs["prompt"] = prompt
                resp = client.audio.transcriptions.create(**kwargs)
        except Exception as e:
            raise RuntimeError(f"Transcription failed: {e}")

        text = (getattr(resp, "text", "") or "").strip()
        if not text:
            raise RuntimeError("Whisper returned empty transcript")
        return text
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


class TranscriptionWorker(QObject):
    done = pyqtSignal(str)
    failed = pyqtSignal(str)

    @pyqtSlot(bytes)
    def transcribe(self, audio_bytes: bytes) -> None:
        try:
            text = transcribe_online(audio_bytes)
        except RuntimeError as e:
            self.failed.emit(str(e))
            return
        except Exception as e:
            self.failed.emit(f"Transcription failed: {e}")
            return
        self.done.emit(text)
