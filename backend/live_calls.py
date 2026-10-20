"""In-flight web-chat calls (one per patient) and the events around them.

Nothing here is polled: the patient's page and the operator dashboard each hold a WebSocket and
subscribe to a queue; call start / message / end are pushed to those queues as they happen. Also
owns reminder timers -- a patient who says "I'll take it later" gets a call back at the time they
asked for, armed with `asyncio.sleep`, not a scan loop.

State is in-process only: a server restart drops live calls (their Call document keeps whatever
logs were flushed) and re-arms still-pending reminders from Mongo (see `rearm_pending_reminders`).
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta

from backend.db import reminders_col
from backend.livekit_client import create_call_room as create_livekit_room
from backend.models import Reminder, ReminderStatus
from core.transport.queue_transport import Message, QueueTransport
from core.transport.livekit_transport import LiveKitTransport
from domains.med_adherence.caregiver import notify_caregiver_unreachable
from domains.med_adherence.bot import PatientNotReady, create_call_session, run_call_session, run_voice_call

__all__ = [
    "LiveCall", "PatientNotReady", "VoiceCall", "start_voice_call", "get_voice_call", "finish_voice_call", "active_patient_ids", "end_call", "finish_call", "get_live_call",
    "publish_operator", "publish_patient", "rearm_pending_reminders", "set_escalation_state",
    "snapshot_patient", "start_call", "subscribe_operator", "subscribe_patient",
    "unsubscribe_operator", "unsubscribe_patient",
]

log = logging.getLogger(__name__)

# A reminder that comes due while the patient is still in a call waits and tries again.
REMINDER_RETRY_SECONDS = 15
# After a server restart, reminders more than this late are dropped rather than fired out of the blue.
REMINDER_MAX_LATE = timedelta(minutes=30)


@dataclass
class LiveCall:
    call_id: str
    transport: QueueTransport
    task: asyncio.Task
    # Set once the agent has escalated: the patient's line stays open (held, then merged with the
    # doctor) and backend/escalations.py drives it from there.
    escalation_id: str | None = None
    escalation_status: str | None = None
    escalation_doctor: str | None = None

    @property
    def active(self) -> bool:
        return not self.transport.ended


@dataclass
class VoiceCall:
    """A call carried by a LiveKit room: the agent runs in-process (`task`, then `transport` after an
    escalation), the patient's browser joins with `patient_token`."""
    call_id: str
    room_name: str
    room_url: str
    patient_token: str
    transport: LiveKitTransport
    task: asyncio.Task | None = None
    escalation_id: str | None = None
    escalation_status: str | None = None
    escalation_doctor: str | None = None
    # Everything logged so far (transcript, tool calls, escalation events) as JSON-able dicts, so a
    # reloaded page can show the whole call; the same entries are written to Mongo with the call.
    entries: list[dict] = field(default_factory=list)


_live_calls: dict[str, LiveCall] = {}
_voice_calls: dict[str, VoiceCall] = {}
_patient_subs: dict[str, set[asyncio.Queue]] = {}
_operator_subs: set[asyncio.Queue] = set()
_reminder_tasks: set[asyncio.Task] = set()


# --- subscriptions -------------------------------------------------------------------------

def subscribe_patient(patient_id: str) -> asyncio.Queue:
    queue: asyncio.Queue = asyncio.Queue()
    _patient_subs.setdefault(patient_id, set()).add(queue)
    return queue


def unsubscribe_patient(patient_id: str, queue: asyncio.Queue) -> None:
    subs = _patient_subs.get(patient_id)
    if subs is not None:
        subs.discard(queue)
        if not subs:
            del _patient_subs[patient_id]


def subscribe_operator() -> asyncio.Queue:
    queue: asyncio.Queue = asyncio.Queue()
    _operator_subs.add(queue)
    return queue


def unsubscribe_operator(queue: asyncio.Queue) -> None:
    _operator_subs.discard(queue)


def publish_patient(patient_id: str, event: dict) -> None:
    for queue in _patient_subs.get(patient_id, ()):
        queue.put_nowait(event)


def publish_operator(event: dict) -> None:
    for queue in _operator_subs:
        queue.put_nowait(event)


# --- state for a newly connected socket ----------------------------------------------------

def snapshot_patient(patient_id: str) -> dict:
    live = _live_calls.get(patient_id)
    voice = _voice_calls.get(patient_id)
    if voice is not None:
        return {"type": "snapshot", "call_id": None, "active": False, "messages": [], "escalation": None,
                "voice": _voice_event(voice), "log": voice.entries,
                "escalation": _voice_escalation_event(voice) if voice.escalation_status else None}
    if live is None:
        return {"type": "snapshot", "call_id": None, "active": False, "messages": [], "escalation": None}
    return {
        "type": "snapshot",
        "call_id": live.call_id,
        "active": live.active,
        "messages": [asdict(m) for m in live.transport.messages],
        "escalation": _escalation_event(live) if live.escalation_status else None,
    }


