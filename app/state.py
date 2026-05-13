from enum import Enum, auto


class RecorderState(Enum):
    IDLE = auto()
    RECORDING = auto()
    PAUSED = auto()
    TRANSCRIBING = auto()
