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
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta

from backend.db import reminders_col
from backend.models import Reminder, ReminderStatus
from core.transport.queue_transport import Message, QueueTransport
from domains.med_adherence.bot import PatientNotReady, create_call_session, run_call_session

__all__ = [
    "LiveCall", "PatientNotReady", "active_patient_ids", "get_live_call", "rearm_pending_reminders",
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

    @property
    def active(self) -> bool:
        return not self.transport.ended


_live_calls: dict[str, LiveCall] = {}
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


def _publish_patient(patient_id: str, event: dict) -> None:
    for queue in _patient_subs.get(patient_id, ()):
        queue.put_nowait(event)


def _publish_operator(event: dict) -> None:
    for queue in _operator_subs:
        queue.put_nowait(event)


# --- state for a newly connected socket ----------------------------------------------------

def snapshot_patient(patient_id: str) -> dict:
    live = _live_calls.get(patient_id)
    if live is None:
        return {"type": "snapshot", "call_id": None, "active": False, "messages": []}
    return {
        "type": "snapshot",
        "call_id": live.call_id,
        "active": live.active,
        "messages": [asdict(m) for m in live.transport.messages],
    }


def get_live_call(patient_id: str) -> LiveCall | None:
    """The patient's current call, or their most recent one if it has just ended (so the page can
    show the closing message); None if they haven't had one since the server started."""
    return _live_calls.get(patient_id)


def active_patient_ids() -> list[str]:
    return [pid for pid, live in _live_calls.items() if live.active]


# --- calls ---------------------------------------------------------------------------------

async def start_call(patient_id: str) -> LiveCall:
    existing = _live_calls.get(patient_id)
    if existing is not None and existing.active:
        return existing

    session = await create_call_session(patient_id, on_reminder_created=arm_reminder)
    call_id = session.call.id

    def on_message(message: Message) -> None:
        _publish_patient(patient_id, {"type": "message", "call_id": call_id, **asdict(message)})

    transport = QueueTransport(on_message=on_message)
    task = asyncio.create_task(_run(patient_id, call_id, session, transport))
    _live_calls[patient_id] = LiveCall(call_id=call_id, transport=transport, task=task)

    # No await between create_task and here, so the session can't have produced a message yet:
    # subscribers always see call_started before the first message.
    _publish_patient(patient_id, {"type": "call_started", "call_id": call_id})
    _publish_operator({"type": "call_started", "patient_id": patient_id})
    return _live_calls[patient_id]


async def _run(patient_id: str, call_id: str, session, transport: QueueTransport) -> None:
    try:
        await run_call_session(session, transport)
    except Exception:
        log.exception("call %s crashed", call_id)
        await transport.send_text("Sorry, something went wrong on our side. We'll try again shortly.")
    finally:
        # run_chat_session only reaches transport.end() on a clean exit.
        await transport.end()
        _publish_patient(patient_id, {"type": "call_ended", "call_id": call_id})
        _publish_operator({"type": "call_ended", "patient_id": patient_id})


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
