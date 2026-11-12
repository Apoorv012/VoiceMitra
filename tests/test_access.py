"""Who may call what (backend/access.py): every route is closed unless it says otherwise."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from backend import access, logins
from backend.db import model_to_doc
from backend.models import Call, CallType, Caregiver, Patient

pytestmark = pytest.mark.anyio

# Routes anyone may call. The device routes check the phone's own token themselves (tests/test_devices.py).
PUBLIC = {
    ("GET", "/health"),
    ("POST", "/api/contact"),
    ("POST", "/api/auth/login"),
    ("POST", "/api/auth/session"),
    ("DELETE", "/api/auth/session"),
    ("POST", "/api/devices/pair"),
    ("GET", "/api/devices/{device_id}"),
    ("PUT", "/api/devices/{device_id}"),
    ("DELETE", "/api/devices/{device_id}"),
}


@pytest.fixture(autouse=True)
def _fresh_limiter(monkeypatch):
    monkeypatch.setattr(logins, "_bad_logins", type(logins._bad_logins)())
    monkeypatch.setattr(logins, "_bad_by_username", type(logins._bad_by_username)(type(logins._bad_logins)))


def _http_routes():
    from backend.main import app

    for path, ops in app.openapi()["paths"].items():
        for method in ops:
            yield method.upper(), path


async def test_every_route_is_closed_to_strangers(anon_client):
    checked = 0
    for method, path in _http_routes():
        if (method, path) in PUBLIC:
            continue
        url = re.sub(r"\{[^}]+\}", "x", path)
        res = await anon_client.request(method, url, json={} if method in ("POST", "PUT", "PATCH") else None)
        assert res.status_code == 401, f"{method} {path} answered {res.status_code} without sign-in"
        checked += 1
    assert checked > 30  # the walk really saw the routers


def test_every_socket_declares_a_rule():
    """Sockets aren't in the OpenAPI schema, so check the source: each one names a ws_require_* rule."""
    found = 0
    for file in Path("backend/routers").glob("*.py"):
        for decorator in re.findall(r"@router\.websocket\([^\n]*", file.read_text(encoding="utf-8")):
            assert "Depends(ws_require_" in decorator, f"{file.name}: {decorator}"
            found += 1
    assert found == 5


@pytest.mark.parametrize("path", ["/ws/operator", "/ws/patients/p1/chat", "/ws/caregivers/c1",
                                  "/ws/doctors/d1", "/ws/escalations/e1"])
def test_sockets_refuse_strangers(path):
    from backend.main import app

    with pytest.raises(WebSocketDisconnect) as e:  # refused before the handshake completes
        with TestClient(app).websocket_connect(path):
            pass
    assert e.value.code == 1008


# --- people see only their own -----------------------------------------------------------------

async def _patient(mongo, name="Sunita", with_caregiver=True) -> tuple[Patient, Caregiver | None]:
    patient = Patient(name=name, age=70, phone_number="+911")
    caregiver = None
    if with_caregiver:
        caregiver = Caregiver(patient_id=patient.id, name=f"{name}'s son", relation="son", phone_number="+912")
        patient.caregiver_id = caregiver.id
        await mongo["caregivers"].insert_one(model_to_doc(caregiver))
    await mongo["patients"].insert_one(model_to_doc(patient))
    return patient, caregiver


async def _call(mongo, patient_id: str) -> Call:
    call = Call(patient_id=patient_id, type=CallType.just_catch_up)
    await mongo["calls"].insert_one(model_to_doc(call))
    return call


async def test_a_patient_sees_only_their_own(mongo, client_as):
    a, _ = await _patient(mongo, "Sunita")
    b, _ = await _patient(mongo, "Ravi")
    a_call, b_call = await _call(mongo, a.id), await _call(mongo, b.id)
    me = await client_as("patient", a.id)

    for url in [f"/api/app/patients/{a.id}/home", f"/api/app/patients/{a.id}/history",
                f"/api/patients/{a.id}/devices", f"/api/app/calls/{a_call.id}"]:
        assert (await me.get(url)).status_code == 200, url
    for url in [f"/api/app/patients/{b.id}/home", f"/api/patients/{b.id}/devices", f"/api/app/calls/{b_call.id}",
                "/api/app/calls/no-such-call", "/api/patients", f"/api/patients/{a.id}", "/api/app/operator/roster",
                "/api/app/people", "/api/contact", f"/api/app/caregivers/{a.caregiver_id}/home"]:
        assert (await me.get(url)).status_code == 403, url
    assert (await me.post(f"/api/patients/{b.id}/call/end")).status_code == 403
    # Only staff take a login away.
    assert (await me.delete(f"/api/patients/{a.id}/login")).status_code == 403


