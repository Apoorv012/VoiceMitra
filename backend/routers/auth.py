"""Phone-app login with a username + password (mobile/API.md, "Identity: login").

The web page (patient's Me tab) sets the patient's username and password; the app sends them to
`POST /api/auth/login` and gets back the same device id + token as pairing does, so everything after
that (X-Device-Token, unpairing = logging out) is shared with pairing. Pairing stays as a fallback.
"""

from __future__ import annotations

import asyncio
import time
from collections import deque

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from pymongo.errors import DuplicateKeyError

from backend.auth import DUMMY_HASH, hash_password, verify_password
from backend.db import doc_to_model, get_db, model_to_doc, patients_col
from backend.models import DevicePlatform, Patient, PatientLogin
from backend.routers.devices import PairResponse, create_device

router = APIRouter(tags=["auth"])

MIN_PASSWORD = 6
MIN_USERNAME, MAX_USERNAME = 3, 40
# Failed logins allowed (across all callers: behind the tunnel every phone has the same address) per
# window before logins are paused -- the same rule as wrong pairing codes.
MAX_BAD_LOGINS = 20
BAD_LOGIN_WINDOW_SECONDS = 600

_bad_logins: deque[float] = deque()


def logins_col():
    return get_db()["patient_logins"]


async def _ensure_index() -> None:
    # Here rather than in db.ensure_indexes so this feature stays in its own files; cheap when it exists.
    await logins_col().create_index("username_key", unique=True)


def _key(username: str) -> str:
    return username.strip().casefold()


# --- the web side: set / show / remove the login -------------------------------------------

class SetLoginRequest(BaseModel):
    username: str = Field(max_length=200)
    password: str = Field(max_length=200)


class LoginView(BaseModel):
    username: str


async def _require_patient(patient_id: str) -> None:
    if await patients_col().find_one({"_id": patient_id}, {"_id": 1}) is None:
        raise HTTPException(status_code=404, detail="patient not found")


@router.put("/api/patients/{patient_id}/login", status_code=204,
            responses={400: {"description": "username or password too short/long"},
                       409: {"description": "username taken by another patient"}})
async def set_login(patient_id: str, body: SetLoginRequest) -> None:
    await _require_patient(patient_id)
    username = body.username.strip()
    if not MIN_USERNAME <= len(username) <= MAX_USERNAME:
        raise HTTPException(status_code=400, detail=f"username must be {MIN_USERNAME}-{MAX_USERNAME} characters")
    if len(body.password) < MIN_PASSWORD:
        raise HTTPException(status_code=400, detail=f"password must be at least {MIN_PASSWORD} characters")
    await _ensure_index()
    key = _key(username)
    taken = await logins_col().find_one({"username_key": key, "_id": {"$ne": patient_id}}, {"_id": 1})
    if taken is not None:
        raise HTTPException(status_code=409, detail="username already taken")
    login = PatientLogin(id=patient_id, username=username, username_key=key,
                         password_hash=await asyncio.to_thread(hash_password, body.password))
    doc = model_to_doc(login)
    try:
        await logins_col().replace_one({"_id": patient_id}, doc, upsert=True)
    except DuplicateKeyError:  # someone took it between the check and the write
        raise HTTPException(status_code=409, detail="username already taken") from None


@router.get("/api/patients/{patient_id}/login", response_model=LoginView,
            responses={404: {"description": "no login set"}})
async def get_login(patient_id: str) -> LoginView:
    login = doc_to_model(PatientLogin, await logins_col().find_one({"_id": patient_id}))
    if login is None:
        raise HTTPException(status_code=404, detail="no login set")
    return LoginView(username=login.username)


@router.delete("/api/patients/{patient_id}/login", status_code=204)
async def delete_login(patient_id: str) -> None:
    """Phones already logged in stay connected (unpair them separately)."""
    await logins_col().delete_one({"_id": patient_id})


# --- the app side --------------------------------------------------------------------------

class LoginRequest(BaseModel):
    username: str = Field(max_length=200)
    password: str = Field(max_length=200)
    platform: DevicePlatform
    push_token: str | None = Field(default=None, max_length=4096)
    name: str | None = Field(default=None, max_length=100)


def _too_many_bad_logins() -> bool:
    cutoff = time.monotonic() - BAD_LOGIN_WINDOW_SECONDS
    while _bad_logins and _bad_logins[0] < cutoff:
        _bad_logins.popleft()
    return len(_bad_logins) >= MAX_BAD_LOGINS


@router.post("/api/auth/login", response_model=PairResponse,
             responses={401: {"description": "wrong username or password"},
                        429: {"description": "too many failed logins, paused"}})
async def login(body: LoginRequest) -> PairResponse:
    if _too_many_bad_logins():
        raise HTTPException(status_code=429, detail="too many failed logins, try again in a few minutes")
    record = doc_to_model(PatientLogin, await logins_col().find_one({"username_key": _key(body.username)}))
    ok = await asyncio.to_thread(verify_password, body.password, record.password_hash if record else DUMMY_HASH)
    patient = None
    if ok and record is not None:
        patient = doc_to_model(Patient, await patients_col().find_one({"_id": record.id}))
    if patient is None:
        _bad_logins.append(time.monotonic())
        raise HTTPException(status_code=401, detail="wrong username or password")
    return await create_device(patient, body.platform, body.push_token, body.name)
