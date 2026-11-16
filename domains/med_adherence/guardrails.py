"""Concrete guardrail rules for the medicine-adherence agent. See core/agent/guardrails.py for
what each kind of check means; this module just supplies the domain-specific logic."""

from __future__ import annotations

import re

from pipecat_guardrails import Guard
from pipecat_guardrails.packs import india
from pipecat_guardrails.rules import BannedTerms

from core.agent.guardrails import ForcedAction, GuardrailPipeline, GuardrailViolation
from domains.med_adherence.context import CallContext
from backend.models import CareMode
from domains.med_adherence.prompts import HANDOFF_LINE_ENGLISH, HANDOFF_LINE_HINGLISH, caregiver_line

# update_daily_log seriousness (1-10, scored by the LLM): below OFFER_DOCTOR just log it; from there up
# to ESCALATE_AT the patient is asked whether they want the doctor; at ESCALATE_AT and above escalate.
# In caregiver mode (the pilot) there is no doctor to offer: from OFFER_DOCTOR up the caregiver is
# alerted (urgently from ESCALATE_AT, see tools.alert_caregiver).
OFFER_DOCTOR_AT_SERIOUSNESS = 5
ESCALATE_AT_SERIOUSNESS = 8

# What the agent says is checked by pipecat-guardrails' `BannedTerms`: whole-word, case-insensitive
# phrase matching. Roman Hindi phrases also use `india.hinglish_word_pattern`, so the usual spelling
# variants match too (dawai/davai/dawaai, chinta/cheenta, theek/thik). English phrases match as written.
# Whole words means "aaram kar" no longer matches inside "aaram kariye", so verb endings are listed
# in `variants` (each one gets the same spelling tolerance).
DOSAGE_CHANGE_OR_DIAGNOSIS_HINGLISH = [
    "dosage badha", "dosage kam", "dose badha", "dose kam", "dose double",
    "dawai band kar do", "dawai band karo", "dawai band kijiye", "dawai band kar dijiye",
    "dawai badal do", "dawai badliye", "dawai badal dijiye",
    "aapko ho sakta hai", "aap ko ho sakta hai",
]
DOSAGE_CHANGE_OR_DIAGNOSIS_ENGLISH = [
    "increase the dose", "decrease the dose", "double the dose", "stop taking",
    "you might have", "this is likely",
]

# The agent must not give advice or reassurance of any kind (for now). Deliberately narrow phrases:
# anything common in ordinary polite speech would cause false blocks.
ADVICE_OR_REASSURANCE_HINGLISH = [
    "aaram kar", "rest kar", "paani pi", "aap ko chahiye", "aapko chahiye", "meri salah", "meri rai",
    "theek ho jayega", "chinta mat", "chinta ki koi baat nahi", "ghabraiye mat", "ghabrao mat",
]
ADVICE_OR_REASSURANCE_ENGLISH = [
    "take rest", "get some rest", "get rest", "drink water", "drink plenty", "you should",
    "i suggest", "i recommend", "everything will be fine", "will be fine", "don't worry",
    "do not worry",
]

_HINGLISH_ENDINGS = {
    "kar": ["karo", "kariye", "kijiye", "karein", "karen", "karna", "karte", "kar lijiye"],
    "pi": ["piyo", "pijiye", "piye", "pina", "pite", "pi lijiye"],
    "badha": ["badhao", "badhaiye", "badhana", "badha do", "badha dijiye"],
    "jayega": ["jaega", "jayegi", "jaegi", "jaoge", "jayenge", "jaenge", "jaayega"],
}
_ENGLISH_ENDINGS = {"dose": ["dosage"]}

_DOSAGE_MESSAGE = (
    "I'm not able to advise on dosage changes or give a diagnosis myself -- I'll make sure the doctor knows."
)
_ADVICE_MESSAGE = "I'm not able to give advice or reassurance -- please ask your doctor about that."


def dosage_or_diagnosis_rules() -> list:
    """Shared with the doctor-brief agent (doctor_agent.py), which must not suggest these either."""
    return [
        BannedTerms(DOSAGE_CHANGE_OR_DIAGNOSIS_HINGLISH, id="dosage-or-diagnosis-hinglish",
                    word_pattern=india.hinglish_word_pattern, variants=_HINGLISH_ENDINGS),
        BannedTerms(DOSAGE_CHANGE_OR_DIAGNOSIS_ENGLISH, id="dosage-or-diagnosis-english",
                    variants=_ENGLISH_ENDINGS),
    ]


def _advice_or_reassurance_rules() -> list:
    return [
        BannedTerms(ADVICE_OR_REASSURANCE_HINGLISH, id="advice-or-reassurance-hinglish",
                    word_pattern=india.hinglish_word_pattern, variants=_HINGLISH_ENDINGS),
        BannedTerms(ADVICE_OR_REASSURANCE_ENGLISH, id="advice-or-reassurance-english"),
    ]


