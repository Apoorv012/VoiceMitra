from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.models import CallLogEntry, CallLogEntryType, DoseStatus
from core.agent.context import AgentContext
from domains.med_adherence.escalation_rules import detect_red_flag


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
    log_entries: list[CallLogEntry] = field(default_factory=list)

    def observe_user_text(self, text: str) -> None:
        if self.escalated or self.mentioned_red_flag:
            return
        flag = detect_red_flag(text)
        if flag:
            self.mentioned_red_flag = True
            self.red_flag_reason = flag

    def record_user_text(self, text: str) -> None:
        self.log_entries.append(CallLogEntry(type=CallLogEntryType.patient_said, content=text))

    def record_agent_text(self, text: str) -> None:
        self.log_entries.append(CallLogEntry(type=CallLogEntryType.agent_said, content=text))

    def record_tool_call(self, name: str, args: dict, result: Any, *, note: str | None = None) -> None:
        self.log_entries.append(CallLogEntry(
            type=CallLogEntryType.tool_call,
            tool_name=name,
            tool_args=args,
            tool_result=result if isinstance(result, dict) else {"value": result},
            note=note,
        ))
