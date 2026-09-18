"""Entrypoint that assembles an AgentRuntime for a given patient's call.

Chunk 2: chat-mode only (ChatTransport), for building/debugging the agent's logic without audio.
Chunk 3 adds a voice entrypoint using DailyTransport alongside this, reusing everything else
(policy/tools/guardrails/prompts) unchanged -- only the transport differs.

Usage: python -m domains.med_adherence.bot <patient_id>
"""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

from backend.db import calls_col, doc_to_model, model_to_doc, patients_col, prescriptions_col
from backend.models import Call, CallType, Patient, Prescription, Reminder
from core.agent.runtime import AgentConfig, run_chat_session
from core.providers.llm import get_llm_client_and_model
from core.transport.base import Transport
from core.transport.chat_transport import ChatTransport
from domains.med_adherence.context import CallContext
from domains.med_adherence.guardrails import build_guardrails
from domains.med_adherence.policy_states import build_policy
from domains.med_adherence.prompts import build_base_system_prompt
from domains.med_adherence.tools import registry as tool_registry


class PatientNotReady(Exception):
    """The patient can't be called yet (unknown id, or no prescription/dosage to remind about)."""


@dataclass
class CallSession:
    patient: Patient
    call: Call
    context: CallContext
    config: AgentConfig


async def _load_patient_and_dosage(patient_id: str) -> tuple[Patient, Prescription]:
    patient = doc_to_model(Patient, await patients_col().find_one({"_id": patient_id}))
    if patient is None:
        raise PatientNotReady(f"no patient with id {patient_id}")
    if not patient.prescription_ids:
        raise PatientNotReady(f"patient {patient.name} has no prescriptions")
    prescription = doc_to_model(
        Prescription, await prescriptions_col().find_one({"_id": patient.prescription_ids[0]})
    )
    if not prescription or not prescription.medicines:
        raise PatientNotReady(f"patient {patient.name}'s prescription has no dosages")
    return patient, prescription


async def create_call_session(
    patient_id: str, *, on_reminder_created: Callable[[Reminder], None] | None = None
) -> CallSession:
    """Creates the Call document and assembles everything a session needs, independent of which
    transport will carry it."""
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
        on_reminder_created=on_reminder_created,
    )

    llm_client, model = get_llm_client_and_model()
    config = AgentConfig(
        llm_client=llm_client,
        model=model,
        base_system_prompt=build_base_system_prompt(
            patient_name=patient.name,
            medicine_name=dosage.medicine_name,
            medicine_dosage=dosage.dosage,
            allergies=patient.allergies,
            now_local=datetime.now().astimezone().strftime("%A %H:%M (UTC%z)"),
        ),
        tool_registry=tool_registry,
        policy=build_policy(),
        guardrails=build_guardrails(),
    )
    return CallSession(patient=patient, call=call, context=context, config=config)


async def run_call_session(session: CallSession, transport: Transport) -> None:
    """Runs the conversation over `transport`, then flushes the transcript to Mongo -- even if
    the session dies mid-call, so a crashed call still leaves its partial log behind."""
    try:
        await run_chat_session(transport, session.config, session.context)
    finally:
        await calls_col().update_one(
            {"_id": session.call.id},
            {"$set": {"logs": [e.model_dump(mode="json") for e in session.context.log_entries]}},
        )


async def run_chat_demo(patient_id: str) -> None:
    session = await create_call_session(patient_id)
    await run_call_session(session, ChatTransport(speaker_label=session.patient.name))
    print(f"\n(call id {session.call.id} -- inspect dose_events/daily_logs/calls in Mongo)")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("usage: python -m domains.med_adherence.bot <patient_id>")
    try:
        asyncio.run(run_chat_demo(sys.argv[1]))
    except PatientNotReady as e:
        raise SystemExit(str(e))
