"""Live updates for a patient's caregiver page (/ws/caregivers/{id}). Keyed by patient: a caregiver
looks after one patient, and the events are about that patient -- a new alert, a call starting or
ending. The page refetches its view on each one, so the events carry no more than their type.

Kept apart from live_calls.py so the domain code (caregiver.py) can publish without importing it.
"""

from __future__ import annotations

import asyncio

_subs: dict[str, set[asyncio.Queue]] = {}


def subscribe(patient_id: str) -> asyncio.Queue:
    queue: asyncio.Queue = asyncio.Queue()
    _subs.setdefault(patient_id, set()).add(queue)
    return queue


def unsubscribe(patient_id: str, queue: asyncio.Queue) -> None:
    subs = _subs.get(patient_id)
    if subs is not None:
        subs.discard(queue)
        if not subs:
            del _subs[patient_id]


def publish(patient_id: str, event: dict) -> None:
    for queue in _subs.get(patient_id, ()):
        queue.put_nowait(event)
