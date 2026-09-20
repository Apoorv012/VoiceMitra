"""The agent's side of an escalation, once a doctor picks up: brief them, answer their questions from
the record, and merge them into the patient's call on their say-so. Same core runtime, policy engine
and guardrail pipeline as the patient-facing agent -- only the tools, states, rules and prompt differ.

  briefing  -> merge_call (doctor confirmed) -> merging (terminal: one closing line)

After the merge the agent stops talking: the host (backend/escalations.py) relays messages between
doctor and patient, and hands the merged transcript to `summarize_merged_call` when the call ends.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from openai import AsyncOpenAI
from pydantic import BaseModel

from backend.db import (
    calls_col,
    daily_logs_col,
    doc_to_model,
    doctors_col,
    dose_events_col,
    patients_col,
    prescriptions_col,
)
from backend.models import (
    Call,
    CallLogEntry,
    CallLogEntryType,
    DailyLog,
    Doctor,
    DoseEvent,
    Escalation,
    Patient,
    Prescription,
)
from core.agent.context import AgentContext
from core.agent.guardrails import GuardrailPipeline, GuardrailViolation
from core.agent.policy import PolicyEngine, PolicyState
from core.agent.runtime import AgentConfig
from core.agent.tool_registry import ToolRegistry
from core.providers.llm import get_llm_client_and_model
from domains.med_adherence.guardrails import DOSAGE_CHANGE_OR_DIAGNOSIS_PHRASES

BRIEFING = "briefing"
MERGING = "merging"
CHANNEL = "doctor_briefing"

# Older transcript lines are dropped from the briefing prompt beyond this many.
MAX_TRANSCRIPT_ENTRIES = 40


# --- context, tool -------------------------------------------------------------------------

@dataclass
class DoctorBriefContext(AgentContext):
    escalation_id: str
    patient_name: str
    doctor_name: str
    merge_confirmed: bool = False
    last_doctor_text: str = ""
    log_entries: list[CallLogEntry] = field(default_factory=list)

    def observe_user_text(self, text: str) -> None:
        self.last_doctor_text = text

    def hands_off_transport(self) -> bool:
        # After a merge the doctor's chat stays open: the host relays the conversation through it.
        return self.merge_confirmed

    def record_user_text(self, text: str) -> None:
        self.log_entries.append(
            CallLogEntry(type=CallLogEntryType.doctor_said, content=text, channel=CHANNEL))

    def record_agent_text(self, text: str) -> None:
        self.log_entries.append(
            CallLogEntry(type=CallLogEntryType.agent_said, content=text, channel=CHANNEL))

    def record_tool_call(self, name: str, args: dict, result: Any, *, note: str | None = None) -> None:
        self.log_entries.append(CallLogEntry(
            type=CallLogEntryType.tool_call,
            tool_name=name,
            tool_args=args,
            tool_result=result if isinstance(result, dict) else {"value": result},
            note=note,
            channel=CHANNEL,
        ))


registry = ToolRegistry()


class MergeCallArgs(BaseModel):
    doctor_confirmation_quote: str


@registry.register(
    name="merge_call",
    description=(
        "Merge the doctor into the patient's call. Only call this once the doctor has clearly said "
        "to merge / connect / put them through. `doctor_confirmation_quote` must be their exact "
        "words, copied from their latest message."
    ),
    args_model=MergeCallArgs,
)
async def merge_call(args: MergeCallArgs, context: DoctorBriefContext) -> dict:
    context.merge_confirmed = True
    return {"merging": True, "patient": context.patient_name}


# --- policy, guardrails --------------------------------------------------------------------

def build_policy(patient_name: str) -> PolicyEngine:
    return PolicyEngine(
        [
            PolicyState(
                name=BRIEFING,
                prompt_fragment=(
                    "Current step: briefing.\n"
                    "- Your first message is the brief: at most 5 short lines covering who the "
                    "patient is (name, age), why the call was escalated, what they said (their own "
                    "words where the transcript has them), today's dose status, allergies and "
                    "their current medicine. Then end with exactly one question: shall you merge "
                    f"the doctor into the call with {patient_name} now?\n"
                    "- After that, answer the doctor's questions from the records. Don't merge "
                    "until they say so. After answering, remind them in a few words that they can "
                    "ask you to merge.\n"
                    "- When the doctor clearly says to merge / connect / put them through, call "
                    "merge_call with their exact words as doctor_confirmation_quote. A question, "
                    "'wait' or 'not yet' is not a confirmation. Never call it on your own."
                ),
                allowed_tools=["merge_call"],
                on_tool_called={"merge_call": MERGING},
            ),
            PolicyState(
                name=MERGING,
                prompt_fragment=(
                    f"Current step: in one short line, tell the doctor you're merging them into "
                    f"the call with {patient_name} now and that you'll stay on the line quietly to "
                    "take notes. Nothing else: no tools, no question."
                ),
                allowed_tools=[],
                is_terminal=True,
            ),
        ],
        start_state=BRIEFING,
    )


def _words(text: str) -> str:
    return " ".join(re.sub(r"\W+", " ", text.casefold()).split())


def _merge_needs_doctor_confirmation(tool_name: str, args: dict, context: DoctorBriefContext) -> None:
    if tool_name != "merge_call":
        return
    quote = _words(args.get("doctor_confirmation_quote", ""))
    if not quote or quote not in _words(context.last_doctor_text):
        raise GuardrailViolation(
            "merge_call needs the doctor's confirmation: `doctor_confirmation_quote` must be words "
            "copied exactly from their latest message, and they haven't asked to merge. Carry on "
            "answering their question instead."
        )


def _no_diagnosis_or_dosage_advice(text: str, context: DoctorBriefContext) -> str:
    lowered = text.lower()
    for phrase in DOSAGE_CHANGE_OR_DIAGNOSIS_PHRASES:
        if phrase in lowered:
            raise GuardrailViolation(
                "you gave a diagnosis or a dosage/treatment suggestion; the doctor decides those. "
                "Restate using only what's in the records"
            )
    return text


def build_guardrails() -> GuardrailPipeline:
    pipeline = GuardrailPipeline()
    pipeline.add_text_check(_no_diagnosis_or_dosage_advice)
    pipeline.add_tool_call_check(_merge_needs_doctor_confirmation)
    return pipeline


# --- prompt, session -----------------------------------------------------------------------

def _build_system_prompt(*, doctor_name: str, patient_name: str, facts: str) -> str:
    return f"""You are VoiceMitra, a medicine-adherence assistant, now talking to {doctor_name}, a doctor. \
