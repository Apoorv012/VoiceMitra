"""The read models behind each screen, built from in-memory records (no database)."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from backend import insights as ins
from backend import views
from backend.models import (
    Call, CallLogEntry, CallLogEntryType, CallType, Caregiver, DailyLog, Dosage, DoseConfidence, DoseEvent,
    DoseFrequency, DoseSource, DoseStatus, Escalation, EscalationStatus, Patient, Symptom, SymptomSeverity,
)

TODAY = date(2026, 10, 21)
NOW = datetime(2026, 10, 21, 10, 0, tzinfo=ins.TZ)


def utc(dt: datetime) -> datetime:
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def at(h: int, m: int = 0, day: date = TODAY) -> datetime:
    return datetime(day.year, day.month, day.day, h, m, tzinfo=ins.TZ)


def data(**over) -> views.PatientData:
    patient = Patient(name="Sunita Verma", age=72, phone_number="+911", allergies=["Penicillin"])
    dosage = Dosage(prescription_id="rx", medicine_name="Glimepiride", dosage="2 mg", from_date=TODAY - timedelta(days=10),
                    to_date=TODAY + timedelta(days=20), frequency=DoseFrequency.fixed_times, times=["08:30", "21:00"])
    base = dict(patient=patient, caregiver=Caregiver(patient_id=patient.id, name="Neha", relation="daughter", phone_number="+912"),
                dosages=[dosage], events=[], logs=[], calls=[], escalations=[], reminders=[], alerts=[])
    base.update(over)
    return views.PatientData(**base)


def taken(d: Dosage, when: datetime) -> DoseEvent:
    return DoseEvent(patient_id="p", dosage_id=d.id, scheduled_at=utc(when), recorded_at=utc(when),
                     status=DoseStatus.taken, confidence=DoseConfidence.high, source=DoseSource.patient_self_report)


def test_home_lists_todays_doses_and_the_next_one():
    d = data()
    d.events = [taken(d.dosages[0], at(8, 40))]
    home = views.patient_home(d, now=NOW)
    assert [s.state for s in home.today] == ["taken", "upcoming"]
    assert home.next_dose is not None and home.next_dose.at.hour == 21
    assert home.timezone == ins.TZ.key
    assert home.allergies == ["Penicillin"] and home.caregiver and home.caregiver.name == "Neha"
    assert len(home.week) == 7 and home.week[-1].date == TODAY


def test_home_with_no_medicines_is_an_empty_but_valid_screen():
    home = views.patient_home(data(dosages=[]), now=NOW)
    assert home.today == [] and home.next_dose is None
    assert all(day.state == "none" for day in home.week)
    assert home.adherence.rate is None and home.how_doing is None and home.last_checkin is None


def test_how_doing_comes_from_the_latest_report_within_a_week_and_is_banded():
    log = DailyLog(patient_id="p", call_id="c", summary="Cough for 2 days", seriousness=6, created_at=utc(NOW - timedelta(hours=5)),
                   symptoms=[Symptom(name="Cough", severity=SymptomSeverity.moderate)])
    old = log.model_copy(update={"created_at": utc(NOW - timedelta(days=9)), "id": "old"})
    assert views.patient_home(data(logs=[log]), now=NOW).how_doing.band == "watch"
    assert views.patient_home(data(logs=[old]), now=NOW).how_doing is None


def test_checkin_knows_when_a_doctor_actually_joined():
    call = Call(patient_id="p", type=CallType.medicine_reminder, date_time=utc(NOW - timedelta(hours=3)),
                escalation_reason="Chest pain")
    ringing = Escalation(patient_id="p", call_id=call.id, reason="Chest pain", brief_summary="s", status=EscalationStatus.abandoned)
    merged = ringing.model_copy(update={"merged_at": utc(NOW), "status": EscalationStatus.resolved})
    assert views.patient_history(data(calls=[call], escalations=[ringing])).checkins[0].doctor_connected is False
    c = views.patient_history(data(calls=[call], escalations=[merged])).checkins[0]
    assert c.escalated and c.doctor_connected and c.escalation_reason == "Chest pain"


def test_medicines_split_current_from_finished_and_count_days_left():
    d = data()
    old = Dosage(prescription_id="rx", medicine_name="Amoxicillin", dosage="500 mg", from_date=TODAY - timedelta(days=30),
                 to_date=TODAY - timedelta(days=20), frequency=DoseFrequency.daily, times=["09:00"])
    d.dosages.append(old)
    meds = views.patient_medicines(d, now=NOW).medicines
    assert [(m.name, m.active) for m in meds] == [("Glimepiride", True), ("Amoxicillin", False)]
    assert meds[0].days_left == 20 and meds[0].times == ["08:30", "21:00"]


def test_clinical_view_flags_a_live_call_and_covers_two_weeks():
    live = Escalation(patient_id="p", call_id="c", reason="Chest pain", brief_summary="s", status=EscalationStatus.briefing)
    d = data(escalations=[live])
    import asyncio

    async def build():
        async def fake_load(_):
            return d
        original = views.load_patient
        views.load_patient = fake_load
        try:
            return await views.patient_clinical("p", {}, None, now=NOW)
        finally:
            views.load_patient = original

    clinical = asyncio.run(build())
    assert clinical.attention.level == "critical" and clinical.attention.reasons[0].startswith("On a live doctor call")
    assert len(clinical.days) == views.CLINICAL_DAYS


def test_transcript_keeps_staff_only_entries_distinguishable():
    call = Call(patient_id="p", type=CallType.medicine_reminder, logs=[
        CallLogEntry(type=CallLogEntryType.agent_said, content="Namaste"),
        CallLogEntry(type=CallLogEntryType.tool_call, tool_name="log_dose_event", tool_args={"status": "taken"}, tool_result={"ok": True}),
        CallLogEntry(type=CallLogEntryType.escalation_call_started, note="ringing Dr. Mehta"),
        CallLogEntry(type=CallLogEntryType.doctor_said, content="Hello", channel="doctor_briefing"),
    ])
    t = views.call_transcript(call, Patient(name="Sunita", age=72, phone_number="+911"))
    assert [e.kind for e in t.entries] == ["agent", "tool", "event", "doctor"]
    assert t.entries[1].tool_name == "log_dose_event"
    assert t.entries[2].text == "ringing Dr. Mehta"          # an event's wording comes from its note
    assert t.entries[3].leg == "doctor_briefing"
