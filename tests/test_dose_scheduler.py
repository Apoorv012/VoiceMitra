"""B5: ring the patient at dose time; not answered -> once more after 5 min -> caregiver alert (once).

Real live_calls.start_voice_call with the agent and LiveKit faked out, a fake FCM sender, and a fake
clock (sleeping just moves it on). Throwaway database via the `mongo` fixture.
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from backend import dose_scheduler, insights, live_calls, push_fcm
from backend.db import model_to_doc
from backend.models import (
    Device, Dosage, DoseConfidence, DoseEvent, DoseFrequency, DoseSource, DoseStatus, Patient, Prescription,
)
from backend.push_fcm import SendResult

pytestmark = pytest.mark.anyio

DAY = date(2026, 11, 4)
TZ = insights.TZ


def local(h: int, m: int = 0, day: date = DAY) -> datetime:
    return datetime(day.year, day.month, day.day, h, m, tzinfo=TZ)


def utc(dt: datetime) -> datetime:
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


class World:
    """The fakes, and what happened."""

    def __init__(self, monkeypatch, start: datetime):
        self.now = start
        self.pushes: list[dict] = []
        self.alerts: list[str] = []
        self.calls: list[dict] = []
        self.answer = False  # does the patient join?
        self._n = 0

        async def sleep(seconds):
            if seconds > 3600:  # waiting for tomorrow's slot: the test is over by then
                await asyncio.Event().wait()
            self.now += timedelta(seconds=seconds)
            for _ in range(5):
                await asyncio.sleep(0)

        async def sender(tokens, data):
            self.pushes += [data for _ in tokens]
            return [SendResult.ok for _ in tokens]

        async def fake_session(patient_id, *, slot_at=None, dosage_ids=None, **kw):
            self._n += 1
            self.calls.append({"slot_at": slot_at, "dosage_ids": dosage_ids})
            return SimpleNamespace(call=SimpleNamespace(id=f"call-{self._n}"), context=SimpleNamespace(on_log_entry=None))

        async def run_voice(session, transport):
            if not self.answer:
                raise TimeoutError  # nobody joined within the agent's wait

        class Transport:
            ended = True

            def __init__(self, *a):
                pass

            async def abort(self):
                pass

        async def alert(patient_id, call_id):
            self.alerts.append(call_id)

        async def wrong_alert(patient_id, call_id):
            raise AssertionError("a dose-time call must not alert on its first unanswered ring")

        monkeypatch.setenv("DOSE_RINGING_ENABLED", "true")
        monkeypatch.setattr(dose_scheduler, "_now", lambda: self.now)
        monkeypatch.setattr(dose_scheduler, "_sleep", sleep)
        monkeypatch.setattr(push_fcm, "_sender", sender)
        monkeypatch.setattr(live_calls, "create_call_session", fake_session)
        monkeypatch.setattr(live_calls, "create_livekit_room",
                            lambda name: SimpleNamespace(name=name, url="wss://lk", bot_token="b", patient_token="p"))
        monkeypatch.setattr(live_calls, "LiveKitTransport", Transport)
        monkeypatch.setattr(live_calls, "run_voice_call", run_voice)
        monkeypatch.setattr(live_calls, "notify_caregiver_unreachable", wrong_alert)
        monkeypatch.setattr("domains.med_adherence.caregiver.notify_caregiver_unreachable", alert)
        monkeypatch.setattr(live_calls, "_voice_calls", {})
        monkeypatch.setattr(live_calls, "_live_calls", {})

    async def settle(self, until=None, timeout: float = 5.0):
        """Let the timers run (database calls take real time): until `until()` holds, or the scheduler
        has nothing left to do but wait for tomorrow's slot."""
        loop = asyncio.get_running_loop()
        end = loop.time() + timeout
        while loop.time() < end:
            await asyncio.sleep(0.02)
            if until is not None and until():
                break
            busy = dose_scheduler._retries or live_calls._voice_calls or push_fcm._tasks
            if until is None and not busy and self.calls:
                await asyncio.sleep(0.1)
                if not (dose_scheduler._retries or live_calls._voice_calls or push_fcm._tasks):
                    break
        await asyncio.gather(*list(push_fcm._tasks), return_exceptions=True)

    def rings(self):
        return [p["call_id"] for p in self.pushes if p["type"] == "ring"]


@pytest.fixture
async def world(mongo, monkeypatch):
    w = World(monkeypatch, start=local(7, 59))
    yield w
    dose_scheduler.stop()


async def _patient(mongo, times=("08:00",), extra_times=None) -> tuple[Patient, list[Dosage]]:
    patient = Patient(id="p1", name="Sunita", age=70, phone_number="+911")
    rx = Prescription(patient_id=patient.id)
    rx.medicines = [
        Dosage(prescription_id=rx.id, medicine_name="Metformin", dosage="500 mg", from_date=DAY - timedelta(days=5),
               frequency=DoseFrequency.daily, times=list(times)),
        Dosage(prescription_id=rx.id, medicine_name="Amlodipine", dosage="5 mg", from_date=DAY - timedelta(days=5),
               frequency=DoseFrequency.daily, times=list(extra_times or times)),
    ]
    patient.prescription_ids = [rx.id]
    await mongo["patients"].insert_one(model_to_doc(patient))
    await mongo["prescriptions"].insert_one(model_to_doc(rx))
    await mongo["devices"].insert_one(model_to_doc(
        Device(patient_id=patient.id, platform="android", push_token="tok", token_hash="h")))
    return patient, rx.medicines


