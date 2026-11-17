"""The two kinds of medicines (backend/routers/medicines.py): prescribed (staff) and the patient's own."""

from __future__ import annotations

import base64
from datetime import timedelta

import pytest

from backend import insights, prescription_photo
from backend.db import model_to_doc
from backend.models import DoseConfidence, DoseEvent, DoseSource, DoseStatus, Patient
from backend.routers import medicines as med_routes

pytestmark = pytest.mark.anyio

TODAY = insights.now_local().date()


def _med(name="Amlodipine 5", times=("08:00",), **extra) -> dict:
    return {"medicine_name": name, "dosage": "1 tablet", "frequency": "fixed_times", "times": list(times),
            "from_date": TODAY.isoformat(), **extra}


async def _patient(mongo, name="Sunita") -> Patient:
    p = Patient(name=name, age=70, phone_number="+911")
    await mongo["patients"].insert_one(model_to_doc(p))
    return p


async def _medicines(c, pid) -> list[dict]:
    res = await c.get(f"/api/app/patients/{pid}/medicines")
    assert res.status_code == 200
    return res.json()["medicines"]


async def test_staff_prescription_is_prescribed_and_locked_for_the_patient(mongo, client, client_as):
    p = await _patient(mongo)
    res = await client.post(f"/api/patients/{p.id}/prescriptions",
                            json={"medicines": [_med(), _med("Metformin 500", ("08:00", "21:00"))]})
    assert res.status_code == 200 and res.json()["source"] == "prescribed"
    me = await client_as("patient", p.id)
    meds = await _medicines(me, p.id)
    assert {m["source"] for m in meds} == {"prescribed"} and len(meds) == 2
    dosage_id = meds[0]["dosage_id"]
    assert (await me.put(f"/api/patients/{p.id}/medicines/{dosage_id}", json=_med("Changed"))).status_code == 403
    assert (await me.delete(f"/api/patients/{p.id}/medicines/{dosage_id}")).status_code == 403
    # Patients can't add a prescription or read a photo either.
    assert (await me.post(f"/api/patients/{p.id}/prescriptions", json={"medicines": [_med()]})).status_code == 403
    # Staff can fix a prescribed one.
    res = await client.put(f"/api/patients/{p.id}/medicines/{dosage_id}", json=_med("Amlodipine 10", ("09:30",)))
    assert res.status_code == 200 and res.json()["id"] == dosage_id
    assert any(m["name"] == "Amlodipine 10" and m["times"] == ["09:30"] for m in await _medicines(client, p.id))


async def test_patient_adds_edits_and_removes_their_own(mongo, client_as):
    p = await _patient(mongo)
    me = await client_as("patient", p.id)
    res = await me.post(f"/api/patients/{p.id}/own-medicines", json=_med("Own one", ("7:05",)))
    assert res.status_code == 201
    first = res.json()
    assert first["times"] == ["07:05"]
    second = (await me.post(f"/api/patients/{p.id}/own-medicines", json=_med("Own two"))).json()
    assert first["prescription_id"] == second["prescription_id"]  # one "own" prescription per patient
    meds = await _medicines(me, p.id)
    assert [m["source"] for m in meds] == ["own", "own"]

    res = await me.put(f"/api/patients/{p.id}/medicines/{first['id']}",
                       json=_med("Own one", ("21:00",), frequency="every_x_day", interval_days=3))
    assert res.status_code == 200 and res.json()["interval_days"] == 3
    # Nothing recorded for it yet: removing deletes it.
    res = await me.delete(f"/api/patients/{p.id}/medicines/{second['id']}")
    assert res.json() == {"outcome": "deleted"}
    assert [m["name"] for m in await _medicines(me, p.id)] == ["Own one"]
    patient_doc = await mongo["patients"].find_one({"_id": p.id})
    assert len(patient_doc["prescription_ids"]) == 1


async def test_removing_one_with_history_stops_it(mongo, client_as):
    p = await _patient(mongo)
    me = await client_as("patient", p.id)
    started = (TODAY - timedelta(days=5)).isoformat()
    med = (await me.post(f"/api/patients/{p.id}/own-medicines", json=_med(from_date=started))).json()
    ev = DoseEvent(patient_id=p.id, dosage_id=med["id"], scheduled_at=insights.now_local(), status=DoseStatus.taken,
                   confidence=DoseConfidence.high, source=DoseSource.patient_self_report)
    await mongo["dose_events"].insert_one(model_to_doc(ev))
    assert (await me.delete(f"/api/patients/{p.id}/medicines/{med['id']}")).json() == {"outcome": "stopped"}
    [m] = await _medicines(me, p.id)
    assert m["active"] is False and m["to_date"] == (TODAY - timedelta(days=1)).isoformat()
    # Removing it again (now finished) deletes it with its records.
    assert (await me.delete(f"/api/patients/{p.id}/medicines/{med['id']}")).json() == {"outcome": "deleted"}
    assert await _medicines(me, p.id) == []
    assert await mongo["dose_events"].count_documents({"dosage_id": med["id"]}) == 0


