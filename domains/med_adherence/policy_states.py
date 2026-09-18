"""Concrete dialogue policy for the medicine-adherence agent.

dosage_check (start)
  -> log_dose_event -> symptom_check
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
                "Current step: greet the patient by name, confirm you're speaking to them, and "
                "ask about the dose that is due right now (you'll be told which medicine/dosage "
                "in the context above). Once you know whether they took it, are about to, missed "
                "it, or are unsure, call log_dose_event with your best judgement of status, "
                "confidence, and source. If they're unsure/can't recall, that's still a valid "
                "outcome (status=unknown, confidence=low) -- don't push them to guess."
            ),
            allowed_tools=["log_dose_event"],
            on_tool_called={
                "log_dose_event": SYMPTOM_CHECK,
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
                "Current step: ask how the patient is feeling / whether they've noticed any "
                "symptoms or discomfort. If nothing concerning comes up, call update_daily_log "
                "summarizing the call with a low seriousness score. If they mention something "
                "concerning (e.g. chest pain, breathlessness, severe/unusual symptoms), call "
                "escalate_to_doctor instead of update_daily_log -- do not try to diagnose or "
                "reassure them yourself first, just move to escalation."
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
                "end the call. Do not call any tools."
            ),
            allowed_tools=[],
            is_terminal=True,
        ),
    ]
    return PolicyEngine(states, start_state=DOSAGE_CHECK)
