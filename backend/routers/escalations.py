"""Doctor side of an escalated call.

Dashboard socket  /ws/doctors/{id}          server -> snapshot | incoming_call | call_taken | call_ended
Call-page socket  /ws/escalations/{id}      server -> snapshot | message | status
                                            client -> {"type": "reply", "text": "..."}
Join / end are plain POSTs. Events come from backend/escalations.py; nothing here is polled.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, WebSocket
from pydantic import BaseModel

from backend import escalations
from backend.routers.live import MAX_REPLY_CHARS, serve_socket

router = APIRouter(tags=["escalations"])


@router.websocket("/ws/doctors/{doctor_id}")
async def doctor_events(ws: WebSocket, doctor_id: str) -> None:
    await ws.accept()
    queue = escalations.subscribe_doctor(doctor_id)
    try:
        await ws.send_json(escalations.snapshot_doctor(doctor_id))
        await serve_socket(ws, queue)
    finally:
        escalations.unsubscribe_doctor(doctor_id, queue)


@router.websocket("/ws/escalations/{escalation_id}")
async def escalation_call(ws: WebSocket, escalation_id: str) -> None:
    await ws.accept()
    queue = escalations.subscribe_call(escalation_id)
    try:
        snapshot = escalations.snapshot_call(escalation_id)
        if snapshot is None:  # not live any more (ended, or the server restarted)
            await ws.send_json({"type": "gone"})
            return
        await ws.send_json(snapshot)

        async def on_receive(data: dict) -> None:
            text = data.get("text")
            if data.get("type") != "reply" or not isinstance(text, str):
                return
            text = text.strip()
            if text:
                await escalations.doctor_message(escalation_id, text[:MAX_REPLY_CHARS])

        await serve_socket(ws, queue, on_receive)
    finally:
        escalations.unsubscribe_call(escalation_id, queue)


class JoinRequest(BaseModel):
    doctor_id: str


@router.post("/api/escalations/{escalation_id}/join")
async def join_escalation(escalation_id: str, body: JoinRequest) -> dict:
    try:
        await escalations.join(escalation_id, body.doctor_id)
    except escalations.EscalationError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
    return {"url": f"/doctors/{body.doctor_id}/escalations/{escalation_id}"}


@router.post("/api/escalations/{escalation_id}/end", status_code=204)
async def end_escalation(escalation_id: str) -> None:
    await escalations.end(escalation_id, by="doctor")
