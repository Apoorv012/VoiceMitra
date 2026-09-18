# VoiceMitra — Plan & Status

This is the living plan for the project: what's being built, why, and what's actually done vs.
not. Update the **Status** section as chunks complete or scope changes — this file is the source
of truth for progress, not chat history.

## Context

VoiceMitra is a voice-first medicine-adherence system for hospitals: patients get called to be
reminded to take medicine, the agent logs whether they took it and how they're feeling, and if
something's wrong it escalates by bringing a doctor live into the same call, with a secondary
caregiver (e.g. an adult child) kept in the loop. Built as a capstone project — beyond working
demo behavior, it needs to read as real AI/systems engineering, not a thin prompt-and-API wrapper.

Design constraints:
- Own the agent's logic (prompting, escalation rules, data model, dialogue control) — no no-code
  voice-agent product.
- **Modularity for a future real-phone version**: the call transport must be swappable later
  (browser/WebRTC now → Twilio/PSTN later) without touching agent logic. Pipecat already ships a
  Twilio-compatible transport, so this is a real migration path, not aspirational — `core/transport/base.py`
  is the interface domain/agent code depends on, never Daily or Twilio directly.
- **Real AI engineering, not just STT→LLM→TTS plumbing**:
  - An explicit **dialogue policy / state machine** (`core/agent/policy.py` +
    `domains/med_adherence/policy_states.py`) governing conversation flow, constraining what
    tool-calls are allowed at each point.
  - A **rules+LLM escalation/triage layer** (`domains/med_adherence/escalation_rules.py`): red-flag
    symptom list + LLM judgment, cross-checked against allergies.
  - A **guardrails layer** (`core/agent/guardrails.py` + `domains/med_adherence/guardrails.py`),
    separate from policy: safety constraints checked regardless of conversation flow — e.g. a
    red-flag symptom forces escalation even if the LLM tries to downplay it, no dosage-change
    advice, no diagnosis, tool-call args schema-validated before touching the database.
  - **Structured symptom extraction**: free conversation → typed `daily_log` symptom entries
    (name, location, severity, duration), not a text blob.
  - A **scripted evaluation harness** (`eval/`, not yet built) replaying reference scenarios
    against the live agent, asserting correct tool-call paths.
- Scope is **medicine-adherence only** — no second domain being built. The `core/`/`domains/`
  split exists so the boundary is real and demonstrable, not to build a multi-domain platform.
- **Chunked delivery**: work proceeds in chunks; after each, stop and show runnable output before
  continuing.

## Stack

- **Voice pipeline**: Pipecat (Chunk 3+, not yet wired).
- **STT/TTS**: Sarvam AI (`SarvamSTTService`/`SarvamTTSService`, built into Pipecat) — best
  Hindi/Hinglish quality, matches `reference_transcripts/` style.
- **LLM (chat-completions)**: swappable via `LLM_PROVIDER` env var in `core/providers/llm.py` —
  Sarvam (`sarvam-105b-conversations`, primary/demo-quality) or Gemini (`gemini-3.5-flash-lite`,
  higher free quota, used to conserve Sarvam credits during iterative chat-based testing). Both
  are OpenAI-compatible chat-completions endpoints, so `core/agent/runtime.py` is identical either
  way.
- **Transport**: Daily.co WebRTC for the POC (native multi-participant rooms make the doctor
  "merge" trivial); Twilio swap-in later via the same `Transport` interface.
- **Data store**: MongoDB via Motor (async).
- **Backend**: FastAPI — JSON routers + server-rendered Jinja2 dashboards.

## Data model

Extends the original `reference_transcripts/original_schema.txt` draft:
- `caregiver` is a real entity (name + relation + phone), not a bare number list on `patient`.
- `daily_log.symptoms` is a structured array (name, location, severity, duration_note, raw_quote),
  not free text.
- `call.logs` is a structured transcript+tool-call log (`CallLogEntry`: patient_said / agent_said /
  tool_call with args+result / escalation_call_started / escalation_call_merged), not `list[str]`.
- `call` has `escalation_reason` and `caregiver_notified`.

Full field-level detail lives in `backend/models.py` (source of truth) — this file just tracks the
rationale for the deviations from the original draft schema.

## Repository structure

```
voicemitra/
  CLAUDE.md                      # git rules + pointer to this file
  PLAN.md                        # this file
  README.md                      # setup/run instructions only
  requirements.txt
  .env.example

  core/                          # transport-agnostic voice-agent runtime
    transport/                   # base.py (interface), chat_transport.py + queue_transport.py (done), daily_transport.py (Chunk 3)
    providers/                   # llm.py (done, Sarvam+Gemini), stt.py / tts.py (Chunk 3)
    agent/                       # runtime.py, tool_registry.py, policy.py, guardrails.py, context.py (all done)

  domains/med_adherence/         # prompts.py, policy_states.py, tools.py, guardrails.py,
                                  # escalation_rules.py, context.py, bot.py (all done for chat; voice pending)

  backend/
    main.py, db.py, models.py, queries.py, seed.py, live_calls.py
    routers/                     # patients.py, doctors.py, calls.py (JSON API), live.py (WebSockets + call controls)
    pages.py                     # server-rendered dashboards
    templates/, static/

  eval/                          # not yet built (Chunk 5)
  reference_transcripts/         # sample Hindi/Hinglish transcripts, prompt/eval grounding material
```

