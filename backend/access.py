"""Who is asking, and what they may see.

Two ways in:
- the website: a `vm_session` cookie, set by `POST /api/auth/session` (the browser reaches the API through
  the website's own `/api/*`, so the cookie belongs to the website's host);
- the phone apps: their `X-Device-Token` header (mobile/API.md), which makes them the patient they belong to.

Every route declares one of the rules below as a dependency (`tests/test_access.py` fails for a route that
has none and is not on its public list):
- `require_staff`: staff only;
- `require_patient`: staff, or the patient whose `patient_id` is in the path;
- `require_caregiver`: staff, or the caregiver whose `caregiver_id` is in the path;
- `require_call_owner`: staff, or the patient the call in the path belongs to;
- `signed_in`: anyone signed in (used by the auth routes about yourself).
401 = not signed in, 403 = signed in as someone else.

WebSockets connect straight to the API host, which never sees the website's cookie, so the page first asks
`POST /api/auth/ws-ticket` for a short-lived single-use ticket and connects with `?ticket=`. Phones send their
`X-Device-Token` header on the socket instead. The `ws_*` rules check either.
"""

from __future__ import annotations

import hashlib
import os
import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Request, WebSocket, WebSocketException, status

from backend.db import calls_col, web_sessions_col
from backend.models import Login, LoginRole

SESSION_COOKIE = "vm_session"
SESSION_DAYS = {LoginRole.staff: 7, LoginRole.patient: 30, LoginRole.caregiver: 30}
TICKET_SECONDS = 60


@dataclass(frozen=True)
class Principal:
    role: LoginRole
    id: str                       # the patient's / caregiver's id, or the staff login's id
    device_id: str | None = None  # set when a phone app is asking
    session_hash: str | None = None  # set when the website is asking

    @property
    def is_staff(self) -> bool:
        return self.role == LoginRole.staff


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def cookie_secure() -> bool:
    return os.environ.get("SESSION_COOKIE_SECURE", "true").lower() != "false"


# --- website sessions -----------------------------------------------------------------------

async def create_session(login: Login) -> tuple[str, int]:
    """A new session for `login`: (the cookie's secret value, its lifetime in seconds). Only the hash is stored."""
    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    lifetime = timedelta(days=SESSION_DAYS[login.role])
    await web_sessions_col().insert_one({
        "_id": token_hash(token), "role": login.role.value, "subject_id": login.id,
        "created_at": now, "expires_at": now + lifetime,  # real dates: `expires_at` drives the TTL index
    })
    return token, int(lifetime.total_seconds())


async def end_session(token: str) -> None:
    await web_sessions_col().delete_one({"_id": token_hash(token)})


async def _session_principal(token: str) -> Principal | None:
    h = token_hash(token)
    doc = await web_sessions_col().find_one({"_id": h})
    if doc is None:
        return None
    expires = doc["expires_at"]
    if expires.tzinfo is None:  # Mongo hands dates back without a zone; they are UTC
        expires = expires.replace(tzinfo=timezone.utc)
    if expires <= datetime.now(timezone.utc):  # the TTL monitor runs only once a minute
        return None
    return Principal(role=LoginRole(doc["role"]), id=doc["subject_id"], session_hash=h)


async def _device_principal(token: str) -> Principal | None:
    from backend.routers.devices import device_for_token  # devices imports nothing from here; avoid a cycle anyway

    device = await device_for_token(token)
    if device is None:
        return None
    return Principal(role=LoginRole.patient, id=device.patient_id, device_id=device.id)


async def principal(request: Request) -> Principal | None:
    """Who sent this request (cookie first, then a phone's token), or None. Looked up once per request."""
    if hasattr(request.state, "principal"):
        return request.state.principal
    found = None
    cookie = request.cookies.get(SESSION_COOKIE)
    if cookie:
        found = await _session_principal(cookie)
    if found is None:
        device_token = request.headers.get("x-device-token")
        if device_token:
            found = await _device_principal(device_token)
    request.state.principal = found
    return found


# --- HTTP rules -----------------------------------------------------------------------------

def _unauthorised() -> HTTPException:
    return HTTPException(status_code=401, detail="sign in first")


def _forbidden() -> HTTPException:
    return HTTPException(status_code=403, detail="not allowed")


async def signed_in(request: Request) -> Principal:
    p = await principal(request)
    if p is None:
        raise _unauthorised()
    return p


async def require_staff(request: Request) -> Principal:
    p = await signed_in(request)
    if not p.is_staff:
        raise _forbidden()
    return p


def _may_see_patient(p: Principal, patient_id: str) -> bool:
    return p.is_staff or (p.role == LoginRole.patient and p.id == patient_id)


def _may_see_caregiver(p: Principal, caregiver_id: str) -> bool:
    return p.is_staff or (p.role == LoginRole.caregiver and p.id == caregiver_id)


async def require_patient(patient_id: str, request: Request) -> Principal:
    p = await signed_in(request)
    if not _may_see_patient(p, patient_id):
        raise _forbidden()
    return p


async def require_caregiver(caregiver_id: str, request: Request) -> Principal:
    p = await signed_in(request)
    if not _may_see_caregiver(p, caregiver_id):
        raise _forbidden()
    return p


async def require_call_owner(call_id: str, request: Request) -> Principal:
    p = await signed_in(request)
    if p.is_staff:
        return p
    call = await calls_col().find_one({"_id": call_id}, {"patient_id": 1})
    if call is None or not _may_see_patient(p, call["patient_id"]):
        raise _forbidden()  # also for a missing call, so ids can't be probed
    return p


# --- WebSocket tickets and rules ------------------------------------------------------------

_tickets: dict[str, tuple[Principal, float]] = {}


def issue_ticket(p: Principal) -> str:
    """A single-use ticket for opening one socket within TICKET_SECONDS. Kept in memory: there is one
    API process (live calls live in it too)."""
    now = time.monotonic()
    for t, (_, expires) in list(_tickets.items()):
        if expires <= now:
            del _tickets[t]
    ticket = secrets.token_urlsafe(24)
    _tickets[ticket] = (p, now + TICKET_SECONDS)
    return ticket


def _take_ticket(ticket: str) -> Principal | None:
    entry = _tickets.pop(ticket, None)
    if entry is None or entry[1] <= time.monotonic():
        return None
    return entry[0]


async def _ws_principal(websocket: WebSocket) -> Principal:
    ticket = websocket.query_params.get("ticket")
    found = _take_ticket(ticket) if ticket else None
    if found is None:
        device_token = websocket.headers.get("x-device-token")
        if device_token:
            found = await _device_principal(device_token)
    if found is None:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="sign in first")
    return found


def _ws_forbidden() -> WebSocketException:
    return WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="not allowed")


async def ws_require_staff(websocket: WebSocket) -> Principal:
    p = await _ws_principal(websocket)
    if not p.is_staff:
        raise _ws_forbidden()
    return p


async def ws_require_patient(patient_id: str, websocket: WebSocket) -> Principal:
    p = await _ws_principal(websocket)
    if not _may_see_patient(p, patient_id):
        raise _ws_forbidden()
    return p


async def ws_require_caregiver(caregiver_id: str, websocket: WebSocket) -> Principal:
    p = await _ws_principal(websocket)
    if not _may_see_caregiver(p, caregiver_id):
        raise _ws_forbidden()
    return p


# The rules a route may declare (the access test checks every route has one of these, or is public).
RULES = {signed_in, require_staff, require_patient, require_caregiver, require_call_owner,
         ws_require_staff, ws_require_patient, ws_require_caregiver}
