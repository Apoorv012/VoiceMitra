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
from core.agent.tool_registry import ToolRegistry
from domains.med_adherence.context import CallContext

registry = ToolRegistry()


class LogDoseEventArgs(BaseModel):
    status: DoseStatus
    confidence: DoseConfidence
    source: DoseSource
    note: str | None = None


@registry.register(
    name="log_dose_event",
    description="Record whether the patient took their due medicine dose this call.",
    args_model=LogDoseEventArgs,
)
async def log_dose_event(args: LogDoseEventArgs, context: CallContext) -> dict:
    event = DoseEvent(
        patient_id=context.patient_id,
        dosage_id=context.dosage_id,
        scheduled_at=datetime.utcnow(),
        status=args.status,
        confidence=args.confidence,
        source=args.source,
        recorded_via_call_id=context.call_id,
        note=args.note,
    )
    await dose_events_col().insert_one(model_to_doc(event))
    context.dose_status = args.status
    return {"logged": True, "status": args.status.value}


class RescheduleDoseArgs(BaseModel):
    remind_in_minutes: int = Field(ge=1, le=720)
    reason: str | None = None


@registry.register(
    name="reschedule_dose",
    description=(
        "The patient will take this dose later and asked to be reminded: record the dose as "
        "not taken yet and schedule a reminder call `remind_in_minutes` minutes from now. Only "
        "call this once the patient has told you when they want to be reminded."
    ),
    args_model=RescheduleDoseArgs,
)
async def reschedule_dose(args: RescheduleDoseArgs, context: CallContext) -> dict:
    remind_at = datetime.utcnow() + timedelta(minutes=args.remind_in_minutes)
    note = f"will take it later; reminder in {args.remind_in_minutes} min"
    if args.reason:
        note += f" ({args.reason})"
    event = DoseEvent(
        patient_id=context.patient_id,
        dosage_id=context.dosage_id,
        scheduled_at=datetime.utcnow(),
        status=DoseStatus.not_taken,
        confidence=DoseConfidence.high,
        source=DoseSource.patient_self_report,
        recorded_via_call_id=context.call_id,
        note=note,
    )
    await dose_events_col().insert_one(model_to_doc(event))
    context.dose_status = DoseStatus.not_taken

    reminder = Reminder(
        patient_id=context.patient_id,
        dosage_id=context.dosage_id,
        call_id=context.call_id,
        remind_at=remind_at,
    )
    await reminders_col().insert_one(model_to_doc(reminder))
    if context.on_reminder_created is not None:
        context.on_reminder_created(reminder)

    local = remind_at.replace(tzinfo=timezone.utc).astimezone()
    return {
        "reminder_set": True,
        "remind_at_local": local.strftime("%H:%M"),
        "note": note,
    }


class SymptomArg(BaseModel):
    name: str
    location: str | None = None
    severity: SymptomSeverity
    duration_note: str | None = None
    raw_quote: str | None = None


class UpdateDailyLogArgs(BaseModel):
    summary: str
    seriousness: int = Field(ge=1, le=10)
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
    await calls_col().update_one(
        {"_id": context.call_id},
        {"$set": {
            "escalation_reason": args.reason,
            "patient_status": PatientStatus.urgent.value,
        }},
    )
    # Chunk 4 extends this to actually notify a doctor dashboard and set up the live call merge;
    # for now it just records the decision so the agent core/logic is fully testable on its own.
    return {"escalation_recorded": True, "reason": args.reason}


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
    if context.dose_status is None:
        return None
    mapping = {
        DoseStatus.taken: "taken",
        DoseStatus.not_taken: "not_taken",
        DoseStatus.unknown: "confusion",
        DoseStatus.partial: "confusion",
        DoseStatus.skipped_on_advice: "not_taken",
    }
    return mapping.get(context.dose_status)
