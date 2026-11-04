"""Phones paired to a patient (mobile/API.md, "Identity: pairing").

The patient's page shows a 6-digit code ("Connect a phone"); the phone app sends it to
`POST /api/devices/pair` and gets back a device id + secret token. The token (sent as
`X-Device-Token`) is the app's only credential -- there is no login yet. Only its hash is stored.
"""

from __future__ import annotations

import hashlib
import secrets
import time
from collections import deque
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from backend.db import devices_col, doc_to_model, model_to_doc, pairing_codes_col, patients_col
from backend.models import Device, DevicePlatform, PairingCode, Patient

router = APIRouter(tags=["devices"])

CODE_LIFETIME = timedelta(minutes=10)
# Wrong codes allowed (across all callers: behind the tunnel every phone has the same address)
# per window before pairing is paused. 6 digits = 1,000,000 codes, so guessing one in time is hopeless.
MAX_BAD_CODES = 20
BAD_CODE_WINDOW_SECONDS = 600

_bad_codes: deque[float] = deque()


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def device_for_token(token: str | None) -> Device | None:
    """The device this `X-Device-Token` belongs to, or None (no/unknown token)."""
    if not token:
        return None
    return doc_to_model(Device, await devices_col().find_one({"token_hash": hash_token(token)}))


async def _authorised(device_id: str, token: str | None) -> Device:
    device = doc_to_model(Device, await devices_col().find_one({"_id": device_id}))
    if device is None:
        raise HTTPException(status_code=404, detail="device not found (unpaired)")
    if not token or not secrets.compare_digest(device.token_hash, hash_token(token)):
        raise HTTPException(status_code=401, detail="wrong device token")
    return device


# --- the web side: show a code -----------------------------------------------------------

def _utc(dt: datetime) -> datetime:
    """Stored times are naive UTC; send them with the zone so clients don't read them as local time."""
    return dt.replace(tzinfo=timezone.utc)


class PairingCodeOut(BaseModel):
    code: str
    expires_at: datetime
    expires_in: int  # seconds: count down from this, so a wrong clock on the screen doesn't matter


@router.post("/api/patients/{patient_id}/pairing-code", response_model=PairingCodeOut)
async def create_pairing_code(patient_id: str) -> PairingCodeOut:
    if await patients_col().find_one({"_id": patient_id}, {"_id": 1}) is None:
        raise HTTPException(status_code=404, detail="patient not found")
    now = datetime.utcnow()
    # One live code per patient: asking again replaces the one on screen.
    await pairing_codes_col().update_many({"patient_id": patient_id, "used": False}, {"$set": {"used": True}})
    while True:
        code = f"{secrets.randbelow(1_000_000):06d}"
        clash = await pairing_codes_col().find_one({"code": code, "used": False})
        if clash is None:
            break
        if doc_to_model(PairingCode, clash).expires_at <= now:
            # An old, never-used code with the same digits: retire it so pairing can't claim it instead.
            await pairing_codes_col().update_one({"_id": clash["_id"]}, {"$set": {"used": True}})
            break
    pairing = PairingCode(code=code, patient_id=patient_id, expires_at=now + CODE_LIFETIME)
    await pairing_codes_col().insert_one(model_to_doc(pairing))
    return PairingCodeOut(code=code, expires_at=_utc(pairing.expires_at), expires_in=int(CODE_LIFETIME.total_seconds()))


class DeviceView(BaseModel):
    id: str
    platform: DevicePlatform
    name: str | None
    created_at: datetime
    last_seen: datetime


@router.get("/api/patients/{patient_id}/devices", response_model=list[DeviceView])
async def list_devices(patient_id: str) -> list[DeviceView]:
    """The patient's paired phones (the web page shows them, and notices when a new one pairs)."""
    docs = await devices_col().find({"patient_id": patient_id}).sort("created_at", 1).to_list(length=50)
    views = []
    for d in docs:
        device = doc_to_model(Device, d)
        views.append(DeviceView(id=device.id, platform=device.platform, name=device.name,
                                created_at=_utc(device.created_at), last_seen=_utc(device.last_seen)))
    return views


# --- the app side ------------------------------------------------------------------------