async def _taken(mongo, dosage: Dosage, at: datetime):
    ev = DoseEvent(patient_id="p1", dosage_id=dosage.id, scheduled_at=utc(at), recorded_at=utc(at),
                   status=DoseStatus.taken, confidence=DoseConfidence.high, source=DoseSource.patient_self_report)
    await mongo["dose_events"].insert_one(model_to_doc(ev))


async def test_unanswered_rings_twice_then_alerts_the_caregiver_once(world, mongo):
    _, meds = await _patient(mongo)
    await dose_scheduler.arm("p1")
    await world.settle(until=lambda: world.alerts)

    # Rang at 08:00 about both medicines due then, again 5 min later, then one caregiver alert.
    assert world.rings() == ["call-1", "call-2"]
    assert [c["slot_at"] for c in world.calls] == [utc(local(8)), utc(local(8))]
    assert all(sorted(c["dosage_ids"]) == sorted(m.id for m in meds) for c in world.calls)
    assert world.alerts == ["call-2"]
    assert world.now == local(8, 5)


async def test_answered_call_is_not_retried(world, mongo):
    await _patient(mongo)
    world.answer = True
    await dose_scheduler.arm("p1")
    await world.settle()
    assert world.rings() == ["call-1"] and world.alerts == []


async def test_dose_taken_before_the_retry_stops_it(world, mongo, monkeypatch):
    _, meds = await _patient(mongo)
    real_retry = dose_scheduler._retry

    async def retry_after_taking_it(patient_id, at, dosage_ids):
        for m in meds:  # the patient took them (told the web app, or a family member logged it)
            await _taken(mongo, m, at)
        await real_retry(patient_id, at, dosage_ids)

    monkeypatch.setattr(dose_scheduler, "_retry", retry_after_taking_it)
    await dose_scheduler.arm("p1")
    await world.settle()
    assert world.rings() == ["call-1"] and world.alerts == []


async def test_only_unanswered_medicines_are_asked_about_and_answered_slots_skipped(world, mongo):
    _, meds = await _patient(mongo)
    await _taken(mongo, meds[0], local(8))  # Metformin already logged
    world.answer = True
    await dose_scheduler.arm("p1")
    await world.settle()
    assert [c["dosage_ids"] for c in world.calls] == [[meds[1].id]]

    # Everything answered -> no call at all.
    started = await dose_scheduler.ring_slot("p1", local(8), [m.id for m in meds], attempt=1)
    assert started is True  # Amlodipine still open (the faked call logs nothing)
    for m in meds:
        await _taken(mongo, m, local(8))
    assert await dose_scheduler.ring_slot("p1", local(8), [m.id for m in meds], attempt=1) is False


async def test_no_ring_while_the_patient_is_on_a_call(world, mongo):
    await _patient(mongo)
    live_calls._voice_calls["p1"] = object()
    assert await dose_scheduler.ring_slot("p1", local(8), ["x"], attempt=1) is False
    assert world.calls == []


async def test_next_slot_groups_medicines_and_rolls_over_to_tomorrow(world, mongo):
    _, meds = await _patient(mongo, times=("08:00", "20:00"), extra_times=("20:00",))
    at, ids = dose_scheduler._next_slot(meds, local(7, 0))
    assert at == local(8) and ids == [meds[0].id]
    at, ids = dose_scheduler._next_slot(meds, local(8))
    assert at == local(20) and sorted(ids) == sorted(m.id for m in meds)
    at, _ = dose_scheduler._next_slot(meds, local(21))
    assert at == local(8, day=DAY + timedelta(days=1))


async def test_off_by_default(mongo, monkeypatch, caplog):
    monkeypatch.delenv("DOSE_RINGING_ENABLED", raising=False)
    await _patient(mongo)
    with caplog.at_level("INFO", logger="backend.dose_scheduler"):
        await dose_scheduler.start()
        await dose_scheduler.arm("p1")
    assert dose_scheduler._timers == {}
    assert "dose-time ringing is off" in caplog.text


async def test_adding_a_prescription_rearms(world, mongo, client):
    await _patient(mongo, times=("20:00",))
    await dose_scheduler.arm("p1")
    first = dose_scheduler._timers["p1"]
    res = await client.post("/api/patients/p1/prescriptions", json={"medicines": [
        {"medicine_name": "Vitamin D", "dosage": "1 tab", "from_date": str(DAY), "frequency": "daily", "times": ["09:00"]}]})
    assert res.status_code == 200
    await asyncio.sleep(0)
    assert first.cancelled() and dose_scheduler._timers["p1"] is not first
