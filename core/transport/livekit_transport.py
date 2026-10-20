"""LiveKit room as the call medium (see voice_pipeline.py for the pipeline). Works on Windows."""

from __future__ import annotations

from pipecat.transports.livekit.transport import LiveKitParams
from pipecat.transports.livekit.transport import LiveKitTransport as PipecatLiveKitTransport

from core.transport.voice_pipeline import VoiceTransport


# Participant identities used in a call's room (see backend/livekit_client.py, which mints the tokens).
PATIENT_IDENTITY = "patient"
DOCTOR_IDENTITY = "doctor"


class LiveKitTransport(VoiceTransport):
    def __init__(
        self, url: str, token: str, room_name: str,
        speakers: tuple[str, ...] = (PATIENT_IDENTITY, DOCTOR_IDENTITY),
    ) -> None:
        room = PipecatLiveKitTransport(
            url, token, room_name, LiveKitParams(audio_in_enabled=True, audio_out_enabled=True)
        )
        super().__init__(
            room,
            speakers=speakers,
            joined_events=("on_first_participant_joined",),
            left_events=("on_participant_disconnected",),
        )
