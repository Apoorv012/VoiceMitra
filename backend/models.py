"""Pydantic models mirroring the data model in the approved plan (extends reference_transcripts/original_schema.txt)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


def new_id() -> str:
    return str(uuid.uuid4())


class MongoDocument(BaseModel):
    """Base for models that are stored as their own top-level Mongo document.

    The domain id (a UUID, per schema.txt) IS the Mongo `_id` -- no separate
    id field, no duplicate index. `populate_by_name` lets callers still build
    instances as `Patient(id=..., ...)`; `by_alias=True` on `model_dump()`
    writes it out under `_id` for Mongo, and reads map `_id` back to `id`.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(default_factory=new_id, alias="_id")


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class DoseFrequency(str, Enum):
    daily = "daily"
    weekly = "weekly"
    every_x_days = "every_x_day"
    fixed_times = "fixed_times"


class DoseStatus(str, Enum):
    taken = "taken"
    not_taken = "not_taken"
    partial = "partial"
    unknown = "unknown"
    skipped_on_advice = "skipped_on_advice"


class DoseConfidence(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


class DoseSource(str, Enum):
    patient_self_report = "patient_self_report"
    family_report = "family_report"
    inferred = "inferred"
    doctor_instruction = "doctor_instruction"


class CallType(str, Enum):
    medicine_reminder = "medicine_reminder"
    just_catch_up = "just_catch_up"
    inbound_call = "inbound_call"
    other = "other"


class MedicineStatus(str, Enum):
    taken = "taken"
    confusion = "confusion"
    not_taken = "not_taken"
    dont_know = "dont_know"


class PatientStatus(str, Enum):
    good = "good"
    remedy = "remedy"
    urgent = "urgent"


class SymptomSeverity(str, Enum):
    mild = "mild"
    moderate = "moderate"
    severe = "severe"


class CaregiverNotifyOn(str, Enum):
    unreachable = "unreachable"
    escalation = "escalation"


class CallLogEntryType(str, Enum):
    patient_said = "patient_said"
    agent_said = "agent_said"
    tool_call = "tool_call"
    escalation_call_started = "escalation_call_started"  # agent dialed the doctor separately
    escalation_call_merged = "escalation_call_merged"    # doctor's call merged into the patient's


# ---------------------------------------------------------------------------
# Core entities
# ---------------------------------------------------------------------------

class Caregiver(MongoDocument):
    patient_id: str
    name: str
    relation: str
    phone_number: str
    notify_on: list[CaregiverNotifyOn] = Field(
        default_factory=lambda: [CaregiverNotifyOn.unreachable, CaregiverNotifyOn.escalation]
    )


class Dosage(BaseModel):
    id: str = Field(default_factory=new_id)
    prescription_id: str
    medicine_name: str
    dosage: str
    from_date: date
    to_date: date | None = None
    frequency: DoseFrequency
    times: list[str] = Field(default_factory=list)  # e.g. ["08:00", "20:00"]


class Prescription(MongoDocument):
    patient_id: str
    medicines: list[Dosage] = Field(default_factory=list)


class DoseEvent(MongoDocument):
    patient_id: str
    dosage_id: str
    scheduled_at: datetime
    status: DoseStatus
    confidence: DoseConfidence
    source: DoseSource
    recorded_via_call_id: str | None = None
    recorded_at: datetime = Field(default_factory=datetime.utcnow)


class Doctor(MongoDocument):
    name: str
    age: int | None = None
    description: str | None = None
    phone_number: str
    secondary_phone_numbers: list[str] = Field(default_factory=list)
    address: str | None = None
    patient_ids: list[str] = Field(default_factory=list)


class Symptom(BaseModel):
    name: str
    location: str | None = None
    severity: SymptomSeverity
    duration_note: str | None = None
    raw_quote: str | None = None


class DailyLog(MongoDocument):
    patient_id: str
    call_id: str
    summary: str
    symptoms: list[Symptom] = Field(default_factory=list)
    seriousness: int = Field(ge=1, le=10)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class CallLogEntry(BaseModel):
    type: CallLogEntryType
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    content: str | None = None               # for patient_said / agent_said
    tool_name: str | None = None              # for tool_call
    tool_args: dict | None = None             # for tool_call
    tool_result: dict | None = None           # for tool_call
    related_call_id: str | None = None        # for escalation_call_started / _merged
    note: str | None = None                   # e.g. "guardrail override: <reason>"


class Call(MongoDocument):
    patient_id: str
    date_time: datetime = Field(default_factory=datetime.utcnow)
    logs: list[CallLogEntry] = Field(default_factory=list)
    doctor_id: str | None = None
    type: CallType
    medicine_status: MedicineStatus | None = None
    patient_status: PatientStatus | None = None
    escalation_reason: str | None = None
    caregiver_notified: bool = False
    room_url: str | None = None


class Patient(MongoDocument):
    name: str
    age: int
    description: str | None = None
    phone_number: str
    address: str | None = None
    allergies: list[str] = Field(default_factory=list)
    caregiver_id: str | None = None
    prescription_ids: list[str] = Field(default_factory=list)
    daily_log_ids: list[str] = Field(default_factory=list)
    call_ids: list[str] = Field(default_factory=list)