@pytest.mark.parametrize("body,why", [
    ({"times": []}, "own medicine needs a time"),
    ({"times": ["25:00"]}, "not a time"),
    ({"medicine_name": "   "}, "empty name"),
    ({"frequency": "every_x_day"}, "no interval"),
    ({"to_date": (TODAY - timedelta(days=1)).isoformat()}, "ends before it starts"),
])
async def test_own_medicine_input_is_checked(mongo, client_as, body, why):
    p = await _patient(mongo)
    me = await client_as("patient", p.id)
    res = await me.post(f"/api/patients/{p.id}/own-medicines", json={**_med(), **body})
    assert res.status_code == 422, why


async def test_patients_cant_touch_someone_elses(mongo, client_as):
    a, b = await _patient(mongo, "A"), await _patient(mongo, "B")
    b_client = await client_as("patient", b.id)
    med = (await b_client.post(f"/api/patients/{b.id}/own-medicines", json=_med())).json()
    a_client = await client_as("patient", a.id)
    assert (await a_client.post(f"/api/patients/{b.id}/own-medicines", json=_med())).status_code == 403
    assert (await a_client.delete(f"/api/patients/{b.id}/medicines/{med['id']}")).status_code == 403
    # Another patient's medicine id under your own path is simply not found.
    assert (await a_client.delete(f"/api/patients/{a.id}/medicines/{med['id']}")).status_code == 404


async def test_changes_rearm_the_dose_timer(mongo, client_as, monkeypatch):
    armed = []

    async def fake_arm(pid):
        armed.append(pid)

    monkeypatch.setattr(med_routes.dose_scheduler, "arm", fake_arm)
    p = await _patient(mongo)
    me = await client_as("patient", p.id)
    med = (await me.post(f"/api/patients/{p.id}/own-medicines", json=_med())).json()
    await me.put(f"/api/patients/{p.id}/medicines/{med['id']}", json=_med(times=("10:00",)))
    await me.delete(f"/api/patients/{p.id}/medicines/{med['id']}")
    assert armed == [p.id] * 3


# --- reading a prescription photo ----------------------------------------------------------------

PNG = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"0" * 64).decode()


async def test_read_photo_returns_a_draft(mongo, client, monkeypatch):
    async def fake_read(image_b64, mime):
        assert image_b64 == PNG and mime == "image/png"
        return prescription_photo._parse(
            '```json\n{"medicines": [{"medicine_name": "Telma 40", "dosage": "1 tablet", "frequency": "daily",'
            ' "times": ["8:00", "21:00", "nonsense"], "days": 30}, {"medicine_name": ""},'
            ' {"medicine_name": "Folic", "frequency": "every_x_day"}], "prescribed_on": "2026-11-10",'
            ' "notes": "Paracetamol SOS left out"}\n```')

    monkeypatch.setattr(med_routes, "read_prescription_photo", fake_read)
    p = await _patient(mongo)
    res = await client.post(f"/api/patients/{p.id}/prescriptions/read-photo",
                            json={"image_base64": PNG, "mime_type": "image/png"})
    assert res.status_code == 200
    draft = res.json()
    assert [m["medicine_name"] for m in draft["medicines"]] == ["Telma 40", "Folic"]
    telma, folic = draft["medicines"]
    assert telma["frequency"] == "fixed_times" and telma["times"] == ["08:00", "21:00"] and telma["days"] == 30
    assert folic["interval_days"] == 2
    assert draft["prescribed_on"] == "2026-11-10" and "SOS" in draft["notes"]
    # Nothing was saved.
    assert await mongo["prescriptions"].count_documents({}) == 0


async def test_read_photo_rejects_bad_input(mongo, client, client_as):
    p = await _patient(mongo)
    url = f"/api/patients/{p.id}/prescriptions/read-photo"
    assert (await client.post(url, json={"image_base64": PNG, "mime_type": "application/pdf"})).status_code == 415
    assert (await client.post(url, json={"image_base64": "not base64!", "mime_type": "image/png"})).status_code == 422
    me = await client_as("patient", p.id)
    assert (await me.post(url, json={"image_base64": PNG, "mime_type": "image/png"})).status_code == 403


def test_garbage_from_the_reader_is_an_error():
    with pytest.raises(prescription_photo.PhotoUnreadable):
        prescription_photo._parse("Sorry, I can't read this.")


async def test_doctor_brief_marks_own_medicines(mongo, client, client_as):
    from domains.med_adherence import doctor_agent
    from backend.models import Escalation

    p = await _patient(mongo)
    await client.post(f"/api/patients/{p.id}/prescriptions", json={"medicines": [_med("Prescribed one")]})
    me = await client_as("patient", p.id)
    await me.post(f"/api/patients/{p.id}/own-medicines", json=_med("Own one"))
    patient = Patient.model_validate(await mongo["patients"].find_one({"_id": p.id}))
    facts = await doctor_agent._gather_facts(Escalation(patient_id=p.id, call_id="none", reason="test", brief_summary="test"), patient)
    assert "Prescribed one, 1 tablet" in facts and "[added by the patient" not in facts.split("Own one")[0]
    assert "Own one, 1 tablet, fixed_times at 08:00 [added by the patient, not prescribed]" in facts


def test_draft_days_are_bounded():
    d = prescription_photo._parse('{"medicines": [{"medicine_name": "X", "days": 9999, "interval_days": 0}]}')
    assert d.medicines[0].days is None and d.medicines[0].interval_days is None
