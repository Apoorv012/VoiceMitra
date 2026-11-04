"""B3: a voice call rings the patient's Android phones over FCM (fake sender here)."""

from __future__ import annotations

import pytest

from backend import push_fcm
from backend.db import model_to_doc
from backend.models import Device
from backend.push_fcm import SendResult

pytestmark = pytest.mark.anyio


class FakeSender:
    def __init__(self, results: dict[str, SendResult] | None = None):
        self.sent: list[tuple[str, dict]] = []
        self.results = results or {}

    async def __call__(self, tokens, data):
        self.sent += [(t, data) for t in tokens]
        return [self.results.get(t, SendResult.ok) for t in tokens]


@pytest.fixture
def fake(monkeypatch):
    sender = FakeSender()
    monkeypatch.setattr(push_fcm, "_sender", sender)
    return sender


async def _device(mongo, patient_id="p1", platform="android", push_token="tok-a") -> Device:
    device = Device(patient_id=patient_id, platform=platform, push_token=push_token, token_hash="h-" + str(push_token))
    await mongo["devices"].insert_one(model_to_doc(device))
    return device


async def test_ring_reaches_android_phones_except_the_caller(mongo, fake):
    a = await _device(mongo, push_token="tok-a")
    await _device(mongo, push_token="tok-b")
    await _device(mongo, platform="ios", push_token="apns-x")   # iPhones ring from the socket instead
    await _device(mongo, push_token=None)                       # no token yet
    await _device(mongo, patient_id="someone-else", push_token="tok-z")

    reached = await push_fcm.ring("p1", "call-1", skip_device_id=a.id)
    assert reached == 1
    assert fake.sent == [("tok-b", {"type": "ring", "call_id": "call-1", "patient_id": "p1"})]


async def test_unregistered_tokens_are_dropped_but_failures_kept(mongo, fake):
    stale = await _device(mongo, push_token="tok-stale")
    flaky = await _device(mongo, push_token="tok-flaky")
    fake.results = {"tok-stale": SendResult.unregistered, "tok-flaky": SendResult.failed}

    assert await push_fcm.ring("p1", "call-1") == 0
    assert (await mongo["devices"].find_one({"_id": stale.id}))["push_token"] is None
    assert (await mongo["devices"].find_one({"_id": flaky.id}))["push_token"] == "tok-flaky"


async def test_call_ended_message_stops_the_ring(mongo, fake):
    await _device(mongo)
    await push_fcm.cancel_ring("p1", "call-1")
    assert fake.sent == [("tok-a", {"type": "call_ended", "call_id": "call-1", "patient_id": "p1"})]


async def test_without_firebase_credentials_nothing_is_sent(mongo, monkeypatch, caplog):
    monkeypatch.setattr(push_fcm, "_sender", None)
    monkeypatch.setattr(push_fcm, "_warned_unset", False)
    monkeypatch.delenv("FIREBASE_CREDENTIALS", raising=False)
    await _device(mongo)
    with caplog.at_level("INFO", logger="backend.push_fcm"):
        assert await push_fcm.ring("p1", "call-1") == 0
    assert "FIREBASE_CREDENTIALS is not set" in caplog.text


async def test_starting_a_voice_call_rings_and_ending_it_cancels(mongo, fake, monkeypatch):
    """Through live_calls, with the agent session and LiveKit room faked out."""
    import asyncio
    from types import SimpleNamespace

    from backend import live_calls

    caller = await _device(mongo, push_token="tok-caller")
    await _device(mongo, push_token="tok-other")

    async def fake_session(patient_id, **kw):
        return SimpleNamespace(call=SimpleNamespace(id="call-9"), context=SimpleNamespace(on_log_entry=None))

    class FakeTransport:
        ended = True

        def __init__(self, *a):
            pass

        async def abort(self):
            pass

    async def never_answered(session, transport):
        await asyncio.Event().wait()

    monkeypatch.setattr(live_calls, "create_call_session", fake_session)
    monkeypatch.setattr(live_calls, "create_livekit_room",
                        lambda name: SimpleNamespace(name=name, url="wss://lk", bot_token="b", patient_token="p"))
    monkeypatch.setattr(live_calls, "LiveKitTransport", FakeTransport)
    monkeypatch.setattr(live_calls, "run_voice_call", never_answered)
    monkeypatch.setattr(live_calls, "_voice_calls", {})

    await live_calls.start_voice_call("p1", skip_device_id=caller.id)
    await asyncio.gather(*push_fcm._tasks)
    assert fake.sent == [("tok-other", {"type": "ring", "call_id": "call-9", "patient_id": "p1"})]

    await live_calls.end_call("p1")  # cancels the agent task -> finish_voice_call
    for _ in range(20):
        await asyncio.sleep(0)
    await asyncio.gather(*push_fcm._tasks)
    assert [d["type"] for _, d in fake.sent] == ["ring", "call_ended", "call_ended"]
