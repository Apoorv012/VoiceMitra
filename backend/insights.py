"""Derived views of a patient's records, for the UI: today's dose schedule, how the last week went,
and whether a doctor should look at this patient now.

Everything stored is naive UTC; people see times in APP_TIMEZONE (default Asia/Kolkata). The raw
collections only say *what was reported*, so two things are decided here and nowhere else:

* A scheduled dose ("slot") is matched to the dose events recorded on that local day for that
  medicine. `DoseEvent.scheduled_at` is just the moment the agent logged it, not the slot, so an
  event goes to the nearest slot of the day and the latest event for a slot wins (a "not yet"
  followed by "taken" reads as taken).
* A dose nobody asked about is "no check-in", never "missed": absence of data is not a miss.
"""

from __future__ import annotations

import os
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from backend.models import (
    Call,
    DailyLog,
    Dosage,
    DoseEvent,
    DoseFrequency,
    DoseStatus,
    Escalation,
    EscalationStatus,
)

TZ = ZoneInfo(os.environ.get("APP_TIMEZONE", "Asia/Kolkata"))

# Slot states
TAKEN = "taken"
PARTIAL = "partial"
MISSED = "missed"
LATER = "later"            # said they'd take it later; a reminder was set
UNKNOWN = "unknown"        # asked, but the patient wasn't sure
SKIPPED = "skipped"        # skipped on a doctor's advice
UPCOMING = "upcoming"
DUE = "due"                # the time has come (within the last 2 hours) and nobody has asked yet
NO_CHECKIN = "no_checkin"  # time has passed and nothing was recorded

DUE_WINDOW = timedelta(hours=2)
LATER_WINDOW = timedelta(hours=3)


