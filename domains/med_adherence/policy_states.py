"""Concrete dialogue policy for the medicine-adherence agent.

dosage_check (start)
  -> log_dose_event / reschedule_dose (patient will take it later), once every medicine due in
     the call has an answer -> symptom_check (until then it stays in dosage_check)
symptom_check
  -> update_daily_log (nothing concerning)   -> closing_normal (terminal)
  doctor mode:
  -> escalate_to_doctor (concerning symptom) -> escalation_active (terminal; the doctor is rung)
  caregiver mode (the pilot -- no doctor takes the calls):
  -> alert_caregiver (not well, 5+)          -> caregiver_alerted (terminal; the call ends)

escalation_active is terminal itself, with no tools allowed, rather than routing through an
end_call tool call -- a function-calling LLM generally can't both speak text and call a tool in
the same turn (a response with tool_calls usually carries no content), so making the hand-off
state's *only* job "say this one line" (forced to plain text by having zero allowed tools) is what
actually gets that line spoken, instead of the model silently calling a transition tool and never
producing the sentence it was supposed to say first.
"""

from __future__ import annotations

from typing import Any

from backend.models import CareMode
from core.agent.policy import PolicyEngine, PolicyState

DOSAGE_CHECK = "dosage_check"
SYMPTOM_CHECK = "symptom_check"
ESCALATION_ACTIVE = "escalation_active"
CAREGIVER_ALERTED = "caregiver_alerted"
CLOSING_NORMAL = "closing_normal"


def _when_all_doses_answered(context: Any) -> str | None:
    return SYMPTOM_CHECK if context.all_doses_answered else None


_SYMPTOM_INTRO = (
    "Current step: symptom check. Ask how the patient is feeling / whether they've "
    "had any discomfort since their last dose. If a reminder was just set (see the "
    "reschedule_dose result), first confirm it in a few words ('theek hai, X baje "
    "yaad dilaungi') in the same message as your question.\n"
)

_FOLLOW_UPS = (
    "- They mention any discomfort, even mild: do not log yet. Ask short follow-ups, "
    "one per turn -- where is it, how bad, since when -- until you can fill in the "
    "symptom's location, severity and duration (at most 3 questions; duration -- "
    "since when -- is mandatory, don't skip it). How bad it is comes in the patient's own "
    "words ('bahut', 'kaafi tez', 'thoda sa') -- never ask them to pick mild / moderate / "
    "severe, and don't ask for anything they have already told you, in any order. Once "
    "you have the three, decide -- no more questions. Then score it 1-10 (seriousness) from "
    "those details -- take the patient's own intensity words at face value ('bahut "
    "khansi' is not mild), and score 5-7 for several symptoms together, a symptom they "
    "call heavy, or anything lasting 2+ days. "
)

_NO_ADVICE = (
    "Just acknowledge what they told you: don't suggest remedies or rest, and don't promise it "
    "will be fine.\n"
)

_SYMPTOM_CHECK_DOCTOR = (
    _SYMPTOM_INTRO
    + "Before calling update_daily_log, make a deliberate escalation check: consider "
    "everything the patient has said in this call and confirm there is no concerning, "
    "severe, unusual, or red-flag symptom. If escalation might be needed or you are "
    "not sure, do not log yet -- ask the necessary short follow-up or call "
    "escalate_to_doctor. Only call update_daily_log once you are sure escalation is "
    "not needed.\n"
    "- They say they're fine and there are no red flags: call update_daily_log with a "
    "low seriousness score.\n"
    + _FOLLOW_UPS
    + "1-4: log it with update_daily_log. 5-7: ask them in one short sentence whether "
    "they'd like to speak to the doctor now -- if yes call escalate_to_doctor, if no "
    "log it with their refusal as patient_declined_doctor_quote. 8-10: call "
    "escalate_to_doctor instead of logging. "
    + _NO_ADVICE
    + "- They mention something concerning (e.g. chest pain, breathlessness, "
    "severe/unusual symptoms): call escalate_to_doctor instead -- do not diagnose or "
    "reassure them yourself first.\n"
    "If they ask for advice or a medical question, say you can't advise on that and "
    "they should ask their doctor."
)

_SYMPTOM_CHECK_CAREGIVER = (
    _SYMPTOM_INTRO
    + "No doctor takes these calls: when the patient isn't well, their family member "
    "(caregiver) is alerted instead. Never offer to connect a doctor.\n"
    "- They say they're fine and nothing is wrong: call update_daily_log with a low "
    "seriousness score.\n"
    + _FOLLOW_UPS
    + "1-4: log it with update_daily_log. 5-10: call alert_caregiver with the same "
    "details and the score, and a plain `reason` for the family -- don't ask the "
    "patient's permission first; the patient is told afterwards. "
    + _NO_ADVICE
    + "- They mention something alarming (e.g. chest pain, breathlessness, fainting, "
    "severe or unusual symptoms): call alert_caregiver straight away with seriousness 8 "
    "or more -- no follow-up questions first, no diagnosis, no reassurance.\n"
    "- They ask you to tell their family: call alert_caregiver.\n"
    "If they ask for advice or a medical question, say you can't advise on that and "
    "they should ask their doctor."
)


# A call with no dose to ask about starts at the symptom step, so that step also does the greeting.
_GREET_FIRST = (
    "This call has no dose to ask about (see the context above) -- do NOT ask whether they took any "
    "medicine. Your first turn is ONE short sentence: greet the patient by name and ask if you're "
    "speaking to them ('Namaste, kya main <name> ji se baat kar rahi hoon?') -- nothing else. If it "
    "isn't them, ask politely for the patient and say nothing about medicine or health to anyone "
    "else. Once they confirm, ask how they're feeling. If they ask when their next medicine is, tell "
    "them from the context.\n"
)


