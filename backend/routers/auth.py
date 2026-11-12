"""Signing in: the website (a session cookie) and the phone apps (a device token), plus setting logins.

Website  POST /api/auth/session {username, password} -> sets the `vm_session` cookie; GET /api/auth/me;
         DELETE /api/auth/session signs out; POST /api/auth/ws-ticket -> a ticket for opening a socket.
Apps     POST /api/auth/login -> the same device id + token as pairing (mobile/API.md, "Identity: login").
         Patients only: a family or staff login gets 403 with a reason the app can show.
Logins   PUT/GET /api/patients/{id}/login and /api/caregivers/{id}/login (staff, or that person changing
         their own); DELETE is staff only. Staff logins come from `python -m backend.create_staff`.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from backend import access, logins
from backend.access import Principal, require_caregiver, require_patient, require_staff, signed_in
from backend.db import caregivers_col, doc_to_model, patients_col
from backend.models import Caregiver, DevicePlatform, LoginRole, Patient
from backend.routers.devices import PairResponse, create_device

router = APIRouter(tags=["auth"])


class SetLoginRequest(BaseModel):
    username: str = Field(max_length=200)
    password: str = Field(max_length=200)


class LoginView(BaseModel):
    username: str


async def _view(subject_id: str) -> LoginView:
    login = await logins.get(subject_id)
    if login is None:
        raise HTTPException(status_code=404, detail="no login set")
    return LoginView(username=login.username)


def _keep(p: Principal, subject_id: str) -> str | None:
    """Changing your own password keeps the session you changed it from."""
    return p.session_hash if p.id == subject_id else None


# --- patients' logins (website + phone apps) -------------------------------------------------

async def _require_patient_exists(patient_id: str) -> None:
    if await patients_col().find_one({"_id": patient_id}, {"_id": 1}) is None:
        raise HTTPException(status_code=404, detail="patient not found")


@router.put("/api/patients/{patient_id}/login", status_code=204,
            responses={400: {"description": "username or password too short/long"},
                       409: {"description": "username taken by someone else"}})
async def set_patient_login(patient_id: str, body: SetLoginRequest,
                            p: Principal = Depends(require_patient)) -> None:
    await _require_patient_exists(patient_id)
    await logins.set_login(LoginRole.patient, patient_id, body.username, body.password, _keep(p, patient_id))


@router.get("/api/patients/{patient_id}/login", response_model=LoginView,
            responses={404: {"description": "no login set"}}, dependencies=[Depends(require_patient)])
async def get_patient_login(patient_id: str) -> LoginView:
    return await _view(patient_id)


@router.delete("/api/patients/{patient_id}/login", status_code=204, dependencies=[Depends(require_staff)])
async def delete_patient_login(patient_id: str) -> None:
    """Signs them out of the website; phones already signed in stay connected (unpair them separately)."""
    await logins.delete(patient_id)


# --- caregivers' logins (website only) --------------------------------------------------------

async def _require_caregiver_exists(caregiver_id: str) -> None:
    if await caregivers_col().find_one({"_id": caregiver_id}, {"_id": 1}) is None:
        raise HTTPException(status_code=404, detail="caregiver not found")


@router.put("/api/caregivers/{caregiver_id}/login", status_code=204,
            responses={400: {"description": "username or password too short/long"},
                       409: {"description": "username taken by someone else"}})
async def set_caregiver_login(caregiver_id: str, body: SetLoginRequest,
                              p: Principal = Depends(require_caregiver)) -> None:
    await _require_caregiver_exists(caregiver_id)
    await logins.set_login(LoginRole.caregiver, caregiver_id, body.username, body.password, _keep(p, caregiver_id))


@router.get("/api/caregivers/{caregiver_id}/login", response_model=LoginView,
            responses={404: {"description": "no login set"}}, dependencies=[Depends(require_caregiver)])
async def get_caregiver_login(caregiver_id: str) -> LoginView:
    return await _view(caregiver_id)


@router.delete("/api/caregivers/{caregiver_id}/login", status_code=204, dependencies=[Depends(require_staff)])
async def delete_caregiver_login(caregiver_id: str) -> None:
    await logins.delete(caregiver_id)


# --- the phone apps ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    username: str = Field(max_length=200)
    password: str = Field(max_length=200)
    platform: DevicePlatform
    push_token: str | None = Field(default=None, max_length=4096)
    name: str | None = Field(default=None, max_length=100)


@router.post("/api/auth/login", response_model=PairResponse,
             responses={401: {"description": "wrong username or password"},
                        403: {"description": "`family_login` / `staff_login`: right password, but this login "
                                             "is for the website, not the phone app"},
                        429: {"description": "too many failed logins, paused"}})
async def login(body: LoginRequest) -> PairResponse:
    record = await logins.check(body.username, body.password)
    if record is not None and record.role != LoginRole.patient:
        # Only said once the password is right, so it tells a guesser nothing.
        raise HTTPException(status_code=403,
                            detail="family_login" if record.role == LoginRole.caregiver else "staff_login")
    patient = None
    if record is not None:
        patient = doc_to_model(Patient, await patients_col().find_one({"_id": record.id}))
    if patient is None:
        raise HTTPException(status_code=401, detail="wrong username or password")
    return await create_device(patient, body.platform, body.push_token, body.name)


# --- the website ------------------------------------------------------------------------------

class SessionRequest(BaseModel):
    username: str = Field(max_length=200)
    password: str = Field(max_length=200)


class Me(BaseModel):
    """Who is signed in. `patient_id`: the patient's own id, or (a caregiver) the patient they look after."""
    role: LoginRole
    id: str
    name: str
    patient_id: str | None = None


