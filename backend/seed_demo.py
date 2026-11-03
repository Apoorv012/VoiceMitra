"""Realistic demo data: a doctor with five patients in very different situations, two weeks of history,
transcripts and one resolved emergency -- enough to see (and demo) every state the screens show.

    MONGODB_DB_NAME=voicemitra_demo python -m backend.seed_demo

WIPES the database it points at, so it refuses to run against the default `voicemitra` database (where
real test calls live) unless the name contains "demo". Point the backend at the same name to see it:
    MONGODB_DB_NAME=voicemitra_demo uvicorn backend.main:app
"""

from __future__ import annotations

import asyncio
import os
import random
import sys
from datetime import date, datetime, time, timedelta, timezone

from dotenv import load_dotenv

load_dotenv()

from backend import db  # noqa: E402
from backend.insights import TZ  # noqa: E402
from backend.models import (  # noqa: E402
    Call, CallLogEntry, CallLogEntryType, CallType, Caregiver, CaregiverNotification, CaregiverNotifyOn,
    DailyLog, Doctor, Dosage, DoseConfidence, DoseEvent, DoseFrequency, DoseSource, DoseStatus,
    Escalation, EscalationStatus, MedicineStatus, Patient, PatientStatus, Prescription, Symptom,
    SymptomSeverity,
)

DAYS = 14
rng = random.Random(7)  # same demo every time


def utc(day: date, hour: int, minute: int = 0) -> datetime:
    """A local wall-clock time as the naive UTC the database stores."""
    return datetime.combine(day, time(hour, minute), tzinfo=TZ).astimezone(timezone.utc).replace(tzinfo=None)


def hours_ago(hours: float) -> datetime:
    return datetime.utcnow() - timedelta(hours=hours)


def entry(kind: CallLogEntryType, when: datetime, text: str | None = None, **kw) -> CallLogEntry:
    return CallLogEntry(type=kind, timestamp=when, content=text, **kw)


def chat(when: datetime, patient: str, took: bool | None) -> list[CallLogEntry]:
    """A short, believable check-in transcript."""
    said = {True: "Haan ji, le li.", False: "Nahi, bhool gaya.", None: "Pata nahi, yaad nahi aa raha."}[took]
    status = {True: "taken", False: "not_taken", None: "unknown"}[took]
    t = when
    return [
        entry(CallLogEntryType.agent_said, t, f"Namaste, kya main {patient} ji se baat kar rahi hoon?"),
        entry(CallLogEntryType.patient_said, t + timedelta(seconds=9), "Haan ji, boliye."),
        entry(CallLogEntryType.agent_said, t + timedelta(seconds=14), "Achha. Kya aapne subah ki dawai li?"),
        entry(CallLogEntryType.patient_said, t + timedelta(seconds=24), said),
        entry(CallLogEntryType.tool_call, t + timedelta(seconds=30), tool_name="log_dose_event",
              tool_args={"status": status, "confidence": "high"}, tool_result={"ok": True}),
        entry(CallLogEntryType.agent_said, t + timedelta(seconds=36), "Theek hai, dhanyawad. Apna dhyan rakhiyega."),
    ]


PATIENTS = [
    dict(name="Ramesh Sharma", age=67, phone="+919810000001", address="Rohini, Delhi", allergies=["Penicillin"],
         about="Hypertension, on treatment for 6 years.", caregiver=("Anita Sharma", "wife"),
         meds=[("Amlodipine", "5 mg, 1 tablet", ["09:00"]), ("Metformin", "500 mg, 1 tablet", ["09:00", "21:00"])],
         p=lambda d: 0.93, symptoms={9: (3, "Mild headache in the morning, gone by afternoon.", [("Headache", "head", "mild", "since morning")])}),
    dict(name="Sunita Verma", age=72, phone="+919810000002", address="Dwarka, Delhi", allergies=[],
         about="Type 2 diabetes. Lives alone; daughter checks in by phone.", caregiver=("Neha Verma", "daughter"),
         meds=[("Glimepiride", "2 mg, 1 tablet", ["08:30"]), ("Atorvastatin", "10 mg, 1 tablet", ["21:00"])],
         p=lambda d: 0.9 if d > 5 else 0.5,
         symptoms={1: (6, "Cough and mild fever for 2 days; feeling weak and not eating well.",
                       [("Cough", "chest", "moderate", "2 days"), ("Fever", None, "moderate", "2 days")])}),
    dict(name="Apoorv", age=21, phone="+919810000003", address="Delhi", allergies=[],
         about="No known chronic conditions.", caregiver=("Rakesh", "father"),
         meds=[("PCM 500", "1 tablet", ["09:00", "21:00"])], p=lambda d: 0.85, symptoms={}),
    dict(name="Mohan Lal", age=80, phone="+919810000004", address="Karol Bagh, Delhi", allergies=["Sulfa drugs", "Aspirin"],
         about="Heart failure, on diuretics. High risk.", caregiver=("Vikas Lal", "son"),
         meds=[("Furosemide", "40 mg, 1 tablet", ["08:00"]), ("Ramipril", "5 mg, 1 tablet", ["08:00", "20:00"])],
         p=lambda d: 0.75, symptoms={0: (9, "Chest pain and breathlessness since this morning.",
                                         [("Chest pain", "chest", "severe", "since morning"), ("Breathlessness", None, "severe", "since morning")])}),
    dict(name="Kavita Joshi", age=58, phone="+919810000005", address="Saket, Delhi", allergies=[],
         about="Newly registered.", caregiver=None, meds=[], p=lambda d: 0, symptoms={}),
]


