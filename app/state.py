from enum import Enum, auto


class RecorderState(Enum):
    IDLE = auto()
    RECORDING = auto()
    PAUSED = auto()
    TRANSCRIBING = auto()
    # Respeaker-only: cloned-voice playback has finished; window stays
    # open so the user can replay or save the generated WAV.
    DONE = auto()
