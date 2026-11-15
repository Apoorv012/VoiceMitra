"""Phone-app login with a username + password (mobile/API.md, "Identity: login")."""

from __future__ import annotations

import pytest

from backend.auth import hash_password, verify_password
from backend.db import model_to_doc
from backend.models import Caregiver, Patient
from backend import logins

pytestmark = pytest.mark.anyio


async def _patient(mongo, name="Sunita") -> Patient:
    patient = Patient(name=name, age=70, phone_number="+911")
    await mongo["patients"].insert_one(model_to_doc(patient))
    return patient


async def _set(client, patient_id, username="Sunita", password="secret12"):
    return await client.put(f"/api/patients/{patient_id}/login", json={"username": username, "password": password})


def _login(username="sunita", password="secret12", push_token="fcm-1", platform="android"):
    return {"username": username, "password": password, "platform": platform, "push_token": push_token,
            "name": "Pixel 7"}


@pytest.fixture(autouse=True)
def _fresh_limiter(monkeypatch):
    monkeypatch.setattr(logins, "_bad_logins", type(logins._bad_logins)())
    monkeypatch.setattr(logins, "_bad_by_username", type(logins._bad_by_username)(type(logins._bad_logins)))


def test_password_hash_round_trip():
    stored = hash_password("secret12")
    assert stored.startswith("scrypt$") and "secret12" not in stored
    assert verify_password("secret12", stored)
    assert not verify_password("secret13", stored)
    assert hash_password("secret12") != stored  # random salt
    assert not verify_password("secret12", "garbage")


async def test_set_and_show_login(client, mongo):
    patient = await _patient(mongo)
    url = f"/api/patients/{patient.id}/login"
    assert (await client.get(url)).status_code == 404
    assert (await _set(client, patient.id, username="  Sunita ")).status_code == 204
    res = await client.get(url)
    assert res.status_code == 200 and res.json() == {"username": "Sunita"}

    # Changing it replaces the old one.
    assert (await _set(client, patient.id, username="sunita2", password="newpass1")).status_code == 204
    assert (await client.get(url)).json() == {"username": "sunita2"}
    assert (await client.post("/api/auth/login", json=_login())).status_code == 401
    assert (await client.post("/api/auth/login", json=_login("SUNITA2", "newpass1"))).status_code == 200

    assert (await client.delete(url)).status_code == 204
    assert (await client.get(url)).status_code == 404
    assert (await client.post("/api/auth/login", json=_login("sunita2", "newpass1"))).status_code == 401


async def test_bad_logins_are_refused(client, mongo):
    patient = await _patient(mongo)
    assert (await _set(client, patient.id, password="12345")).status_code == 400  # too short
    assert (await _set(client, patient.id, username=" a ")).status_code == 400
    assert (await _set(client, "nobody")).status_code == 404
    assert (await _set(client, patient.id)).status_code == 204

    wrong_password = await client.post("/api/auth/login", json=_login(password="secret13"))
    unknown_user = await client.post("/api/auth/login", json=_login(username="ravi"))
    assert wrong_password.status_code == unknown_user.status_code == 401
    assert wrong_password.json() == unknown_user.json()  # can't tell which one was wrong
    assert await mongo["devices"].count_documents({}) == 0


async def test_login_gives_a_working_device_token(client, mongo):
    patient = await _patient(mongo)
    await _set(client, patient.id)
    res = await client.post("/api/auth/login", json=_login(username="  SUNITA "))
    assert res.status_code == 200
    body = res.json()
    assert set(body) == {"device_id", "device_token", "role", "patient_id", "patient_name", "caregiver_id",
                         "caregiver_name"}
    assert body["patient_id"] == patient.id and body["patient_name"] == "Sunita"
    assert body["role"] == "patient" and body["caregiver_id"] is None and body["caregiver_name"] is None

    dev = f"/api/devices/{body['device_id']}"
    good = {"X-Device-Token": body["device_token"]}
    assert (await client.get(dev, headers=good)).status_code == 200
    assert (await client.get(dev, headers={"X-Device-Token": "nope"})).status_code == 401
    listed = (await client.get(f"/api/patients/{patient.id}/devices")).json()
    assert [d["id"] for d in listed] == [body["device_id"]] and listed[0]["name"] == "Pixel 7"

    # Same phone logging in again replaces its record (it would otherwise ring twice).
    again = (await client.post("/api/auth/login", json=_login())).json()
    assert [d["_id"] for d in await mongo["devices"].find().to_list(length=10)] == [again["device_id"]]

    # Logging out = unpairing.
    dev = f"/api/devices/{again['device_id']}"
    good = {"X-Device-Token": again["device_token"]}
    assert (await client.delete(dev, headers=good)).status_code == 204
    assert (await client.get(dev, headers=good)).status_code == 404


