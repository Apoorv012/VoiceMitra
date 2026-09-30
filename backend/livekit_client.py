"""LiveKit access tokens: one for the agent to join a call's room, one for the patient's browser.
Rooms are created implicitly on first join, so no REST call is needed."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import timedelta

from livekit import api

TOKEN_LIFETIME = timedelta(hours=1)


@dataclass(frozen=True)
class LiveKitRoom:
    url: str
    name: str
    bot_token: str
    patient_token: str


def create_call_room(room_name: str) -> LiveKitRoom:
    key, secret = os.environ["LIVEKIT_API_KEY"], os.environ["LIVEKIT_API_SECRET"]

    def token(identity: str) -> str:
        return (
            api.AccessToken(key, secret)
            .with_identity(identity)
            .with_name(identity)
            .with_ttl(TOKEN_LIFETIME)
            .with_grants(api.VideoGrants(room_join=True, room=room_name))
            .to_jwt()
        )

    return LiveKitRoom(
        url=os.environ["LIVEKIT_URL"], name=room_name, bot_token=token("voicemitra-agent"),
        patient_token=token("patient"),
    )
