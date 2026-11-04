"""B4: a "remind me later" reminder starts a voice call (so the patient's phone rings), after any call
they are already on."""

from __future__ import annotations

import asyncio
from datetime import datetime

import pytest

from backend import live_calls
from backend.db import model_to_doc
from backend.models import Reminder, ReminderStatus

pytestmark = pytest.mark.anyio


async def test_reminder_starts_a_voice_call_and_waits_for_the_current_one(mongo, monkeypatch):
    started: list[dict] = []

    async def fake_start_voice_call(patient_id, **kw):
        started.append({"patient_id": patient_id, **kw})

    async def no_chat_call(*a, **kw):
        raise AssertionError("reminders no longer start chat calls")

    monkeypatch.setattr(live_calls, "start_voice_call", fake_start_voice_call)
    monkeypatch.setattr(live_calls, "start_call", no_chat_call)
    monkeypatch.setattr(live_calls, "REMINDER_RETRY_SECONDS", 0.01)
    monkeypatch.setattr(live_calls, "_voice_calls", {"p1": object()})  # already on a voice call

    slot = datetime(2026, 11, 4, 3, 0)
    reminder = Reminder(patient_id="p1", dosage_ids=["d1"], slot_at=slot, call_id="c0", remind_at=datetime.utcnow())
    await mongo["reminders"].insert_one(model_to_doc(reminder))

    task = asyncio.create_task(live_calls._fire_reminder(reminder, 0))
    await asyncio.sleep(0.05)
    assert started == []  # waits while the patient is on a call
    live_calls._voice_calls.clear()
    await asyncio.wait_for(task, 2)

    assert started == [{"patient_id": "p1", "slot_at": slot, "dosage_ids": ["d1"]}]
    assert (await mongo["reminders"].find_one({"_id": reminder.id}))["status"] == ReminderStatus.fired.value