def to_local(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(TZ)


def now_local() -> datetime:
    return datetime.now(TZ)


# --- dose schedule -------------------------------------------------------------------------

@dataclass
class Slot:
    dosage: Dosage
    at: datetime                    # local, timezone-aware
    event: DoseEvent | None = None
    state: str = UPCOMING

    @property
    def day(self) -> date:
        return self.at.date()


def dosage_slots_on(dosage: Dosage, day: date) -> list[datetime]:
    """When `dosage` is due on `day` (empty if the prescription isn't active that day)."""
    if day < dosage.from_date or (dosage.to_date is not None and day > dosage.to_date):
        return []
    if dosage.frequency == DoseFrequency.weekly and (day - dosage.from_date).days % 7:
        return []
    # "every X days" has no interval stored, so it is treated as daily rather than guessed.
    slots = []
    for text in sorted(dosage.times or ["09:00"]):
        try:
            hour, minute = (int(part) for part in text.split(":")[:2])
            slots.append(datetime.combine(day, time(hour, minute), tzinfo=TZ))
        except ValueError:
            continue
    return slots


def _state(slot: Slot, now: datetime) -> str:
    ev = slot.event
    if ev is not None:
        if ev.status == DoseStatus.taken:
            return TAKEN
        if ev.status == DoseStatus.partial:
            return PARTIAL
        if ev.status == DoseStatus.unknown:
            return UNKNOWN
        if ev.status == DoseStatus.skipped_on_advice:
            return SKIPPED
        recent = now - to_local(ev.recorded_at) <= LATER_WINDOW
        if ev.note and ev.note.startswith("will take it later") and recent:
            return LATER
        return MISSED
    if slot.at > now:
        return UPCOMING
    return DUE if now - slot.at <= DUE_WINDOW else NO_CHECKIN


def build_slots(
    dosages: list[Dosage], events: list[DoseEvent], first: date, last: date, now: datetime | None = None,
) -> list[Slot]:
    """Every scheduled dose from `first` to `last` (inclusive, local dates), with what happened."""
    now = now or now_local()
    slots: list[Slot] = []
    for dosage in dosages:
        day = first
        while day <= last:
            slots.extend(Slot(dosage, at) for at in dosage_slots_on(dosage, day))
            day += timedelta(days=1)

    groups: dict[tuple[str, date], list[Slot]] = defaultdict(list)
    for slot in slots:
        groups[(slot.dosage.id, slot.day)].append(slot)
    for ev in sorted(events, key=lambda e: e.recorded_at):
        local = to_local(ev.recorded_at)
        group = groups.get((ev.dosage_id, local.date()))
        if group:
            min(group, key=lambda s: abs((s.at - local).total_seconds())).event = ev
    for slot in slots:
        slot.state = _state(slot, now)
    return sorted(slots, key=lambda s: s.at)


@dataclass
class Adherence:
    taken: int = 0
    missed: int = 0       # asked, and not taken (or only partly)
    unrecorded: int = 0   # time has passed but nobody asked / the patient wasn't sure
    total_past: int = 0

    @property
    def known(self) -> int:
        return self.taken + self.missed

    @property
    def rate(self) -> int | None:
        """Share of doses we actually heard about that were taken; None until we've heard about any."""
        return round(100 * self.taken / self.known) if self.known else None


def adherence(slots: list[Slot]) -> Adherence:
    result = Adherence()
    for s in slots:
        if s.state in (UPCOMING, DUE, LATER):
            continue
        result.total_past += 1
        if s.state == TAKEN:
            result.taken += 1
        elif s.state in (MISSED, PARTIAL):
            result.missed += 1
        elif s.state != SKIPPED:
            result.unrecorded += 1
    return result


# --- the week at a glance ------------------------------------------------------------------

DAY_GOOD = "good"         # every dose that is due has been taken
DAY_MIXED = "mixed"       # some taken, some missed / unconfirmed
DAY_MISSED = "missed"     # none taken, and at least one reported as missed
DAY_UNKNOWN = "unknown"   # nothing recorded
DAY_UPCOMING = "upcoming"
DAY_NONE = "none"         # no medicine scheduled


def day_state(slots: list[Slot]) -> str:
    if not slots:
        return DAY_NONE
    counted = [s for s in slots if s.state not in (UPCOMING, SKIPPED)]
    if not counted:
        return DAY_UPCOMING if any(s.state == UPCOMING for s in slots) else DAY_GOOD
    taken = sum(s.state == TAKEN for s in counted)
    if taken == len(counted):
        return DAY_GOOD
    if taken:
        return DAY_MIXED
    if any(s.state in (MISSED, PARTIAL) for s in counted):
        return DAY_MISSED
    return DAY_UNKNOWN


@dataclass
class DayCell:
    day: date
    state: str
    taken: int
    due: int          # doses that have come due (taken or not)
    slots: list[Slot] = field(default_factory=list)


def week_cells(slots: list[Slot], last: date, days: int = 7) -> list[DayCell]:
    by_day: dict[date, list[Slot]] = defaultdict(list)
    for s in slots:
        by_day[s.day].append(s)
    cells = []
    for offset in range(days - 1, -1, -1):
        day = last - timedelta(days=offset)
        todays = by_day.get(day, [])
        cells.append(DayCell(
            day=day, state=day_state(todays), slots=todays,
            taken=sum(s.state == TAKEN for s in todays),
            due=sum(s.state not in (UPCOMING,) for s in todays),
        ))
    return cells


# --- how the patient is doing ---------------------------------------------------------------

def seriousness_band(score: int) -> str:
    """1-4 fine, 5-7 worth a look, 8-10 needs attention -- the same bands the agent escalates on."""
    return "ok" if score <= 4 else "watch" if score <= 7 else "urgent"


@dataclass
class Attention:
    level: str                       # "critical" | "warning" | "ok"
    reasons: list[str] = field(default_factory=list)

    @property
    def needs_attention(self) -> bool:
        return self.level != "ok"


LIVE_ESCALATION = (EscalationStatus.ringing, EscalationStatus.briefing, EscalationStatus.merged)


def assess(
    *, slots: list[Slot], logs: list[DailyLog], escalations: list[Escalation], calls: list[Call],
    now: datetime | None = None,
) -> Attention:
    """Whether a doctor should look at this patient now, and why, in plain words. `logs` and
    `escalations` newest first."""
    now = now or now_local()
    critical: list[str] = []
    warning: list[str] = []

    if any(e.status in LIVE_ESCALATION for e in escalations):
        critical.append("On a live doctor call right now")

    recent_logs = [l for l in logs if now - to_local(l.created_at) <= timedelta(hours=72)]
    if recent_logs:
        worst = max(recent_logs, key=lambda l: l.seriousness)
        when = ago(worst.created_at, now)
        if worst.seriousness >= 8:
            critical.append(f"Serious symptoms reported {when}")
        elif worst.seriousness >= 5:
            warning.append(f"Symptoms reported {when}: {_clip(worst.summary)}")

    recent_esc = [e for e in escalations
                  if e.status not in LIVE_ESCALATION and now - to_local(e.created_at) <= timedelta(hours=48)]
    if recent_esc:
        warning.append(f"Escalated to a doctor {ago(recent_esc[0].created_at, now)}")

    last3 = [s for s in slots if now - s.at <= timedelta(days=3)]
    missed = sum(s.state in (MISSED, PARTIAL) for s in last3)
    if missed >= 2:
        warning.append(f"Missed {missed} doses in the last 3 days")
    week = adherence(slots)
    if week.known >= 4 and week.rate is not None and week.rate < 60 and not missed >= 2:
        warning.append(f"Only {week.rate}% of doses taken this week")

    if slots and not any(now - to_local(c.date_time) <= timedelta(days=3) for c in calls):
        warning.append("No check-in call in 3 days")

    if critical:
        return Attention("critical", critical + warning)
    if warning:
        return Attention("warning", warning)
    return Attention("ok")


# --- wording --------------------------------------------------------------------------------

def _clip(text: str, n: int = 80) -> str:
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def ago(dt: datetime, now: datetime | None = None) -> str:
    """English "5 min ago" style, for staff screens."""
    now = now or now_local()
    seconds = max(0, int((now - to_local(dt)).total_seconds()))
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        return f"{seconds // 60} min ago"
    if seconds < 86400:
        hours = seconds // 3600
        return f"{hours} h ago"
    days = seconds // 86400
    return "yesterday" if days == 1 else f"{days} days ago"
