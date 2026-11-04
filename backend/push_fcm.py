"""Ring the patient's Android phones when a voice call starts (mobile/API.md, "Push").

An FCM *data* message at high priority wakes the app even when the phone is locked; the app shows its
full-screen call screen and, on answer, asks `GET /api/patients/{id}/voice-call` how to join. The
payload carries ids only -- no health information goes through Google.

Needs `FIREBASE_CREDENTIALS` (path to the Firebase service-account JSON). Without it nothing is sent
and a line is logged, so the rest of the app works the same.
"""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Awaitable, Callable
from datetime import timedelta
from enum import Enum

from backend.db import devices_col, doc_to_model
from backend.models import Device, DevicePlatform

log = logging.getLogger(__name__)

RING_TTL = timedelta(seconds=60)  # a ring delivered later than this is useless: drop it


class SendResult(str, Enum):
    ok = "ok"
    unregistered = "unregistered"  # the app was uninstalled / the token is stale: stop using it
    failed = "failed"              # anything else (network, quota): keep the token, try next time


# (push tokens, data) -> one result per token. Swapped for a fake in tests.
Sender = Callable[[list[str], dict[str, str]], Awaitable[list[SendResult]]]

_sender: Sender | None = None
_warned_unset = False
_tasks: set[asyncio.Task] = set()


def set_sender(sender: Sender | None) -> None:
    global _sender
    _sender = sender


def _firebase_sender() -> Sender | None:
    """The real sender, or None (with a log line, once) when Firebase isn't configured."""
    global _warned_unset
    path = os.environ.get("FIREBASE_CREDENTIALS", "").strip()
    if not path:
        if not _warned_unset:
            log.info("FIREBASE_CREDENTIALS is not set: phones are not rung (push skipped)")
            _warned_unset = True
        return None

    import firebase_admin
    from firebase_admin import credentials, messaging

    if not firebase_admin._apps:
        firebase_admin.initialize_app(credentials.Certificate(path))

    async def send(tokens: list[str], data: dict[str, str]) -> list[SendResult]:
        messages = [
            messaging.Message(token=t, data=data,
                              android=messaging.AndroidConfig(priority="high", ttl=RING_TTL))
            for t in tokens
        ]
        batch = await asyncio.to_thread(messaging.send_each, messages)
        results = []
        for r in batch.responses:
            if r.success:
                results.append(SendResult.ok)
            elif isinstance(r.exception, (messaging.UnregisteredError, messaging.SenderIdMismatchError)):
                results.append(SendResult.unregistered)
            else:
                log.warning("FCM send failed: %s", r.exception)
                results.append(SendResult.failed)
        return results

    return send


async def _push(patient_id: str, data: dict[str, str], skip_device_id: str | None) -> int:
    """Send `data` to the patient's Android phones; returns how many it reached."""
    query = {"patient_id": patient_id, "platform": DevicePlatform.android.value, "push_token": {"$ne": None}}
    devices = [doc_to_model(Device, d) async for d in devices_col().find(query)]
    devices = [d for d in devices if d.id != skip_device_id and d.push_token]
    if not devices:
        return 0
    sender = _sender or _firebase_sender()
    if sender is None:
        return 0
    results = await sender([d.push_token for d in devices], data)
    for device, result in zip(devices, results):
        if result is SendResult.unregistered:
            log.info("dropping stale push token of device %s", device.id)
            await devices_col().update_one({"_id": device.id, "push_token": device.push_token},
                                           {"$set": {"push_token": None}})
    return sum(r is SendResult.ok for r in results)


async def ring(patient_id: str, call_id: str, *, skip_device_id: str | None = None) -> int:
    return await _push(patient_id, {"type": "ring", "call_id": call_id, "patient_id": patient_id}, skip_device_id)


async def cancel_ring(patient_id: str, call_id: str) -> int:
    """The call ended (answered elsewhere, declined, timed out, operator hung up): stop ringing."""
    return await _push(patient_id, {"type": "call_ended", "call_id": call_id, "patient_id": patient_id}, None)


def spawn(coro: Awaitable[int], what: str) -> None:
    """Send in the background, so a slow FCM round trip never holds up starting or ending a call."""

    async def run() -> None:
        try:
            await coro
        except Exception:
            log.exception("push (%s) failed", what)

    task = asyncio.create_task(run())
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