def _escalation_event(live: LiveCall) -> dict:
    return {
        "type": "escalation",
        "call_id": live.call_id,
        "status": live.escalation_status,
        "doctor_name": live.escalation_doctor,
    }


def set_escalation_state(
    patient_id: str, status: str, *, escalation_id: str | None = None, doctor_name: str | None = None
) -> None:
    """Record where the patient's escalated call has got to (ringing / briefing / merged) and tell
    their page, so it can show the hold notice or let them talk to the doctor."""
    voice = _voice_calls.get(patient_id)
    if voice is not None:
        voice.escalation_status = status
        if escalation_id is not None:
            voice.escalation_id = escalation_id
        if doctor_name is not None:
            voice.escalation_doctor = doctor_name
        publish_patient(patient_id, _voice_escalation_event(voice))
        return
    live = _live_calls.get(patient_id)
    if live is None:
        return
    live.escalation_status = status
    if escalation_id is not None:
        live.escalation_id = escalation_id
    if doctor_name is not None:
        live.escalation_doctor = doctor_name
    publish_patient(patient_id, _escalation_event(live))


def add_voice_entry(patient_id: str, entry) -> None:
    """Show a call-log entry on the patient's page and keep it for pages that connect later."""
    voice = _voice_calls.get(patient_id)
    if voice is None:
        return
    data = entry.model_dump(mode="json")
    voice.entries.append(data)
    publish_patient(patient_id, {"type": "log_entry", "call_id": voice.call_id, "entry": data})


def get_voice_call(patient_id: str) -> VoiceCall | None:
    return _voice_calls.get(patient_id)


def get_live_call(patient_id: str) -> LiveCall | None:
    """The patient's current call, or their most recent one if it has just ended (so the page can
    show the closing message); None if they haven't had one since the server started."""
    return _live_calls.get(patient_id)


def active_patient_ids() -> list[str]:
    return [pid for pid, live in _live_calls.items() if live.active] + list(_voice_calls)


# --- calls ---------------------------------------------------------------------------------

async def start_call(patient_id: str) -> LiveCall:
    existing = _live_calls.get(patient_id)
    if existing is not None and existing.active:
        return existing

    session = await create_call_session(patient_id, on_reminder_created=arm_reminder)
    call_id = session.call.id

    def on_message(message: Message) -> None:
        publish_patient(patient_id, {"type": "message", "call_id": call_id, **asdict(message)})

    transport = QueueTransport(on_message=on_message)
    task = asyncio.create_task(_run(patient_id, call_id, session, transport))
    _live_calls[patient_id] = LiveCall(call_id=call_id, transport=transport, task=task)

    # No await between create_task and here, so the session can't have produced a message yet:
    # subscribers always see call_started before the first message.
    publish_patient(patient_id, {"type": "call_started", "call_id": call_id})
    publish_operator({"type": "call_started", "patient_id": patient_id})
    return _live_calls[patient_id]


async def _run(patient_id: str, call_id: str, session, transport: QueueTransport) -> None:
    handed_off = False
    try:
        await run_call_session(session, transport)
        if session.context.escalation is not None:
            # Imported here: escalations.py itself builds on this module.
            from backend import escalations

            await escalations.begin(patient_id, session.patient.name, call_id, session.context.escalation)
            handed_off = True  # the patient stays on the line; escalations.py ends the call
    except Exception:
        log.exception("call %s crashed", call_id)
        await transport.send_text("Sorry, something went wrong on our side. We'll try again shortly.")
    finally:
        # run_chat_session only reaches transport.end() on a clean exit, and skips it on hand-off.
        if not handed_off:
            await finish_call(patient_id, call_id)


async def finish_call(patient_id: str, call_id: str) -> None:
    """Hang up on the patient and tell their page and the operator dashboard."""
    live = _live_calls.get(patient_id)
    if live is not None and live.call_id == call_id:
        await live.transport.end()
    publish_patient(patient_id, {"type": "call_ended", "call_id": call_id})
    publish_operator({"type": "call_ended", "patient_id": patient_id})


def _voice_event(voice: VoiceCall) -> dict:
    return {"type": "voice_call", "call_id": voice.call_id, "url": voice.room_url, "token": voice.patient_token}


def _voice_escalation_event(voice: VoiceCall) -> dict:
    return {
        "type": "escalation",
        "call_id": voice.call_id,
        "status": voice.escalation_status,
        "doctor_name": voice.escalation_doctor,
    }


