from __future__ import annotations

from dataclasses import dataclass, field

from backend.models import DoseStatus
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

    def observe_user_text(self, text: str) -> None:
        if self.escalated or self.mentioned_red_flag:
            return
        flag = detect_red_flag(text)
        if flag:
            self.mentioned_red_flag = True
            self.red_flag_reason = flag
