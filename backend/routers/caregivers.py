"""The caregiver's side: mark alerts as seen, and a socket that tells their page when to refresh.

Caregiver socket  /ws/caregivers/{id}  server -> snapshot | alert | alerts_seen | call_started | call_ended
                                       (each one means "refetch /api/app/caregivers/{id}/home")
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, WebSocket

from backend import family_feed
from backend.access import require_caregiver, ws_require_caregiver
from backend.db import caregiver_notifications_col, caregivers_col, doc_to_model
from backend.live_calls import active_patient_ids
from backend.models import Caregiver
from backend.routers.live import serve_socket

router = APIRouter(tags=["caregivers"])


async def _caregiver(caregiver_id: str) -> Caregiver | None:
    return doc_to_model(Caregiver, await caregivers_col().find_one({"_id": caregiver_id}))


async def _mark_seen(caregiver: Caregiver, query: dict) -> None:
    await caregiver_notifications_col().update_many(
        {"caregiver_id": caregiver.id, "seen_at": None, **query},
        {"$set": {"seen_at": datetime.utcnow().isoformat()}},
    )
    family_feed.publish(caregiver.patient_id, {"type": "alerts_seen"})


@router.post("/api/caregivers/{caregiver_id}/alerts/{alert_id}/seen", status_code=204,
             dependencies=[Depends(require_caregiver)])
async def mark_alert_seen(caregiver_id: str, alert_id: str) -> None:
    caregiver = await _caregiver(caregiver_id)
    if caregiver is None:
        raise HTTPException(status_code=404, detail="caregiver not found")
    await _mark_seen(caregiver, {"_id": alert_id})


@router.post("/api/caregivers/{caregiver_id}/alerts/seen", status_code=204, dependencies=[Depends(require_caregiver)])
async def mark_all_alerts_seen(caregiver_id: str) -> None:
    caregiver = await _caregiver(caregiver_id)
    if caregiver is None:
        raise HTTPException(status_code=404, detail="caregiver not found")
    await _mark_seen(caregiver, {})


@router.websocket("/ws/caregivers/{caregiver_id}", dependencies=[Depends(ws_require_caregiver)])
async def caregiver_events(ws: WebSocket, caregiver_id: str) -> None:
    await ws.accept()
    caregiver = await _caregiver(caregiver_id)
    if caregiver is None:
        await ws.close(code=4404)
        return
    queue = family_feed.subscribe(caregiver.patient_id)
    try:
        await ws.send_json({"type": "snapshot", "in_call": caregiver.patient_id in set(active_patient_ids())})
        await serve_socket(ws, queue)
    finally:
        family_feed.unsubscribe(caregiver.patient_id, queue)
