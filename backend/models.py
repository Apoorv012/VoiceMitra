"""Pydantic models mirroring the data model in the approved plan (extends reference_transcripts/original_schema.txt)."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
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


class CareMode(str, Enum):
    """Who is brought in when the patient isn't well. One switch for every call, not per patient:
    DOCTOR_FLOW_ENABLED in .env (off for the pilot -- see domains/med_adherence/bot.py)."""
    caregiver = "caregiver"  # the pilot: the caregiver is alerted, no doctor is rung
    doctor = "doctor"        # the doctor is rung and merged into the call


class CaregiverNotifyOn(str, Enum):
    unreachable = "unreachable"
    escalation = "escalation"


class CallLogEntryType(str, Enum):
    patient_said = "patient_said"
    agent_said = "agent_said"
    tool_call = "tool_call"
    escalation_call_started = "escalation_call_started"  # agent dialed the doctor separately
    escalation_call_merged = "escalation_call_merged"    # doctor's call merged into the patient's
    doctor_said = "doctor_said"                          # doctor's message, in the briefing or merged
    escalation_summary = "escalation_summary"            # agent's summary of the merged conversation


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
    # For frequency=every_x_days: due every `interval_days` days counting from `from_date`. Older
    # records have none, and are then treated as daily.
    interval_days: int | None = Field(default=None, ge=1)


class Prescription(MongoDocument):
    patient_id: str
    medicines: list[Dosage] = Field(default_factory=list)


class DoseEvent(MongoDocument):
    patient_id: str
    dosage_id: str
    # The dose slot this event is about (UTC). Events from calls made before calls knew their slot
    # carry the moment they were logged instead.
    scheduled_at: datetime
    status: DoseStatus
    confidence: DoseConfidence
    source: DoseSource
    recorded_via_call_id: str | None = None
    note: str | None = None          # e.g. why a dose was missed
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
    related_call_id: str | None = None        # for escalation_call_started / _merged (the escalation's id)
    note: str | None = None                   # e.g. "guardrail override: <reason>"
    # Which leg of an escalated call an entry belongs to: None = the patient's own conversation with
    # the agent, "doctor_briefing" = doctor <-> agent (patient on hold), "merged" = doctor + patient.
    channel: str | None = None


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
    # The dose slot the call is about (UTC) and the medicines due in it.
    slot_at: datetime | None = None
    dosage_ids: list[str] = Field(default_factory=list)


class EscalationStatus(str, Enum):
    ringing = "ringing"      # doctor(s) notified, nobody has joined yet; patient on hold
    briefing = "briefing"    # a doctor joined and is talking to the agent; patient still on hold
    merged = "merged"        # doctor and patient are talking; the agent listens and takes notes
    resolved = "resolved"    # ended after a merge, summary recorded
    abandoned = "abandoned"  # ended (or the server restarted) before the doctor and patient were merged


class Escalation(MongoDocument):
    """The doctor leg of an escalated call: rung, briefed, merged, summarised."""

    patient_id: str
    call_id: str
    reason: str
    brief_summary: str
    urgency: str = "high"
    doctor_ids: list[str] = Field(default_factory=list)  # doctors rung (those the patient is assigned to)
    doctor_id: str | None = None                          # the one who joined
    status: EscalationStatus = EscalationStatus.ringing
    created_at: datetime = Field(default_factory=datetime.utcnow)
    joined_at: datetime | None = None
    merged_at: datetime | None = None
    ended_at: datetime | None = None
    summary: str | None = None


class CaregiverNotification(MongoDocument):
    """An alert to a patient's caregiver. Delivery is simulated for the POC: the record (shown on the
    patient/family page) is the notification."""

    patient_id: str
    caregiver_id: str
    call_id: str
    trigger: CaregiverNotifyOn
    message: str
    urgent: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    seen_at: datetime | None = None  # the caregiver marked it as seen on their page


class ReminderStatus(str, Enum):
    pending = "pending"
    fired = "fired"
    missed = "missed"    # came due while the server was down, and too late to still be useful


class Reminder(MongoDocument):
    """A follow-up call the patient asked for (e.g. "I'll take it later, remind me in an hour")."""

    patient_id: str
    dosage_ids: list[str] = Field(default_factory=list)  # the medicines still to be taken
    slot_at: datetime | None = None  # the dose slot they belong to (UTC)
    dosage_id: str | None = None     # older records: a single medicine and no slot
    call_id: str                     # the call in which the patient asked for it
    remind_at: datetime              # UTC, like every other timestamp here
    status: ReminderStatus = ReminderStatus.pending


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


# ---------------------------------------------------------------------------
# Phones (mobile/API.md): a patient's phone pairs once with a short code from the web app, then
# rings when a voice call starts for them.
# ---------------------------------------------------------------------------

class DevicePlatform(str, Enum):
    android = "android"
    ios = "ios"


class Device(MongoDocument):
    """A phone paired to a patient. Its secret token is stored only as a SHA-256 hash."""

    patient_id: str
    platform: DevicePlatform
    push_token: str | None = None  # FCM registration token (Android); none on iPhone for now
    name: str | None = None        # e.g. "Pixel 7", shown on the patient's page
    token_hash: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_seen: datetime = Field(default_factory=datetime.utcnow)


class PairingCode(MongoDocument):
    """A 6-digit code the web app shows so a phone can pair with this patient. Single use."""

    code: str
    patient_id: str
    expires_at: datetime
    used: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)


class LoginRole(str, Enum):
    staff = "staff"          # hospital/pilot staff: the operator screens, everything
    patient = "patient"      # the patient: their own app (website and phone apps)
    caregiver = "caregiver"  # a patient's family contact: their page on the website


class Login(MongoDocument):
    """A username + password: how staff, patients and caregivers sign in (backend/logins.py).

    One collection (`logins`) for everyone, so a username is unique across all of them. `id` is the id
    of who signs in: the patient's or caregiver's id, or (staff, who have no other record) a fresh one.
    Kept apart from the patient/caregiver documents so a password hash can never end up in their
    responses. Only an scrypt hash of the password is stored (backend/auth.py).
    """

    role: LoginRole
    username: str      # as typed (trimmed), shown on the web page
    username_key: str  # lower-cased: what logins match on, unique
    password_hash: str
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ContactTopic(str, Enum):
    demo = "demo"        # book a demo
    pilot = "pilot"      # run a pilot at a clinic or hospital
    family = "family"    # set it up for a family member
    other = "other"


class ContactMessage(MongoDocument):
    """A message sent from the contact form on the public homepage. Operators read them in the web app."""

    name: str
    email: str
    phone: str | None = None
    organisation: str | None = None
    topic: ContactTopic = ContactTopic.demo
    message: str
    handled: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))  # sent with its zone
