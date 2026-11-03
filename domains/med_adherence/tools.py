"""LLM-callable tools for the medicine-adherence agent, registered against a domain-owned
ToolRegistry and persisted straight to Mongo via backend.db/backend.models (a deliberate
simplification for the POC -- the domain layer reaches into backend.db directly rather than going
through an HTTP client/repository abstraction, since it's one Python codebase end to end)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from pydantic import BaseModel, Field

from backend.db import calls_col, daily_logs_col, dose_events_col, model_to_doc, reminders_col
from backend.models import (
    DailyLog,
    DoseConfidence,
    DoseEvent,
    DoseSource,
    DoseStatus,
    PatientStatus,
    Reminder,
    Symptom,
    SymptomSeverity,
)
from core.agent.tool_registry import ToolCallError, ToolRegistry
from domains.med_adherence.caregiver import notify_caregiver_of_escalation, notify_caregiver_unwell
from domains.med_adherence.context import CallContext, CaregiverAlert, DueMedicine, EscalationRequest

registry = ToolRegistry()


_MEDICINES_DESCRIPTION = (
    "Which of the due medicines this is about, names exactly as listed in the context. Several "
    "medicines with the same answer go in one call; leave it empty to mean every due medicine not "
    "answered yet.")


def _medicines_for(context: CallContext, names: list[str]) -> list[DueMedicine]:
    try:
        return context.resolve_medicines(names)
    except ValueError as e:
        raise ToolCallError(str(e)) from e


async def _log_doses(
    context: CallContext, meds: list[DueMedicine], *, status: DoseStatus, confidence: DoseConfidence,
    source: DoseSource, note: str | None,
) -> None:
    events = [
        DoseEvent(
            patient_id=context.patient_id,
            dosage_id=m.dosage_id,
            scheduled_at=context.slot_at,
            status=status,
            confidence=confidence,
            source=source,
            recorded_via_call_id=context.call_id,
            note=note,
        )
        for m in meds
    ]
    await dose_events_col().insert_many([model_to_doc(e) for e in events])
    for m in meds:
        context.dose_statuses[m.dosage_id] = status


def _progress(context: CallContext) -> dict:
    """Tells the model whether the dose step is finished."""
    left = [m.name for m in context.unanswered]
    return {"still_to_ask_about": left} if left else {"all_due_medicines_answered": True}


class LogDoseEventArgs(BaseModel):
    medicines: list[str] = Field(default_factory=list, description=_MEDICINES_DESCRIPTION)
    status: DoseStatus
    confidence: DoseConfidence
    source: DoseSource
    note: str | None = None


@registry.register(
    name="log_dose_event",
    description="Record whether the patient took their due medicine(s) in this call.",
    args_model=LogDoseEventArgs,
)
async def log_dose_event(args: LogDoseEventArgs, context: CallContext) -> dict:
    meds = _medicines_for(context, args.medicines)
    await _log_doses(context, meds, status=args.status, confidence=args.confidence,
                     source=args.source, note=args.note)
    return {"logged": [m.name for m in meds], "status": args.status.value, **_progress(context)}


class RescheduleDoseArgs(BaseModel):
    medicines: list[str] = Field(default_factory=list, description=_MEDICINES_DESCRIPTION)
    remind_in_minutes: int = Field(ge=1, le=720)
    reason: str | None = None


@registry.register(
    name="reschedule_dose",
    description=(
        "The patient will take these medicines later and asked to be reminded: record them as "
        "not taken yet and schedule a reminder call `remind_in_minutes` minutes from now. Only "
        "call this once the patient has told you when they want to be reminded."
    ),
    args_model=RescheduleDoseArgs,
)
async def reschedule_dose(args: RescheduleDoseArgs, context: CallContext) -> dict:
    meds = _medicines_for(context, args.medicines)
    remind_at = datetime.utcnow() + timedelta(minutes=args.remind_in_minutes)
    # insights.py reads this prefix as "later", not "missed".
    note = f"will take it later; reminder in {args.remind_in_minutes} min"
    if args.reason:
        note += f" ({args.reason})"
    await _log_doses(context, meds, status=DoseStatus.not_taken, confidence=DoseConfidence.high,
                     source=DoseSource.patient_self_report, note=note)

    reminder = Reminder(
        patient_id=context.patient_id,
        dosage_ids=[m.dosage_id for m in meds],
        slot_at=context.slot_at,
        call_id=context.call_id,
        remind_at=remind_at,
    )
    await reminders_col().insert_one(model_to_doc(reminder))
    if context.on_reminder_created is not None:
        context.on_reminder_created(reminder)

    local = remind_at.replace(tzinfo=timezone.utc).astimezone()
    return {
        "reminder_set": True,
        "for": [m.name for m in meds],
        "remind_at_local": local.strftime("%H:%M"),
        "note": note,
        **_progress(context),
    }


class SymptomArg(BaseModel):
    name: str
    location: str | None = None
    severity: SymptomSeverity = Field(
        description="How bad the PATIENT says it is. Take their own intensity words at face value: "
        "'bahut'/'very'/'bohot zyada' means moderate or severe, never mild.")
    duration_note: str | None = None
    raw_quote: str | None = Field(default=None, description="The patient's own words about this symptom.")


class UpdateDailyLogArgs(BaseModel):
    summary: str
    seriousness: int = Field(
        ge=1, le=10,
        description="1-4: nothing, or mild and short-lived. 5-7: moderate -- several symptoms "
        "together, or one the patient calls heavy/very bad ('bahut'), or anything lasting 2+ days. "
        "8-10: severe or alarming. Only 1-4 can always be logged here; for 5 and up follow the "
        "current step's instructions.")
    patient_declined_doctor_quote: str | None = Field(
        default=None,
        description="Only when you offered the doctor (seriousness 5-7) and the patient said no: "
        "their exact words, copied from their latest message.")
    symptoms: list[SymptomArg] = Field(default_factory=list)


@registry.register(
    name="update_daily_log",
    description=(
        "Record a summary of how the patient is doing and any (non-severe) symptoms mentioned, "
        "when nothing requires escalation."
    ),
    args_model=UpdateDailyLogArgs,
)
async def update_daily_log(args: UpdateDailyLogArgs, context: CallContext) -> dict:
    log = DailyLog(
        patient_id=context.patient_id,
        call_id=context.call_id,
        summary=args.summary,
        symptoms=[Symptom(**s.model_dump()) for s in args.symptoms],
        seriousness=args.seriousness,
    )
    await daily_logs_col().insert_one(model_to_doc(log))
    patient_status = PatientStatus.good if args.seriousness <= 4 else PatientStatus.remedy
    await calls_col().update_one(
        {"_id": context.call_id},
        {"$set": {
            "patient_status": patient_status.value,
            "medicine_status": _medicine_status(context),
        }},
    )
    return {"logged": True, "daily_log_id": log.id}


class EscalateToDoctorArgs(BaseModel):
    reason: str
    brief_summary: str
    urgency: str = "high"


@registry.register(
    name="escalate_to_doctor",
    description="Escalate the call to the patient's doctor because of a concerning symptom.",
    args_model=EscalateToDoctorArgs,
)
async def escalate_to_doctor(args: EscalateToDoctorArgs, context: CallContext) -> dict:
    context.escalated = True
    context.escalation = EscalationRequest(
        reason=args.reason, brief_summary=args.brief_summary, urgency=args.urgency
    )
    await calls_col().update_one(
        {"_id": context.call_id},
        {"$set": {
            "escalation_reason": args.reason,
            "patient_status": PatientStatus.urgent.value,
        }},
    )
    # The doctor is rung by whoever hosts the call (backend/escalations.py) once the patient has
    # heard the hand-off line; the caregiver is told here, unconditionally.
    caregiver = await notify_caregiver_of_escalation(context, args.reason)
    return {"escalation_recorded": True, "reason": args.reason, "caregiver": caregiver}


_URGENT_AT_SERIOUSNESS = 8


class AlertCaregiverArgs(BaseModel):
    reason: str = Field(description="What is wrong, in a few plain words for the family member, e.g. "
                        "'headache since 2 days, says it is bad'.")
    summary: str = Field(description="A short summary of how the patient is doing, for the day's log.")
    seriousness: int = Field(
        ge=1, le=10,
        description="Same scale as update_daily_log: 5-7 moderate, 8-10 severe or alarming (the "
        "family is told it is urgent).")
    symptoms: list[SymptomArg] = Field(default_factory=list)


@registry.register(
    name="alert_caregiver",
    description=(
        "The patient isn't well: record the symptoms and alert their family member (caregiver) with "
        "what is wrong. Ends the call."
    ),
    args_model=AlertCaregiverArgs,
)
async def alert_caregiver(args: AlertCaregiverArgs, context: CallContext) -> dict:
    urgent = args.seriousness >= _URGENT_AT_SERIOUSNESS
    log = DailyLog(
        patient_id=context.patient_id,
        call_id=context.call_id,
        summary=args.summary,
        symptoms=[Symptom(**s.model_dump()) for s in args.symptoms],
        seriousness=args.seriousness,
    )
    await daily_logs_col().insert_one(model_to_doc(log))
    await calls_col().update_one(
        {"_id": context.call_id},
        {"$set": {
            "patient_status": (PatientStatus.urgent if urgent else PatientStatus.remedy).value,
            "medicine_status": _medicine_status(context),
        }},
    )
    caregiver = await notify_caregiver_unwell(context, args.reason, urgent=urgent)
    context.caregiver_alert = CaregiverAlert(
        reason=args.reason, urgent=urgent,
        caregiver_name=caregiver.get("caregiver") if caregiver.get("notified") else None,
    )
    return {"daily_log_id": log.id, "urgent": urgent, "caregiver": caregiver}


class EndCallArgs(BaseModel):
    pass


@registry.register(
    name="end_call",
    description="Close out the call after the doctor hand-off has been communicated.",
    args_model=EndCallArgs,
)
async def end_call(args: EndCallArgs, context: CallContext) -> dict:
    return {"ended": True}


def _medicine_status(context: CallContext) -> str | None:
    """One word for the whole call: taken only if every medicine was, not_taken if any wasn't."""
    statuses = set(context.dose_statuses.values())
    if not statuses:
        return None
    if statuses == {DoseStatus.taken}:
        return "taken"
    if statuses & {DoseStatus.not_taken, DoseStatus.skipped_on_advice}:
        return "not_taken"
    return "confusion"