# Rules only (no classifier/judge): local and instant, so no extra delay before the agent speaks.
# No fallback: a blocked reply goes back to the LLM to be regenerated (core/agent/runtime.py).
_PATIENT_GUARD = Guard(rules=[*dosage_or_diagnosis_rules(), *_advice_or_reassurance_rules()])


def _fixed_closing_line(text: str, context: CallContext) -> str:
    """The first thing said after escalating (doctor hand-off) or alerting the caregiver is always a
    fixed line, whatever the model wrote."""
    if context.closing_line_sent:
        return text
    english = context.patient_language == "english"
    if context.escalation is not None:
        context.closing_line_sent = True
        return HANDOFF_LINE_ENGLISH if english else HANDOFF_LINE_HINGLISH
    alert = context.caregiver_alert
    if alert is not None:
        context.closing_line_sent = True
        return caregiver_line(english=english, caregiver_name=alert.caregiver_name, urgent=alert.urgent)
    return text


async def _no_dosage_change_or_diagnosis(text: str, context: CallContext) -> str:
    verdict = await _PATIENT_GUARD.check(text)
    if verdict.blocked:
        dosage = any(r.startswith("dosage-or-diagnosis") for r in verdict.rule_ids)
        raise GuardrailViolation(_DOSAGE_MESSAGE if dosage else _ADVICE_MESSAGE)
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
                f"{context.escalation_tool} instead"
            )


def _words(text: str) -> str:
    return " ".join(re.sub(r"\W+", " ", text.casefold()).split())


def _serious_needs_escalation(tool_name: str, args: dict, context: CallContext) -> None:
    """Three tiers on the LLM's own seriousness score: low is just logged, high is escalated, and in
    between the patient is asked and only their refusal lets it be logged."""
    if tool_name != "update_daily_log":
        return
    score = args.get("seriousness")
    if not isinstance(score, int) or score < OFFER_DOCTOR_AT_SERIOUSNESS:
        return
    if context.care_mode == CareMode.caregiver:
        raise GuardrailViolation(
            f"seriousness {score} is {OFFER_DOCTOR_AT_SERIOUSNESS} or above, so it can't just be "
            "logged -- call alert_caregiver instead (same details)"
        )
    if score >= ESCALATE_AT_SERIOUSNESS:
        raise GuardrailViolation(
            f"seriousness {score} is {ESCALATE_AT_SERIOUSNESS} or above, so it can't just be logged "
            "-- call escalate_to_doctor instead"
        )
    quote = _words(args.get("patient_declined_doctor_quote") or "")
    if not quote or quote not in _words(context.last_patient_text):
        raise GuardrailViolation(
            f"seriousness {score} is moderate: don't log it yet. Ask the patient, in one short "
            "sentence and nothing else, whether they'd like to speak to the doctor now. If they say "
            "yes, call escalate_to_doctor. If they decline, call update_daily_log again with "
            "patient_declined_doctor_quote set to their exact words from that reply."
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
    # An urgent alert isn't held up to ask "since when".
    urgent_alert = tool_name == "alert_caregiver" and (args.get("seriousness") or 0) >= ESCALATE_AT_SERIOUSNESS
    if tool_name not in ("update_daily_log", "alert_caregiver") or urgent_alert:
        return
    for symptom in args.get("symptoms", []):
        if not (symptom.get("duration_note") or "").strip():
            raise GuardrailViolation(
                f"symptom '{symptom.get('name')}' has no duration_note -- ask the patient since "
                "when they've had it (or record that they don't know), then log it"
            )


def _forced_escalation(context: CallContext) -> ForcedAction | None:
    if not context.mentioned_red_flag or context.escalated or context.caregiver_alert is not None:
        return None
    reason = context.red_flag_reason or "red-flag symptom reported"
    if context.care_mode == CareMode.caregiver:
        return ForcedAction(
            tool_name="alert_caregiver",
            args={"reason": reason, "summary": f"Patient reported: {reason}", "seriousness": 9},
            reason=f"red-flag symptom detected ({reason})",
        )
    return ForcedAction(
        tool_name="escalate_to_doctor",
        args={"reason": reason, "brief_summary": f"Patient reported: {reason}", "urgency": "high"},
        reason=f"red-flag symptom detected ({reason})",
    )


def build_guardrails() -> GuardrailPipeline:
    pipeline = GuardrailPipeline()
    pipeline.add_text_check(_fixed_closing_line)
    pipeline.add_text_check(_no_dosage_change_or_diagnosis)
    pipeline.add_text_check(_no_question_when_wrapping_up)
    pipeline.add_tool_call_check(_no_severe_symptom_without_escalation)
    pipeline.add_tool_call_check(_serious_needs_escalation)
    pipeline.add_tool_call_check(_missed_dose_needs_reason)
    pipeline.add_tool_call_check(_symptom_needs_duration)
    pipeline.add_forced_action_check(_forced_escalation)
    return pipeline
