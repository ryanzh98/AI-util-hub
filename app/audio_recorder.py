import io
import threading

import numpy as np
import sounddevice as sd
import soundfile as sf
from PyQt6.QtCore import QObject, pyqtSignal

SAMPLE_RATE = 16_000
CHANNELS = 1
DTYPE = "int16"
MIN_SAMPLES = int(SAMPLE_RATE * 0.3)


class AudioRecorder(QObject):
    error = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._stream: sd.InputStream | None = None
        self._chunks: list[np.ndarray] = []
        self._paused = False
        self._lock = threading.Lock()

    def _callback(self, indata, frames, time_info, status):
        if status:
            pass
        if not self._paused:
            with self._lock:
                self._chunks.append(indata.copy())

    def start(self) -> bool:
        try:
            self._chunks = []
            self._paused = False
            self._stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype=DTYPE,
                callback=self._callback,
            )
            self._stream.start()
            return True
        except Exception as e:
            self.error.emit(f"Microphone error: {e}")
            self._stream = None
            return False

    def pause(self) -> None:
        self._paused = True

    def resume(self) -> None:
        self._paused = False

    @property
    def is_paused(self) -> bool:
        return self._paused

    def stop(self) -> bytes:
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

        with self._lock:
            chunks = self._chunks
            self._chunks = []

        if not chunks:
            return b""

        audio = np.concatenate(chunks, axis=0)
        if audio.shape[0] < MIN_SAMPLES:
            return b""

        buf = io.BytesIO()
        sf.write(buf, audio, samplerate=SAMPLE_RATE, format="WAV", subtype="PCM_16")
        return buf.getvalue()
