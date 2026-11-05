# VoiceMitra — Plan & Status

This is the living plan for the project: what's being built, why, and what's actually done vs.
not. Update the **Status** section as chunks complete or scope changes — this file is the source
of truth for progress, not chat history.

## Context

VoiceMitra is a voice-first medicine-adherence system for hospitals: patients get called to be
reminded to take medicine, the agent logs whether they took it and how they're feeling, and if
something's wrong it escalates by bringing a doctor live into the same call, with a secondary
caregiver (e.g. an adult child) kept in the loop. (For the pilot there is no doctor: reminders, a call when
the patient doesn't respond, and caregiver alerts -- see "Pilot: patients + caregivers" in Status.) Built as a capstone project — beyond working
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

- **Voice pipeline**: Pipecat (audio I/O only), with LiveKit as the room (Daily was dropped, see Chunk 3).
- **STT/TTS**: Sarvam AI (`SarvamSTTService`/`SarvamTTSService`, built into Pipecat) — best
  Hindi/Hinglish quality, matches `reference_transcripts/` style.
- **LLM (chat-completions)**: swappable via `LLM_PROVIDER` env var in `core/providers/llm.py` —
  Sarvam (`sarvam-105b-conversations`, primary/demo-quality) or Gemini (`gemini-3.5-flash-lite`,
  higher free quota, used to conserve Sarvam credits during iterative chat-based testing). Both
  are OpenAI-compatible chat-completions endpoints, so `core/agent/runtime.py` is identical either
  way.
- **Transport**: LiveKit WebRTC rooms for the POC (native multi-participant rooms make the doctor
  "merge" trivial); Twilio swap-in later via the same `Transport` interface.
- **Data store**: MongoDB via Motor (async). Dates are stored as ISO *strings* (`model_to_doc` dumps in
  JSON mode), so range queries must compare strings.
- **Backend**: FastAPI — API only: JSON (CRUD routers + the screen read-models in `backend/views.py`) and
  WebSockets. It serves no HTML. (The old Jinja pages were deleted on 2026-10-21; see "Web app" below.)
- **Frontend**: Next.js 16 (React 19, TypeScript, App Router) in `web/`. Client-driven screens: SWR for
  data, direct WebSockets for live events, `livekit-client` for the call. The design system is one plain
  CSS file (`web/src/app/globals.css`, palette from the dataviz reference, light + dark). Types are generated
  from the API's OpenAPI schema.

## Data model

Extends the original `reference_transcripts/original_schema.txt` draft:
- `caregiver` is a real entity (name + relation + phone), not a bare number list on `patient`.
- `daily_log.symptoms` is a structured array (name, location, severity, duration_note, raw_quote),
  not free text.
- `call.logs` is a structured transcript+tool-call log (`CallLogEntry`: patient_said / agent_said /
  tool_call with args+result / escalation_call_started / escalation_call_merged), not `list[str]`.
- `call` has `escalation_reason` and `caregiver_notified`.
- `escalation` (new collection): the doctor leg of an escalated call -- status `ringing` -> `briefing`
  -> `merged` -> `resolved` (or `abandoned`), which doctor joined, timestamps, and the agent's summary
  of the merged conversation.
- `caregiver_notification` (new collection): one record per alert sent to a caregiver (delivery is
  simulated; the record is the notification). `urgent` marks the pilot's urgent alerts.
- Care mode (pilot step 2) is one switch for all calls, not stored per patient: `DOCTOR_FLOW_ENABLED` in
  `.env` (off for the pilot: alert the caregiver; on: ring the doctor, the original flow).
- `caregiver_notification.seen_at` (pilot step 3): when the caregiver marked it seen on their page.
- `CallLogEntry` gained a `channel` (`None` = patient<->agent, `doctor_briefing`, `merged`) and two
  types, `doctor_said` and `escalation_summary`, so one call log tells the whole escalated story.

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
    transport/                   # base.py (interface), chat_transport.py + queue_transport.py + hybrid_transport.py (done), voice_pipeline.py + livekit_transport.py (voice)
    providers/                   # llm.py (done, Sarvam+Gemini), stt.py / tts.py (built)
    agent/                       # runtime.py, tool_registry.py, policy.py, guardrails.py, context.py (all done)

  domains/med_adherence/         # prompts.py, policy_states.py, tools.py, guardrails.py,
                                  # escalation_rules.py, context.py, bot.py (all done for chat; voice pending)
                                  # doctor_agent.py (briefing agent + summariser), caregiver.py (done)

  backend/
    main.py, db.py, models.py, queries.py, seed.py, seed_demo.py, live_calls.py, escalations.py
    insights.py                  # dose schedule, adherence, "needs attention" rules (pure, tested)
    views.py                     # read models: what each screen is told (the API contract)
    dump_openapi.py              # writes web/openapi.json for the frontend's generated types
    family_feed.py               # live events for a caregiver's page, keyed by patient (alerts, calls starting/ending)
    routers/                     # patients.py, doctors.py, calls.py (JSON API), live.py (WebSockets + call controls),
                                 # escalations.py (doctor WebSockets + join/end), app_api.py (/api/app/* read endpoints),
                                 # caregivers.py (mark alerts seen + the caregiver WebSocket)

  web/                           # Next.js app: src/app (screens), src/components, src/lib (api, ws, i18n, format, events)
                                 # public/ (icons, service worker, offline page), scripts/make_icons.py
  mobile/                        # native apps (see Pilot status): README.md (start here), API.md (contract), android/ (Kotlin + Compose APK, rings via FCM), ios/ (SwiftUI built with xtool in WSL, CallKit, rings only while open)
  tests/                         # pytest: insights.py, views.py, the dose step, care modes
  package.json, scripts/dev.mjs  # `npm run dev|demo` runs API + web app + tunnel in one terminal; `-- --hot` for hot reload (see README)

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
- **Three server-rendered dashboards** (`backend/pages.py` + `backend/templates/`; **replaced by the Next.js web app and deleted 2026-10-21**, this entry is history):
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

### Doctor escalation flow (text chat) — **DONE**, verified by scripted runs and **tested by the user by hand (2026-11-03): working**
Built ahead of voice (Chunk 4's doctor/caregiver logic, on the chat transport) so the flow is demoable
now and maps onto a Daily room later. The flow:

1. The agent escalates (LLM `escalate_to_doctor`, or the red-flag forced-action guardrail). The patient
   hears a **fixed hand-off line** and is **held on the line** (their call is not ended: new generic
   `AgentContext.hands_off_transport()` hook makes the runtime skip `transport.end()`).
2. The patient's doctor(s) get an **incoming call** on their dashboard, pushed over `/ws/doctors/<id>`:
   patient name + id only (like a phone ringing), pulsing card, **Join call** button. First doctor to
   join wins (claimed before any `await`); others' cards clear.
3. Join opens `/doctors/<id>/escalations/<esc_id>`: a **private chat between the doctor and the agent**
   (patient still on hold). The agent (`domains/med_adherence/doctor_agent.py`, same core runtime /
   policy engine / guardrail pipeline, its own tool registry + states) sends a brief written from the
   records (patient, allergies, prescription, today's transcript, recent doses/logs, escalation reason),
   answers the doctor's questions from those records only ("not recorded" otherwise), and asks whether
   to merge.
4. The doctor says merge -> the agent calls `merge_call`. **Guardrail:** `merge_call` requires
   `doctor_confirmation_quote`, which must be words from the doctor's *latest actual message* -- the LLM
   can't merge on its own or on a mere question (no keyword-list NLU). Then the patient's chat
   unlocks; doctor and patient talk directly (relayed by `backend/escalations.py`, not the LLM). The agent
   stays on the line, silent, and the patient is told it stays on to take notes.
5. Either side ends (doctor **End call**, or operator **End call**). The agent summarises the merged
   conversation (`Concern / Doctor's instructions / Follow-up`) into `Escalation.summary` and the call log
   (`escalation_summary`); the whole thing (briefing Q&A, merge, relay, summary) is in the call log,
   tagged by `channel`.
6. **Caregiver** is notified automatically on escalation (`domains/med_adherence/caregiver.py`, called
   from `escalate_to_doctor` -- deliberately *not* an LLM-callable tool, so the agent can't skip or spam
   it): a `CaregiverNotification` record shown on the patient/family page and `Call.caregiver_notified`.
   Respects `Caregiver.notify_on`. Delivery is simulated (no SMS/WhatsApp).

Other paths handled: no doctor assigned to the patient (patient told the hospital will follow up,
call ends, escalation `abandoned`); operator ends the call while ringing or during the briefing
(`abandoned`, patient told, ring cards cleared, late join -> 410); doctor rejoin/reload (snapshot
resend); patient replies while on hold are dropped; escalations still open at server start are marked
`abandoned` (`escalations.abandon_stale`).

**Bug found and fixed during testing:** the LLM-written hand-off line came out as medical advice
("go to the hospital right away...") -- the exact thing the no-advice rule forbids -- and the phrase-list
guardrail missed it. The hand-off line is now decided in code (`_fixed_handoff_line` text guardrail,
`HANDOFF_LINE_*` in `prompts.py`), Hinglish or English by the patient's language.

Verified against the live LLM (Gemini) over the real WebSockets in an isolated `voicemitra_test` DB
(since dropped): full happy path, operator-ends-while-ringing, doctor-leaves-during-briefing (a "wait,
what dose is he on" question did not trigger a merge), no-doctor patient, 403 for a non-assigned
doctor, 410 for a late join; unit checks for the `merge_call` guardrail and the doctor policy. The new
pages' inline JS was syntax-checked (`node --check`) but **not exercised in a real browser**.

Known limits (POC): no ring timeout (a patient stays on hold until a doctor joins or the operator ends
the call); live state is in-process (a restart drops open escalations); the brief and the summary are
LLM-written from the records with only prompt + a diagnosis/dosage-phrase check behind them (a summary
can miss a follow-up the doctor mentioned, e.g. "I'll call the hospital"); doctors aren't
authenticated; the caregiver is told on escalation whether or not a doctor ever connects; the
`unreachable` caregiver trigger (patient never answers) isn't built.

### Chunk 3 — Voice transport swap-in — **DONE (first end-to-end voice call verified by hand)**
Built: `core/providers/{stt,tts}.py` (Sarvam via Pipecat; STT uses Sarvam's server-side VAD, mode
`codemix`; TTS Bulbul v3 `hi-IN`), `core/transport/voice_pipeline.py` (`VoiceTransport`: a `Transport`
wrapping the pipeline room in -> Sarvam STT -> bridge -> Sarvam TTS -> room out; the bridge turns final
transcripts into `receive_text` and tracks bot speech so hang-up waits for the closing line),
`core/transport/livekit_transport.py` (the Daily transport was deleted 2026-10-21: see below),
`backend/livekit_client.py` (mints the agent's and the patient's room tokens),
`domains/med_adherence/bot.run_voice_call`. Backend: `POST /api/patients/<id>/voice-call` starts the
agent in-process (`live_calls.start_voice_call`), operator **Voice call** button, and the patient page
joins the room with `livekit-client` (CDN) and plays the agent. No changes to `core/agent/` policy/
guardrails or the domain tools.

**Design decisions:** Pipecat is used only for audio I/O; the existing turn loop (`run_chat_session`)
still drives the agent. **Daily -> LiveKit:** Daily was the first choice, but `daily-python` has no
Windows wheels (tried a Docker worker, which worked up to the join) and Daily rejected joins with
`account-missing-payment-method`. LiveKit installs natively on Windows, has a free cloud tier, and is a
multi-party room, so the Chunk 4 doctor merge still fits. Swapping is one class thanks to `Transport`.

Verified: a real spoken call over LiveKit (browser mic -> Sarvam STT -> agent -> Sarvam TTS), running
through dose logging and an escalation to the end-call tool. Not yet assessed: Hinglish STT/TTS quality,
latency. (Barge-in was believed "off" here, but the flag used was a no-op -- see "Voice feel fixes"
below; it is now really on.) Not done: voice calls are tracked only as in-memory patient/operator
events (no live-call object like chat has), reminders started chat calls (voice since B4, 2026-11-04), a patient who never joins
ends the call after 120 s.

### Chunk 4 — Escalation + caregiver + doctor merge (live voice) — **DONE: user tested the doctor escalation by hand (2026-11-03), working**
(For the pilot the doctor is out of the loop -- see "Pilot: patients + caregivers" below. This flow stays in the code.)
The text-chat escalation flow (above) now also runs on a voice call. After the agent's hand-off line the
patient stays in the LiveKit room on hold (`VoiceTransport.set_sink` makes the agent stop listening);
the doctor's dashboard rings and they brief privately with the agent (text only at first; now spoken too,
see "Voice feel fixes"). When the doctor
confirms the merge, their page joins the patient's room with a mic (`escalations._merge` mints a doctor
token, `voice_join` event) and doctor and patient talk directly. The agent stays in the room silently: the
voice pipeline has one Sarvam STT per participant identity (`patient`, `doctor`), so each utterance is
attributed and lands in `Escalation`'s transcript, the call log (channel `merged`) and live captions on the
doctor's page; on hang-up the existing summariser writes the summary. Either side leaving the room (or the
operator's End call) ends the escalation. New: the `unreachable` caregiver trigger -- if the patient never
joins within 120 s, the caregiver is notified (`caregiver.notify_caregiver_unreachable`).
Files: `core/transport/voice_pipeline.py` (per-speaker STT), `backend/escalations.py` (voice branches,
`_room_left`, `_on_room_speech`), `backend/live_calls.py` (`VoiceCall` carries the transport and
escalation state through hand-off, `finish_voice_call`), `backend/livekit_client.py` (`doctor_token`),
`escalation_call.html` / `_chat_widget.html` (LiveKit join, status text).
Not tested yet: everything above with real audio. Known risks: doctor and patient in the same physical
room/browser will feed back; the doctor STT idles until the merge (keepalive is set); caregiver alerts
are still records, not real SMS/WhatsApp. (The briefing used to be typed only; that and the doctor's
silent mic were found in the first hands-on test and addressed below.)

### Voice feel fixes (2026-10-21) — **BUILT; barge-in tried by the user (2026-11-03)**
User test: interrupting the agent worked and conversations were decent. Not checked: whether the agent
knew where it was cut off (the heard/unheard split). Good enough for now; deeper testing deferred.
Triggered by a hands-on call: the agent couldn't be interrupted, opened with one very long turn, spoke bad
Hindi, and on escalation the doctor got a text-only briefing and -- after the merge -- the doctor could
hear the patient but the patient couldn't hear the doctor and the doctor's speech wasn't transcribed.
- **Barge-in was dead.** `PipelineParams(allow_interruptions=False)` doesn't exist in the installed Pipecat
  (1.11), so it did nothing; and nothing in our pipeline turned Sarvam's `ProposedUserStartedSpeakingFrame`
  into an interruption. Now the patient's STT branch has a `UserTurnProcessor(ExternalUserTurnStrategies())`
  (no local VAD/turn model; Sarvam's server VAD decides). Only the patient can cut the agent off, not the
  doctor on a merged call.
- **The agent knows where it was cut off.** A `_SpeechTracker` after `room.output()` sees each
  `TTSTextFrame` (Sarvam TTS has no word timestamps, so one per *sentence*, emitted when that sentence has
  finished playing). On interruption `VoiceTransport` records `heard` (sentences fully played) and `unheard`
  (the rest) -> `Transport.take_interruption()`. `run_chat_session` rewrites the last assistant message to
  just the heard part + "[cut off]" and prefixes the patient's reply with what they did / didn't hear;
  `context.record_interruption` logs it. Granularity is a sentence: a sentence cut half-way counts as
  unheard (the agent may re-say it, never assumes it was heard).
- **Short staged opening.** `policy_states.DOSAGE_CHECK`: turn 1 is only the greeting + "am I speaking to
  X?", the dose question comes after they confirm; wrong person -> ask for the patient, no health talk.
  Base prompt: ~15 words, one question per turn, drop what you were saying if talked over.
- **Hindi.** The TTS voice (`ritu`) is female but the prompts were masculine ("kar raha hun") and used SMS
  spellings ("kr rha h"). Persona is now feminine, with clean example lines and spelling rules (Roman
  script kept -- decision: guardrails/language-detect/escalation keywords are Roman-based; Devanagari
  would be a rework). `HANDOFF_LINE_HINGLISH` fixed. TTS pace now `SARVAM_TTS_PACE` (default 0.9).
- **Doctor voice briefing.** On a voice call, `escalations.join` builds a second LiveKit room
  (`<room>-brief`, `livekit_client.create_briefing_room`) and runs the briefing over a `HybridTransport`
  (`core/transport/hybrid_transport.py`): agent lines always appear as text and are spoken once the doctor
  joins the room (earlier lines are spoken on join), replies can be typed or spoken (spoken ones are echoed
  as captions); the text `QueueTransport` outlives it and keeps carrying merged-call captions. If the voice
  leg can't be built it falls back to text. The doctor agent's prompt is now written for the ear and
  feminine. At merge the page leaves the briefing room and joins the patient's.
- **Doctor mic on the merged call.** Most likely cause of the silent doctor: the page set `voiceRoom` before
  connecting, so a failed `setMicrophoneEnabled` left the doctor connected as a listener only, with the
  error on a status line that later updates overwrote and a guard that blocked retry. `escalation_call.html`
  now joins from a **Join voice** button (user gesture), probes `getUserMedia` first, verifies the mic
  track was actually published, shows failures next to the button and allows retry. Server logs
  `first audio frame from <speaker>` and `transcript from <speaker>`: a speaker missing from the first is
  not publishing; present there but no transcript means STT. **Cause not confirmed on a live call.**
- Risks/untuned: a cough or noise can cut the agent off (Sarvam VAD sensitivity; tune e.g. a min-words
  start strategy); a doctor/patient on one machine will feed back; barge-in latency is Sarvam's VAD;
  merging while the doctor's briefing-room join is still connecting can drop the merged join (rare).

### Fixes after first hands-on voice test (2026-10-13)
- **Mic before room:** the patient page now calls `getUserMedia` *before* joining the LiveKit room
  (`_chat_widget.html`). Before, the agent greeted as soon as the page joined, while the browser's
  mic prompt was still open, so the first answer was lost/garbled.
- **Under-rated symptoms never escalated:** two real calls ("bahut khansi/jukam" + fever, then cold/cough/
  headache/body pain, both for 2 days) were logged with every symptom `mild` and seriousness 3-4 -- the
  patient's "bahut" was dropped and nothing connected the score to escalation (>4 only flipped
  `patient_status`). A keyword rule was tried and **removed** on purpose: urgency should be the LLM's
  judgment, not substring lists. Instead the LLM is told how to score (anchored 1-10 scale in the
  `seriousness` field description and the symptom_check prompt; patient intensity words taken at face
  value) and a **three-tier guardrail** on the LLM's own score (`_serious_needs_escalation`): 1-4 just
  logged; 5-7 (`OFFER_DOCTOR_AT_SERIOUSNESS`) the agent must first ask the patient whether they want the
  doctor -- yes -> `escalate_to_doctor`, no -> `update_daily_log` with `patient_declined_doctor_quote`
  (must be words from the patient's latest message, same trick as `merge_call`); 8-10
  (`ESCALATE_AT_SERIOUSNESS`) `update_daily_log` is rejected and it must escalate. The LLM still decides
  the score; code only enforces what follows from it. Existing `RED_FLAGS` list unchanged. Guardrail
  unit-checked, **not yet tried on a live call**; thresholds and score anchors are untuned (see the
  confidence-gated plan below). Weakness: the quote check proves the words came from the patient's last
  message, not that they mean "no".
- **User test (2026-11-03): escalation felt inconsistent and keyword-driven** -- "severe headache" did not
  escalate while other symptoms did. Cause, from the code: there are two separate paths. (1) `RED_FLAGS` in
  `escalation_rules.py` is a substring list (chest pain, breathlessness, fainting/"chakkar", bleeding, allergic
  reaction); a match forces escalation no matter what the LLM thinks (`context.py` -> `_forced_escalation`).
  Headache is not on it. (2) Everything else rides on the LLM's 1-10 score, and 5-7 only *offers* the doctor.
  So the user's impression was right for the red-flag path, and a "severe headache" likely scored 5-7 (offer)
  or lower. To be replaced by the LLM-judged approach below.
- **Live transcript on voice calls:** the patient's voice card shows the call-log entries as they are
  recorded: agent lines, what the STT heard, every tool call (name, args, result, block notes), the
  escalation events, and -- after the merge -- the doctor's and patient's transcribed words. The domain
  `CallContext.on_log_entry` hook feeds `live_calls.add_voice_entry` (`log_entry` event); `VoiceCall.entries`
  keeps them so a reloaded page gets the whole call in its snapshot, and the card stays on screen after the
  call ends. The doctor's private briefing chat is not shown to the patient. The call log still reaches
  Mongo when the agent's part of the call ends (plus merged-phase entries as they happen), so mid-call the
  source for a reload is memory, not Mongo. Before this, merged-call speech reached only the doctor's page,
  never the patient's.
- **False promise removed:** the normal sign-off said "Doctor ko update kar diya jayega" though
  nothing notifies a doctor on a non-escalated call; the `closing_normal` prompt now forbids that.
  Open idea: flag seriousness>=3 logs on the doctor dashboard.

### Web app (2026-10-21) — **BUILT AND VERIFIED IN A BROWSER; the user has since run a doctor escalation and voice calls through it (2026-11-03)**
Why: the backend-served Jinja pages were a cluttered dump of tables (one template served patient, doctor
and operator with flags) and not installable. Replaced by a separate frontend, `web/` (Next.js), with the
backend reduced to an API.
- **Roles, no accounts (decision):** the first screen asks who you are (patient / doctor / staff); the choice
  is kept in `localStorage` so the installed app opens straight to its home. Not security: anyone can pick
  anyone. Staff open a patient's app with `?preview=1` so that doesn't overwrite their own remembered role.
- **Patient app** (`/patients/[id]`, mobile-first, Hindi + English): Today = one big "Talk to VoiceMitra"
  button, next dose, today's medicines with state chips, the week at a glance, how you're doing, reminders;
  Medicines (schedule in words, days left, 7-day meter); History (timeline of check-ins, conversations, family
  alerts); Me (language, install, switch user). The call is a full-screen sheet owned by `CallProvider` in the
  layout, so it survives tab changes; raw tool calls are never shown to patients. Installable PWA (manifest,
  icons, service worker, offline page; service worker is production-build only).
- **Doctor app** (`/doctors/[id]`): overview built around "who do I look at now" -- tiles, a Needs-attention list
  with the reasons in words, Stable patients, recent escalations; the incoming-call ring is in the layout so a
  call can be picked up from any screen. Patient record (`PatientClinicalView`): flags + allergies first,
  headline numbers, 14-day dose grid (with the reason for each missed dose), symptoms with a seriousness chart
  and timeline, prescriptions (add one), calls/escalations/family alerts. Live call screen: steps (Briefing ->
  On the call -> Summary), conversation, patient context beside it; voice join is button-driven, probes the mic
  and **verifies the mic track was published** (the earlier silent-doctor bug), with errors shown. A finished
  call shows its saved summary.
- **Operator** (`/operator`): roster with live call controls (voice / chat / end), add patient, manage a patient
  (the same clinical view).
- **Backend:** `insights.py` (a dose with no check-in is "no check-in", never "missed"; events are matched to
  the nearest slot of the day, latest wins; attention rules) and `views.py` (one read model per screen),
  exposed under `/api/app/*`. 14 pytest tests cover both. Found and fixed on the way: date range queries
  matched nothing because dates are stored as strings.
- **Run:** `npm run dev` (or `demo`, see README) starts API (:8000), web app (:3000) and the tunnel in one
  terminal with prefixed logs, Ctrl+C stops all of it (`scripts/dev.mjs`, built on `concurrently`; Turborepo was
  rejected, it is for JS-package builds, not a Python API + Next app). **The web app is built and served by default**
  (hot reload, `next dev`, was too slow to load pages); `-- --hot` / `npm run dev:hot` switches to hot reload, and the build is
  skipped when no web source file is newer than `.next/BUILD_ID` (`-- --rebuild` forces it). Hot mode removes any leftover
  service worker/cache from an earlier built run (verified; first version raced with the old worker re-creating its cache).
  The API always runs with `--reload`; one public hostname,
  `test-voicemitra.apoorvm.com`, routes `/api`, `/ws`, `/health` to :8000 and the rest to :3000 (Cloudflare
  ingress rules). Verified through the public URL: pages, API, a live WebSocket, active service worker,
  manifest, no console errors. the `demo` commands use `voicemitra_demo` (`backend/seed_demo.py`: five patients
  incl. a resolved emergency; refuses to wipe the real database).
- **Verified:** 20 scripted browser checks (identity, Hindi/English, patient tabs, doctor overview + adding a
  prescription, operator adding a patient); `next build`, lint and typecheck clean.
- **Not verified / known gaps:** a real voice call and a real escalation + merge through the *new* screens
  (the old pages are the only ones proven with real audio); the iPhone install path (manual Share steps);
  Hindi strings were written by the assistant and need a native read; no auth; times use `APP_TIMEZONE`
  (default Asia/Kolkata) which is one zone for everyone. ("Every X days" now has an interval: pilot step 1.)
- **Cleanup done (2026-10-21, with the user's go-ahead):** deleted the old UI (`backend/pages.py`, `backend/templates/`,
  `backend/static/`, the `/static` mount, the page-only helpers in `queries.py`, and the `jinja2` / `python-multipart`
  dependencies), `run_backend.bat` and then `run.bat` (replaced by the npm scripts), the Daily transport, the Next.js starter boilerplate and the
  unused Jinja helper draft. **The old pages were the only UI proven with real audio, and they were deleted before the new
  screens had a real call run through them** -- the user chose this over waiting; `git log` has the old call/voice-join
  code (`_chat_widget.html`, `escalation_call.html`) to compare against if a call misbehaves.

### Web visual redesign (2026-10-21) — **BUILT, build/tsc/eslint pass; seen by the user**
User's verdict (2026-11-03): doesn't like the look, but fine for piloting. No further redesign planned.
Restyled the Next app from three reference designs (soft sage palette, large rounded cards, pill nav with a
green active tab, dark-green primary button, floating pill tab bar on mobile). Only patterns that map to our
screens were taken; AI-assistant, shift, billing, vitals and capacity widgets were deliberately left out.
Plus Jakarta Sans + Noto Sans Devanagari via `next/font`; green brand accent, dark-green primary action;
status colours still reserved for state and always icon + word. Doctor overview tiles gained icons and the
header shows the date. Token-level change in `web/src/app/globals.css`; markup changes limited to the doctor
overview, the new-patient form and brand-mark sizing. Also applied Web Interface Guidelines fixes
(focus-visible, explicit transitions, reduced motion, `touch-action`, form `autocomplete`/`inputMode`,
`translate="no"` on the brand).

### Operator fixes after first hands-on look (2026-10-21) -- **BUILT; checked by script + tsc/eslint, NOT YET SEEN IN A BROWSER**
- **Patient tab bar:** "Me" stayed lit on the Medicines tab (`/medicines`.startsWith(`/me`)); tabs now match whole path segments.
- **Doctors + editing:** there was no way to assign a doctor (`Doctor.patient_ids` is the link, and an escalation rings
  whoever lists the patient) or to edit a patient after creating it. Backend: `doctor_ids` on create,
  `GET /api/patients/{id}/profile`, `PATCH /api/patients/{id}` (only sent fields change; `caregiver: null` removes the
  contact; `doctor_ids` replaces the set). Web: shared `PatientForm` (doctor checkboxes, family contact) used by
  Add patient and the new `/operator/patients/[id]/edit`, reached from "Edit details & doctors" on the manage page.
  Not built: adding/editing doctors themselves, deleting a patient.
- **Slowness (diagnosis, not fixed):** locally the API answers in ~20 ms and pages in ~6 ms; through the Cloudflare tunnel
  every request costs 0.3-1.1 s, so each screen (page + data call) takes 1-2 s. Fix options: use `localhost:3000` on the
  PC, and fewer sequential requests per screen (e.g. preload data on hover/prefetch).

### To-do (after the pilot): confidence-gated, LLM-judged escalation — **NOT NOW**
**User decision (2026-11-03):** no keyword search and no word cues of the "'bahut' -> 5-7" kind (today's
`seriousness` field description in `tools.py` has exactly that cue, and `RED_FLAGS` is a substring list --
both go). The agent should decide whether escalation is needed and say how confident it is. This is our own
logic, not `pipecat-guardrails` (that package is for output only). Idea:
- Have the LLM return, for each symptom report, `should_escalate` plus a **confidence score** (and its
  reasoning), e.g. via a structured tool/JSON output.
- **High confidence** -> follow the LLM (escalate, or don't). **Low confidence** -> fall back to a second
  check: a rules pass, a second LLM opinion, or ask the patient one more clarifying question.
- **Few-shot examples** in the prompt (user idea, 2026-11-03): labelled cases (what the patient said ->
  decision + short reasoning) to anchor the judgment and cut run-to-run variance. Keep them varied so the
  model learns the reasoning, not trigger words, and keep them **separate from the eval scenarios**
  (otherwise the eval tests the examples it was shown).
- Keep the code guardrails as a hard backstop only for the unambiguous red flags already listed.
- Build `eval/` scenarios around it (e.g. heavy fever + cough 2 days must escalate; mild cough must not)
  and measure how confidence correlates with correct decisions before trusting a threshold.

### To-do (not now): move output guardrails to `pipecat-guardrails`
The user maintains `pipecat-guardrails` (PyPI, 0.3.0, sibling folder `../pipecat-guardrails`), built for this
project. It has rules (banned terms with a Hinglish word pattern, regex, PII, India pack), yes/no
**policies** answered by a classifier -> LLM-judge cascade with confidence thresholds (`block_above` 0.8 /
`allow_below` 0.2, the judge decides in between), shadow mode, `guard.check()` for apps that run their own
LLM loop (this one does), and an `eval` command.
- **Fits:** our text checks on what the agent says -- `_no_dosage_change_or_diagnosis`,
  `ADVICE_OR_REASSURANCE_PHRASES` -- become package rules plus policies ("does this reply advise on
  medication?"), replacing the narrow phrase lists. Wire `guard.check()` into
  `GuardrailPipeline.check_text`; the tool-call checks and `_fixed_handoff_line` / `_no_question_when_wrapping_up`
  stay ours (they depend on call state, not text).
- **Escalation is not the package's job (user decision, 2026-11-03).** The package is for output only;
  judging what the patient said and whether to escalate stays our own logic (see above).
- Pipecat: the user thinks 1.11 should work with the package, but its `pyproject.toml` pins
  `pipecat-ai>=1.12`, so either the pin is relaxed or VoiceMitra upgrades (the user is fine upgrading).
  Re-test the voice pipeline after either. **To-do, not now.**

### Other to-dos (not now)
- **Eval harness** (Chunk 5) -- wanted, built together with the LLM-judged escalation, since that is what it
  has to measure. Design notes (non-determinism) under Chunk 5.
- **Login / accounts** -- deliberately last, once everything else is final (it slows development). Until then
  the app is not for strangers: anyone can open anyone's records, and prescriptions are health data.
- **Barge-in depth** -- check the agent knows where it was cut off.
- **Hosting** -- the backend can move to AWS (or similar) instead of the home PC; needed anyway once
  reminders must fire while the PC is off, and WhatsApp webhooks need a stable public URL.

### Pilot: patients + caregivers, no doctor — **IN PROGRESS: steps 1-3 of 9 done** (user's first priority, 2026-11-03)
There is no doctor available for a pilot, so the pilot runs patient + caregiver only. The doctor escalation
flow stays in the code (tested, working) but is **turned off** (user, 2026-11-03: "turn off the doctor flow as
of now, don't show the option"): backend `DOCTOR_FLOW_ENABLED` (unset = off) and web `src/lib/features.ts`
`DOCTOR_FLOW = false` -- change both together to bring it back. While off: every call uses the caregiver path,
the doctor role is gone from the start screen (and `/who/doctor`), and the patient form doesn't show doctor
assignment. The `/doctors/*` pages still exist for anyone who already has that link.

**The flows the user wants:**
- **Agent-initiated calls (outbound):**
  - *Reminder:* at dose time the patient first gets a notification ("Taken" / "Not yet"). "Taken" logs the
    dose, done. **No reply within 5 minutes** (decided 2026-11-03; a setting) -> the agent calls. The call
    knows which medicine(s) and which time, asks whether they were taken.
  - *Wellbeing* (decided 2026-11-03) -- the patient shouldn't recount their day on every call:
    - **one dose slot a day** -> asked inside that reminder call;
    - **several slots a day** -> at most **once a day** (e.g. the first call of the day), a second time only
      if needed (e.g. a symptom was reported earlier that day);
    - **less than daily** (e.g. a weekly medicine) -> a **standalone check-in call** every N days (per-patient
      setting, e.g. 2) at a time the patient chooses.
- **Patient-initiated calls (inbound):** the patient taps "Talk to VoiceMitra" to ask about a medical issue or
  just to talk. Today that button starts the same reminder script; it needs its own open-ended flow (answers
  about *their own* prescription from the records are fine; still no advice). Symptoms go through the same
  "not well" handling.
- **Not feeling well:** log it, tell the patient the caregiver is being informed, and alert the caregiver
  (in-app first, WhatsApp later) with what the issue is -- "if needed", using the current seriousness score
  as the interim rule until the LLM-judged escalation replaces it. **Urgent:** also call the caregiver.
- **Prescription entry** by the patient or caregiver, **both** a photo upload and manual typing (decided
  2026-11-03). The upload may be rough at first and improved later; the dose schedule comes from it.

**Platform -- OPEN DECISION (user, 2026-11-03):** patients and caregivers may be on iPhone or Android; the user
has no Mac. Go with a PWA only if it gives the features needed, otherwise apps; Android-only is not
acceptable, and WhatsApp-only would be preferred over that. Findings:
- **PWA (today):** no install friction on Android, works now. iPhone: push only after "Add to Home Screen"
  (iOS 16.4+), no action buttons on Safari web push (tapping opens the app instead), no silent push. On both:
  no phone-style ringing screen -- a "call" is a notification the patient must tap.
- **React Native + Expo (cross-platform):** iOS builds run on Expo's cloud Macs (EAS Build), submitted to
  TestFlight from Windows; Android ships as an APK. Gives a real ringing call screen (CallKit on iOS,
  ConnectionService on Android, VoIP push) and notification buttons on both. LiveKit has a React Native SDK.
  Reuses TypeScript/React and the generated API types. Costs: Apple Developer Program ($99/yr) for TestFlight,
  a second frontend codebase (the web app stays for operator/doctor screens).
- **Flutter:** iOS builds need a Mac or a paid cloud CI (e.g. Codemagic); new language (Dart); little reuse.
- **Native Swift + Kotlin:** two codebases. **xtool** (open source) builds and signs Swift apps on Windows via
  WSL and installs them on your own iPhone -- fine for experiments, but free signing expires after 7 days and
  sharing with pilot users still needs the paid account + TestFlight (App Store upload still goes through a
  Mac); it is reverse-engineered, so terms-of-service risk.
- **WhatsApp-first:** nothing to install, most patients/caregivers already have it. Reminders as utility
  templates with "Taken" / "Not yet" buttons, caregiver alerts as messages, prescription photo sent in chat.
  Calls: WhatsApp Business Calling API; Pipecat has a WhatsApp transport for **inbound** calls (patient calls
  the number); **outbound** (agent calls patient) needs the user's call permission first, has rate limits,
  and isn't in Pipecat's transport (own signaling via the Graph API). Costs: Meta business verification,
  template approval, per-message/per-minute charges. Fits the `Transport` interface (a real demo of the swap
  path). Screens that need more than chat (caregiver overview, reviewing an extracted prescription) stay on
  the web.
- **Second round (2026-11-03), the user's requirements:** no money for now (no Apple $99/yr, no Play Store fee);
  must ring like a normal call (full screen, swipe to answer) on **both** iPhone and Android, nothing to open
  first -- users are elderly and only know how to answer a call; WhatsApp is fine only if (nearly) free.
  - PWA: can't ring at all (a notification only). Rejected for the call itself.
  - Own app: Android can ring for free (sideloaded APK, free FCM push, full-screen call screen); **iPhone can't
    without the paid account** -- a free Apple ID gives no push/VoIP push and installs expire after 7 days.
  - WhatsApp calling: rings like any WhatsApp call on both, no install. Not free but cheap: needs a payment
    method on the Meta account; business-initiated calls to India ~Rs 0.47/min (third-party figure, check
    Meta's rate card), the one-time "allow calls" request and reminder templates ~Rs 0.12-0.15 each, calls
    the patient makes to the number are free. ~10 patients x 2 calls/day x 2 min ~ Rs 600-700/month. Meta's test
    number (up to 5 recipients, no payment method needed for messages) for development. Pipecat's WhatsApp
    transport only answers inbound calls; outbound needs our own Graph API signalling.
    Free allowances (checked 2026-11-03, Meta docs): no free calling minutes; user-initiated calls free;
    1,000 free service messages (free-form replies inside the 24 h window) per number per month; utility
    templates inside the window are **charged again since 2026-10-01**. A user call or message opens/refreshes
    the 24 h window. Business-initiated calls have an unpublished 24 h connected-call limit.
    Near-free pattern: at dose time send a free-form message ("tap to call") inside the open window, the
    patient taps call -> a free inbound call (Pipecat's transport supports it). Costs nothing while the
    window stays open; a ~Rs 0.12 template reopens it if a day is missed. One tap, not a ringing call.
  - Regular phone call (Twilio): ~$0.05/min to Indian mobiles once paid. **The free trial can't run the
    agent:** it strips `<Stream>` (the audio stream Pipecat's Twilio transport uses), and allows only 75 voice
    minutes total, 30 days, 5 verified recipients, 10 min/call, 5 concurrent, calls within the sign-up
    country only, from a shared trial number. Corrects the earlier "start on the Twilio trial" advice.
  - Revised advice: WhatsApp. Either the near-free "message -> patient taps call" pattern, or pay ~Rs
    600-700/month for 10 patients for real ringing calls.
  - Native apps (2026-11-03): Android rings the way WhatsApp does (FCM high-priority push -> full-screen
    call screen); free. iPhone without the paid account gets no push at all, so the server can't wake the
    app. But dose times are known ahead, so the phone can ring itself: **AlarmKit** (iOS 26+, iPhone 11 and
    later) alarms ring full-screen on the lock screen even on silent, and their button can open the app.
    AlarmKit has no entitlement, so it should work on a free account -- **unverified, test first**. Backups:
    the free Linphone SIP app (has VoIP push via sip.linphone.org; unverified), keeping the app alive in the
    background (fragile), or the $99/yr account.
- **Tried and dropped (2026-11-03/04): Linphone for the iPhone ring.** Plan was LiveKit SIP dialling the
  patient's free sip.linphone.org address. Built a dial-out (`dial_sip` with the trunk settings inline, a
  "hold the greeting until answered" gate in `VoiceTransport`, dialled calls hidden from the patient page) and a
  bare count-to-20 test. Result: the iPhone rings in 1-2 s (login and Linphone's push work), but LiveKit's
  `sip.callStatus` never leaves `dialing` -- no 180/200 comes back; answered calls are silent and drop with 603
  (or 480) -- with encryption on or off, over TLS or TCP. A plain Linphone-to-Linphone call (PC -> iPhone) also
  had **no audio**. Parked, and **the SIP code was removed** (user, 2026-11-04). Worth knowing if SIP comes back:
  LiveKit puts a dialled line in the room while it's still ringing (the agent must wait for `sip.callStatus ==
  active`); the SDK's `outbound_trunk_config=` fails (protobuf won't assign a message field -- copy it into
  `request.trunk`); the patient's web page auto-joins any voice call as `patient` and would push a phone out;
  LiveKit Cloud's free plan includes 1,000 third-party SIP minutes a month. Researched alternatives: Zoiper (free
  version has no push), Groundwire/Acrobits ($9.99/$6.99 once, reliable push), Zadarma (free PBX + app, free
  internal calls, iPhone push unconfirmed, top-up every 3 months), Exotel (7-day trial -- rejected by the user),
  Telnyx/Plivo/Vonage trials (only own/verified numbers).
- **DECIDED (user, 2026-11-04): native apps, specced in `mobile/`** (`mobile/README.md` is the entry point):
  - **Android** (`mobile/android/SPEC.md`) -- **make it perfect, the main demo**: Kotlin + Compose, sideloaded
    APK, FCM high-priority push -> full-screen call screen even when locked; answer -> join the LiveKit room.
    Its agent also owns the backend pieces both apps need: pairing + devices, join info, the ring push,
    reminders ringing the phone, then dose-time ringing + one retry (pilot steps 4-5).
  - **iPhone** (`mobile/ios/SPEC.md`) -- **rings only while the app is open** for now (free Apple ID = no
    push): SwiftUI built with xtool (WSL), CallKit screen from the patient socket's `voice_call` event,
    installed on the household phones through SideStore. Closed app -> the existing 120 s wait, then the
    caregiver's "couldn't be reached" alert.
  - Contract: `mobile/API.md`. Agents: the user starts one lead agent that runs an Android agent and an iPhone
    agent in this checkout (no worktrees, nobody commits; strict file ownership -- see `mobile/README.md`).
  - Later for a closed iPhone: Zadarma (untested), Groundwire, AlarmKit, or Apple's $99/yr account.
  - **Build status: STARTED (2026-11-04)** -- lead agent running the Android agent (backend B1-B3 first, then
    the app) and the iPhone agent (toolchain check I1 first). Per-step status lives in each `SPEC.md`; done
    steps are mirrored here.
    - **B1 pairing + devices -- DONE (2026-11-04).** `Device` / `PairingCode` models, `backend/routers/devices.py`
      (pair, check, update push token, unpair, list a patient's phones; 429 after too many wrong codes), web
      "Connect a phone" card on the patient's Me tab (big code, countdown, "Phone connected", Hindi/English).
      `mobile/API.md` updated (`expires_in`, `GET /api/devices/{id}`, 401/404 = forget pairing). Verified: pytest
      48/48 (9 new, throwaway DB); tsc + lint clean. Not yet seen by the user.
    - **B2 join info -- DONE (2026-11-04).** `GET /api/patients/{id}/voice-call` -> `{call_id, url, token}` / 404;
      `POST .../voice-call` takes an optional `X-Device-Token`. Covered by the tests above.
    - **B3 ring push -- DONE in code (2026-11-04), not yet tried against real FCM.** `backend/push_fcm.py`
      (`firebase-admin`): a `ring` data message (high priority, TTL 60 s) to the patient's Android phones when a voice
      call starts (except the phone that started it), and a `call_ended` one when it ends so a ringing phone stops;
      unregistered tokens cleared; no `FIREBASE_CREDENTIALS` -> skipped with a log line. Verified: pytest 53/53
      (5 new, fake sender). Firebase set up by the user (2026-11-04): project `voice-mitra`, `google-services.json`
      in `mobile/android/app/` (gitignored), service-account key outside the repo in `C:/Users/apoor/keys/voicemitra/`,
      `FIREBASE_CREDENTIALS` in `.env`; a dry-run send confirmed the key authenticates with FCM. A real ring still
      needs the app on a phone.
    - **App login (username + password) -- DONE (2026-11-04; user: "the user should simply use it by logging
      into the app").** Built by a separate login agent: `POST /api/auth/login` returns the same device credentials
      as pairing (everything after sign-in unchanged; log out = unpair). `backend/auth.py` (scrypt + random salt,
      constant-time compare, unknown usernames checked against a dummy hash), `backend/routers/auth.py`
      (PUT/GET/DELETE `/api/patients/{id}/login`, 409 on a taken username, 429 after 20 failures / 10 min counted
      across all phones), logins in their own `patient_logins` collection so no patient response can carry a hash.
      Web: "Phone app login" card on the Me tab (Hindi/English). Pairing stays as the fallback ("Use a code
      instead"). Only the patient apps get login; web roles are still picked by name. Verified: pytest 60/60
      (7 new), tsc + lint clean, card checked in a browser on a throwaway DB. Open: the backend has no way to delete a
      patient yet; if one is added it must also remove the patient's `patient_logins` row, `devices` and unused
      `pairing_codes`. Changing a password doesn't sign out phones already
      in; the 429 limit is global, so 20 wrong tries by anyone pause logins for everyone for ~10 min.
    - **iPhone I1 toolchain -- DONE (2026-11-04): xtool on WSL builds and links the LiveKit Swift SDK**
      (LiveKit 2.19 + its WebRTC and Rust frameworks, iPhoneOS 27.2 SDK from `Xcode_27.2.xip`); no GitHub Actions
      fallback needed. The iPhone is reached from WSL through Windows' Apple Mobile Device Service via a small relay
      (`mobile/ios/tools/muxrelay.py`) -- no usbipd/admin. Not yet verified: signing, installing and launching on
      the phone (needs the user's spare Apple ID via `xtool auth login` and the iPhone plugged in). The app's
      sign-in (login + code fallback), home, ringing and call code (I2-I5) **compiles cleanly** with xtool (arm64
      .app, LiveKit frameworks embedded, bundle id `app.voicemitra.patient`); nothing has run on a phone yet. The user signed xtool in with the spare
      Apple ID (2026-11-04). Signing needs the phone once (Apple won't issue a free profile until a device is
      registered; the first `tools/wsl-build.sh VoiceMitra run` with the phone plugged in does it). Unsigned `.ipa`
      for SideStore builds without a device (`tools/build-ipa.sh` -> `mobile/ios/dist/`, gitignored). I6 SideStore
      steps written in `mobile/ios/README.md`; a 14-item on-device checklist in the SPEC. Review fixes: the socket
      stays open while CallKit's ring banner is up and during a background call (so `voice_call_ended` stops the
      ring), and the mic is asked for on the home screen.
    - **iPhone on-device test -- PASSED the core flows (2026-11-04, user's iPhone, iOS 26.5).** Install via
      xtool, mic prompt, login, staying signed in across relaunch/reinstall, home, **Talk now both ways (speaker and
      earpiece, agent replies in 0.2-0.6 s)**, **Call now from the web rings CallKit while the app is open, answer
      connects, decline ends it**, speaker toggle + hang-up, **call survives the screen locking**. App closed -> no
      ring (expected; accepted by the user for now); opening the app inside the 120 s wait rings at once. Not yet
      tried: code pairing, unpair, wrong password, Hindi/large text/offline, mute, the 120 s give-up, the web page
      open at the same time, and the SideStore install (I6). Details in `mobile/ios/SPEC.md`. The user's phone is on
      iOS 26, so **AlarmKit is a real option later** for dose-time rings with the app closed.
      History of the test: installed with xtool over USB
      (through `muxrelay`, no usbipd; Apple's provisioning timed out once and returned a 500 once, then worked). Fixed on the way: starting a call crashed because xtool links packages as static
      archives and dropped LiveKit's Objective-C categories -- `-ObjC` linker flag in `Package.swift`. Open: long
      gaps before the agent replies (call `fe9df92e`). The backend log shows Sarvam's VAD responding promptly; the
      gaps were a 12.7 s STT silence with a keepalive error (the PC's network was flaky all session -- tunnel QUIC
      timeouts) and 10.7 s from turn end to TTS (LLM, or a restart after a short echo blip). Retest on earpiece vs
      speaker, with a web call alongside for comparison. App icon added (the web's voice-wave mark). Found
      during the test: `npm run dev`'s uvicorn `--reload` watched the whole repo, so an edit under `mobile/` restarted
      the API (and took the dev stack down); `scripts/dev.mjs` now reloads only on `backend/`, `core/`, `domains/`.
      Test data in the real DB
      (to clean up later -- there's no delete-patient endpoint): "Test Patient iPhone"
      `05803d68-2062-4104-9649-4d0b3eef6750` (Test Vitamin D 09:00 + 21:00), login `testiphone` (password in the
      gitignored `mobile/ios/test-login.local.txt`).
    - **After the iPhone test (user, 2026-11-04):** "works fine.. with the limitations"; **SideStore (I6)
      deferred** ("will do that later"). The user found the iPhone UI poor, so **both apps get a UI pass** matched
      to the web patient app (colours from `web/src/app/globals.css`, the same home/medicines/history/me tabs,
      i18n wording, elderly-friendly sizes). Android renders its screens on the JVM (Paparazzi/Roborazzi, no
      emulator) to `mobile/android/screenshots/` so the user can review before the Android phone arrives.
      Committed up to here: `d7b8c41`.
    - **Focus now (user, 2026-11-05): only the Android app -- "make the android app workable, and pretty".** The
      iPhone agent's conversation was cleared and its work paused; its unfinished UI redesign (new Today / Medicines
      / History / Me / Sign-in views and `Theme.swift`, replacing `HomeView` / `PairingView`) is staged but
      uncommitted and not verified to build or run. The login agent was archived (work done). Same day the user
      asked to let the iPhone agent finish: it got a fresh brief to complete that redesign to the same web-matched
      target, build it and re-check it on the phone. **Redesign builds cleanly (2026-11-05)**: Today / Medicines /
      History / Me tabs in the web's colours and wording (week legend, reminders with their day, caregiver line,
      history merging family alerts with check-ins, call-screen strings matching the web). **Tested on the
      user's iPhone and committed (`5eba454`)**: sign-in, all four tabs with real data, Talk now both ways, Call now
      ringing CallKit while open, answer, decline (backend ends the call in ~6 s); long medicine names fixed on
      device. Screenshots in `mobile/ios/screenshots/` (gitignored). Not checked: light mode, Hindi, largest
      Dynamic Type. Asked for next (from the user's screenshots): a full-screen in-app ringing view while the app is
      open (iOS only shows a small banner when unlocked), "VoiceMitra" instead of "VoiceMitra Audio…" on the
      banner, no duplicate language toggle, Server under Advanced, empty history cards labelled, bottom padding
      under the tab bar.
    - **Testing plan (user, 2026-11-04):** no Android phone yet; build everything that can be built without a
      device, then test **both phones together** once the Android phone arrives. The iPhone is available now, so
      its on-device test (I2-I5) is starting first. Work up to here committed by the user (`772b6be`).
    - **Android app (A1-A6) -- IN PROGRESS.** User decided (2026-11-04): **command-line SDK locally, no Android
      Studio and no emulator** ("i dont want the emulator to run on my laptop"); testing on a real Android phone
      the user is getting. Toolchain done: SDK in `C:\Users\apoor\Android\Sdk` (444 MB: cmdline-tools,
      platform-tools/adb, android-37.0, build-tools 36.0.0; no emulator or system images), Gradle 9.8.2 wrapper,
      the existing JDK 25 works with AGP 9.5.0 + Kotlin 2.4.21; SDK path only in gitignored `local.properties`.
      Project skeleton builds (`./gradlew assembleDebug` -> debug APK; placeholder screen) with LiveKit 2.30.0,
      Firebase BOM 35.1.0, Compose BOM 2026.09.00, core-telecom 1.0.1; application id `in.voicemitra.patient`,
      Kotlin package `com.voicemitra.patient`. Setup/build/install in `mobile/android/README.md`.
      **A1-A5 written, compile + lint clean, not yet run on a phone (2026-11-04):** login first (code pad as
      fallback, debug patient picker), settings (server URL, Hindi/English, log out), launch check + FCM token
      refresh; home with a big Talk button; call screen over the lock screen (foreground service, speaker on, mute,
      timer, live transcript, rejoin after a network drop); ringing from FCM and the socket through one path
      (CallStyle + full-screen intent, ringtone, 60 s timeout, decline -> call/end); setup checklist (notifications,
      full-screen, mic, battery, maker auto-start page). Verified: JVM unit tests + a contract test running the app's
      Kotlin API client against a live backend on a throwaway DB. Needs a phone for the ring when locked, answering,
      audio and the setup flow. Next: B4 (reminders ring the phone) and device-free A6 polish. Note for later:
      Firebase is moving from FCM registration tokens to FIDs; tokens still work, switching is a contract change.
      **Redesign + workable screens -- DONE in code (2026-11-05), not yet on a phone:** matched to the web patient
      app and the iPhone redesign -- web colour tokens (light/dark), Plus Jakarta Sans (+ Noto Devanagari), header
      with brand + EN/हि, floating Today / Medicines / History / Me tab bar, Me tab (profile, family contact,
      allergies, phone setup status, Advanced server address, log out with confirm), Medicines and History from
      `/api/app/patients/{id}/medicines` + `/history`, loading/error/offline states, 19 sp body, 56 dp+ targets.
      Rendered on the JVM with Roborazzi (no emulator): `./gradlew.bat screenshots` -> `mobile/android/screenshots/`
      (gitignored, 60 PNGs, en/hi, light/dark). Verified: assembleDebug, lint 0 errors, JVM tests incl. the contract
      test against a throwaway DB. Polish pass done the same day -- now matches the iPhone redesign side by side
      (`compare_*.png` in the screenshots folder): iPhone-style top bar and bottom nav, the "This phone" card shows
      the ringing checklist status, red sign-out with confirm, language switch only in the header, server address
      only under Advanced (also on the login screen), Answer bigger than Decline, due-now amber / missed red,
      "Nothing was recorded on this call." on empty history cards. assembleDebug + lint clean.
      A6 so far: APK limited to real-phone CPUs (debug 46 MB, release 39 MB, was 78 MB).
    - **B4 reminders ring the phone -- DONE (2026-11-04).** `live_calls._fire_reminder` starts a **voice** call (so
      the FCM ring goes out), waiting until any call the patient is on has finished. Verified: pytest 61/61
      (`tests/test_reminder_rings.py`, throwaway DB). Side effect: an open patient web page auto-joins it as a
      voice call (the web joins every voice call), where it used to get a chat.
    - **B5 dose-time ringing + one retry (pilot steps 4-5) -- DONE in code (2026-11-04), OFF until the phone
      test.** `backend/dose_scheduler.py`, behind `DOSE_RINGING_ENABLED=true` (unset = nothing armed, one startup
      warning). One timer per patient for their next slot (`insights.build_slots`), armed at startup and when a
      prescription is added; at the slot a voice call about the still-unanswered medicines; skipped if all answered,
      a "later" reminder covers it, or the patient is on a call. Nobody joins in 120 s -> ring again after 5 min ->
      still nobody -> one caregiver "couldn't be reached" alert (new `on_unanswered` hook on `start_voice_call`;
      other calls unchanged). **A decline counts as the patient's choice: no retry, no alert** -- the user may want
      to change that. Verified: pytest 69/69 (8 new in `tests/test_dose_scheduler.py`: fake clock, fake FCM, fake
      agent/LiveKit, throwaway DB). The phone test should cover a locked phone ringing at a dose time, the retry and
      the alert.
Steps 1-3 and 6-8 below don't depend on this.

**What exists:** voice + chat calls, dose/symptom logging, the seriousness tiers, caregiver records with a
simulated notification on escalation and on "unreachable", one-off "remind me later" timers
(`live_calls.arm_reminder`, re-armed from Mongo on startup), a dose-schedule calculator (`insights.py`), the
installable PWA with a service worker, an add-prescription form (doctor/operator screens).

**Gaps found in the code:** every call was about `prescription.medicines[0]` only (`bot.py`) -- fixed in step 1;
the "Talk to VoiceMitra" button and the reminder call are the same flow (`CallType.inbound_call` /
`just_catch_up` exist but are unused); nothing fires at dose times; no push notifications; no caregiver
screen or role; escalation always means "ring the doctor".

**Build order (each step runnable and shown before the next):**
1. **Calls about the right dose** -- **DONE (2026-11-03): tests + scripted calls pass; not yet tried by the user.**
   A call is about one dose *slot* and every medicine due in it, across all the patient's prescriptions.
   - Slot choice (`insights.pick_call_slot`, when the caller doesn't give one): the most recent slot (up to 30
     min ahead) with medicines still unanswered, asking only about those. If there is none, the call is a
     wellbeing check-in with no dose question (fixed after step 3 -- it used to fall back to the next slot
     however far ahead, see below). A
     reminder call passes its own slot and medicines (`Reminder.dosage_ids` / `slot_at`; old records with a
     single `dosage_id` still work).
   - `log_dose_event` / `reschedule_dose` take `medicines` (names as listed; "Name (dose)" accepted, empty =
     every one not yet answered) and return what is still to ask about. `DoseEvent.scheduled_at` is now the
     slot, and `insights.build_slots` matches events by it (a morning dose reported in the evening counts
     for the morning). `Call` stores `slot_at` and `dosage_ids`.
   - Policy: the generic engine (`core/agent/policy.py`) now allows a transition that depends on the context;
     the dose step moves on only once every due medicine has an answer.
   - Prompt: lists the slot's medicines and how to say the time aloud (`prompts.spoken_time`: "dopahar 1
     baje" / "1 PM") -- left to the model, a 13:00 dose came out as "subah" and "do baje".
   - Schedules: `Dosage.interval_days` for "every N days" (API requires it for that frequency; old records
     stay daily); the add-prescription form asks for it and both medicine screens show it. Weekly already
     worked (every 7 days from `from_date`).
   - Bug fixed on the way: a reminder set during a *voice* call was saved but its timer never armed (until a
     restart); voice calls now arm it too.
   - Verified: 10 new pytest tests (24 total); scripted calls against the live LLM (Gemini) in a throwaway DB
     -- both taken (one log for both), one taken + one forgotten (two logs, reason kept), one taken + one
     "later" (reminder for that one only). Not tried: a real voice call with several medicines. (Reminders
     starting chat calls: fixed by B4, see below.)
   - Seen in those runs, not fixed (older prompt issues): the agent sometimes narrates its step ("ab main
     symptom check kar leti hoon"), asks two questions in one turn, and slipped into Hinglish once while the
     patient spoke English. With a fixed script it keeps re-asking about an unanswered medicine -- correct, but
     there is no limit on how often.
2. **Pilot mode: caregiver instead of doctor** -- **DONE (2026-11-03): tests + scripted calls pass; not yet tried
   by the user.**
   - Switch: first built per patient, then changed the same day (user) to one global switch that is **off**
     -- see the top of this section. `CareMode` (`caregiver` / `doctor`) is still what the policy, guardrails
     and prompts are built from; `bot.CARE_MODE` picks it from `DOCTOR_FLOW_ENABLED`.
   - Caregiver mode: the symptom step offers `alert_caregiver` instead of `escalate_to_doctor` and never offers a
     doctor. Seriousness 1-4 -> `update_daily_log` as before; 5+ -> `alert_caregiver` (guardrail: a 5+ score
     can't just be logged), without asking the patient's permission; alarming symptoms -> straight away with
     8+. `alert_caregiver` writes the daily log (symptoms, score), sets the call's patient status (remedy /
     urgent), and stores a `CaregiverNotification` (`urgent` from 8 up; message says what is wrong). A red-flag
     phrase forces it (seriousness 9) the same way it forced the doctor escalation. Urgent alerts skip the
     "since when" question.
   - Then the call ends with a fixed line (`prompts.caregiver_line`, Hinglish/English, not LLM-written):
     "Maine yeh note kar liya hai aur Rahul ji ko bata diya hai…"; **urgent adds "call 112"** (India's
     emergency number, `prompts.EMERGENCY_NUMBER`) since no doctor is on the call -- a safety line the user
     may want to review. No caregiver on file (or opted out) -> the line doesn't claim anyone was told.
   - Doctor mode is unchanged (same prompts and tiers; the shared follow-up text was only factored out).
   - Prompt fix found while testing, both modes: the agent kept asking the patient to pick "mild, moderate or
     severe" after they had said "bahut dard... kaafi tez"; it now takes their own words and stops asking once
     it has location, severity and duration.
   - Verified: 11 new pytest tests (35 total); scripted calls against the live LLM (Sarvam) in a throwaway DB --
     two-day bad headache -> caregiver alerted (x2), same with no caregiver on file, chest pain -> urgent alert
     + 112 line, "all fine" -> just logged, doctor mode -> still escalates to the doctor. Seen, not fixed: it
     re-asks "since when" after the patient already said "do din se", and twice wrote "parson se" (day before
     yesterday) as "since yesterday". The caregiver only sees the alert where alerts already show (patient
     history, operator view) until step 3.
3. **Caregiver app** -- **DONE (2026-11-03): tests pass, checked in a browser on a seeded throwaway DB; not yet
   tried by the user.**
   - Start screen: "I'm family of a patient" -> pick your name (`/who/caregiver`, each listed with who they look
     after) -> `/caregivers/[id]`, remembered on the device like the other roles. A caregiver record belongs
     to one patient, so the page is about that patient.
   - The page (patient-app look, Hindi/English): alerts newest first -- new ones as cards (red if urgent, amber
     otherwise; "Not feeling well" / "Couldn't be reached" / "Urgent") with **Mark as seen** (and "mark all" for
     several), seen ones folded under "Earlier"; a banner while the patient is on a call; the patient's
     doses today with their state; the week; how they're doing; last check-in. The tab title shows the unseen
     count.
   - API: `GET /api/app/caregivers/{id}/home` (`views.CaregiverHome`), `POST /api/caregivers/{id}/alerts/{aid}/seen`
     and `.../alerts/seen` (all); `AlertView` gained `id`, `urgent`, `seen_at`. Live: `/ws/caregivers/{id}` fed by
     `backend/family_feed.py` -- a new alert (published where the notification is stored), alerts seen, a call
     starting or ending; the page refetches on each (and on reconnect).
   - Verified in the browser: start screen without the doctor role, the picker, the page with an urgent and a
     seen alert, Mark as seen, Hindi, and **live**: a chat call started from the API showed the banner, and
     playing the patient ("chest mein dard") made the urgent alert appear on the open page with no reload, the
     dose turn "Taken" and the banner clear. 2 new view tests (37 total).
   - Not done: the alert text itself is English (built in `caregiver.py`, includes the LLM's `reason`) even in
     the Hindi UI; no push/sound when the page is closed (step 4); no link to the call's conversation.
   - **Found while testing, FIXED (2026-11-03):** at 3 PM, with the 8:30 dose already marked missed, "Call now"
     picked the *9 PM* dose and asked "kya aapne raat 9 baje wali dawai li?", and "haan" logged it taken six
     hours early -- `pick_call_slot` fell back to the next slot however far ahead. Now it returns None unless a
     slot is due (or within 30 min) and unanswered, and such a call is a **wellbeing check-in**
     (`CallType.just_catch_up`, no `slot_at`): `build_policy(..., ask_doses=False)` starts at the symptom step,
     which greets and confirms the patient first and never asks about doses; the prompt gives the next dose
     (`insights.next_slot`, today or tomorrow) in case they ask. So "Call now" and the patient's "Talk to
     VoiceMitra" button no longer fail with "no medicine is due today". Verified: 3 new tests (39 total);
     scripted live calls -- check-in (no dose question, told the next dose time correctly when asked) and a
     normal two-medicine dose call (unchanged). Step 6 replaces this interim check-in with the open
     inbound flow; step 7 decides when a check-in asks about wellbeing at all.
4. **Dose-time ring (native apps)** -- the call itself is the reminder: at each dose slot the patient's
   phone rings (Android: server push to our app; iPhone: only while the app is open), answering joins the voice
   call for that slot. Specced in `mobile/android/SPEC.md` (step B5). Caregiver alerts as push to the caregiver's
   phone can reuse it later.
5. **No answer in 5 min -> ring again** -- then the existing `unreachable` caregiver alert.
6. **Inbound call flow** -- its own policy states: open greeting, questions about their medicines answered
   from the records, symptoms -> same "not well" path, plain chat.
7. **Wellbeing rules** -- per the decision above: asked in the reminder call for one slot a day, once a day
   (twice if needed) for several, a standalone check-in call (`CallType.just_catch_up`) every N days for
   less-than-daily medicines.
8. **Prescription entry by patient/caregiver** -- both together: the existing form, and a **photo upload**
   read by the LLM (Gemini, already configured, takes images) into the same form for the person to check
   and save. A rough first version is fine; improve extraction later.
9. **Urgent -> call the caregiver** -- the agent calls the caregiver and tells them what happened.

**Known limits:** timers live in the server process, so the machine running the API must stay on (see
Hosting); the platform limits above. **Open questions:** whether xtool can build the LiveKit Swift SDK (iPhone step I1),
how to ring a closed iPhone later, whether caregivers can also edit prescriptions.

### Chunk 5 — Structured extraction polish + eval harness + rehearsal — **NOT STARTED** (user agreed to build the eval harness, 2026-11-03; after the pilot)
**Handling non-determinism (the same input can score 5 one run and 8 the next):**
- Assert the *decision* (escalate / alert caregiver / just log), never the exact score.
- Run every scenario several times (e.g. 5-10) and report a pass *rate* per scenario plus the overall rate
  with its spread. One run of 10 scenarios swinging between 50% and 90% is sampling noise, not a result.
- Label scenarios by type: **clear-cut** ("all fine" must never alert; chest pain must always escalate --
  target ~100%) vs **borderline** (headache for 2 days -- an acceptable *set* of outcomes, e.g. "offer or
  escalate", both pass).
- Report misses separately: a missed urgent case is worse than an extra alert.
- Consistency is a metric in itself: if one input flips between outcomes, that is the low-confidence case
  the confidence-gated escalation is meant to catch (ask one more question, second opinion). Agreement
  across runs is also a cheap way to measure confidence.
- Two levels: **decision tests** (a fixed transcript fed to the escalation decision only -- cheap, many runs)
  and **full-call tests** (a scripted or LLM-played patient through the whole call, checking the tool-call
  path -- costly, fewer runs). Temperature 0 lowers variance but doesn't remove it.
Plan: tighten symptom-extraction tool schema, build `eval/scenarios/` (reference-derived +
unreachable-patient + caregiver-notified-on-escalation) and `eval/run_eval.py`, demo rehearsal
checklist.

## Verification approach
No automated UI tests for this POC timeline — verification is live run-throughs of each scenario
plus the Chunk 5 eval harness, which doubles as a panel-visible artifact of evaluation rigor.
