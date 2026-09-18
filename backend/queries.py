"""Read-side queries that assemble a patient's/doctor's full picture across collections. Shared
between the JSON routers and the server-rendered dashboard pages so there's one place that knows
how these documents relate."""

from __future__ import annotations

from backend.db import (
    calls_col,
    caregivers_col,
    daily_logs_col,
    doc_to_model,
    doctors_col,
    dose_events_col,
    patients_col,
    prescriptions_col,
)
from backend.models import Call, Caregiver, DailyLog, Doctor, DoseEvent, Patient, Prescription


async def get_patient_bundle(patient_id: str) -> dict | None:
    patient = doc_to_model(Patient, await patients_col().find_one({"_id": patient_id}))
    if patient is None:
        return None

    caregiver = None
    if patient.caregiver_id:
        caregiver = doc_to_model(Caregiver, await caregivers_col().find_one({"_id": patient.caregiver_id}))

    prescriptions = [
        doc_to_model(Prescription, d)
        async for d in prescriptions_col().find({"_id": {"$in": patient.prescription_ids}})
    ]
    dose_events = [
        doc_to_model(DoseEvent, d)
        async for d in dose_events_col().find({"patient_id": patient_id}).sort("recorded_at", -1)
    ]
    daily_logs = [
        doc_to_model(DailyLog, d)
        async for d in daily_logs_col().find({"patient_id": patient_id}).sort("created_at", -1)
    ]
    calls = [
        doc_to_model(Call, d)
        async for d in calls_col().find({"patient_id": patient_id}).sort("date_time", -1)
    ]

    return {
        "patient": patient,
        "caregiver": caregiver,
        "prescriptions": prescriptions,
        "dose_events": dose_events,
        "daily_logs": daily_logs,
        "calls": calls,
    }


async def list_patients_with_last_status() -> list[dict]:
    patients = [doc_to_model(Patient, d) async for d in patients_col().find()]
    out = []
    for patient in patients:
        last_call_doc = await calls_col().find_one(
            {"patient_id": patient.id}, sort=[("date_time", -1)]
        )
        last_call = doc_to_model(Call, last_call_doc)
        out.append({"patient": patient, "last_call": last_call})
    return out


async def get_doctor_bundle(doctor_id: str) -> dict | None:
    doctor = doc_to_model(Doctor, await doctors_col().find_one({"_id": doctor_id}))
    if doctor is None:
        return None

    patients = [
        doc_to_model(Patient, d)
        async for d in patients_col().find({"_id": {"$in": doctor.patient_ids}})
    ]
    escalations = [
        doc_to_model(Call, d)
        async for d in calls_col().find({
            "patient_id": {"$in": doctor.patient_ids},
            "escalation_reason": {"$ne": None},
        }).sort("date_time", -1)
    ]

    return {"doctor": doctor, "patients": patients, "escalations": escalations}