async def seed() -> None:
    name = os.environ.get("MONGODB_DB_NAME", "voicemitra")
    if "demo" not in name and "--force" not in sys.argv:
        raise SystemExit(f"Refusing to wipe database '{name}'. Use MONGODB_DB_NAME=voicemitra_demo "
                         "(or pass --force if you really mean it).")
    await db.ensure_indexes()
    for col in (db.patients_col, db.caregivers_col, db.prescriptions_col, db.dose_events_col, db.doctors_col,
                db.calls_col, db.daily_logs_col, db.escalations_col, db.reminders_col,
                db.caregiver_notifications_col):
        await col().delete_many({})

    doctor = Doctor(name="Dr. Mehta", age=45, description="General physician · Apollo Clinic, Delhi",
                    phone_number="+919800000001", address="Apollo Clinic, Delhi")
    today = datetime.now(TZ).date()

    for cfg in PATIENTS:
        patient = Patient(name=cfg["name"], age=cfg["age"], phone_number=cfg["phone"], address=cfg["address"],
                          allergies=cfg["allergies"], description=cfg["about"])
        caregiver = None
        if cfg["caregiver"]:
            caregiver = Caregiver(patient_id=patient.id, name=cfg["caregiver"][0], relation=cfg["caregiver"][1],
                                  phone_number="+919820000000")
            patient.caregiver_id = caregiver.id
            await db.caregivers_col().insert_one(db.model_to_doc(caregiver))

        rx = Prescription(patient_id=patient.id)
        started = today - timedelta(days=DAYS + 3)
        for med, dose, times in cfg["meds"]:
            rx.medicines.append(Dosage(
                prescription_id=rx.id, medicine_name=med, dosage=dose, from_date=started,
                to_date=today + timedelta(days=30), frequency=DoseFrequency.fixed_times, times=times))
        if cfg["meds"]:
            patient.prescription_ids.append(rx.id)
            await db.prescriptions_col().insert_one(db.model_to_doc(rx))

        now = datetime.utcnow()
        for ago in range(DAYS - 1, -1, -1):
            day = today - timedelta(days=ago)
            if not cfg["meds"]:
                break
            took_first: bool | None = None
            call = Call(patient_id=patient.id, date_time=utc(day, 9, 5), type=CallType.medicine_reminder,
                        doctor_id=doctor.id)
            events = []
            for dosage in rx.medicines:
                for t in dosage.times:
                    hh, mm = (int(x) for x in t.split(":"))
                    slot = utc(day, hh, mm)
                    if slot + timedelta(minutes=40) > now:
                        continue  # hasn't happened yet
                    took = rng.random() < cfg["p"](ago)
                    took_first = took if took_first is None else took_first
                    events.append(DoseEvent(
                        patient_id=patient.id, dosage_id=dosage.id, scheduled_at=slot + timedelta(minutes=5),
                        recorded_at=slot + timedelta(minutes=5),
                        status=DoseStatus.taken if took else DoseStatus.not_taken,
                        confidence=DoseConfidence.high, source=DoseSource.patient_self_report,
                        note=None if took else rng.choice(["forgot", "was out of the house", "felt nauseous"]),
                        recorded_via_call_id=call.id))
            sym = cfg["symptoms"].get(ago)
            if not events and not sym:
                continue  # nothing was asked and nothing was reported that day
            if events:
                call.date_time = events[0].recorded_at
                call.medicine_status = MedicineStatus.taken if took_first else MedicineStatus.not_taken
            else:
                call.date_time = hours_ago(3)  # a symptom call before any dose came due
            call.patient_status = PatientStatus.good
            call.logs = chat(call.date_time, cfg["name"].split()[0], took_first)
            if sym:
                score, summary, syms = sym
                log_at = call.date_time + timedelta(minutes=2) if ago else hours_ago(3)
                if ago == 0:
                    call.date_time = log_at - timedelta(minutes=3)
                call.patient_status = PatientStatus.urgent if score >= 8 else PatientStatus.remedy
                await db.daily_logs_col().insert_one(db.model_to_doc(DailyLog(
                    patient_id=patient.id, call_id=call.id, summary=summary, seriousness=score, created_at=log_at,
                    symptoms=[Symptom(name=n, location=loc, severity=SymptomSeverity(sev), duration_note=dur)
                              for n, loc, sev, dur in syms])))
                if score >= 8:
                    await escalate(patient, doctor, call, summary, log_at, caregiver)
            if events:
                await db.dose_events_col().insert_many([db.model_to_doc(e) for e in events])
            await db.calls_col().insert_one(db.model_to_doc(call))

        await db.patients_col().insert_one(db.model_to_doc(patient))
        doctor.patient_ids.append(patient.id)
        print(f"seeded {patient.name} ({patient.id})")

    await db.doctors_col().insert_one(db.model_to_doc(doctor))
    print(f"seeded {doctor.name} ({doctor.id}) in database '{name}'")


