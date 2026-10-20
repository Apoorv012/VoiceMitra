from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from backend import insights as ins
from backend.models import (
    Call, CallType, DailyLog, Dosage, DoseConfidence, DoseEvent, DoseFrequency, DoseSource,
    DoseStatus, Escalation, EscalationStatus,
)

DAY = date(2026, 10, 20)


def local(h: int, m: int = 0, day: date = DAY) -> datetime:
    return datetime(day.year, day.month, day.day, h, m, tzinfo=ins.TZ)


def utc(dt: datetime) -> datetime:
    """How events are stored: naive UTC."""
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def dosage(times=("09:00", "21:00"), frequency=DoseFrequency.fixed_times, start=DAY, end=None) -> Dosage:
    return Dosage(prescription_id="rx", medicine_name="PCM 500", dosage="1 tablet",
                  from_date=start, to_date=end, frequency=frequency, times=list(times))


def event(d: Dosage, status: DoseStatus, at: datetime, note: str | None = None) -> DoseEvent:
    return DoseEvent(patient_id="p", dosage_id=d.id, scheduled_at=utc(at), status=status,
                     confidence=DoseConfidence.high, source=DoseSource.patient_self_report,
                     recorded_at=utc(at), note=note)


def test_slots_follow_dates_and_weekly_frequency():
    d = dosage(end=DAY + timedelta(days=2))
    assert len(ins.dosage_slots_on(d, DAY)) == 2
    assert ins.dosage_slots_on(d, DAY - timedelta(days=1)) == []
    assert ins.dosage_slots_on(d, DAY + timedelta(days=3)) == []
    w = dosage(frequency=DoseFrequency.weekly, times=("08:00",))
    assert len(ins.dosage_slots_on(w, DAY)) == 1
    assert ins.dosage_slots_on(w, DAY + timedelta(days=3)) == []
    assert len(ins.dosage_slots_on(w, DAY + timedelta(days=7))) == 1


def test_event_goes_to_the_nearest_slot_and_latest_wins():
    d = dosage()
    evs = [
        event(d, DoseStatus.not_taken, local(9, 20), note="will take it later; reminder in 60 min"),
        event(d, DoseStatus.taken, local(10, 30)),
        event(d, DoseStatus.not_taken, local(21, 40), note="forgot"),
    ]
    slots = ins.build_slots([d], evs, DAY, DAY, now=local(22, 30))
    assert [s.state for s in slots] == [ins.TAKEN, ins.MISSED]


def test_unrecorded_doses_are_not_called_missed():
    d = dosage()
    slots = ins.build_slots([d], [], DAY, DAY, now=local(23, 30))
    assert [s.state for s in slots] == [ins.NO_CHECKIN, ins.NO_CHECKIN]
    assert ins.adherence(slots).rate is None
    soon = ins.build_slots([d], [], DAY, DAY, now=local(10))
    assert [s.state for s in soon] == [ins.DUE, ins.UPCOMING]


def test_took_it_later_reminder_reads_as_later_then_missed():
    d = dosage(times=("09:00",))
    ev = event(d, DoseStatus.not_taken, local(9, 10), note="will take it later; reminder in 30 min")
    assert ins.build_slots([d], [ev], DAY, DAY, now=local(10))[0].state == ins.LATER
    assert ins.build_slots([d], [ev], DAY, DAY, now=local(14))[0].state == ins.MISSED


def test_adherence_rate_counts_only_doses_we_heard_about():
    d = dosage(times=("09:00",))
    days = [DAY - timedelta(days=n) for n in range(4)]
    evs = [event(d, DoseStatus.taken, local(9, 5, days[0])),
           event(d, DoseStatus.taken, local(9, 5, days[1])),
           event(d, DoseStatus.not_taken, local(9, 5, days[2]), note="forgot")]
    d.from_date = days[-1]
    slots = ins.build_slots([d], evs, days[-1], DAY, now=local(23))
    a = ins.adherence(slots)
    assert (a.taken, a.missed, a.unrecorded, a.rate) == (2, 1, 1, 67)


def test_week_cells_and_day_states():
    d = dosage()
    evs = [event(d, DoseStatus.taken, local(9, 5)), event(d, DoseStatus.taken, local(21, 5))]
    slots = ins.build_slots([d], evs, DAY - timedelta(days=1), DAY, now=local(22))
    cells = ins.week_cells(slots, DAY, days=3)
    # the prescription starts today, so the two days before it have nothing scheduled
    assert [c.state for c in cells] == [ins.DAY_NONE, ins.DAY_NONE, ins.DAY_GOOD]
    assert (cells[-1].taken, cells[-1].due) == (2, 2)


def test_attention_flags_live_calls_symptoms_and_missed_doses():
    d = dosage()
    now = local(12)
    quiet = ins.assess(slots=[], logs=[], escalations=[], calls=[], now=now)
    assert quiet.level == "ok"

    live = Escalation(patient_id="p", call_id="c", reason="r", brief_summary="s",
                      status=EscalationStatus.briefing)
    assert ins.assess(slots=[], logs=[], escalations=[live], calls=[], now=now).level == "critical"

    log = DailyLog(patient_id="p", call_id="c", summary="Bahut khansi and fever for 2 days",
                   seriousness=6, created_at=utc(now - timedelta(hours=5)))
    a = ins.assess(slots=[], logs=[log], escalations=[], calls=[], now=now)
    assert a.level == "warning" and "Symptoms reported 5 h ago" in a.reasons[0]

    severe = log.model_copy(update={"seriousness": 9})
    assert ins.assess(slots=[], logs=[severe], escalations=[], calls=[], now=now).level == "critical"

    yesterday = DAY - timedelta(days=1)
    evs = [event(d, DoseStatus.not_taken, local(9, 5, yesterday), note="forgot"),
           event(d, DoseStatus.not_taken, local(21, 5, yesterday), note="forgot")]
    d.from_date = yesterday
    slots = ins.build_slots([d], evs, yesterday, DAY, now=now)
    call = Call(patient_id="p", type=CallType.medicine_reminder, date_time=utc(now - timedelta(hours=3)))
    a = ins.assess(slots=slots, logs=[], escalations=[], calls=[call], now=now)
    assert a.level == "warning" and any("Missed 2 doses" in r for r in a.reasons)