async def test_username_is_unique_ignoring_case(client, mongo):
    sunita, ravi = await _patient(mongo), await _patient(mongo, "Ravi")
    assert (await _set(client, sunita.id, username="Sunita")).status_code == 204
    assert (await _set(client, ravi.id, username="sUNITA")).status_code == 409
    assert (await _set(client, sunita.id, username="SUNITA")).status_code == 204  # her own, re-cased


async def test_hash_never_leaves_the_backend(client, mongo):
    patient = await _patient(mongo)
    await _set(client, patient.id, password="secret12")
    stored = (await mongo["logins"].find_one({"_id": patient.id}))["password_hash"]
    assert "secret12" not in stored
    for url in ["/api/patients", f"/api/patients/{patient.id}", f"/api/patients/{patient.id}/login",
                f"/api/app/patients/{patient.id}/home", "/api/app/people"]:
        res = await client.get(url)
        assert stored not in res.text and "password" not in res.text, url


async def test_guessing_passwords_is_paused(client, mongo, monkeypatch):
    monkeypatch.setattr(logins, "MAX_BAD_LOGINS", 3)
    patient = await _patient(mongo)
    await _set(client, patient.id)
    for _ in range(3):
        assert (await client.post("/api/auth/login", json=_login(password="wrong123"))).status_code == 401
    assert (await client.post("/api/auth/login", json=_login())).status_code == 429


# --- family contacts (mobile/API.md, "Caregivers in the apps") ----------------------------------

async def _with_caregiver(client, mongo, name="Sunita") -> tuple[Patient, Caregiver]:
    patient = Patient(name=name, age=70, phone_number="+911")
    caregiver = Caregiver(patient_id=patient.id, name="Rahul", relation="son", phone_number="+912")
    patient.caregiver_id = caregiver.id
    await mongo["caregivers"].insert_one(model_to_doc(caregiver))
    await mongo["patients"].insert_one(model_to_doc(patient))
    assert (await client.put(f"/api/caregivers/{caregiver.id}/login",
                             json={"username": "rahul", "password": "family12"})).status_code == 204
    return patient, caregiver


async def test_a_family_login_gives_a_caregiver_phone(client, mongo):
    patient, caregiver = await _with_caregiver(client, mongo)
    res = await client.post("/api/auth/login", json=_login("Rahul", "family12", push_token="fcm-rahul"))
    assert res.status_code == 200
    body = res.json()
    assert {k: v for k, v in body.items() if k not in ("device_id", "device_token")} == {
        "role": "caregiver", "patient_id": patient.id, "patient_name": "Sunita",
        "caregiver_id": caregiver.id, "caregiver_name": "Rahul"}
    stored = await mongo["devices"].find_one({"_id": body["device_id"]})
    assert stored["role"] == "caregiver" and stored["caregiver_id"] == caregiver.id
    assert stored["patient_id"] == patient.id

    dev = f"/api/devices/{body['device_id']}"
    info = (await client.get(dev, headers={"X-Device-Token": body["device_token"]})).json()
    assert info == {"device_id": body["device_id"], "role": "caregiver", "patient_id": patient.id,
                    "patient_name": "Sunita", "caregiver_id": caregiver.id, "caregiver_name": "Rahul"}

    # The patient's devices card lists only the patient's own phones.
    assert (await client.get(f"/api/patients/{patient.id}/devices")).json() == []


async def test_a_removed_family_contact_is_signed_out_of_the_app(client, mongo):
    patient, caregiver = await _with_caregiver(client, mongo)
    body = (await client.post("/api/auth/login", json=_login("rahul", "family12"))).json()
    token = {"X-Device-Token": body["device_token"]}
    assert (await client.patch(f"/api/patients/{patient.id}", json={"caregiver": None})).status_code == 200
    assert await mongo["devices"].count_documents({}) == 0
    assert (await client.get(f"/api/devices/{body['device_id']}", headers=token)).status_code == 404


async def test_a_caregiver_phone_whose_contact_changed_gets_404(client, mongo):
    """Even without going through the removal route (e.g. a record changed by hand): the check says 404."""
    patient, caregiver = await _with_caregiver(client, mongo)
    body = (await client.post("/api/auth/login", json=_login("rahul", "family12"))).json()
    await mongo["patients"].update_one({"_id": patient.id}, {"$set": {"caregiver_id": "someone-else"}})
    token = {"X-Device-Token": body["device_token"]}
    assert (await client.get(f"/api/devices/{body['device_id']}", headers=token)).status_code == 404
    assert await mongo["devices"].count_documents({}) == 0
    # And that login no longer signs in to the app.
    assert (await client.post("/api/auth/login", json=_login("rahul", "family12"))).status_code == 401


async def test_pairing_codes_stay_patient_only(client, mongo):
    patient, _ = await _with_caregiver(client, mongo)
    code = (await client.post(f"/api/patients/{patient.id}/pairing-code")).json()["code"]
    res = await client.post("/api/devices/pair", json={"code": code, "platform": "android"})
    assert res.json()["role"] == "patient" and res.json()["caregiver_id"] is None