An automated call to their patient {patient_name} was just escalated to them; the patient is on hold \
on the line. Your job: brief the doctor, answer their questions about the case, and merge them into \
the call with the patient when they ask.

Talk to the doctor as a colleague would: brief and to the point, in English -- or Roman-script \
Hinglish if they write in Hindi/Hinglish.

Hard rules:
- Use only the records below. If something isn't in them, say it isn't recorded -- never guess or \
fill gaps.
- You do not diagnose, and you do not suggest treatment, dosage changes or what to tell the patient. \
Those are the doctor's decisions.

RECORDS
{facts}"""


async def _gather_facts(escalation: Escalation, patient: Patient) -> str:
    prescription_lines: list[str] = []
    for rx_id in patient.prescription_ids:
        rx = doc_to_model(Prescription, await prescriptions_col().find_one({"_id": rx_id}))
        for m in (rx.medicines if rx else []):
            times = f" at {', '.join(m.times)}" if m.times else ""
            prescription_lines.append(f"- {m.medicine_name}, {m.dosage}, {m.frequency.value}{times}")

    call = doc_to_model(Call, await calls_col().find_one({"_id": escalation.call_id}))
    transcript_lines: list[str] = []
    for e in (call.logs if call else [])[-MAX_TRANSCRIPT_ENTRIES:]:
        if e.type == CallLogEntryType.patient_said:
            transcript_lines.append(f"Patient: {e.content}")
        elif e.type == CallLogEntryType.agent_said:
            transcript_lines.append(f"Agent: {e.content}")
        elif e.type == CallLogEntryType.tool_call and e.tool_name in ("log_dose_event", "update_daily_log"):
            transcript_lines.append(f"[recorded {e.tool_name}: {e.tool_args}]")

    dose_events = [
        doc_to_model(DoseEvent, d)
        async for d in dose_events_col().find({"patient_id": patient.id}).sort("recorded_at", -1).limit(5)
    ]
    daily_logs = [
        doc_to_model(DailyLog, d)
        async for d in daily_logs_col().find({"patient_id": patient.id}).sort("created_at", -1).limit(3)
    ]

    def none_if_empty(lines: list[str]) -> str:
        return "\n".join(lines) if lines else "(none)"

    return "\n".join([
        f"Patient: {patient.name}, {patient.age} years old. Notes: {patient.description or 'none'}.",
        f"Allergies: {', '.join(patient.allergies) if patient.allergies else 'none known'}.",
        "Prescribed medicine:",
        none_if_empty(prescription_lines),
        "",
        f"Escalation (urgency {escalation.urgency}): {escalation.reason}",
        f"Agent's summary at the time: {escalation.brief_summary}",
        "",
        "Transcript of today's call (before the hand-off):",
        none_if_empty(transcript_lines),
        "",
        "Recent dose events (newest first):",
        none_if_empty([
            f"- {e.recorded_at:%d %b %H:%M}: {e.status.value}"
            + (f" ({e.note})" if e.note else "") for e in dose_events
        ]),
        "",
        "Recent daily logs (newest first):",
        none_if_empty([
            f"- {log.created_at:%d %b %H:%M}: {log.summary} (seriousness {log.seriousness}/10)"
            + "".join(f"; symptom: {s.name} {s.severity.value}, {s.duration_note or 'duration unknown'}"
                      for s in log.symptoms)
            for log in daily_logs
        ]),
    ])


@dataclass
class DoctorSession:
    context: DoctorBriefContext
    config: AgentConfig


async def create_doctor_session(escalation: Escalation, doctor_id: str) -> DoctorSession:
    patient = doc_to_model(Patient, await patients_col().find_one({"_id": escalation.patient_id}))
    doctor = doc_to_model(Doctor, await doctors_col().find_one({"_id": doctor_id}))
    facts = await _gather_facts(escalation, patient)

    llm_client, model = get_llm_client_and_model()
    context = DoctorBriefContext(
        escalation_id=escalation.id, patient_name=patient.name, doctor_name=doctor.name)
    config = AgentConfig(
        llm_client=llm_client,
        model=model,
        base_system_prompt=_build_system_prompt(
            doctor_name=doctor.name, patient_name=patient.name, facts=facts),
        tool_registry=registry,
        policy=build_policy(patient.name),
        guardrails=build_guardrails(),
    )
    return DoctorSession(context=context, config=config)


# --- summary of the merged conversation ----------------------------------------------------

async def summarize_merged_call(
    *, patient_name: str, doctor_name: str, reason: str, transcript: list[tuple[str, str]],
) -> str:
    """One LLM call over the doctor<->patient messages exchanged after the merge. `transcript` is
    (speaker, text) pairs, speaker being "doctor" or "patient"."""
    if not transcript:
        return "Doctor and patient were connected, but no messages were exchanged."

    llm_client, model = get_llm_client_and_model()
    lines = "\n".join(
        f"{doctor_name if speaker == 'doctor' else patient_name}: {text}" for speaker, text in transcript
    )
    response = await _chat(llm_client, model, system=(
        "You take notes on a call between a doctor and a patient for the medical record. Write a "
        "summary of what was said, in English, at most 100 words, as three short labelled lines:\n"
        "Concern: what the patient reported.\n"
        "Doctor's instructions: what the doctor told or asked the patient to do, as they said it.\n"
        "Follow-up: anything to be done afterwards, or 'none stated'.\n"
        "Record only what was actually said. Do not add your own medical opinion or advice, and do "
        "not invent details."
    ), user=f"Reason for the escalation: {reason}\n\nConversation:\n{lines}")
    return response.strip()


async def _chat(client: AsyncOpenAI, model: str, *, system: str, user: str) -> str:
    response = await client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
    )
    return response.choices[0].message.content or ""
