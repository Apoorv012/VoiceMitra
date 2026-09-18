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

# The agent must not give advice or reassurance of any kind (for now). Deliberately narrow phrases:
# a substring match, so anything common in ordinary polite speech would cause false blocks.
ADVICE_OR_REASSURANCE_PHRASES = [
    "aaram kar", "rest kar", "take rest", "get some rest", "get rest",
    "paani pi", "drink water", "drink plenty", "you should", "i suggest", "i recommend",
    "aap ko chahiye", "aapko chahiye", "meri salah", "meri rai",
    "sab theek ho jayega", "sab theek ho jaega", "theek ho jayega", "everything will be fine",
    "will be fine", "don't worry", "do not worry", "chinta mat", "chinta ki koi baat nahi",
    "ghabraiye mat", "ghabrao mat",
]


def _no_dosage_change_or_diagnosis(text: str, context: CallContext) -> str:
    lowered = text.lower()
    for phrase in DOSAGE_CHANGE_OR_DIAGNOSIS_PHRASES:
        if phrase in lowered:
            raise GuardrailViolation(
                "I'm not able to advise on dosage changes or give a diagnosis myself -- "
                "I'll make sure the doctor knows."
            )
    for phrase in ADVICE_OR_REASSURANCE_PHRASES:
        if phrase in lowered:
            raise GuardrailViolation(
                "I'm not able to give advice or reassurance -- please ask your doctor about that."
            )
    return text


def _no_question_when_wrapping_up(text: str, context: CallContext) -> str:
    # The call hangs up right after this message, so a question would go unanswered.
    if context.wrapping_up and "?" in text:
        raise GuardrailViolation(
            "the call ends right after this message, so it can't contain a question -- sign off "
            "without asking anything",
            fallback_text=(
                "Thank you, take care. Goodbye!" if context.patient_language == "english"
                else "Dhanyawad, apna dhyan rakhiyega. Namaste!"
            ),
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


def _missed_dose_needs_reason(tool_name: str, args: dict, context: CallContext) -> None:
    if tool_name != "log_dose_event" or args.get("status") != "not_taken":
        return
    if not (args.get("note") or "").strip():
        raise GuardrailViolation(
            "a missed dose can't be logged without the reason in `note` -- ask the patient why "
            "they didn't take it (or when they plan to), then log it"
        )


def _symptom_needs_duration(tool_name: str, args: dict, context: CallContext) -> None:
    if tool_name != "update_daily_log":
        return
    for symptom in args.get("symptoms", []):
        if not (symptom.get("duration_note") or "").strip():
            raise GuardrailViolation(
                f"symptom '{symptom.get('name')}' has no duration_note -- ask the patient since "
                "when they've had it (or record that they don't know), then log it"
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
    pipeline.add_text_check(_no_question_when_wrapping_up)
    pipeline.add_tool_call_check(_no_severe_symptom_without_escalation)
    pipeline.add_tool_call_check(_missed_dose_needs_reason)
    pipeline.add_tool_call_check(_symptom_needs_duration)
    pipeline.add_forced_action_check(_forced_escalation)
    return pipeline
