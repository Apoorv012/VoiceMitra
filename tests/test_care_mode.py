"""Care mode: in the pilot (caregiver) a patient who isn't well gets their caregiver alerted and the
call ends; in doctor mode the doctor is rung as before."""

from __future__ import annotations

from datetime import datetime

import pytest

from backend.models import CareMode
from core.agent.guardrails import GuardrailViolation
from domains.med_adherence.context import CallContext, CaregiverAlert, DueMedicine, EscalationRequest
from domains.med_adherence.guardrails import build_guardrails
from domains.med_adherence.policy_states import (
    CAREGIVER_ALERTED,
    ESCALATION_ACTIVE,
    SYMPTOM_CHECK,
    build_policy,
)
from domains.med_adherence.prompts import EMERGENCY_NUMBER, HANDOFF_LINE_HINGLISH


def context(mode: CareMode) -> CallContext:
    return CallContext(
        patient_id="p", call_id="c", slot_at=datetime(2026, 11, 3, 2, 30), care_mode=mode,
        due=[DueMedicine(dosage_id="d0", name="Metformin", dose="500 mg")],
    )


def at_symptom_check(mode: CareMode):
    ctx = context(mode)
    policy = build_policy(mode)
    ctx.dose_statuses["d0"] = "taken"
    policy.advance("log_dose_event", ctx)
    assert policy.current_state_name == SYMPTOM_CHECK
    return ctx, policy


def test_caregiver_mode_offers_the_caregiver_alert_not_the_doctor():
    _, policy = at_symptom_check(CareMode.caregiver)
    assert set(policy.allowed_tools()) == {"update_daily_log", "alert_caregiver"}
    assert policy.advance("alert_caregiver") == CAREGIVER_ALERTED
    assert policy.is_done()


def test_doctor_mode_is_unchanged():
    _, policy = at_symptom_check(CareMode.doctor)
    assert set(policy.allowed_tools()) == {"update_daily_log", "escalate_to_doctor"}
    assert policy.advance("escalate_to_doctor") == ESCALATION_ACTIVE


def test_moderate_score_cannot_just_be_logged_in_caregiver_mode():
    ctx = context(CareMode.caregiver)
    args = {"summary": "headache", "seriousness": 6, "symptoms": []}
    with pytest.raises(GuardrailViolation, match="alert_caregiver"):
        build_guardrails().check_tool_call("update_daily_log", args, ctx)
    # mild is fine
    build_guardrails().check_tool_call("update_daily_log", {**args, "seriousness": 3}, ctx)


def test_doctor_mode_still_offers_the_doctor_for_a_moderate_score():
    ctx = context(CareMode.doctor)
    with pytest.raises(GuardrailViolation, match="speak to the doctor"):
        build_guardrails().check_tool_call("update_daily_log", {"seriousness": 6, "symptoms": []}, ctx)


def test_moderate_alert_needs_a_duration_but_an_urgent_one_does_not():
    ctx = context(CareMode.caregiver)
    symptom = [{"name": "headache", "severity": "moderate"}]
    with pytest.raises(GuardrailViolation, match="duration"):
        build_guardrails().check_tool_call("alert_caregiver", {"seriousness": 6, "symptoms": symptom}, ctx)
    build_guardrails().check_tool_call("alert_caregiver", {"seriousness": 9, "symptoms": symptom}, ctx)


@pytest.mark.parametrize("mode, tool", [(CareMode.caregiver, "alert_caregiver"), (CareMode.doctor, "escalate_to_doctor")])
def test_red_flag_forces_the_mode_s_escalation(mode, tool):
    ctx = context(mode)
    ctx.observe_user_text("mujhe chest mein dard ho raha hai")
    forced = build_guardrails().forced_action(ctx)
    assert forced is not None and forced.tool_name == tool
    if mode == CareMode.caregiver:
        assert forced.args["seriousness"] >= 8
        build_guardrails().check_tool_call(forced.tool_name, forced.args, ctx)  # passes its own checks
        ctx.caregiver_alert = CaregiverAlert(reason="chest pain", urgent=True, caregiver_name="Rakesh")
        assert build_guardrails().forced_action(ctx) is None  # not forced twice


def test_closing_line_after_a_caregiver_alert_is_fixed():
    ctx = context(CareMode.caregiver)
    ctx.caregiver_alert = CaregiverAlert(reason="headache", urgent=False, caregiver_name="Rakesh (father)")
    line = build_guardrails().check_text("Main doctor ko bula rahi hoon, aaram kijiye", ctx)
    assert "Rakesh ji ko bata diya" in line and "(father)" not in line and "?" not in line
    # only the first line after the alert is replaced
    assert build_guardrails().check_text("Namaste", ctx) == "Namaste"


def test_urgent_alert_line_gives_the_emergency_number_in_english():
    ctx = context(CareMode.caregiver)
    ctx.patient_language = "english"
    ctx.caregiver_alert = CaregiverAlert(reason="chest pain", urgent=True, caregiver_name="Rahul")
    line = build_guardrails().check_text("anything", ctx)
    assert "let Rahul know" in line and EMERGENCY_NUMBER in line


def test_no_caregiver_on_file_means_nobody_is_claimed_to_be_told():
    ctx = context(CareMode.caregiver)
    ctx.caregiver_alert = CaregiverAlert(reason="headache", urgent=False, caregiver_name=None)
    line = build_guardrails().check_text("anything", ctx)
    assert "note kar liya" in line and "bata diya" not in line


def test_doctor_hand_off_line_still_wins_in_doctor_mode():
    ctx = context(CareMode.doctor)
    ctx.escalation = EscalationRequest(reason="chest pain", brief_summary="chest pain")
    assert build_guardrails().check_text("anything", ctx) == HANDOFF_LINE_HINGLISH