async def escalate(patient: Patient, doctor: Doctor, call: Call, reason: str, at: datetime, caregiver) -> None:
    """A resolved emergency: the agent escalated, the doctor was briefed, merged, and a summary written."""
    esc = Escalation(
        patient_id=patient.id, call_id=call.id, reason=reason, urgency="high", doctor_ids=[doctor.id],
        doctor_id=doctor.id, status=EscalationStatus.resolved, created_at=at, joined_at=at + timedelta(minutes=1),
        merged_at=at + timedelta(minutes=3), ended_at=at + timedelta(minutes=9),
        brief_summary=f"{patient.name}, {patient.age}: {reason} Known allergies: {', '.join(patient.allergies) or 'none'}.",
        summary=("Doctor spoke with the patient for about 6 minutes.\nPatient reported chest tightness since morning, "
                 "worse on walking.\nDoctor advised going to the nearest emergency room now; family informed."))
    t = at
    call.escalation_reason = reason
    call.caregiver_notified = caregiver is not None
    call.logs += [
        entry(CallLogEntryType.escalation_call_started, t, note=f"ringing {doctor.name}"),
        entry(CallLogEntryType.agent_said, t + timedelta(seconds=70),
              f"Dr. Mehta, {patient.name} ji (80) reported chest pain and breathlessness. Allergies: sulfa, aspirin. "
              "Should I merge you in?", channel="doctor_briefing"),
        entry(CallLogEntryType.doctor_said, t + timedelta(seconds=95), "Yes, merge me in.", channel="doctor_briefing"),
        entry(CallLogEntryType.escalation_call_merged, t + timedelta(minutes=3), note=f"{doctor.name} merged into the patient's call"),
        entry(CallLogEntryType.doctor_said, t + timedelta(minutes=3, seconds=10), "Namaste, tell me where it hurts.", channel="merged"),
        entry(CallLogEntryType.patient_said, t + timedelta(minutes=3, seconds=25), "Seene mein dard hai, saans phool rahi hai.", channel="merged"),
        entry(CallLogEntryType.escalation_summary, t + timedelta(minutes=9), esc.summary, note="ended by doctor", channel="merged"),
    ]
    await db.escalations_col().insert_one(db.model_to_doc(esc))
    if caregiver:
        await db.caregiver_notifications_col().insert_one(db.model_to_doc(CaregiverNotification(
            patient_id=patient.id, caregiver_id=caregiver.id, call_id=call.id, trigger=CaregiverNotifyOn.escalation,
            created_at=at + timedelta(minutes=9),
            message=f"{patient.name} reported {reason.lower()} The doctor was connected and advised urgent care.")))


if __name__ == "__main__":
    asyncio.run(seed())