async def test_a_caregiver_sees_only_their_own_page(mongo, client_as):
    a, a_carer = await _patient(mongo, "Sunita")
    b, b_carer = await _patient(mongo, "Ravi")
    me = await client_as("caregiver", a_carer.id)
    assert (await me.get(f"/api/app/caregivers/{a_carer.id}/home")).status_code == 200
    assert (await me.post(f"/api/caregivers/{a_carer.id}/alerts/seen")).status_code == 204
    for url in [f"/api/app/caregivers/{b_carer.id}/home", f"/api/app/patients/{a.id}/home", "/api/patients"]:
        assert (await me.get(url)).status_code == 403, url
    assert (await me.post(f"/api/caregivers/{b_carer.id}/alerts/seen")).status_code == 403


async def test_a_phone_token_is_its_patient(mongo, anon_client, client):
    a, _ = await _patient(mongo, "Sunita")
    b, _ = await _patient(mongo, "Ravi")
    await client.put(f"/api/patients/{a.id}/login", json={"username": "sunita", "password": "secret12"})
    pair = (await anon_client.post("/api/auth/login", json={"username": "sunita", "password": "secret12",
                                                            "platform": "android"})).json()
    token = {"X-Device-Token": pair["device_token"]}
    assert (await anon_client.get(f"/api/app/patients/{a.id}/home", headers=token)).status_code == 200
    assert (await anon_client.get(f"/api/patients/{a.id}/voice-call", headers=token)).status_code == 404  # no call
    assert (await anon_client.get(f"/api/app/patients/{b.id}/home", headers=token)).status_code == 403
    assert (await anon_client.get("/api/app/people", headers=token)).status_code == 403
    bad = {"X-Device-Token": "made-up"}
    assert (await anon_client.get(f"/api/app/patients/{a.id}/home", headers=bad)).status_code == 401


# --- signing in on the website ---------------------------------------------------------------

async def test_website_sign_in_and_out(mongo, client, anon_client):
    a, _ = await _patient(mongo)
    await client.put(f"/api/patients/{a.id}/login", json={"username": "Sunita", "password": "secret12"})

    assert (await anon_client.get("/api/auth/me")).status_code == 401
    wrong = await anon_client.post("/api/auth/session", json={"username": "sunita", "password": "nope1234"})
    assert wrong.status_code == 401 and access.SESSION_COOKIE not in wrong.cookies

    res = await anon_client.post("/api/auth/session", json={"username": " SUNITA ", "password": "secret12"})
    assert res.status_code == 200
    assert res.json() == {"role": "patient", "id": a.id, "name": "Sunita", "patient_id": a.id}
    cookie = res.headers["set-cookie"].lower()
    for flag in ("httponly", "secure", "samesite=lax", "path=/", "max-age=2592000"):
        assert flag in cookie, flag
    stored = await mongo["web_sessions"].find_one({"subject_id": a.id})
    assert stored["_id"] != anon_client.cookies[access.SESSION_COOKIE]  # only a hash is kept

    assert (await anon_client.get("/api/auth/me")).json()["role"] == "patient"
    assert (await anon_client.get(f"/api/app/patients/{a.id}/home")).status_code == 200

    assert (await anon_client.delete("/api/auth/session")).status_code == 204
    assert await mongo["web_sessions"].count_documents({"subject_id": a.id}) == 0
    assert (await anon_client.get("/api/auth/me")).status_code == 401


async def test_caregiver_and_staff_sign_in(mongo, client, anon_client):
    a, carer = await _patient(mongo)
    assert (await client.put(f"/api/caregivers/{carer.id}/login",
                             json={"username": "rahul", "password": "family12"})).status_code == 204
    assert (await client.get(f"/api/caregivers/{carer.id}/login")).json() == {"username": "rahul"}
    res = await anon_client.post("/api/auth/session", json={"username": "rahul", "password": "family12"})
    assert res.json() == {"role": "caregiver", "id": carer.id, "name": "Sunita's son", "patient_id": a.id}

    # Usernames are unique across patients, caregivers and staff.
    taken = await client.put(f"/api/patients/{a.id}/login", json={"username": "RAHUL", "password": "secret12"})
    assert taken.status_code == 409

    # A family contact who is removed loses their login and is signed out.
    assert (await client.patch(f"/api/patients/{a.id}", json={"caregiver": None})).status_code == 200
    assert (await anon_client.get("/api/auth/me")).status_code == 401
    assert await mongo["logins"].count_documents({"_id": carer.id}) == 0


