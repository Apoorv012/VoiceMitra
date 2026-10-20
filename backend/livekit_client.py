"""LiveKit access tokens: one for the agent to join a call's room, one for the patient's browser.
Rooms are created implicitly on first join, so no REST call is needed."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import timedelta

from livekit import api

from core.transport.livekit_transport import DOCTOR_IDENTITY, PATIENT_IDENTITY

TOKEN_LIFETIME = timedelta(hours=1)


@dataclass(frozen=True)
class LiveKitRoom:
    url: str
    name: str
    bot_token: str
    patient_token: str


def mint_token(room_name: str, identity: str) -> str:
    return (
        api.AccessToken(os.environ["LIVEKIT_API_KEY"], os.environ["LIVEKIT_API_SECRET"])
        .with_identity(identity)
        .with_name(identity)
        .with_ttl(TOKEN_LIFETIME)
        .with_grants(api.VideoGrants(room_join=True, room=room_name))
        .to_jwt()
    )


def create_call_room(room_name: str) -> LiveKitRoom:
    return LiveKitRoom(
        url=os.environ["LIVEKIT_URL"], name=room_name, bot_token=mint_token(room_name, "voicemitra-agent"),
        patient_token=mint_token(room_name, PATIENT_IDENTITY),
    )


def doctor_token(room_name: str) -> str:
    return mint_token(room_name, DOCTOR_IDENTITY)


@dataclass(frozen=True)
class BriefingRoom:
    url: str
    name: str
    bot_token: str
    doctor_token: str


def create_briefing_room(call_room_name: str) -> BriefingRoom:
    """A private room for the agent to brief the doctor in while the patient is on hold in the call's
    own room. Separate because the agent speaks into a whole room: in the patient's it would be heard
    by the patient."""
    name = f"{call_room_name}-brief"
    return BriefingRoom(
        url=os.environ["LIVEKIT_URL"], name=name,
        bot_token=mint_token(name, "voicemitra-agent"), doctor_token=mint_token(name, DOCTOR_IDENTITY),
    )
