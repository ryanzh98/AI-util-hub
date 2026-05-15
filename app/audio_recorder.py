import io
import threading
from collections import deque

import numpy as np
import sounddevice as sd
import soundfile as sf
from PyQt6.QtCore import QObject, pyqtSignal

SAMPLE_RATE = 16_000
CHANNELS = 1
DTYPE = "int16"
MIN_SAMPLES = int(SAMPLE_RATE * 0.3)

LEVEL_FRAME_SAMPLES = int(SAMPLE_RATE * 0.05)  # 50ms @ 16kHz = 800 samples
LEVEL_HISTORY_FRAMES = 64                      # ~3.2s of 50ms slices


class AudioRecorder(QObject):
    error = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._stream: sd.InputStream | None = None
        self._chunks: list[np.ndarray] = []
        self._paused = False
        self._lock = threading.Lock()
        self._level_buffer = np.zeros(0, dtype=np.int16)
        self._levels: deque[float] = deque(maxlen=LEVEL_HISTORY_FRAMES)

    def _callback(self, indata, frames, time_info, status):
        if status:
            pass
        if not self._paused:
            with self._lock:
                self._chunks.append(indata.copy())
            flat = indata.reshape(-1).astype(np.int16, copy=False)
            self._level_buffer = np.concatenate((self._level_buffer, flat))
            while len(self._level_buffer) >= LEVEL_FRAME_SAMPLES:
                frame = self._level_buffer[:LEVEL_FRAME_SAMPLES]
                self._level_buffer = self._level_buffer[LEVEL_FRAME_SAMPLES:]
                if frame.size == 0:
                    continue
                normalized = frame.astype(np.float32) / 32768.0
                rms = float(np.sqrt(np.mean(np.square(normalized))))
                with self._lock:
                    self._levels.append(rms)
        else:
            extra_samples = indata.size
            frames_to_emit = (len(self._level_buffer) + extra_samples) // LEVEL_FRAME_SAMPLES
            self._level_buffer = np.zeros(0, dtype=np.int16)
            if frames_to_emit > 0:
                with self._lock:
                    for _ in range(frames_to_emit):
                        self._levels.append(0.0)

    def start(self) -> bool:
        try:
            self._chunks = []
            self._paused = False
            self._level_buffer = np.zeros(0, dtype=np.int16)
            with self._lock:
                self._levels.clear()
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

    def recent_levels(self, n: int) -> list[float]:
        """Return the last n RMS samples (0..1, most recent last). Pads left with 0.0 if short."""
        with self._lock:
            snap = list(self._levels)
        if len(snap) < n:
            snap = [0.0] * (n - len(snap)) + snap
        return snap[-n:]

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
            self._levels.clear()
        self._level_buffer = np.zeros(0, dtype=np.int16)

        if not chunks:
            return b""

        audio = np.concatenate(chunks, axis=0)
        if audio.shape[0] < MIN_SAMPLES:
            return b""

        buf = io.BytesIO()
        sf.write(buf, audio, samplerate=SAMPLE_RATE, format="WAV", subtype="PCM_16")
        return buf.getvalue()