def build_policy(care_mode: CareMode = CareMode.caregiver, *, ask_doses: bool = True) -> PolicyEngine:
    """`ask_doses` False: nothing is due, so the call skips the dose step (a wellbeing check-in)."""
    doctor = care_mode == CareMode.doctor
    escalation_tool, escalated_state = (
        ("escalate_to_doctor", ESCALATION_ACTIVE) if doctor else ("alert_caregiver", CAREGIVER_ALERTED)
    )
    states = [
        PolicyState(
            name=DOSAGE_CHECK,
            prompt_fragment=(
                "Current step: dose check. Your first turn is ONE short sentence: greet the "
                "patient by name and ask if you're speaking to them (e.g. 'Namaste, kya main "
                "<name> ji se baat kar rahi hoon?') -- nothing else, no medicine, no second "
                "question. Wait for their answer. If it isn't them, ask politely for the "
                "patient and say nothing about medicine or health to anyone else. Once they "
                "confirm, your next turn asks about the dose this call is about (time and "
                "medicines are in the context above) in one short question. If several medicines "
                "are due, ask about them together ('kya aapne <time> wali dawaiyan li?', the "
                "time said as the context gives it) -- don't go "
                "through them one by one unless the answer differs between them; then ask which, "
                "and log each answer with `medicines` set to the names it covers (one call can "
                "cover several with the same answer). If the dose time has already passed, name "
                "it the way the context says it ('<time> wali dawai'). This "
                "is a real conversation: do NOT call "
                "log_dose_event until you actually know what happened with a medicine. The step "
                "ends only once every due medicine has an answer (the tool result lists what is "
                "still to ask about).\n"
                "- They took it: call log_dose_event with status=taken.\n"
                "- They're about to take it right now ('abhi leta hun', 'let me take it'): do not "
                "log anything yet. Say something short like 'theek hai, le lijiye, main wait "
                "karti hoon' and wait for their next message. When they confirm they've taken it, "
                "log taken.\n"
                "- They'll take it later ('baad mein', 'thodi der mein', 'later'): ask when they "
                "would like to be reminded ('kab yaad dilaun?'). Once they tell you, work out the "
                "number of minutes from the current time in the context above and call "
                "reschedule_dose. Don't call it before they've told you a time.\n"
                "- They say no / didn't take it: a bare 'no' is not enough to log. Ask why, in "
                "one short, kind question (bhool gaye? tabiyat theek nahi? dawai khatam?), and "
                "listen. Once you know the reason, log status=not_taken with the reason in note. "
                "Don't lecture, and never tell them to take extra or skip doses.\n"
                "- They're unsure / can't recall: ask at most one gentle question to help them "
                "recall (a question only -- don't suggest ways to check or work it out). If still "
                "unsure, log status=unknown, confidence=low -- don't push them to guess.\n"
                "If the reason for a missed dose is itself a symptom (e.g. nausea after the "
                "tablet), log the dose first; the next step follows up on the symptom."
            ),
            allowed_tools=["log_dose_event", "reschedule_dose"],
            on_tool_called={
                "log_dose_event": _when_all_doses_answered,
                "reschedule_dose": _when_all_doses_answered,
                # Not offered to the LLM in this state (not in allowed_tools above), but a
                # forced-action guardrail can still dispatch the escalation tool directly if a
                # red-flag symptom is blurted out before the dosage question is even answered --
                # this transition just makes sure the policy ends up in the right place if that
                # happens.
                escalation_tool: escalated_state,
            },
        ),
        PolicyState(
            name=SYMPTOM_CHECK,
            prompt_fragment=("" if ask_doses else _GREET_FIRST)
            + (_SYMPTOM_CHECK_DOCTOR if doctor else _SYMPTOM_CHECK_CAREGIVER),
            allowed_tools=["update_daily_log", escalation_tool],
            on_tool_called={
                "update_daily_log": CLOSING_NORMAL,
                escalation_tool: escalated_state,
            },
        ),
        PolicyState(
            name=ESCALATION_ACTIVE,
            prompt_fragment=(
                "Current step: in one short line, tell the patient you're connecting them to the "
                "doctor now and to hold for a couple of minutes. That's it -- do not call any "
                "tools, do not say anything else (the doctor-merge itself happens outside this "
                "conversation loop)."
            ),
            allowed_tools=[],
            is_terminal=True,
        ) if doctor else PolicyState(
            name=CAREGIVER_ALERTED,
            prompt_fragment=(
                "Current step: in one short line, tell the patient you've noted it and let their "
                "family member know. Do not call any tools, ask anything, or give any advice."
            ),
            allowed_tools=[],
            is_terminal=True,
        ),
        PolicyState(
            name=CLOSING_NORMAL,
            prompt_fragment=(
                "Current step: give a brief, warm sign-off (no more than a sentence or two) and "
                "end the call. Do not ask any question -- the call ends right after this "
                "message. Do not call any tools. You may say it has been noted, but do not say or "
                "imply that the doctor or anyone else will be told, called or will follow up -- "
                "nothing like that happens on this path."
            ),
            allowed_tools=[],
            is_terminal=True,
        ),
    ]
    return PolicyEngine(states, start_state=DOSAGE_CHECK if ask_doses else SYMPTOM_CHECK)
