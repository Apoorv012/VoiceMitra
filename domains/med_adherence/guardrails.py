"""Concrete guardrail rules for the medicine-adherence agent. See core/agent/guardrails.py for
what each kind of check means; this module just supplies the domain-specific logic."""

from __future__ import annotations

from core.agent.guardrails import ForcedAction, GuardrailPipeline, GuardrailViolation
from domains.med_adherence.context import CallContext

DOSAGE_CHANGE_OR_DIAGNOSIS_PHRASES = [
    "dosage badha", "dosage kam", "dawai band kar do", "dawai badal do", "dose double",
    "increase the dose", "decrease the dose", "stop taking", "double the dose",
    "aapko ho sakta hai", "you might have", "this is likely",
]


def _no_dosage_change_or_diagnosis(text: str, context: CallContext) -> str:
    lowered = text.lower()
    for phrase in DOSAGE_CHANGE_OR_DIAGNOSIS_PHRASES:
        if phrase in lowered:
            raise GuardrailViolation(
                "I'm not able to advise on dosage changes or give a diagnosis myself -- "
                "I'll make sure the doctor knows."
            )
    return text


def _no_severe_symptom_without_escalation(tool_name: str, args: dict, context: CallContext) -> None:
    if tool_name != "update_daily_log":
        return
    for symptom in args.get("symptoms", []):
        if symptom.get("severity") == "severe":
            raise GuardrailViolation(
                "a 'severe' symptom can't be logged via update_daily_log -- call "
                "escalate_to_doctor instead"
            )


def _forced_escalation(context: CallContext) -> ForcedAction | None:
    if context.mentioned_red_flag and not context.escalated:
        return ForcedAction(
            tool_name="escalate_to_doctor",
            args={
                "reason": context.red_flag_reason or "red-flag symptom reported",
                "brief_summary": f"Patient reported: {context.red_flag_reason}",
                "urgency": "high",
            },
            reason=f"red-flag symptom detected ({context.red_flag_reason})",
        )
    return None


def build_guardrails() -> GuardrailPipeline:
    pipeline = GuardrailPipeline()
    pipeline.add_text_check(_no_dosage_change_or_diagnosis)
    pipeline.add_tool_call_check(_no_severe_symptom_without_escalation)
    pipeline.add_forced_action_check(_forced_escalation)
    return pipeline
