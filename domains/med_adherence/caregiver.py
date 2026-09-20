"""Caregiver notification. Deliberately not an LLM-callable tool: it fires from the escalation code
path itself, so the agent can neither skip it nor spam a family member. Delivery is simulated for the
POC -- the stored CaregiverNotification (shown on the patient/family page and noted in the call log)
is the notification; a real SMS/WhatsApp send would slot in where the record is written."""

from __future__ import annotations

from backend.db import (
    calls_col,
    caregiver_notifications_col,
    caregivers_col,
    doc_to_model,
    model_to_doc,
    patients_col,
)
from backend.models import Caregiver, CaregiverNotification, CaregiverNotifyOn, Patient
from domains.med_adherence.context import CallContext


async def notify_caregiver_of_escalation(context: CallContext, reason: str) -> dict:
    patient = doc_to_model(Patient, await patients_col().find_one({"_id": context.patient_id}))
    if patient is None or not patient.caregiver_id:
        return {"notified": False, "why": "no caregiver on file"}
    caregiver = doc_to_model(Caregiver, await caregivers_col().find_one({"_id": patient.caregiver_id}))
    if caregiver is None:
        return {"notified": False, "why": "no caregiver on file"}
    if CaregiverNotifyOn.escalation not in caregiver.notify_on:
        return {"notified": False, "why": "caregiver opted out of escalation alerts"}

    notification = CaregiverNotification(
        patient_id=patient.id,
        caregiver_id=caregiver.id,
        call_id=context.call_id,
        trigger=CaregiverNotifyOn.escalation,
        message=(
            f"{patient.name} reported a concerning symptom on today's medicine call ({reason}). "
            "Their doctor is being brought onto the call."
        ),
    )
    await caregiver_notifications_col().insert_one(model_to_doc(notification))
    await calls_col().update_one({"_id": context.call_id}, {"$set": {"caregiver_notified": True}})
    return {"notified": True, "caregiver": caregiver.name, "relation": caregiver.relation}
