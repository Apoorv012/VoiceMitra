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


async def _device(mongo, patient_id="p1", platform="android", push_token="tok-a", **kw) -> Device:
    device = Device(patient_id=patient_id, platform=platform, push_token=push_token, token_hash="h-" + str(push_token),
                    **kw)
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


# --- caregiver phones (mobile/API.md, "Caregivers in the apps") ---------------------------------

async def test_rings_skip_caregiver_phones_but_old_records_ring(mongo, fake):
    await _device(mongo, push_token="tok-family", role="caregiver", caregiver_id="c1")
    old = await _device(mongo, push_token="tok-old")
    await mongo["devices"].update_one({"_id": old.id}, {"$unset": {"role": "", "caregiver_id": ""}})

    await push_fcm.ring("p1", "call-1")
    await push_fcm.cancel_ring("p1", "call-1")
    assert [(t, d["type"]) for t, d in fake.sent] == [("tok-old", "ring"), ("tok-old", "call_ended")]


async def test_alert_push_goes_to_that_caregivers_android_phones(mongo, fake):
    await _device(mongo, push_token="tok-rahul", role="caregiver", caregiver_id="c1")
    await _device(mongo, push_token="apns-rahul", platform="ios", role="caregiver", caregiver_id="c1")
    await _device(mongo, push_token="tok-other-family", role="caregiver", caregiver_id="c2")
    await _device(mongo, push_token="tok-patient")
    stale = await _device(mongo, push_token="tok-stale", role="caregiver", caregiver_id="c1")
    fake.results = {"tok-stale": SendResult.unregistered}

    assert await push_fcm.alert("c1", "p1", "n1") == 1
    data = {"type": "alert", "alert_id": "n1", "caregiver_id": "c1", "patient_id": "p1"}
    assert sorted(fake.sent, key=lambda s: s[0]) == [("tok-rahul", data), ("tok-stale", data)]
    assert (await mongo["devices"].find_one({"_id": stale.id}))["push_token"] is None


def test_alerts_live_an_hour_rings_a_minute():
    assert push_fcm._ttl({"type": "alert"}).total_seconds() == 3600
    assert push_fcm._ttl({"type": "ring"}).total_seconds() == 60
    assert push_fcm._ttl({"type": "call_ended"}).total_seconds() == 60


async def _family(mongo):
    from backend.models import Caregiver, Patient

    patient = Patient(name="Sunita", age=70, phone_number="+911")
    caregiver = Caregiver(patient_id=patient.id, name="Rahul", relation="son", phone_number="+912")
    patient.caregiver_id = caregiver.id
    await mongo["caregivers"].insert_one(model_to_doc(caregiver))
    await mongo["patients"].insert_one(model_to_doc(patient))
    await _device(mongo, patient_id=patient.id, push_token="tok-rahul", role="caregiver", caregiver_id=caregiver.id)
    await _device(mongo, patient_id=patient.id, push_token="tok-sunita")
    return patient, caregiver


async def test_a_new_caregiver_alert_pushes_to_their_phone(mongo, fake):
    import asyncio

    from domains.med_adherence import caregiver as caregiver_alerts

    patient, carer = await _family(mongo)
    result = await caregiver_alerts.notify_caregiver_unreachable(patient.id, "call-1")
    assert result["notified"]
    await asyncio.gather(*push_fcm._tasks)
    alert = await mongo["caregiver_notifications"].find_one({})
    assert fake.sent == [("tok-rahul", {"type": "alert", "alert_id": alert["_id"], "caregiver_id": carer.id,
                                        "patient_id": patient.id})]
    assert "reach" not in str(fake.sent)  # ids only, no message text


async def test_a_failing_push_never_breaks_the_alert(mongo, monkeypatch):
    import asyncio

    from domains.med_adherence import caregiver as caregiver_alerts

    async def broken(tokens, data):
        raise RuntimeError("FCM down")

    monkeypatch.setattr(push_fcm, "_sender", broken)
    patient, _ = await _family(mongo)
    assert (await caregiver_alerts.notify_caregiver_unreachable(patient.id, "call-1"))["notified"]
    await asyncio.gather(*push_fcm._tasks)
    assert await mongo["caregiver_notifications"].count_documents({}) == 1

    def spawn_fails(*a, **kw):
        raise RuntimeError("no loop")

    monkeypatch.setattr(push_fcm, "spawn", spawn_fails)
    assert (await caregiver_alerts.notify_caregiver_unreachable(patient.id, "call-2"))["notified"]
    assert await mongo["caregiver_notifications"].count_documents({}) == 2
