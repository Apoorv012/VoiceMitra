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


async def _notify(patient_id: str, call_id: str, trigger: CaregiverNotifyOn, message) -> dict:
    """Store a notification for the patient's caregiver if they have one and haven't opted out of this
    trigger. `message` is called with the patient's name to build the text."""
    patient = doc_to_model(Patient, await patients_col().find_one({"_id": patient_id}))
    if patient is None or not patient.caregiver_id:
        return {"notified": False, "why": "no caregiver on file"}
    caregiver = doc_to_model(Caregiver, await caregivers_col().find_one({"_id": patient.caregiver_id}))
    if caregiver is None:
        return {"notified": False, "why": "no caregiver on file"}
    if trigger not in caregiver.notify_on:
        return {"notified": False, "why": f"caregiver opted out of {trigger.value} alerts"}

    notification = CaregiverNotification(
        patient_id=patient.id,
        caregiver_id=caregiver.id,
        call_id=call_id,
        trigger=trigger,
        message=message(patient.name),
    )
    await caregiver_notifications_col().insert_one(model_to_doc(notification))
    await calls_col().update_one({"_id": call_id}, {"$set": {"caregiver_notified": True}})
    return {"notified": True, "caregiver": caregiver.name, "relation": caregiver.relation}


async def notify_caregiver_of_escalation(context: CallContext, reason: str) -> dict:
    return await _notify(
        context.patient_id, context.call_id, CaregiverNotifyOn.escalation,
        lambda name: (
            f"{name} reported a concerning symptom on today's medicine call ({reason}). "
            "Their doctor is being brought onto the call."
        ),
    )


async def notify_caregiver_unreachable(patient_id: str, call_id: str) -> dict:
    """The patient never picked up the medicine call."""
    return await _notify(
        patient_id, call_id, CaregiverNotifyOn.unreachable,
        lambda name: f"We could not reach {name} for today's medicine reminder call. Please check on them.",
    )
