"""What the agents may not say: dosage changes, diagnoses, advice, reassurance (pipecat-guardrails rules)."""

from __future__ import annotations

from datetime import datetime

import pytest

from backend.models import CareMode
from core.agent.guardrails import GuardrailViolation
from domains.med_adherence import doctor_agent
from domains.med_adherence.context import CallContext, DueMedicine
from domains.med_adherence.guardrails import build_guardrails

pytestmark = pytest.mark.anyio


def context() -> CallContext:
    return CallContext(
        patient_id="p", call_id="c", slot_at=datetime(2026, 11, 3, 2, 30), care_mode=CareMode.caregiver,
        due=[DueMedicine(dosage_id="d0", name="Metformin", dose="500 mg")],
    )


@pytest.mark.parametrize("text", [
    "Aap davai band kar do.",                 # spelling variant of dawai
    "Aapko dawaai badal deni chahiye, dawai badal dijiye.",
    "Dosage badhao thoda.",                   # verb ending the old substring list caught
    "Please increase the dosage.",
    "You might have an infection.",
])
async def test_dosage_change_or_diagnosis_is_blocked(text):
    with pytest.raises(GuardrailViolation, match="dosage"):
        await build_guardrails().check_text(text, context())


@pytest.mark.parametrize("text", [
    "Thoda aaram kariye.",
    "Aaram kijiye, sab theek ho jaega.",
    "Paani pijiye zyada.",
    "Cheenta mat kijiye.",                    # spelling variant of chinta
    "Don't worry, you should rest.",
    "Everything will be fine.",
])
async def test_advice_or_reassurance_is_blocked(text):
    with pytest.raises(GuardrailViolation, match="advice or reassurance"):
        await build_guardrails().check_text(text, context())


@pytest.mark.parametrize("text", [
    "Namaste, aap kaisi hain?",
    "Kya aapne aaj subah Metformin li?",
    "Aap kab se is dard se pareshan hain?",
    "Thank you, I'll note that down.",
    "Kya aapne paani piya?",                  # a question, not advice
])
async def test_ordinary_speech_is_allowed(text):
    assert await build_guardrails().check_text(text, context()) == text


async def test_doctor_brief_agent_blocks_dosage_advice_but_not_the_records():
    guardrails = doctor_agent.build_guardrails()
    with pytest.raises(GuardrailViolation, match="the doctor decides"):
        await guardrails.check_text("You might have a viral fever; increase the dose.", None)
    fact = "She took Metformin 500 mg this morning and reported a mild headache since yesterday."
    assert await guardrails.check_text(fact, None) == fact
