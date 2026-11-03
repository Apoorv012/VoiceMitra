"""The dose step of a call covers every medicine due in the slot: tool calls name the medicines they
are about, and the policy moves on only once each one has an answer."""

from __future__ import annotations

from datetime import datetime

import pytest

from backend.models import DoseStatus
from domains.med_adherence.context import CallContext, DueMedicine
from domains.med_adherence.policy_states import DOSAGE_CHECK, SYMPTOM_CHECK, build_policy


def context(*names: str) -> CallContext:
    return CallContext(
        patient_id="p", call_id="c", slot_at=datetime(2026, 11, 3, 2, 30),
        due=[DueMedicine(dosage_id=f"d{i}", name=n, dose="1 tablet") for i, n in enumerate(names)],
    )


def test_medicines_are_matched_by_name_ignoring_case_and_spacing():
    ctx = context("Metformin 500", "Amlodipine")
    assert [m.dosage_id for m in ctx.resolve_medicines(["metformin  500", "AMLODIPINE", "amlodipine"])] == ["d0", "d1"]
    # as the prompt lists them: "Name (dose)"
    assert [m.dosage_id for m in ctx.resolve_medicines(["Amlodipine (1 tablet)"])] == ["d1"]


def test_unknown_medicine_names_list_the_valid_ones():
    ctx = context("Metformin 500", "Amlodipine")
    with pytest.raises(ValueError, match="Metformin 500, Amlodipine"):
        ctx.resolve_medicines(["Paracetamol"])


def test_no_names_means_every_medicine_still_without_an_answer():
    ctx = context("A", "B", "C")
    ctx.dose_statuses["d0"] = DoseStatus.taken
    assert [m.dosage_id for m in ctx.resolve_medicines([])] == ["d1", "d2"]


def test_dose_step_ends_only_when_every_medicine_is_answered():
    ctx = context("A", "B")
    policy = build_policy()
    ctx.dose_statuses["d0"] = DoseStatus.taken
    assert policy.advance("log_dose_event", ctx) == DOSAGE_CHECK
    ctx.dose_statuses["d1"] = DoseStatus.not_taken
    assert policy.advance("reschedule_dose", ctx) == SYMPTOM_CHECK