async def start_voice_call(patient_id: str) -> VoiceCall:
    """Put the patient and the agent in a LiveKit room: the agent joins now (in-process), the
    patient's page joins with the token it is sent."""
    existing = _voice_calls.get(patient_id)
    if existing is not None:
        return existing
    if (chat := _live_calls.get(patient_id)) is not None and chat.active:
        raise PatientNotReady("patient is already in a chat call")
    session = await create_call_session(patient_id)
    call_id = session.call.id
    room = create_livekit_room(f"call-{call_id}")
    voice = VoiceCall(
        call_id=call_id, room_name=room.name, room_url=room.url, patient_token=room.patient_token,
        transport=LiveKitTransport(room.url, room.bot_token, room.name),
    )
    session.context.on_log_entry = lambda entry: add_voice_entry(patient_id, entry)
    voice.task = asyncio.create_task(_run_voice(patient_id, session, voice))
    _voice_calls[patient_id] = voice
    publish_patient(patient_id, _voice_event(voice))
    publish_operator({"type": "call_started", "patient_id": patient_id})
    return voice


async def _run_voice(patient_id: str, session, voice: VoiceCall) -> None:
    handed_off = False
    try:
        await run_voice_call(session, voice.transport)
        if session.context.escalation is not None:
            from backend import escalations  # imported here: escalations.py builds on this module

            await escalations.begin(patient_id, session.patient.name, voice.call_id, session.context.escalation)
            handed_off = True  # the patient stays in the room; escalations.py ends the call
    except asyncio.CancelledError:
        pass
    except TimeoutError:
        log.info("patient %s never joined call %s", patient_id, voice.call_id)
        await notify_caregiver_unreachable(patient_id, voice.call_id)
    except Exception:
        log.exception("voice call %s failed", voice.call_id)
    finally:
        if not handed_off:
            await finish_voice_call(patient_id, voice.call_id, speak=None)


async def finish_voice_call(patient_id: str, call_id: str, *, speak: str | None) -> None:
    """Hang up on the patient (saying `speak` first, if given) and tell their page and the operator."""
    voice = _voice_calls.get(patient_id)
    if voice is None or voice.call_id != call_id:
        return
    del _voice_calls[patient_id]
    if speak and not voice.transport.ended:
        await voice.transport.send_text(speak)
        await voice.transport.end()  # waits for the line to be spoken
    else:
        await voice.transport.abort()
    publish_patient(patient_id, {"type": "voice_call_ended", "call_id": call_id})
    publish_operator({"type": "call_ended", "patient_id": patient_id})


async def end_call(patient_id: str) -> None:
    """The operator's End call: closes the conversation, or the doctor leg if the call has escalated."""
    if (voice := _voice_calls.get(patient_id)) is not None:
        if voice.escalation_id is not None:
            from backend import escalations

            await escalations.end(voice.escalation_id, by="operator")
        elif voice.task is not None:
            voice.task.cancel()  # _run_voice hangs up and announces the end
        return
    live = _live_calls.get(patient_id)
    if live is None or not live.active:
        return
    if live.escalation_id is not None:
        from backend import escalations

        await escalations.end(live.escalation_id, by="operator")
    else:
        live.transport.hang_up()


# --- reminders -----------------------------------------------------------------------------

def arm_reminder(reminder: Reminder) -> None:
    delay = max(0.0, (reminder.remind_at - datetime.utcnow()).total_seconds())
    task = asyncio.create_task(_fire_reminder(reminder, delay))
    _reminder_tasks.add(task)
    task.add_done_callback(_reminder_tasks.discard)


async def _fire_reminder(reminder: Reminder, delay: float) -> None:
    try:
        await asyncio.sleep(delay)
        while (live := _live_calls.get(reminder.patient_id)) is not None and live.active:
            await asyncio.sleep(REMINDER_RETRY_SECONDS)
        await start_call(reminder.patient_id)
        await reminders_col().update_one(
            {"_id": reminder.id}, {"$set": {"status": ReminderStatus.fired.value}}
        )
    except Exception:
        log.exception("reminder %s could not be fired", reminder.id)


async def rearm_pending_reminders() -> None:
    """On startup: timers don't survive a restart, but the Reminder documents do."""
    now = datetime.utcnow()
    async for doc in reminders_col().find({"status": ReminderStatus.pending.value}):
        reminder = Reminder(**doc)
        if now - reminder.remind_at > REMINDER_MAX_LATE:
            await reminders_col().update_one(
                {"_id": reminder.id}, {"$set": {"status": ReminderStatus.missed.value}}
            )
        else:
            arm_reminder(reminder)
