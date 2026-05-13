"""Mute the default Windows playback device while recording is active.

Snapshots the prior mute state on mute() and restores it on unmute(), so a user
who already had their speakers muted ends up exactly where they started. All
operations are best-effort: if pycaw / COM fails, recording continues normally.
"""

from __future__ import annotations

import sys


class SpeakerMute:
    def __init__(self) -> None:
        self._was_muted: int = 0
        self._is_muted: bool = False

    def _endpoint_volume(self):
        # Imported lazily so a missing pycaw never breaks app startup.
        from pycaw.pycaw import AudioUtilities

        return AudioUtilities.GetSpeakers().EndpointVolume

    def mute(self) -> None:
        if self._is_muted:
            return
        try:
            volume = self._endpoint_volume()
            self._was_muted = int(volume.GetMute())
            volume.SetMute(1, None)
            self._is_muted = True
        except Exception as exc:
            print(f"[speaker_mute] mute failed: {exc}", file=sys.stderr)

    def unmute(self) -> None:
        if not self._is_muted:
            return
        try:
            volume = self._endpoint_volume()
            volume.SetMute(self._was_muted, None)
        except Exception as exc:
            print(f"[speaker_mute] unmute failed: {exc}", file=sys.stderr)
        finally:
            self._is_muted = False
