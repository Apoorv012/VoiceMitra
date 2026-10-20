"""Read models for the web app: what each screen needs, already worked out.

The frontend is a separate app that only talks JSON to this backend, so everything that takes
judgment about the records lives here (via `insights.py`) rather than being re-derived in the browser:
today's doses and their state, the week at a glance, who needs a doctor's attention. These Pydantic
models are the contract -- the frontend generates its TypeScript types from FastAPI's OpenAPI schema.

Times go out as timezone-aware ISO strings. Every view carries `timezone` (APP_TIMEZONE) because "today"
and dose times like 09:00 are decided in that zone and the browser should render them in it too.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from pydantic import BaseModel, ConfigDict, Field

from backend import insights as ins
from backend.db import (
    calls_col,
    caregiver_notifications_col,
    caregivers_col,
    daily_logs_col,
    doc_to_model,
    doctors_col,
    dose_events_col,
    escalations_col,
    patients_col,
    prescriptions_col,
    reminders_col,
)
from backend.models import (
    Call,
    CallLogEntryType,
    Caregiver,
    CaregiverNotification,
    DailyLog,
    Doctor,
    Dosage,
    DoseEvent,
    Escalation,
    EscalationStatus,
    Patient,
    Prescription,
    Reminder,
    ReminderStatus,
)

WEEK = 7
CLINICAL_DAYS = 14
HISTORY_LIMIT = 60
EVENT_LOOKBACK = timedelta(days=45)


def aware(dt: datetime | None) -> datetime | None:
    """Stored timestamps are naive UTC; send them out with their zone."""
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


# --- schemas ----------------------------------------------------------------------------------

class View(BaseModel):
    """Base for response models. Fields with defaults are still always sent, so the generated OpenAPI
    (and the frontend's TypeScript types) mark them required rather than optional."""

    model_config = ConfigDict(json_schema_serialization_defaults_required=True)


class Person(View):
    id: str
    name: str
    age: int | None = None
    description: str | None = None


class People(View):
    patients: list[Person]
    doctors: list[Person]


class CaregiverView(View):
    id: str
    name: str
    relation: str
    phone_number: str


class SlotView(View):
    dosage_id: str
    medicine: str
    dose: str
    at: datetime
    state: str          # taken|partial|missed|later|unknown|skipped|upcoming|due|no_checkin
    note: str | None = None
    recorded_at: datetime | None = None


class DayView(View):
    date: date
    state: str          # good|mixed|missed|unknown|upcoming|none
    taken: int
    due: int
    slots: list[SlotView]


class AdherenceView(View):
    taken: int
    missed: int
    unrecorded: int
    rate: int | None    # % of the doses we heard about that were taken; None until we've heard about any


class SymptomView(View):
    name: str
    location: str | None = None
    severity: str
    duration_note: str | None = None


class LogView(View):
    id: str
    call_id: str
    at: datetime
    seriousness: int
    band: str           # ok|watch|urgent
    summary: str
    symptoms: list[SymptomView]


class CheckinView(View):
    call_id: str
    at: datetime
    type: str
    medicine_status: str | None = None
    patient_status: str | None = None
    summary: str | None = None
    symptoms: list[str] = Field(default_factory=list)
    seriousness: int | None = None
    escalated: bool = False
    doctor_connected: bool = False
    escalation_reason: str | None = None


class MedicineView(View):
    dosage_id: str
    name: str
    dose: str
    frequency: str
    times: list[str]
    from_date: date
    to_date: date | None
    active: bool
    days_left: int | None   # None: no end date
    taken: int              # last 7 days
    known: int


class HowDoing(View):
    at: datetime
    summary: str
    band: str


class AlertView(View):
    at: datetime
    message: str
    caregiver: str | None
    trigger: str
    call_id: str


class AttentionView(View):
    level: str          # critical|warning|ok
    reasons: list[str]


class PatientHome(View):
    timezone: str
    patient: Person
    allergies: list[str]
    today: list[SlotView]
    next_dose: SlotView | None
    week: list[DayView]
    adherence: AdherenceView
    last_checkin: CheckinView | None
    how_doing: HowDoing | None
    reminders: list[datetime]
    caregiver: CaregiverView | None


class PatientMedicines(View):
    timezone: str
    patient: Person
    allergies: list[str]
    medicines: list[MedicineView]


class PatientHistory(View):
    timezone: str
    patient: Person
    checkins: list[CheckinView]
    alerts: list[AlertView]


class EscalationRow(View):
    id: str
    patient_id: str
    patient_name: str
    status: str
    created_at: datetime
    reason: str
    summary: str | None
    urgency: str
    call_id: str
    doctor_name: str | None
    is_mine: bool


class PatientRow(View):
    id: str
    name: str
    age: int
    attention: AttentionView
    adherence: AdherenceView
    week: list[str]                 # day states, oldest first
    last_checkin_at: datetime | None
    latest_seriousness: int | None
    live_escalation_id: str | None


class Tiles(View):
    patients: int
    needing_attention: int
    checkins_today: int
    adherence_rate: int | None


class DoctorOverview(View):
    timezone: str
    doctor: Person
    tiles: Tiles
    patients: list[PatientRow]
    escalations: list[EscalationRow]


class PatientClinical(View):
    timezone: str
    patient: Person
    phone_number: str
    address: str | None
    allergies: list[str]
    caregiver: CaregiverView | None
    attention: AttentionView
    adherence: AdherenceView
    days: list[DayView]             # CLINICAL_DAYS, oldest first
    logs: list[LogView]             # newest first
    medicines: list[MedicineView]
    checkins: list[CheckinView]
    escalations: list[EscalationRow]
    alerts: list[AlertView]
    reminders: list[datetime]


class EscalationView(View):
    timezone: str
    id: str
    status: str
    created_at: datetime
    reason: str
    brief_summary: str
    urgency: str
    summary: str | None
    call_id: str
    doctor: Person | None
    patient: Person
    phone_number: str
    allergies: list[str]
    medicines: list[MedicineView]
    week: list[DayView]
    adherence: AdherenceView
    recent_logs: list[LogView]


class TranscriptEntry(View):
    kind: str           # patient|agent|doctor|tool|summary|event
    at: datetime
    text: str | None = None
    leg: str | None = None            # doctor_briefing|merged|None
    tool_name: str | None = None
    tool_args: dict | None = None
    tool_result: dict | None = None
    note: str | None = None


class CallTranscript(View):
    timezone: str
    id: str
    patient: Person
    at: datetime
    type: str
    medicine_status: str | None
    patient_status: str | None
    escalation_reason: str | None
    caregiver_notified: bool
    entries: list[TranscriptEntry]


class RosterRow(View):
    id: str
    name: str
    age: int
    phone_number: str
    last_call_at: datetime | None
    last_status: str | None
    in_call: bool
    attention: AttentionView


class OperatorRoster(View):
    timezone: str
    patients: list[RosterRow]


# --- loading ----------------------------------------------------------------------------------

@dataclass
class PatientData:
    patient: Patient
    caregiver: Caregiver | None
    dosages: list[Dosage]
    events: list[DoseEvent]
    logs: list[DailyLog]               # newest first
    calls: list[Call]                  # newest first, without their transcripts
    escalations: list[Escalation]      # newest first
    reminders: list[Reminder]
    alerts: list[CaregiverNotification]


async def _all(cursor) -> list:
    return [d async for d in cursor]


async def load_patient(patient_id: str) -> PatientData | None:
    patient = doc_to_model(Patient, await patients_col().find_one({"_id": patient_id}))
    if patient is None:
        return None
    # Dates are stored as ISO strings (db.model_to_doc dumps in JSON mode), so a range filter must
    # compare strings: a datetime here would silently match nothing.
    since = (datetime.utcnow() - EVENT_LOOKBACK).isoformat()
    (caregiver_doc, rx_docs, event_docs, log_docs, call_docs, esc_docs, reminder_docs, alert_docs) = (
        await asyncio.gather(
            caregivers_col().find_one({"_id": patient.caregiver_id}) if patient.caregiver_id else _none(),
            _all(prescriptions_col().find({"_id": {"$in": patient.prescription_ids}})),
            _all(dose_events_col().find({"patient_id": patient_id, "recorded_at": {"$gte": since}})),
            _all(daily_logs_col().find({"patient_id": patient_id}).sort("created_at", -1).limit(HISTORY_LIMIT)),
            _all(calls_col().find({"patient_id": patient_id}, {"logs": 0}).sort("date_time", -1).limit(HISTORY_LIMIT)),
            _all(escalations_col().find({"patient_id": patient_id}).sort("created_at", -1).limit(HISTORY_LIMIT)),
            _all(reminders_col().find({"patient_id": patient_id, "status": ReminderStatus.pending.value}).sort("remind_at", 1)),
            _all(caregiver_notifications_col().find({"patient_id": patient_id}).sort("created_at", -1).limit(30)),
        )
    )
    prescriptions = [doc_to_model(Prescription, d) for d in rx_docs]
    return PatientData(
        patient=patient,
        caregiver=doc_to_model(Caregiver, caregiver_doc),
        dosages=[m for rx in prescriptions for m in rx.medicines],
        events=[doc_to_model(DoseEvent, d) for d in event_docs],
        logs=[doc_to_model(DailyLog, d) for d in log_docs],
        calls=[doc_to_model(Call, d) for d in call_docs],
        escalations=[doc_to_model(Escalation, d) for d in esc_docs],
        reminders=[doc_to_model(Reminder, d) for d in reminder_docs],
        alerts=[doc_to_model(CaregiverNotification, d) for d in alert_docs],
    )


async def _none():
    return None


# --- building blocks ------------------------------------------------------------------------

def person(p: Patient) -> Person:
    return Person(id=p.id, name=p.name, age=p.age, description=p.description)


def _slot(s: ins.Slot) -> SlotView:
    return SlotView(
        dosage_id=s.dosage.id, medicine=s.dosage.medicine_name, dose=s.dosage.dosage, at=s.at,
        state=s.state, note=s.event.note if s.event else None,
        recorded_at=aware(s.event.recorded_at) if s.event else None,
    )


def _day(cell: ins.DayCell) -> DayView:
    return DayView(date=cell.day, state=cell.state, taken=cell.taken, due=cell.due,
                   slots=[_slot(s) for s in cell.slots])


def _adherence(a: ins.Adherence) -> AdherenceView:
    return AdherenceView(taken=a.taken, missed=a.missed, unrecorded=a.unrecorded, rate=a.rate)


def _log(l: DailyLog) -> LogView:
    return LogView(
        id=l.id, call_id=l.call_id, at=aware(l.created_at), seriousness=l.seriousness,
        band=ins.seriousness_band(l.seriousness), summary=l.summary,
        symptoms=[SymptomView(name=s.name, location=s.location, severity=s.severity.value,
                              duration_note=s.duration_note) for s in l.symptoms],
    )


def _caregiver(c: Caregiver | None) -> CaregiverView | None:
    return None if c is None else CaregiverView(
        id=c.id, name=c.name, relation=c.relation, phone_number=c.phone_number)


def _slots(data: PatientData, first: date, last: date, now: datetime) -> list[ins.Slot]:
    return ins.build_slots(data.dosages, data.events, first, last, now)


def _checkin(call: Call, data: PatientData) -> CheckinView:
    log = next((l for l in data.logs if l.call_id == call.id), None)
    esc = next((e for e in data.escalations if e.call_id == call.id), None)
    return CheckinView(
        call_id=call.id, at=aware(call.date_time), type=call.type.value,
        medicine_status=call.medicine_status.value if call.medicine_status else None,
        patient_status=call.patient_status.value if call.patient_status else None,
        summary=log.summary if log else None,
        symptoms=[s.name for s in log.symptoms] if log else [],
        seriousness=log.seriousness if log else None,
        escalated=esc is not None or bool(call.escalation_reason),
        doctor_connected=esc is not None and (esc.merged_at is not None or esc.status == EscalationStatus.merged),
        escalation_reason=call.escalation_reason or (esc.reason if esc else None),
    )


def _medicines(data: PatientData, today: date, week_slots: list[ins.Slot]) -> list[MedicineView]:
    views = []
    for d in data.dosages:
        mine = [s for s in week_slots if s.dosage.id == d.id]
        a = ins.adherence(mine)
        active = d.from_date <= today and (d.to_date is None or d.to_date >= today)
        views.append(MedicineView(
            dosage_id=d.id, name=d.medicine_name, dose=d.dosage, frequency=d.frequency.value,
            times=sorted(d.times), from_date=d.from_date, to_date=d.to_date, active=active,
            days_left=None if d.to_date is None else max(0, (d.to_date - today).days),
            taken=a.taken, known=a.known,
        ))
    # Current medicines first, then by name.
    return sorted(views, key=lambda m: (not m.active, m.name.lower()))


def _alert(n: CaregiverNotification, data: PatientData) -> AlertView:
    return AlertView(at=aware(n.created_at), message=n.message, trigger=n.trigger.value, call_id=n.call_id,
                     caregiver=data.caregiver.name if data.caregiver else None)


def _attention(data: PatientData, week_slots: list[ins.Slot], now: datetime) -> AttentionView:
    a = ins.assess(slots=week_slots, logs=data.logs, escalations=data.escalations, calls=data.calls, now=now)
    return AttentionView(level=a.level, reasons=a.reasons)


def _escalation_row(e: Escalation, patient_name: str, doctor_names: dict[str, str], viewer: str | None) -> EscalationRow:
    return EscalationRow(
        id=e.id, patient_id=e.patient_id, patient_name=patient_name, status=e.status.value,
        created_at=aware(e.created_at), reason=e.reason, summary=e.summary, urgency=e.urgency,
        call_id=e.call_id, doctor_name=doctor_names.get(e.doctor_id or ""), is_mine=(e.doctor_id == viewer),
    )


# --- patient screens ------------------------------------------------------------------------

def patient_home(data: PatientData, now: datetime | None = None) -> PatientHome:
    now = now or ins.now_local()
    today = now.date()
    slots = _slots(data, today - timedelta(days=WEEK - 1), today + timedelta(days=1), now)
    todays = [s for s in slots if s.day == today]
    upcoming = [s for s in slots if s.state in (ins.DUE, ins.UPCOMING, ins.LATER)]
    week_slots = [s for s in slots if s.day <= today]
    recent = next((l for l in data.logs if now - ins.to_local(l.created_at) <= timedelta(days=7)), None)
    return PatientHome(
        timezone=ins.TZ.key,
        patient=person(data.patient),
        allergies=data.patient.allergies,
        today=[_slot(s) for s in todays],
        next_dose=_slot(upcoming[0]) if upcoming else None,
        week=[_day(c) for c in ins.week_cells(week_slots, today, WEEK)],
        adherence=_adherence(ins.adherence(week_slots)),
        last_checkin=_checkin(data.calls[0], data) if data.calls else None,
        how_doing=HowDoing(at=aware(recent.created_at), summary=recent.summary,
                           band=ins.seriousness_band(recent.seriousness)) if recent else None,
        reminders=[aware(r.remind_at) for r in data.reminders],
        caregiver=_caregiver(data.caregiver),
    )


def patient_medicines(data: PatientData, now: datetime | None = None) -> PatientMedicines:
    now = now or ins.now_local()
    today = now.date()
    week_slots = [s for s in _slots(data, today - timedelta(days=WEEK - 1), today, now)]
    return PatientMedicines(
        timezone=ins.TZ.key, patient=person(data.patient), allergies=data.patient.allergies,
        medicines=_medicines(data, today, week_slots),
    )


def patient_history(data: PatientData) -> PatientHistory:
    return PatientHistory(
        timezone=ins.TZ.key, patient=person(data.patient),
        checkins=[_checkin(c, data) for c in data.calls],
        alerts=[_alert(n, data) for n in data.alerts],
    )


# --- doctor screens -------------------------------------------------------------------------

def patient_row(data: PatientData, now: datetime) -> PatientRow:
    today = now.date()
    week_slots = _slots(data, today - timedelta(days=WEEK - 1), today, now)
    live = next((e for e in data.escalations if e.status in ins.LIVE_ESCALATION), None)
    return PatientRow(
        id=data.patient.id, name=data.patient.name, age=data.patient.age,
        attention=_attention(data, week_slots, now),
        adherence=_adherence(ins.adherence(week_slots)),
        week=[c.state for c in ins.week_cells(week_slots, today, WEEK)],
        last_checkin_at=aware(data.calls[0].date_time) if data.calls else None,
        latest_seriousness=data.logs[0].seriousness if data.logs else None,
        live_escalation_id=live.id if live else None,
    )


async def doctor_overview(doctor_id: str, now: datetime | None = None) -> DoctorOverview | None:
    doctor = doc_to_model(Doctor, await doctors_col().find_one({"_id": doctor_id}))
    if doctor is None:
        return None
    now = now or ins.now_local()
    loaded = await asyncio.gather(*(load_patient(pid) for pid in doctor.patient_ids))
    datas = [d for d in loaded if d is not None]
    rows = [patient_row(d, now) for d in datas]
    # Most urgent first, then alphabetical, so the top of the list is always "who to look at".
    rank = {"critical": 0, "warning": 1, "ok": 2}
    rows.sort(key=lambda r: (rank[r.attention.level], r.name.lower()))

    names = {d.patient.id: d.patient.name for d in datas}
    esc_docs = await _all(escalations_col().find({"doctor_ids": doctor_id}).sort("created_at", -1).limit(12))
    escalations = [
        _escalation_row(doc_to_model(Escalation, d), names.get(d["patient_id"], "Patient"),
                        {doctor.id: doctor.name}, doctor_id)
        for d in esc_docs
    ]
    known = [r.adherence for r in rows if r.adherence.rate is not None]
    taken, total = sum(a.taken for a in known), sum(a.taken + a.missed for a in known)
    today = now.date()
    return DoctorOverview(
        timezone=ins.TZ.key,
        doctor=Person(id=doctor.id, name=doctor.name, description=doctor.description),
        tiles=Tiles(
            patients=len(rows),
            needing_attention=sum(r.attention.level != "ok" for r in rows),
            checkins_today=sum(1 for d in datas for c in d.calls if ins.to_local(c.date_time).date() == today),
            adherence_rate=round(100 * taken / total) if total else None,
        ),
        patients=rows,
        escalations=escalations,
    )


async def patient_clinical(patient_id: str, doctor_names: dict[str, str], viewer: str | None,
                           now: datetime | None = None) -> PatientClinical | None:
    data = await load_patient(patient_id)
    if data is None:
        return None
    now = now or ins.now_local()
    today = now.date()
    slots = _slots(data, today - timedelta(days=CLINICAL_DAYS - 1), today, now)
    week_slots = [s for s in slots if s.day >= today - timedelta(days=WEEK - 1)]
    return PatientClinical(
        timezone=ins.TZ.key,
        patient=person(data.patient), phone_number=data.patient.phone_number, address=data.patient.address,
        allergies=data.patient.allergies, caregiver=_caregiver(data.caregiver),
        attention=_attention(data, week_slots, now),
        adherence=_adherence(ins.adherence(week_slots)),
        days=[_day(c) for c in ins.week_cells(slots, today, CLINICAL_DAYS)],
        logs=[_log(l) for l in data.logs],
        medicines=_medicines(data, today, week_slots),
        checkins=[_checkin(c, data) for c in data.calls],
        escalations=[_escalation_row(e, data.patient.name, doctor_names, viewer) for e in data.escalations],
        alerts=[_alert(n, data) for n in data.alerts],
        reminders=[aware(r.remind_at) for r in data.reminders],
    )


async def escalation_view(escalation_id: str, doctor_id: str, now: datetime | None = None) -> EscalationView | None:
    esc = doc_to_model(Escalation, await escalations_col().find_one({"_id": escalation_id}))
    if esc is None or doctor_id not in esc.doctor_ids:
        return None
    data = await load_patient(esc.patient_id)
    doctor = doc_to_model(Doctor, await doctors_col().find_one({"_id": doctor_id}))
    if data is None:
        return None
    now = now or ins.now_local()
    today = now.date()
    week_slots = _slots(data, today - timedelta(days=WEEK - 1), today, now)
    return EscalationView(
        timezone=ins.TZ.key, id=esc.id, status=esc.status.value, created_at=aware(esc.created_at),
        reason=esc.reason, brief_summary=esc.brief_summary, urgency=esc.urgency, summary=esc.summary,
        call_id=esc.call_id,
        doctor=Person(id=doctor.id, name=doctor.name, description=doctor.description) if doctor else None,
        patient=person(data.patient), phone_number=data.patient.phone_number,
        allergies=data.patient.allergies,
        medicines=[m for m in _medicines(data, today, week_slots) if m.active],
        week=[_day(c) for c in ins.week_cells(week_slots, today, WEEK)],
        adherence=_adherence(ins.adherence(week_slots)),
        recent_logs=[_log(l) for l in data.logs[:3]],
    )


# --- transcripts and the operator roster ---------------------------------------------------

_KINDS = {
    CallLogEntryType.patient_said: "patient",
    CallLogEntryType.agent_said: "agent",
    CallLogEntryType.doctor_said: "doctor",
    CallLogEntryType.tool_call: "tool",
    CallLogEntryType.escalation_summary: "summary",
    CallLogEntryType.escalation_call_started: "event",
    CallLogEntryType.escalation_call_merged: "event",
}


def call_transcript(call: Call, patient: Patient) -> CallTranscript:
    entries = []
    for e in call.logs:
        entries.append(TranscriptEntry(
            kind=_KINDS.get(e.type, "event"), at=aware(e.timestamp),
            text=e.content or (e.note if e.type in (CallLogEntryType.escalation_call_started,
                                                    CallLogEntryType.escalation_call_merged) else None),
            leg=e.channel, tool_name=e.tool_name, tool_args=e.tool_args, tool_result=e.tool_result,
            note=None if e.type in (CallLogEntryType.escalation_call_started,
                                    CallLogEntryType.escalation_call_merged) else e.note,
        ))
    return CallTranscript(
        timezone=ins.TZ.key, id=call.id, patient=person(patient), at=aware(call.date_time),
        type=call.type.value,
        medicine_status=call.medicine_status.value if call.medicine_status else None,
        patient_status=call.patient_status.value if call.patient_status else None,
        escalation_reason=call.escalation_reason, caregiver_notified=call.caregiver_notified,
        entries=entries,
    )


async def operator_roster(in_call_ids: set[str], now: datetime | None = None) -> OperatorRoster:
    now = now or ins.now_local()
    ids = [d["_id"] async for d in patients_col().find({}, {"_id": 1})]
    datas = [d for d in await asyncio.gather(*(load_patient(i) for i in ids)) if d is not None]
    rows = []
    for d in datas:
        today = now.date()
        week_slots = _slots(d, today - timedelta(days=WEEK - 1), today, now)
        last = d.calls[0] if d.calls else None
        rows.append(RosterRow(
            id=d.patient.id, name=d.patient.name, age=d.patient.age, phone_number=d.patient.phone_number,
            last_call_at=aware(last.date_time) if last else None,
            last_status=last.patient_status.value if last and last.patient_status else None,
            in_call=d.patient.id in in_call_ids, attention=_attention(d, week_slots, now),
        ))
    return OperatorRoster(timezone=ins.TZ.key, patients=sorted(rows, key=lambda r: r.name.lower()))
