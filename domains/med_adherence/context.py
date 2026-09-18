from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from backend.models import CallLogEntry, CallLogEntryType, DoseStatus, Reminder
from core.agent.context import AgentContext
from domains.med_adherence.escalation_rules import detect_red_flag
from domains.med_adherence.language import Language, detect_language
from domains.med_adherence.prompts import UNSUPPORTED_LANGUAGE_LINE


# Tools after which the policy moves to a terminal state: whatever the agent says next is the last
# thing the patient hears.
WRAP_UP_TOOLS = frozenset({"update_daily_log", "escalate_to_doctor"})


@dataclass
class CallContext(AgentContext):
    patient_id: str
    call_id: str
    dosage_id: str
    medicine_name: str
    medicine_dosage: str
    allergies: list[str] = field(default_factory=list)
    dose_status: DoseStatus | None = None
    mentioned_red_flag: bool = False
    red_flag_reason: str | None = None
    escalated: bool = False
    wrapping_up: bool = False  # the call ends right after the next agent message
    patient_language: Language | None = None  # of their most recent message that could be told
    log_entries: list[CallLogEntry] = field(default_factory=list)
    # Set by whoever hosts the call if it can act on reminders (arm a timer); left None otherwise,
    # in which case a requested reminder is only recorded.
    on_reminder_created: Callable[[Reminder], None] | None = None

    def observe_user_text(self, text: str) -> None:
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

    def record_user_text(self, text: str) -> None:
        self.log_entries.append(CallLogEntry(type=CallLogEntryType.patient_said, content=text))

    def record_agent_text(self, text: str) -> None:
        self.log_entries.append(CallLogEntry(type=CallLogEntryType.agent_said, content=text))

    def record_tool_call(self, name: str, args: dict, result: Any, *, note: str | None = None) -> None:
        if name in WRAP_UP_TOOLS and not (isinstance(result, dict) and "error" in result):
            self.wrapping_up = True
        self.log_entries.append(CallLogEntry(
            type=CallLogEntryType.tool_call,
            tool_name=name,
            tool_args=args,
            tool_result=result if isinstance(result, dict) else {"value": result},
            note=note,
        ))
