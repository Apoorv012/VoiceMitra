"""B2: a phone that was rung asks how to join the patient's voice call (mobile/API.md, "Calls")."""

from __future__ import annotations

import pytest

from backend import live_calls

pytestmark = pytest.mark.anyio


async def test_join_info_for_the_call_in_progress(client, monkeypatch):
    voice = live_calls.VoiceCall(call_id="c1", room_name="call-c1", room_url="wss://lk.example",
                                 patient_token="jwt-patient", transport=None)  # type: ignore[arg-type]
    monkeypatch.setitem(live_calls._voice_calls, "p1", voice)
    res = await client.get("/api/patients/p1/voice-call")
    assert res.status_code == 200
    assert res.json() == {"call_id": "c1", "url": "wss://lk.example", "token": "jwt-patient"}


async def test_no_call_is_a_404(client):
    assert (await client.get("/api/patients/p1/voice-call")).status_code == 404