async def _me(p: Principal) -> Me | None:
    """None when the person no longer exists (e.g. a family contact who was removed)."""
    if p.role == LoginRole.patient:
        patient = doc_to_model(Patient, await patients_col().find_one({"_id": p.id}))
        return Me(role=p.role, id=p.id, name=patient.name, patient_id=p.id) if patient else None
    if p.role == LoginRole.caregiver:
        caregiver = doc_to_model(Caregiver, await caregivers_col().find_one({"_id": p.id}))
        return Me(role=p.role, id=p.id, name=caregiver.name, patient_id=caregiver.patient_id) if caregiver else None
    login = await logins.get(p.id)
    return Me(role=p.role, id=p.id, name=login.username) if login else None


def _clear_cookie(response: Response) -> None:
    response.delete_cookie(access.SESSION_COOKIE, path="/", secure=access.cookie_secure(), httponly=True,
                           samesite="lax")


@router.post("/api/auth/session", response_model=Me,
             responses={401: {"description": "wrong username or password"},
                        429: {"description": "too many failed logins, paused"}})
async def start_session(body: SessionRequest, response: Response) -> Me:
    record = await logins.check(body.username, body.password)
    me = await _me(Principal(role=record.role, id=record.id)) if record is not None else None
    if record is None or me is None:
        raise HTTPException(status_code=401, detail="wrong username or password")
    token, max_age = await access.create_session(record)
    response.set_cookie(access.SESSION_COOKIE, token, max_age=max_age, path="/", secure=access.cookie_secure(),
                        httponly=True, samesite="lax")
    return me


@router.get("/api/auth/me", response_model=Me, responses={401: {"description": "not signed in"}})
async def me(request: Request, response: Response, p: Principal = Depends(signed_in)) -> Me:
    found = await _me(p)
    if found is None:
        token = request.cookies.get(access.SESSION_COOKIE)
        if token and p.session_hash:
            await access.end_session(token)
            _clear_cookie(response)
        raise HTTPException(status_code=401, detail="sign in first")
    return found


@router.delete("/api/auth/session", status_code=204)
async def end_session(request: Request, response: Response) -> None:
    """Sign out (always succeeds, signed in or not)."""
    token = request.cookies.get(access.SESSION_COOKIE)
    if token:
        await access.end_session(token)
    _clear_cookie(response)


class WsTicket(BaseModel):
    ticket: str
    expires_in: int


@router.post("/api/auth/ws-ticket", response_model=WsTicket)
async def ws_ticket(p: Principal = Depends(signed_in)) -> WsTicket:
    """Open a socket with `?ticket=` within `expires_in` seconds; each ticket opens one socket."""
    return WsTicket(ticket=access.issue_ticket(p), expires_in=access.TICKET_SECONDS)
