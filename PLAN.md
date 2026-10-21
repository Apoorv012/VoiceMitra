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
  simulated; the record is the notification).
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
    routers/                     # patients.py, doctors.py, calls.py (JSON API), live.py (WebSockets + call controls),
                                 # escalations.py (doctor WebSockets + join/end), app_api.py (/api/app/* read endpoints)

  web/                           # Next.js app: src/app (screens), src/components, src/lib (api, ws, i18n, format, events)
                                 # public/ (icons, service worker, offline page), scripts/make_icons.py
  tests/                         # pytest: insights.py and views.py
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

### Doctor escalation flow (text chat) — **DONE**, verified by scripted runs; **awaiting user testing**
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
events (no live-call object like chat has), reminders still start chat calls, a patient who never joins
ends the call after 120 s.

### Chunk 4 — Escalation + caregiver + doctor merge (live voice) — **BUILT, AWAITING FIRST HANDS-ON TEST**
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

### Voice feel fixes (2026-10-21) — **BUILT, NOT YET TRIED ON A LIVE CALL**
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

### Web app (2026-10-21) — **BUILT AND VERIFIED IN A BROWSER; REAL VOICE CALLS NOT YET TRIED IN IT**
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
  (default Asia/Kolkata) which is one zone for everyone; "every X days" prescriptions are treated as daily
  (the model has no interval).
- **Cleanup done (2026-10-21, with the user's go-ahead):** deleted the old UI (`backend/pages.py`, `backend/templates/`,
  `backend/static/`, the `/static` mount, the page-only helpers in `queries.py`, and the `jinja2` / `python-multipart`
  dependencies), `run_backend.bat` and then `run.bat` (replaced by the npm scripts), the Daily transport, the Next.js starter boilerplate and the
  unused Jinja helper draft. **The old pages were the only UI proven with real audio, and they were deleted before the new
  screens had a real call run through them** -- the user chose this over waiting; `git log` has the old call/voice-join
  code (`_chat_widget.html`, `escalation_call.html`) to compare against if a call misbehaves.

### Web visual redesign (2026-10-21) — **BUILT, build/tsc/eslint pass; NOT YET EYEBALLED IN A BROWSER**
Restyled the Next app from three reference designs (soft sage palette, large rounded cards, pill nav with a
green active tab, dark-green primary button, floating pill tab bar on mobile). Only patterns that map to our
screens were taken; AI-assistant, shift, billing, vitals and capacity widgets were deliberately left out.
Plus Jakarta Sans + Noto Sans Devanagari via `next/font`; green brand accent, dark-green primary action;
status colours still reserved for state and always icon + word. Doctor overview tiles gained icons and the
header shows the date. Token-level change in `web/src/app/globals.css`; markup changes limited to the doctor
overview, the new-patient form and brand-mark sizing. Also applied Web Interface Guidelines fixes
(focus-visible, explicit transitions, reduced motion, `touch-action`, form `autocomplete`/`inputMode`,
`translate="no"` on the brand).

### Planned (not built): confidence-gated, LLM-judged escalation
Escalation should come from the LLM's own assessment, not hand-written term lists. Idea:
- Have the LLM return, for each symptom report, `should_escalate` plus a **confidence score** (and its
  reasoning), e.g. via a structured tool/JSON output.
- **High confidence** -> follow the LLM (escalate, or don't). **Low confidence** -> fall back to a second
  check: a rules pass, a second LLM opinion, or ask the patient one more clarifying question.
- Keep the code guardrails as a hard backstop only for the unambiguous red flags already listed.
- Build `eval/` scenarios around it (e.g. heavy fever + cough 2 days must escalate; mild cough must not)
  and measure how confidence correlates with correct decisions before trusting a threshold.

### Chunk 5 — Structured extraction polish + eval harness + rehearsal — **NOT STARTED**
Plan: tighten symptom-extraction tool schema, build `eval/scenarios/` (reference-derived +
unreachable-patient + caregiver-notified-on-escalation) and `eval/run_eval.py`, demo rehearsal
checklist.

## Verification approach
No automated UI tests for this POC timeline — verification is live run-throughs of each scenario
plus the Chunk 5 eval harness, which doubles as a panel-visible artifact of evaluation rigor.
