"""Pairing a phone with a patient (mobile/API.md): code from the web page -> app pairs -> token."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from backend.db import model_to_doc
from backend.models import Patient
from backend.routers import devices

pytestmark = pytest.mark.anyio


async def _patient(mongo, name="Sunita") -> Patient:
    patient = Patient(name=name, age=70, phone_number="+911")
    await mongo["patients"].insert_one(model_to_doc(patient))
    return patient


async def _pair(client, patient_id, push_token="fcm-1", platform="android"):
    code = (await client.post(f"/api/patients/{patient_id}/pairing-code")).json()["code"]
    return await client.post("/api/devices/pair", json={
        "code": code, "platform": platform, "push_token": push_token, "name": "Pixel 7"})


async def test_code_pairs_a_phone_once(client, mongo):
    patient = await _patient(mongo)
    res = await client.post(f"/api/patients/{patient.id}/pairing-code")
    assert res.status_code == 200
    body = res.json()
    assert len(body["code"]) == 6 and body["code"].isdigit()
    expires = datetime.fromisoformat(body["expires_at"])
    assert timedelta(minutes=9) < expires - datetime.now(timezone.utc) <= timedelta(minutes=10)
    assert body["expires_in"] == 600

    pair = {"code": body["code"], "platform": "android", "push_token": "fcm-1", "name": "Pixel 7"}
    res = await client.post("/api/devices/pair", json=pair)
    assert res.status_code == 200
    paired = res.json()
    assert paired["patient_id"] == patient.id and paired["patient_name"] == "Sunita"
    assert paired["device_token"] and paired["device_id"]

    # Single use.
    assert (await client.post("/api/devices/pair", json=pair)).status_code == 400

    # Only the hash of the token is stored.
    doc = await mongo["devices"].find_one({"_id": paired["device_id"]})
    assert doc["token_hash"] == devices.hash_token(paired["device_token"])
    assert paired["device_token"] not in str(doc)

    listed = (await client.get(f"/api/patients/{patient.id}/devices")).json()
    assert [d["id"] for d in listed] == [paired["device_id"]] and listed[0]["name"] == "Pixel 7"
    assert "token_hash" not in listed[0]


async def test_wrong_and_expired_codes_are_refused(client, mongo):
    patient = await _patient(mongo)
    code = (await client.post(f"/api/patients/{patient.id}/pairing-code")).json()["code"]
    wrong = f"{(int(code) + 1) % 1_000_000:06d}"
    assert (await client.post("/api/devices/pair", json={"code": wrong, "platform": "ios"})).status_code == 400

    await mongo["pairing_codes"].update_one(
        {"code": code}, {"$set": {"expires_at": (datetime.utcnow() - timedelta(seconds=1)).isoformat()}})
    assert (await client.post("/api/devices/pair", json={"code": code, "platform": "ios"})).status_code == 400
    assert await mongo["devices"].count_documents({}) == 0


async def test_a_new_code_replaces_the_old_one(client, mongo):
    patient = await _patient(mongo)
    first = (await client.post(f"/api/patients/{patient.id}/pairing-code")).json()["code"]
    second = (await client.post(f"/api/patients/{patient.id}/pairing-code")).json()["code"]
    if first != second:
        assert (await client.post("/api/devices/pair", json={"code": first, "platform": "ios"})).status_code == 400
    assert (await client.post("/api/devices/pair", json={"code": second, "platform": "ios"})).status_code == 200


async def test_unknown_patient_gets_no_code(client, mongo):
    assert (await client.post("/api/patients/nobody/pairing-code")).status_code == 404


async def test_token_guards_update_check_and_unpair(client, mongo):
    patient = await _patient(mongo)
    paired = (await _pair(client, patient.id)).json()
    dev = f"/api/devices/{paired['device_id']}"
    good = {"X-Device-Token": paired["device_token"]}
    bad = {"X-Device-Token": "nope"}

    assert (await client.get(dev, headers=bad)).status_code == 401
    assert (await client.get(dev)).status_code == 401
    info = (await client.get(dev, headers=good)).json()
    assert info == {"device_id": paired["device_id"], "patient_id": patient.id, "patient_name": "Sunita"}

    assert (await client.put(dev, json={"push_token": "fcm-2"}, headers=bad)).status_code == 401
    assert (await client.put(dev, json={"push_token": "fcm-2"}, headers=good)).status_code == 204
    assert (await mongo["devices"].find_one({"_id": paired["device_id"]}))["push_token"] == "fcm-2"

    assert (await client.delete(dev, headers=bad)).status_code == 401
    assert (await client.delete(dev, headers=good)).status_code == 204
    assert (await client.get(dev, headers=good)).status_code == 404  # unpaired


async def test_same_phone_pairing_again_replaces_its_old_record(client, mongo):
    sunita, ravi = await _patient(mongo), await _patient(mongo, "Ravi")
    await _pair(client, sunita.id, push_token="fcm-same")
    await _pair(client, ravi.id, push_token="fcm-same")
    docs = await mongo["devices"].find().to_list(length=10)
    assert [d["patient_id"] for d in docs] == [ravi.id]  # rings once, for the patient it's paired with now


async def test_guessing_codes_is_paused_after_too_many_wrong_ones(client, mongo, monkeypatch):
    monkeypatch.setattr(devices, "MAX_BAD_CODES", 3)
    monkeypatch.setattr(devices, "_bad_codes", type(devices._bad_codes)())
    patient = await _patient(mongo)
    code = (await client.post(f"/api/patients/{patient.id}/pairing-code")).json()["code"]
    wrong = f"{(int(code) + 1) % 1_000_000:06d}"
    for _ in range(3):
        assert (await client.post("/api/devices/pair", json={"code": wrong, "platform": "ios"})).status_code == 400
    assert (await client.post("/api/devices/pair", json={"code": code, "platform": "ios"})).status_code == 429