async def test_the_phone_app_turns_away_website_logins(mongo, client, anon_client):
    _, carer = await _patient(mongo)
    await client.put(f"/api/caregivers/{carer.id}/login", json={"username": "rahul", "password": "family12"})
    body = {"username": "rahul", "password": "family12", "platform": "android"}
    res = await anon_client.post("/api/auth/login", json=body)
    assert res.status_code == 403 and res.json()["detail"] == "family_login"
    # A wrong password says nothing about what kind of login it is.
    res = await anon_client.post("/api/auth/login", json={**body, "password": "wrong123"})
    assert res.status_code == 401
    assert await mongo["devices"].count_documents({}) == 0


async def test_changing_a_password_signs_out_other_browsers(mongo, client, anon_client, client_as):
    a, _ = await _patient(mongo)
    await client.put(f"/api/patients/{a.id}/login", json={"username": "sunita", "password": "secret12"})
    other = await client_as("patient", a.id)  # signed in elsewhere
    assert (await anon_client.post("/api/auth/session", json={"username": "sunita", "password": "secret12"})).status_code == 200

    res = await anon_client.put(f"/api/patients/{a.id}/login", json={"username": "sunita", "password": "newpass1"})
    assert res.status_code == 204
    assert (await anon_client.get("/api/auth/me")).status_code == 200  # the browser that changed it
    assert (await other.get("/api/auth/me")).status_code == 401


async def test_one_username_is_paused_before_everyone(mongo, client, anon_client):
    a, _ = await _patient(mongo, "Sunita")
    b, _ = await _patient(mongo, "Ravi")
    await client.put(f"/api/patients/{a.id}/login", json={"username": "sunita", "password": "secret12"})
    await client.put(f"/api/patients/{b.id}/login", json={"username": "ravi", "password": "secret12"})
    for _ in range(logins.MAX_BAD_PER_USERNAME):
        res = await anon_client.post("/api/auth/session", json={"username": "sunita", "password": "wrong123"})
        assert res.status_code == 401
    res = await anon_client.post("/api/auth/session", json={"username": "sunita", "password": "secret12"})
    assert res.status_code == 429
    res = await anon_client.post("/api/auth/session", json={"username": "ravi", "password": "secret12"})
    assert res.status_code == 200


# --- socket tickets --------------------------------------------------------------------------

class _FakeSocket:
    def __init__(self, ticket=None, device_token=None):
        self.query_params = {"ticket": ticket} if ticket else {}
        self.headers = {"x-device-token": device_token} if device_token else {}


async def test_a_ticket_opens_one_socket_for_its_owner(mongo, client_as, monkeypatch):
    a, _ = await _patient(mongo)
    me = await client_as("patient", a.id)
    res = await me.post("/api/auth/ws-ticket")
    assert res.status_code == 200 and res.json()["expires_in"] == access.TICKET_SECONDS
    ticket = res.json()["ticket"]

    with pytest.raises(Exception):
        await access.ws_require_patient("someone-else", _FakeSocket(ticket))  # used up, even on a refusal
    ticket = (await me.post("/api/auth/ws-ticket")).json()["ticket"]
    assert (await access.ws_require_patient(a.id, _FakeSocket(ticket))).id == a.id
    with pytest.raises(Exception):
        await access.ws_require_patient(a.id, _FakeSocket(ticket))  # single use

    ticket = (await me.post("/api/auth/ws-ticket")).json()["ticket"]
    now = access.time.monotonic()
    monkeypatch.setattr(access.time, "monotonic", lambda: now + access.TICKET_SECONDS + 1)
    with pytest.raises(Exception):
        await access.ws_require_patient(a.id, _FakeSocket(ticket))  # expired


# --- staff logins ----------------------------------------------------------------------------

async def test_create_staff_prints_a_password_that_works(mongo, anon_client, capsys):
    from backend import create_staff

    assert await create_staff._run("Asha", reset=False) == 0
    password = re.search(r"password: (\S+)", capsys.readouterr().out).group(1)
    assert len(password) >= 20
    res = await anon_client.post("/api/auth/session", json={"username": "asha", "password": password})
    assert res.status_code == 200 and res.json()["role"] == "staff"
    assert (await anon_client.get("/api/patients")).status_code == 200
    # Staff can't use the phone app.
    app_login = await anon_client.post("/api/auth/login", json={"username": "asha", "password": password,
                                                                "platform": "ios"})
    assert app_login.status_code == 403 and app_login.json()["detail"] == "staff_login"

    assert await create_staff._run("asha", reset=False) == 1  # exists already
    assert await create_staff._run("asha", reset=True) == 0   # new password, old sessions gone
    assert (await anon_client.get("/api/auth/me")).status_code == 401
