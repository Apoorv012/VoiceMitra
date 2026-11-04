"""Ring the patient at dose time (pilot steps 4-5).

One asyncio timer per patient, for their next dose slot (the same timer pattern as reminders in
live_calls.py -- no scan loop). At the slot it starts a voice call about the medicines in it that still
have no answer (so the phone rings: backend/push_fcm.py). Nobody joins within the agent's wait ->
ring once more after RETRY_AFTER -> still nobody -> the caregiver's "couldn't be reached" alert, once.
Then the timer moves on to the next slot. Timers are armed on startup and re-armed when a prescription
is added.

**Off unless DOSE_RINGING_ENABLED is set** (.env): with real patients in the database, turning it on
starts real calls and caregiver alerts at their dose times.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone

from backend import insights
from backend.db import doc_to_model, dose_events_col, patients_col, prescriptions_col
from backend.models import Dosage, DoseEvent, Patient, Prescription

log = logging.getLogger(__name__)

RETRY_AFTER = timedelta(minutes=5)
# A slot that came due this recently (e.g. while the server was restarting) still rings.
LATE_GRACE = timedelta(minutes=2)
# Slots nobody has answered yet. LATER (the patient asked to be reminded) is left to that reminder.
_OPEN = {insights.UPCOMING, insights.DUE, insights.NO_CHECKIN}

_timers: dict[str, asyncio.Task] = {}  # patient id -> timer for their next slot
_retries: set[asyncio.Task] = set()


def enabled() -> bool:
    return os.environ.get("DOSE_RINGING_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}


# Swapped in tests.
def _now() -> datetime:
    return insights.now_local()


async def _sleep(seconds: float) -> None:
    await asyncio.sleep(seconds)


# --- arming ----------------------------------------------------------------------------------

async def start() -> None:
    """On startup: arm every patient who has prescriptions."""
    if not enabled():
        # Warning level: uvicorn only shows the app's own warnings, and this state should be visible.
        log.warning("dose-time ringing is off (set DOSE_RINGING_ENABLED=true to ring patients at dose time)")
        return
    count = 0
    async for doc in patients_col().find({"prescription_ids.0": {"$exists": True}}, {"_id": 1}):
        await arm(doc["_id"])
        count += 1
    log.warning("dose-time ringing is ON: armed %d patient(s)", count)


async def arm(patient_id: str, *, after: datetime | None = None) -> None:
    """(Re)arm the patient's timer for their first slot after `after` (default: a moment ago)."""
    if not enabled():
        return
    old = _timers.pop(patient_id, None)
    if old is not None and old is not asyncio.current_task():
        old.cancel()
    after = after or (_now() - LATE_GRACE)
    nxt = _next_slot(await _dosages(patient_id), after)
    if nxt is None:
        return
    at, dosage_ids = nxt
    _timers[patient_id] = asyncio.create_task(_wait_and_ring(patient_id, at, dosage_ids))


def stop() -> None:
    for task in [*_timers.values(), *_retries]:
        task.cancel()
    _timers.clear()
    _retries.clear()


def _next_slot(dosages: list[Dosage], after: datetime) -> tuple[datetime, list[str]] | None:
    """The first slot strictly after `after` (local time, today or tomorrow) and its medicines."""
    slots = insights.build_slots(dosages, [], after.date(), after.date() + timedelta(days=1), after)
    later = [s for s in slots if s.at > after]
    if not later:
        return None
    at = min(s.at for s in later)
    return at, [s.dosage.id for s in later if s.at == at]


async def _wait_and_ring(patient_id: str, at: datetime, dosage_ids: list[str]) -> None:
    try:
        delay = (at - _now()).total_seconds()
        if delay > 0:
            await _sleep(delay)
        await ring_slot(patient_id, at, dosage_ids, attempt=1)
    except asyncio.CancelledError:
        raise
    except Exception:
        log.exception("dose-time call for patient %s at %s failed", patient_id, at)
    # On to the next slot (from here, so this one isn't picked again).
    if _timers.get(patient_id) is asyncio.current_task():
        await arm(patient_id, after=at)


# --- ringing ---------------------------------------------------------------------------------

async def ring_slot(patient_id: str, at: datetime, dosage_ids: list[str], *, attempt: int) -> bool:
    """Start the slot's call, unless it's already answered or the patient is on a call. True if started."""
    from backend import live_calls  # imported here: live_calls pulls in the whole agent

    dosages = await _dosages(patient_id)
    events = await _events(patient_id)
    slots = insights.build_slots([d for d in dosages if d.id in dosage_ids], events, at.date(), at.date(), _now())
    still_open = [s.dosage.id for s in slots if s.at == at and s.state in _OPEN]
    if not still_open:
        log.info("dose slot %s for patient %s already answered: not ringing", at, patient_id)
        return False
    if live_calls._patient_busy(patient_id):
        log.info("patient %s is on a call at dose time %s: not ringing", patient_id, at)
        return False

    async def unanswered(call_id: str) -> None:
        if attempt == 1:
            log.info("patient %s didn't answer the %s dose call: ringing again in %s", patient_id, at, RETRY_AFTER)
            task = asyncio.create_task(_retry(patient_id, at, dosage_ids))
            _retries.add(task)
            task.add_done_callback(_retries.discard)
        else:
            from domains.med_adherence.caregiver import notify_caregiver_unreachable

            await notify_caregiver_unreachable(patient_id, call_id)

    try:
        await live_calls.start_voice_call(patient_id, slot_at=_utc(at), dosage_ids=still_open, on_unanswered=unanswered)
    except live_calls.PatientNotReady as e:
        log.info("no dose-time call for patient %s: %s", patient_id, e)
        return False
    return True


async def _retry(patient_id: str, at: datetime, dosage_ids: list[str]) -> None:
    try:
        await _sleep(RETRY_AFTER.total_seconds())
        await ring_slot(patient_id, at, dosage_ids, attempt=2)
    except asyncio.CancelledError:
        raise
    except Exception:
        log.exception("dose-time retry for patient %s at %s failed", patient_id, at)


# --- data ------------------------------------------------------------------------------------

async def _dosages(patient_id: str) -> list[Dosage]:
    patient = doc_to_model(Patient, await patients_col().find_one({"_id": patient_id}))
    if patient is None or not patient.prescription_ids:
        return []
    return [
        m
        async for doc in prescriptions_col().find({"_id": {"$in": patient.prescription_ids}})
        for m in doc_to_model(Prescription, doc).medicines
    ]


async def _events(patient_id: str) -> list[DoseEvent]:
    # Stored as ISO strings, so the range is a string comparison (as in domains/med_adherence/bot.py).
    since = (_utc(_now()) - timedelta(days=2)).isoformat()
    return [
        doc_to_model(DoseEvent, d)
        async for d in dose_events_col().find({"patient_id": patient_id, "scheduled_at": {"$gte": since}})
    ]


def _utc(at: datetime) -> datetime:
    """Local, aware -> naive UTC, like every stored time."""
    return at.astimezone(timezone.utc).replace(tzinfo=None)
