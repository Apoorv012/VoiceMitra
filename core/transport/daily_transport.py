"""Daily room as the call medium (see voice_pipeline.py for the pipeline). Needs `daily-python`, which
only has Linux/macOS wheels, and a Daily account with billing set up; LiveKit is what the POC uses."""

from __future__ import annotations

from pipecat.transports.daily.transport import DailyParams
from pipecat.transports.daily.transport import DailyTransport as PipecatDailyTransport

from core.transport.voice_pipeline import VoiceTransport


class DailyTransport(VoiceTransport):
    def __init__(self, room_url: str, token: str | None, *, bot_name: str = "VoiceMitra") -> None:
        room = PipecatDailyTransport(
            room_url, token, bot_name, DailyParams(audio_in_enabled=True, audio_out_enabled=True)
        )
        super().__init__(
            room, joined_events=("on_first_participant_joined",), left_events=("on_participant_left",)
        )
