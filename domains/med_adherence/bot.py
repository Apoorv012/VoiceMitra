"""Entrypoint that assembles an AgentRuntime for a given patient's call.

Chunk 2: chat-mode only (ChatTransport), for building/debugging the agent's logic without audio.
Chunk 3 adds a voice entrypoint using DailyTransport alongside this, reusing everything else
(policy/tools/guardrails/prompts) unchanged -- only the transport differs.

Usage: python -m domains.med_adherence.bot <patient_id>
"""

from __future__ import annotations

import asyncio
import sys

from dotenv import load_dotenv

load_dotenv()

from backend.db import calls_col, doc_to_model, model_to_doc, patients_col, prescriptions_col
from backend.models import Call, CallType, Patient, Prescription
from core.agent.runtime import AgentConfig, run_chat_session
from core.providers.llm import DEFAULT_MODEL, get_sarvam_llm_client
from core.transport.chat_transport import ChatTransport
from domains.med_adherence.context import CallContext
from domains.med_adherence.guardrails import build_guardrails
from domains.med_adherence.policy_states import build_policy
from domains.med_adherence.prompts import build_base_system_prompt
from domains.med_adherence.tools import registry as tool_registry


async def _load_patient_and_dosage(patient_id: str) -> tuple[Patient, Prescription]:
    patient = doc_to_model(Patient, await patients_col().find_one({"_id": patient_id}))
    if patient is None:
        raise SystemExit(f"no patient with id {patient_id}")
    if not patient.prescription_ids:
        raise SystemExit(f"patient {patient.name} has no prescriptions")
    prescription = doc_to_model(
        Prescription, await prescriptions_col().find_one({"_id": patient.prescription_ids[0]})
    )
    if not prescription or not prescription.medicines:
        raise SystemExit(f"patient {patient.name}'s prescription has no dosages")
    return patient, prescription


async def run_chat_demo(patient_id: str) -> None:
    patient, prescription = await _load_patient_and_dosage(patient_id)
    dosage = prescription.medicines[0]

    call = Call(patient_id=patient.id, type=CallType.medicine_reminder)
    await calls_col().insert_one(model_to_doc(call))

    context = CallContext(
        patient_id=patient.id,
        call_id=call.id,
        dosage_id=dosage.id,
        medicine_name=dosage.medicine_name,
        medicine_dosage=dosage.dosage,
        allergies=patient.allergies,
    )

    config = AgentConfig(
        llm_client=get_sarvam_llm_client(),
        model=DEFAULT_MODEL,
        base_system_prompt=build_base_system_prompt(
            patient_name=patient.name,
            medicine_name=dosage.medicine_name,
            medicine_dosage=dosage.dosage,
            allergies=patient.allergies,
        ),
        tool_registry=tool_registry,
        policy=build_policy(),
        guardrails=build_guardrails(),
    )

    transport = ChatTransport(speaker_label=patient.name)
    await run_chat_session(transport, config, context)

    print(f"\n(call id {call.id} -- inspect dose_events/daily_logs/calls in Mongo)")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("usage: python -m domains.med_adherence.bot <patient_id>")
    asyncio.run(run_chat_demo(sys.argv[1]))
