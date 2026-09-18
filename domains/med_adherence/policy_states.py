"""Concrete dialogue policy for the medicine-adherence agent.

dosage_check (start)
  -> log_dose_event / reschedule_dose (patient will take it later) -> symptom_check
symptom_check
  -> update_daily_log (nothing concerning)   -> closing_normal (terminal)
  -> escalate_to_doctor (concerning symptom) -> escalation_active (terminal)

escalation_active is terminal itself, with no tools allowed, rather than routing through an
end_call tool call -- a function-calling LLM generally can't both speak text and call a tool in
the same turn (a response with tool_calls usually carries no content), so making the hand-off
state's *only* job "say this one line" (forced to plain text by having zero allowed tools) is what
actually gets that line spoken, instead of the model silently calling a transition tool and never
producing the sentence it was supposed to say first.
"""

from __future__ import annotations

from core.agent.policy import PolicyEngine, PolicyState

DOSAGE_CHECK = "dosage_check"
SYMPTOM_CHECK = "symptom_check"
ESCALATION_ACTIVE = "escalation_active"
CLOSING_NORMAL = "closing_normal"


def build_policy() -> PolicyEngine:
    states = [
        PolicyState(
            name=DOSAGE_CHECK,
            prompt_fragment=(
                "Current step: dose check. On your first turn, greet the patient by name and "
                "confirm you're speaking to them. Then ask about the dose due right now (the "
                "medicine/dosage is in the context above). This is a real conversation: do NOT "
                "call log_dose_event until you actually know what happened with the dose.\n"
                "- They took it: call log_dose_event with status=taken.\n"
                "- They're about to take it right now ('abhi leta hun', 'let me take it'): do not "
                "log anything yet. Say something short like 'theek hai, le lijiye, main wait "
                "karta hun' and wait for their next message. When they confirm they've taken it, "
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
                "log_dose_event": SYMPTOM_CHECK,
                "reschedule_dose": SYMPTOM_CHECK,
                # Not offered to the LLM in this state (not in allowed_tools above), but a
                # forced-action guardrail can still dispatch escalate_to_doctor directly if a
                # red-flag symptom is blurted out before the dosage question is even answered --
                # this transition just makes sure the policy ends up in the right place if that
                # happens.
                "escalate_to_doctor": ESCALATION_ACTIVE,
            },
        ),
        PolicyState(
            name=SYMPTOM_CHECK,
            prompt_fragment=(
                "Current step: symptom check. Ask how the patient is feeling / whether they've "
                "had any discomfort since their last dose. If a reminder was just set (see the "
                "reschedule_dose result), first confirm it in a few words ('theek hai, X baje "
                "yaad dilaunga') in the same message as your question.\n"
                "- They say they're fine: call update_daily_log with a low seriousness score.\n"
                "- They mention any discomfort, even mild: do not log yet. Ask short follow-ups, "
                "one per turn -- where is it, how bad, since when -- until you can fill in the "
                "symptom's location, severity and duration (at most 3 questions; duration -- "
                "since when -- is mandatory, don't skip it). Then call update_daily_log with "
                "those details and a seriousness score that reflects them. Just acknowledge what "
                "they told you: don't suggest remedies or rest, and don't promise it will be "
                "fine.\n"
                "- They mention something concerning (e.g. chest pain, breathlessness, "
                "severe/unusual symptoms): call escalate_to_doctor instead -- do not diagnose or "
                "reassure them yourself first.\n"
                "If they ask for advice or a medical question, say you can't advise on that and "
                "they should ask their doctor."
            ),
            allowed_tools=["update_daily_log", "escalate_to_doctor"],
            on_tool_called={
                "update_daily_log": CLOSING_NORMAL,
                "escalate_to_doctor": ESCALATION_ACTIVE,
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
        ),
        PolicyState(
            name=CLOSING_NORMAL,
            prompt_fragment=(
                "Current step: give a brief, warm sign-off (no more than a sentence or two) and "
                "end the call. Do not ask any question -- the call ends right after this "
                "message. Do not call any tools."
            ),
            allowed_tools=[],
            is_terminal=True,
        ),
    ]
    return PolicyEngine(states, start_state=DOSAGE_CHECK)
