"""Real-time side of calls: WebSockets for the patient's chat window and the operator dashboard, plus
the operator's start/end controls. Events come from backend/live_calls.py; nothing here is polled.

Patient socket   /ws/patients/{id}/chat   server -> snapshot | call_started | message | call_ended
                                          client -> {"type": "reply", "text": "..."}
Operator socket  /ws/operator             server -> snapshot | call_started | call_ended
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from backend.live_calls import (
    PatientNotReady,
    active_patient_ids,
    get_live_call,
    snapshot_patient,
    start_call,
    subscribe_operator,
    subscribe_patient,
    unsubscribe_operator,
    unsubscribe_patient,
)

router = APIRouter(tags=["live"])

MAX_REPLY_CHARS = 2000


async def _serve(
    ws: WebSocket, queue: asyncio.Queue, on_receive: Callable[[dict], Awaitable[None]] | None = None
) -> None:
    """Forward queued events to the socket while reading whatever the client sends, until either
    side goes away."""

    async def pump() -> None:
        while True:
            await ws.send_json(await queue.get())

    async def listen() -> None:
        while True:
            try:
                data = await ws.receive_json()
            except WebSocketDisconnect:
                return
            except ValueError:  # not JSON: ignore rather than drop the connection
                continue
            if on_receive is not None and isinstance(data, dict):
                await on_receive(data)

    tasks = [asyncio.create_task(pump()), asyncio.create_task(listen())]
    try:
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


@router.websocket("/ws/patients/{patient_id}/chat")
async def patient_chat(ws: WebSocket, patient_id: str) -> None:
    await ws.accept()
    # Subscribe before taking the snapshot so nothing published in between is missed; the client
    # de-duplicates messages by index.
    queue = subscribe_patient(patient_id)
    try:
        await ws.send_json(snapshot_patient(patient_id))

        async def on_receive(data: dict) -> None:
            text = data.get("text")
            live = get_live_call(patient_id)
            if data.get("type") != "reply" or not isinstance(text, str) or live is None or not live.active:
                return
            text = text.strip()
            if text:
                live.transport.push_user_text(text[:MAX_REPLY_CHARS])

        await _serve(ws, queue, on_receive)
    finally:
        unsubscribe_patient(patient_id, queue)


@router.websocket("/ws/operator")
async def operator_events(ws: WebSocket) -> None:
    await ws.accept()
    queue = subscribe_operator()
    try:
        await ws.send_json({"type": "snapshot", "in_call": active_patient_ids()})
        await _serve(ws, queue)
    finally:
        unsubscribe_operator(queue)


@router.post("/api/patients/{patient_id}/call", status_code=204)
async def start_patient_call(patient_id: str) -> None:
    try:
        await start_call(patient_id)
    except PatientNotReady as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/api/patients/{patient_id}/call/end", status_code=204)
async def end_patient_call(patient_id: str) -> None:
    live = get_live_call(patient_id)
    if live is not None and live.active:
        live.transport.hang_up()