class PairRequest(BaseModel):
    code: str = Field(min_length=1, max_length=12)
    platform: DevicePlatform
    push_token: str | None = Field(default=None, max_length=4096)
    name: str | None = Field(default=None, max_length=100)


class PairResponse(BaseModel):
    device_id: str
    device_token: str
    patient_id: str
    patient_name: str


def _too_many_bad_codes() -> bool:
    cutoff = time.monotonic() - BAD_CODE_WINDOW_SECONDS
    while _bad_codes and _bad_codes[0] < cutoff:
        _bad_codes.popleft()
    return len(_bad_codes) >= MAX_BAD_CODES


@router.post("/api/devices/pair", response_model=PairResponse)
async def pair_device(body: PairRequest) -> PairResponse:
    if _too_many_bad_codes():
        raise HTTPException(status_code=429, detail="too many wrong codes, try again in a few minutes")
    code = "".join(ch for ch in body.code if ch.isdigit())
    now = datetime.utcnow()
    # Claim the code atomically, so two phones can't both use it.
    doc = await pairing_codes_col().find_one_and_update(
        {"code": code, "used": False}, {"$set": {"used": True}},
    )
    pairing = doc_to_model(PairingCode, doc)
    if pairing is None or pairing.expires_at <= now:
        _bad_codes.append(time.monotonic())
        raise HTTPException(status_code=400, detail="wrong or expired code")
    patient = doc_to_model(Patient, await patients_col().find_one({"_id": pairing.patient_id}))
    if patient is None:
        raise HTTPException(status_code=400, detail="wrong or expired code")
    return await create_device(patient, body.platform, body.push_token, body.name)


async def create_device(
    patient: Patient, platform: DevicePlatform, push_token: str | None, name: str | None,
) -> PairResponse:
    """Register a phone for `patient` and hand back its secret token. Shared by pairing and login."""
    if push_token:
        # The same phone pairing again (or for someone else): drop its old record, or it would ring twice.
        await devices_col().delete_many({"push_token": push_token})
    token = secrets.token_urlsafe(32)
    device = Device(patient_id=patient.id, platform=platform, push_token=push_token or None,
                    name=name, token_hash=hash_token(token))
    await devices_col().insert_one(model_to_doc(device))
    return PairResponse(device_id=device.id, device_token=token, patient_id=patient.id, patient_name=patient.name)


class DeviceInfo(BaseModel):
    device_id: str
    patient_id: str
    patient_name: str


@router.get("/api/devices/{device_id}", response_model=DeviceInfo)
async def get_device(device_id: str, x_device_token: str | None = Header(default=None)) -> DeviceInfo:
    """The app checks it is still paired (404 = unpaired, 401 = wrong token: pair again)."""
    device = await _authorised(device_id, x_device_token)
    patient = doc_to_model(Patient, await patients_col().find_one({"_id": device.patient_id}))
    if patient is None:
        raise HTTPException(status_code=404, detail="patient not found")
    await devices_col().update_one({"_id": device_id}, {"$set": {"last_seen": datetime.utcnow().isoformat()}})
    return DeviceInfo(device_id=device.id, patient_id=patient.id, patient_name=patient.name)


class UpdateDeviceRequest(BaseModel):
    push_token: str | None = Field(default=None, max_length=4096)


@router.put("/api/devices/{device_id}", status_code=204)
async def update_device(
    device_id: str, body: UpdateDeviceRequest, x_device_token: str | None = Header(default=None),
) -> None:
    """FCM rotates registration tokens; the app sends the new one."""
    await _authorised(device_id, x_device_token)
    if body.push_token:
        await devices_col().delete_many({"push_token": body.push_token, "_id": {"$ne": device_id}})
    await devices_col().update_one(
        {"_id": device_id},
        {"$set": {"push_token": body.push_token or None, "last_seen": datetime.utcnow().isoformat()}},
    )


@router.delete("/api/devices/{device_id}", status_code=204)
async def unpair_device(device_id: str, x_device_token: str | None = Header(default=None)) -> None:
    await _authorised(device_id, x_device_token)
    await devices_col().delete_one({"_id": device_id})
