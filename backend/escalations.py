"""Doctor leg of an escalated call: ring the doctor, brief them, merge them into the patient's call,
summarise what was said.

  ringing   the patient has heard the hand-off line and is held on the line; the patient's doctor(s)
            get an incoming call on their dashboard (patient name + id, nothing more -- like a phone).
  briefing  a doctor pressed Join call. They talk to the agent in a private chat (patient still on
            hold): it briefs them, answers questions, and asks whether to merge.
  merged    the doctor said to merge. Doctor and patient talk directly; the agent stays on the line
            and just records.
  resolved  either side ended the call after a merge; the agent's summary of the conversation was
            written into the call log.
  abandoned it ended (or the server restarted) before a merge.

As in live_calls.py, nothing is polled: doctor dashboards and the doctor's call page hold WebSockets
and are pushed events. The patient's page keeps using its existing socket via live_calls.

State is in-process (like live calls); the Escalation document and the Call log are the durable record.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime

from backend import live_calls
from backend.db import calls_col, doc_to_model, doctors_col, escalations_col, model_to_doc
from backend.models import CallLogEntry, CallLogEntryType, Doctor, Escalation, EscalationStatus
from core.agent.runtime import run_chat_session
from core.transport.queue_transport import QueueTransport
from domains.med_adherence.context import EscalationRequest
from domains.med_adherence.doctor_agent import create_doctor_session, summarize_merged_call

log = logging.getLogger(__name__)

NO_DOCTOR_LINE = "No doctor is available right now. The hospital will follow up with you shortly."
NOT_CONNECTED_LINE = "We couldn't connect you to the doctor right now. The hospital will follow up with you."
ENDED_LINE = "The call has ended."


class EscalationError(Exception):
    def __init__(self, message: str, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass
class LiveEscalation:
    escalation: Escalation
    patient_name: str
    doctor_names: dict[str, str]                 # id -> name, for the doctors rung
    transport: QueueTransport | None = None      # doctor <-> agent (and, once merged, the relay)
    task: asyncio.Task | None = None             # the briefing conversation
    room: list[tuple[str, str]] = field(default_factory=list)  # merged: (speaker, text)
    closing: bool = False

    @property
    def doctor_name(self) -> str | None:
        return self.doctor_names.get(self.escalation.doctor_id or "")


_live: dict[str, LiveEscalation] = {}
_doctor_subs: dict[str, set[asyncio.Queue]] = {}   # doctor id -> dashboard sockets
_call_subs: dict[str, set[asyncio.Queue]] = {}     # escalation id -> the doctor's call-page sockets


# --- subscriptions -------------------------------------------------------------------------

def _subscribe(subs: dict[str, set[asyncio.Queue]], key: str) -> asyncio.Queue:
    queue: asyncio.Queue = asyncio.Queue()
    subs.setdefault(key, set()).add(queue)
    return queue


def _unsubscribe(subs: dict[str, set[asyncio.Queue]], key: str, queue: asyncio.Queue) -> None:
    group = subs.get(key)
    if group is not None:
        group.discard(queue)
        if not group:
            del subs[key]


def subscribe_doctor(doctor_id: str) -> asyncio.Queue:
    return _subscribe(_doctor_subs, doctor_id)


def unsubscribe_doctor(doctor_id: str, queue: asyncio.Queue) -> None:
    _unsubscribe(_doctor_subs, doctor_id, queue)


def subscribe_call(escalation_id: str) -> asyncio.Queue:
    return _subscribe(_call_subs, escalation_id)


def unsubscribe_call(escalation_id: str, queue: asyncio.Queue) -> None:
    _unsubscribe(_call_subs, escalation_id, queue)


def _publish_doctor(doctor_id: str, event: dict) -> None:
    for queue in _doctor_subs.get(doctor_id, ()):
        queue.put_nowait(event)


def _publish_call(escalation_id: str, event: dict) -> None:
    for queue in _call_subs.get(escalation_id, ()):
        queue.put_nowait(event)


# --- snapshots for a newly connected socket ------------------------------------------------

def _ring(live: LiveEscalation) -> dict:
    esc = live.escalation
    return {
        "escalation_id": esc.id,
        "patient_id": esc.patient_id,
        "patient_name": live.patient_name,
        "created_at": esc.created_at.isoformat() + "Z",
    }


def snapshot_doctor(doctor_id: str) -> dict:
    return {
        "type": "snapshot",
        "ringing": [
            _ring(live) for live in _live.values()
            if live.escalation.status == EscalationStatus.ringing
            and not live.closing and doctor_id in live.escalation.doctor_ids
        ],
    }


def snapshot_call(escalation_id: str) -> dict | None:
    live = _live.get(escalation_id)
    if live is None:
        return None
    esc = live.escalation
    return {
        "type": "snapshot",
        "escalation_id": esc.id,
        "patient_id": esc.patient_id,
        "patient_name": live.patient_name,
        "doctor_name": live.doctor_name,
        "status": esc.status.value,
        "summary": esc.summary,
        "messages": [asdict(m) for m in live.transport.messages] if live.transport else [],
    }


def get_live(escalation_id: str) -> LiveEscalation | None:
    return _live.get(escalation_id)


# --- persistence helpers -------------------------------------------------------------------

async def _log(call_id: str, *entries: CallLogEntry) -> None:
    await calls_col().update_one(
        {"_id": call_id},
        {"$push": {"logs": {"$each": [e.model_dump(mode="json") for e in entries]}}},
    )


async def _save(esc: Escalation, **fields) -> None:
    await escalations_col().update_one(
        {"_id": esc.id}, {"$set": {k: v.value if hasattr(v, "value") else v for k, v in fields.items()}}
    )


def _patient_transport(live: LiveEscalation) -> QueueTransport | None:
    call = live_calls.get_live_call(live.escalation.patient_id)
    return call.transport if call is not None else None


# --- lifecycle -----------------------------------------------------------------------------

async def begin(patient_id: str, patient_name: str, call_id: str, request: EscalationRequest) -> None:
    """The agent has escalated and the patient has heard the hand-off line: ring the doctors."""
    doctors = [doc_to_model(Doctor, d) async for d in doctors_col().find({"patient_ids": patient_id})]
    esc = Escalation(
        patient_id=patient_id,
        call_id=call_id,
        reason=request.reason,
        brief_summary=request.brief_summary,
        urgency=request.urgency,
        doctor_ids=[d.id for d in doctors],
    )
    await escalations_col().insert_one(model_to_doc(esc))
    live = LiveEscalation(esc, patient_name, {d.id: d.name for d in doctors})
    _live[esc.id] = live
    live_calls.set_escalation_state(patient_id, "ringing", escalation_id=esc.id)

    await _log(call_id, CallLogEntry(
        type=CallLogEntryType.escalation_call_started,
        related_call_id=esc.id,
        note=("ringing " + ", ".join(d.name for d in doctors)) if doctors else "no doctor assigned to this patient",
    ))
    if not doctors:
        await _close(live, NO_DOCTOR_LINE)
        return
    for doctor in doctors:
        _publish_doctor(doctor.id, {"type": "incoming_call", **_ring(live)})


async def join(escalation_id: str, doctor_id: str) -> Escalation:
    """A doctor picked up. Claims the call (first one wins) and starts their private briefing."""
    live = _live.get(escalation_id)
    if live is None or live.closing:
        raise EscalationError("this call is no longer active", 410)
    esc = live.escalation
    if doctor_id not in esc.doctor_ids:
        raise EscalationError("this call isn't for you", 403)
    if esc.status != EscalationStatus.ringing:
        if esc.doctor_id == doctor_id:
            return esc  # reloaded page / rejoin
        raise EscalationError("another doctor has already taken this call", 409)

    # Claim before the first await, so two doctors clicking at once can't both get it.
    esc.status = EscalationStatus.briefing
    esc.doctor_id = doctor_id
    esc.joined_at = datetime.utcnow()
    live.transport = QueueTransport(
        on_message=lambda m: _publish_call(escalation_id, {"type": "message", **asdict(m)}))
    live.task = asyncio.create_task(_run_briefing(live, doctor_id))

    await _save(esc, status=esc.status, doctor_id=doctor_id, joined_at=esc.joined_at)
    await calls_col().update_one({"_id": esc.call_id}, {"$set": {"doctor_id": doctor_id}})
    live_calls.set_escalation_state(esc.patient_id, "briefing", doctor_name=live.doctor_name)
    for other in esc.doctor_ids:
        _publish_doctor(other, {"type": "call_taken", "escalation_id": escalation_id})
    return esc


async def _run_briefing(live: LiveEscalation, doctor_id: str) -> None:
    esc = live.escalation
    context = None
    crashed = False
    try:
        session = await create_doctor_session(esc, doctor_id)
        context = session.context
        await run_chat_session(live.transport, session.config, context)
    except asyncio.CancelledError:
        raise  # end() cancelled us; the finally below still saves what was said
    except Exception:
        log.exception("doctor briefing for escalation %s crashed", esc.id)
        crashed = True
    finally:
        if context is not None and context.log_entries:
            await _log(esc.call_id, *context.log_entries)

    if crashed:
        live.transport.add_message("system", "Something went wrong preparing the briefing, so the call is being closed.")
        await end(esc.id, by="system")
    elif context.merge_confirmed:
        await _merge(live)
    else:
        await end(esc.id, by="doctor")


async def _merge(live: LiveEscalation) -> None:
    esc = live.escalation
    esc.status = EscalationStatus.merged
    esc.merged_at = datetime.utcnow()
    await _save(esc, status=esc.status, merged_at=esc.merged_at)
    await _log(esc.call_id, CallLogEntry(
        type=CallLogEntryType.escalation_call_merged,
        related_call_id=esc.id,
        note=f"{live.doctor_name} merged into the patient's call",
        channel="merged",
    ))
    patient_side = _patient_transport(live)
    if patient_side is not None:
        patient_side.add_message(
            "system", f"{live.doctor_name} has joined the call. VoiceMitra stays on the line to take notes.")
    live.transport.add_message(
        "system", f"Merged: you're now talking to {live.patient_name}. VoiceMitra is listening and taking notes.")
    live_calls.set_escalation_state(esc.patient_id, "merged")
    _publish_call(esc.id, {"type": "status", "status": "merged"})


async def doctor_message(escalation_id: str, text: str) -> None:
    live = _live.get(escalation_id)
    if live is None or live.closing or live.transport is None:
        return
    status = live.escalation.status
    if status == EscalationStatus.briefing:
        live.transport.push_user_text(text)  # the agent's turn loop reads it
    elif status == EscalationStatus.merged:
        live.transport.add_message("user", text)
        patient_side = _patient_transport(live)
        if patient_side is not None:
            patient_side.add_message("doctor", text)
        live.room.append(("doctor", text))
        await _log(live.escalation.call_id, CallLogEntry(
            type=CallLogEntryType.doctor_said, content=text, channel="merged"))


async def patient_message(escalation_id: str, text: str) -> None:
    """The patient's reply. Only relayed once merged: until then they're on hold."""
    live = _live.get(escalation_id)
    if live is None or live.closing or live.escalation.status != EscalationStatus.merged:
        return
    patient_side = _patient_transport(live)
    if patient_side is not None:
        patient_side.add_message("user", text)
    live.transport.add_message("patient", text)
    live.room.append(("patient", text))
    await _log(live.escalation.call_id, CallLogEntry(
        type=CallLogEntryType.patient_said, content=text, channel="merged"))


async def end(escalation_id: str, *, by: str) -> None:
    """End the escalated call (doctor, operator, or a failure). After a merge, summarises it."""
    live = _live.get(escalation_id)
    if live is None or live.closing:
        return
    esc = live.escalation
    was_merged = esc.status == EscalationStatus.merged
    live.closing = True

    # Stop the briefing conversation, waiting for it to save its log so the summary lands after it.
    if live.task is not None and live.task is not asyncio.current_task():
        live.task.cancel()
        await asyncio.gather(live.task, return_exceptions=True)

    await _close(live, ENDED_LINE if was_merged else NOT_CONNECTED_LINE)

    if was_merged:
        _publish_call(esc.id, {"type": "status", "status": "summarising"})
        try:
            esc.summary = await summarize_merged_call(
                patient_name=live.patient_name, doctor_name=live.doctor_name or "Doctor",
                reason=esc.reason, transcript=live.room)
        except Exception:
            log.exception("summary for escalation %s failed", esc.id)
            esc.summary = "The summary could not be generated. See the transcript."
        await _log(esc.call_id, CallLogEntry(
            type=CallLogEntryType.escalation_summary, content=esc.summary, related_call_id=esc.id,
            note=f"ended by {by}", channel="merged"))

    esc.status = EscalationStatus.resolved if was_merged else EscalationStatus.abandoned
    esc.ended_at = datetime.utcnow()
    await _save(esc, status=esc.status, ended_at=esc.ended_at, summary=esc.summary)
    _publish_call(esc.id, {"type": "status", "status": esc.status.value, "summary": esc.summary})


async def _close(live: LiveEscalation, patient_line: str) -> None:
    """Hang up both legs: tell the patient why, close the doctor's chat, clear any ringing cards."""
    esc = live.escalation
    live.closing = True
    patient_side = _patient_transport(live)
    if patient_side is not None:
        patient_side.add_message("system", patient_line)
    await live_calls.finish_call(esc.patient_id, esc.call_id)
    if live.transport is not None:
        live.transport.add_message("system", "The call has ended.")
        await live.transport.end()
    for doctor_id in esc.doctor_ids:
        _publish_doctor(doctor_id, {"type": "call_ended", "escalation_id": esc.id})
    if esc.status == EscalationStatus.ringing:  # nobody ever joined (or there was nobody to ring)
        esc.status = EscalationStatus.abandoned
        esc.ended_at = datetime.utcnow()
        await _save(esc, status=esc.status, ended_at=esc.ended_at)


async def abandon_stale() -> None:
    """On startup: live escalations don't survive a restart, so any still open in Mongo never will be."""
    await escalations_col().update_many(
        {"status": {"$in": [EscalationStatus.ringing.value, EscalationStatus.briefing.value,
                            EscalationStatus.merged.value]}},
        {"$set": {"status": EscalationStatus.abandoned.value, "ended_at": datetime.utcnow()}},
    )
