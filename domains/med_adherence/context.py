from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from backend.models import CallLogEntry, CallLogEntryType, CareMode, DoseStatus, Reminder
from core.agent.context import AgentContext
from domains.med_adherence.escalation_rules import detect_red_flag
from domains.med_adherence.language import Language, detect_language
from domains.med_adherence.prompts import UNSUPPORTED_LANGUAGE_LINE


# Tools after which the policy moves to a terminal state: whatever the agent says next is the last
# thing the patient hears.
WRAP_UP_TOOLS = frozenset({"update_daily_log", "escalate_to_doctor", "alert_caregiver"})


@dataclass
class DueMedicine:
    """One medicine the call is asking about."""

    dosage_id: str
    name: str
    dose: str


@dataclass
class EscalationRequest:
    """What the agent decided to escalate, kept so the host can bring a doctor in once the
    patient has heard the hand-off line."""

    reason: str
    brief_summary: str
    urgency: str = "high"


@dataclass
class CaregiverAlert:
    """The caregiver was alerted (pilot mode) -- kept for the line the patient hears last."""

    reason: str
    urgent: bool
    caregiver_name: str | None  # None: no caregiver on file (or they opted out), nobody was told


@dataclass
class CallContext(AgentContext):
    patient_id: str
    call_id: str
    due: list[DueMedicine]
    slot_at: datetime  # the dose slot the call is about (naive UTC)
    allergies: list[str] = field(default_factory=list)
    # Who is brought in when the patient isn't well: the doctor (rung into the call) or, in the pilot,
    # the caregiver (alerted; the call then ends).
    care_mode: CareMode = CareMode.caregiver
    dose_statuses: dict[str, DoseStatus] = field(default_factory=dict)  # dosage_id -> what was logged
    mentioned_red_flag: bool = False
    red_flag_reason: str | None = None
    escalated: bool = False
    escalation: EscalationRequest | None = None
    caregiver_alert: CaregiverAlert | None = None
    closing_line_sent: bool = False  # the fixed line after escalating / alerting has been said
    wrapping_up: bool = False  # the call ends right after the next agent message
    patient_language: Language | None = None  # of their most recent message that could be told
    last_patient_text: str = ""  # their most recent message, for guardrails that check a quote
    log_entries: list[CallLogEntry] = field(default_factory=list)
    # Set by whoever hosts the call if it can act on reminders (arm a timer); left None otherwise,
    # in which case a requested reminder is only recorded.
    on_reminder_created: Callable[[Reminder], None] | None = None
    # Told about every log entry as it is recorded, so a live page can show the call as it happens.
    on_log_entry: Callable[[CallLogEntry], None] | None = None

    @property
    def escalation_tool(self) -> str:
        """The tool for "this needs someone": ring the doctor, or alert the caregiver."""
        return "escalate_to_doctor" if self.care_mode == CareMode.doctor else "alert_caregiver"

    @property
    def unanswered(self) -> list[DueMedicine]:
        return [m for m in self.due if m.dosage_id not in self.dose_statuses]

    @property
    def all_doses_answered(self) -> bool:
        return not self.unanswered

    def resolve_medicines(self, names: list[str]) -> list[DueMedicine]:
        """The due medicines a tool call names (exact names, case and spacing ignored); no names
        means every one still without an answer. Raises ValueError naming the valid choices."""
        if not names:
            return self.unanswered or list(self.due)
        # The prompt lists them as "Name (dose)", and the model often copies that whole.
        by_name = {_key(label): m for m in self.due for label in (m.name, f"{m.name} ({m.dose})")}
        found, unknown = [], []
        for name in names:
            med = by_name.get(_key(name))
            (found if med else unknown).append(med or name)
        if unknown:
            valid = ", ".join(m.name for m in self.due)
            raise ValueError(f"not a medicine due in this call: {', '.join(unknown)}. Use these names: {valid}")
        return _unique(found)

    def observe_user_text(self, text: str) -> None:
        self.last_patient_text = text
        self.patient_language = detect_language(text) or self.patient_language
        if self.escalated or self.mentioned_red_flag:
            return
        flag = detect_red_flag(text)
        if flag:
            self.mentioned_red_flag = True
            self.red_flag_reason = flag

    def prompt_suffix(self) -> str:
        # The model drifts back to the Hinglish it opened the call with even after being told to
        # follow the patient's language, so the decision is made here and stated flatly each turn.
        if self.patient_language == "english":
            return ("\n\n[This turn] The patient is writing in English. Reply in English only -- "
                    "no Hindi words.")
        if self.patient_language == "hindi":
            return ("\n\n[This turn] The patient is writing in Hindi/Hinglish. Reply in Roman-script "
                    "Hinglish.")
        if self.patient_language == "unsupported":
            return ("\n\n[This turn] The patient is writing in a language we don't support. Reply "
                    f"with exactly this and nothing else: {UNSUPPORTED_LANGUAGE_LINE}")
        return ""

    def hands_off_transport(self) -> bool:
        # An escalated patient isn't hung up on: they're held on the line while a doctor is brought in.
        return self.escalation is not None

    def _add(self, entry: CallLogEntry) -> None:
        self.log_entries.append(entry)
        if self.on_log_entry is not None:
            self.on_log_entry(entry)

    def record_user_text(self, text: str) -> None:
        self._add(CallLogEntry(type=CallLogEntryType.patient_said, content=text))

    def record_agent_text(self, text: str) -> None:
        self._add(CallLogEntry(type=CallLogEntryType.agent_said, content=text))

    def record_interruption(self, heard: str, unheard: str) -> None:
        self._add(CallLogEntry(
            type=CallLogEntryType.agent_said,
            content=f"[patient interrupted] heard only: {heard or '(nothing)'}",
            note=f"not heard: {unheard}",
        ))

    def record_tool_call(self, name: str, args: dict, result: Any, *, note: str | None = None) -> None:
        if name in WRAP_UP_TOOLS and not (isinstance(result, dict) and "error" in result):
            self.wrapping_up = True
        self._add(CallLogEntry(
            type=CallLogEntryType.tool_call,
            tool_name=name,
            tool_args=args,
            tool_result=result if isinstance(result, dict) else {"value": result},
            note=note,
        ))


def _key(label: str) -> str:
    return " ".join(label.lower().split())


def _unique(meds: list[DueMedicine]) -> list[DueMedicine]:
    seen: set[str] = set()
    out = []
    for m in meds:
        if m.dosage_id not in seen:
            seen.add(m.dosage_id)
            out.append(m)
    return out