## Status

### Chunk 1 — Scaffold + data layer — **DONE**
Repo scaffold, data model, MongoDB wiring, seed data, minimal API. Verified: seeded patient +
doctor + caregiver + prescription, fetched via API.

### Chunk 2 — Agent core + policy engine + guardrails, via text chat — **DONE**
Built: `core/transport/{base,chat_transport}.py`, `core/providers/llm.py`, `core/agent/{runtime,
tool_registry,policy,guardrails,context}.py`, `domains/med_adherence/{policy_states,tools,
guardrails,prompts,context,escalation_rules,bot}.py`.

Verified live (real LLM calls): happy path (dose taken, feeling fine), unsure/forgot path
(status=unknown, confidence=low), chest-pain escalation (forced-action guardrail fires
independent of LLM judgment, correct hand-off line), dosage-change guardrail (blocks the agent
from advising a dose change).

Two real bugs found and fixed during this chunk:
- A policy-state design bug where a state expected the LLM to both speak and call a tool in one
  turn (function-calling LLMs generally can't do both at once) — fixed by making the escalation
  hand-off its own terminal, tool-free state.
- Sarvam's API requires `tools` to stay non-empty once any tool call exists in conversation
  history, and separately `tool_choice="none"` returned empty output — fixed by always offering
  the full tool schema with `tool_choice="auto"` once tool history exists, enforcing which tools
  are actually usable via an explicit policy check in the runtime.

**Extra work done beyond the original Chunk 2 scope** (added after user feedback):
- **Structured call logging**: every call stores a full transcript+tool-call log (`Call.logs` as
  `list[CallLogEntry]`), not just derived summaries. Wired via `AgentContext.record_*` hooks in
  `core/agent/context.py`, domain implementation in `domains/med_adherence/context.py`, flushed to
  Mongo in `bot.py`.
- **Three server-rendered dashboards** (`backend/pages.py` + `backend/templates/`):
  - Operator (`/operator`): patient roster with adherence-status badges, add-patient +
    add-prescription forms.
  - Patient/family self-view (`/patients/<id>`): read-only adherence history, symptoms over time,
    call history with transcript links.
  - Doctor (`/doctors/<id>`): escalation queue, patient roster, can add prescriptions
    (`/doctors/<id>/patients/<id>`).
  - Home page (`/`) links into all of the above.
- **Gemini as an alternate LLM provider** (`LLM_PROVIDER=gemini` in `.env`): fixed a Gemini-specific
  bug (rejects a system-only first request with no prior turn — worked around with a neutral seed
  message, harmless for every provider) and switched the default model to `gemini-3.5-flash-lite`
  for a much higher free-tier request quota than the plain Flash tier.

### Operator-triggered web chat — **DONE** (added after Chunk 2, before voice)
The operator dashboard has a **Call now** button per patient (and **End call** while one is live).
Pressing it starts the agent's session in the backend and the message appears in the patient's own
window (`/patients/<id>`; the chat panel shows up when a call is live); the patient replies there.
When the session finishes, the transcript is flushed to the `Call` document.

**Real-time, event-driven -- no polling.** Two WebSockets (`backend/routers/live.py`):
`/ws/patients/<id>/chat` (server: snapshot / call_started / message / call_ended; client: reply) and
`/ws/operator` (call_started / call_ended, on which the dashboard re-fetches just that patient's row
via `/operator/patients/<id>/row`). Start/End are plain `POST /api/patients/<id>/call[/end]`. Both
pages reconnect with backoff and resync from the snapshot the server sends on connect. The hub is
in `backend/live_calls.py` (per-socket asyncio queues); `QueueTransport` reports messages through an
`on_message` callback, so the agent core still knows nothing about HTTP.

Built: `core/transport/queue_transport.py` (queue-backed `Transport`, a second implementation
alongside `ChatTransport`), `backend/live_calls.py`, `backend/routers/live.py`,
`backend/templates/_chat_widget.html` + `_operator_row.html`, plus `domains/med_adherence/bot.py`
split into `create_call_session` / `run_call_session` so the CLI and the web backend share setup.

**Conversation-quality pass** (after first hands-on test: the agent asked the dose question, then
symptoms, then hung up -- it didn't react to "no" or "not yet"):
- `policy_states.py` prompts rewritten so `log_dose_event` / `update_daily_log` are only called once
  the outcome is actually known: "no" -> ask why first; "right now" -> wait for the patient to come
  back; any discomfort -> up to 3 follow-ups (where / how bad / since when) before logging.
- New guardrails: `_missed_dose_needs_reason` (`log_dose_event(status=not_taken)` is rejected without
  a `note`) and `_symptom_needs_duration` (`update_daily_log` symptoms need a `duration_note`), so
  "ask why" / "ask since when" are enforced in code, not just prompted.
- Runtime bug fixed: `_run_tool` advanced the policy state even when a guardrail/tool rejected the
  call (`finally`); it now advances only on success.
- `DoseEvent.note` added -- `log_dose_event` accepted a `note` but never stored it, so the reason for
  a missed dose was being dropped. Shown in the patient page's dose history.

**Language + "no advice" rules:**
- The agent replies in the patient's language: Hindi/Hinglish (Roman script only, never Devanagari or
  mixed) or English, following them if they switch. Any other language -> it says (fixed line,
  `UNSUPPORTED_LANGUAGE_LINE`) that only Hindi and English are supported and waits.
  Prompt-only did not work (the model kept answering in the Hinglish it opened with, even when the
  patient wrote only English), so the language is decided in code: `domains/med_adherence/language.py`
  classifies each patient message (Devanagari / non-Latin script / Roman-script word-list count;
  undecided -> left to the LLM, e.g. French), and the domain's `prompt_suffix()` -- a new generic hook
  on `AgentContext`, appended to the end of every LLM call's system prompt -- states the language
  flatly each turn. The word lists are a heuristic and will misjudge some inputs.
- **No question in the last message:** once the call is wrapping up (`update_daily_log` /
  `escalate_to_doctor` succeeded), a reply containing "?" is blocked and regenerated
  (`_no_question_when_wrapping_up`), with a fixed sign-off as fallback, since the call hangs up
  right after and the patient can't answer. (Prompt-only had failed here too.)
- **The agent gives no suggestions or advice of any kind for now** -- no medicine/dose/timing advice,
  no remedies or "rest", no what-to-do-about-symptoms, no reassurance about outcomes; asked for
  advice, it says to ask the doctor. Enforced twice: prompt hard rule, and a text guardrail
  (`ADVICE_OR_REASSURANCE_PHRASES`, substring match on deliberately narrow phrases). A blocked reply
  is now regenerated by the model (up to `MAX_BLOCKED_REPLIES`) instead of being replaced by a
  canned apology. This is a POC-stage restriction and may be relaxed later.

**Reminders ("I'll take it later"):** when the patient says they'll take the dose later, the agent
asks when to remind them and calls `reschedule_dose(remind_in_minutes)`, which logs the dose as
not-taken (with a note), stores a `Reminder` (new collection) and arms a timer
(`live_calls.arm_reminder`, `asyncio.sleep`, no scan loop) that starts a new reminder call at that
time -- or, if the patient is mid-call then, retries every 15 s. The agent is told the current local
time so "8 baje" can become minutes. Pending reminders are re-armed from Mongo on startup (ones more
than 30 min late are marked `missed`). Upcoming reminders show on the patient page. Not built:
cancelling/editing a reminder, or the agent rescheduling one *during* a later call.

Verified with scripted patients over the real WebSockets against the live LLM (Gemini). Not yet
covered by `eval/`. The two pages' JS was syntax-checked but not exercised in a real browser.

Known limits (POC): live calls are in-memory only (server restart drops them); no timeout for a
patient who opens the call and never replies (operator must End call); the reminder time is a
whole number of minutes chosen by the LLM. Doctor briefing on escalation is deliberately **not**
built here -- the doctor's role in the final product isn't settled, so `escalate_to_doctor` still
only records the decision (see Chunk 4).

### Chunk 3 — Voice transport swap-in — **NOT STARTED**
Plan: `core/providers/stt.py` + `tts.py` (Sarvam wiring), `core/transport/daily_transport.py`
(wrapping Pipecat's `DailyTransport`), `backend/daily_client.py` + `bot_runner.py` + trigger
endpoint, patient call page embedding Daily's prebuilt UI, `domains/med_adherence/bot.py` extended
with a Daily-transport entrypoint alongside the existing chat one. No changes expected to
`core/agent/policy.py`, `guardrails.py`, or `domains/med_adherence/tools.py`/`policy_states.py`.

### Chunk 4 — Escalation + caregiver + doctor merge (live voice) — **NOT STARTED**
Plan: `domains/med_adherence/escalation_rules.py` extended with the mandatory-escalation guardrail
override tied to real doctor notification (currently `escalate_to_doctor` only records the
decision — see `domains/med_adherence/tools.py`), `notify_caregiver` tool, doctor dashboard
extended with live "Join Call" into the same Daily room, caregiver-notification recording for both
"unreachable" and "escalation" triggers.

### Chunk 5 — Structured extraction polish + eval harness + rehearsal — **NOT STARTED**
Plan: tighten symptom-extraction tool schema, build `eval/scenarios/` (reference-derived +
unreachable-patient + caregiver-notified-on-escalation) and `eval/run_eval.py`, demo rehearsal
checklist.

## Verification approach
No automated UI tests for this POC timeline — verification is live run-throughs of each scenario
plus the Chunk 5 eval harness, which doubles as a panel-visible artifact of evaluation rigor.
