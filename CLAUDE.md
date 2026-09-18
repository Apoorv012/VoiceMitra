# VoiceMitra

Voice-first medicine-adherence system. A Pipecat-based voice agent calls patients to remind them
about medicine, logs adherence and symptoms, and escalates to a doctor (with a live audio merge)
or notifies a caregiver when needed. Built as a capstone project.

**Read `PLAN.md` first** for the full architecture rationale, design constraints, and — critically
— the up-to-date status of what's done vs. not (chunk-by-chunk). It's the source of truth for
project status, not chat history or this file.

**Keep `PLAN.md` up to date.** Whenever a chunk (or any piece of work) is completed, whenever
scope is added or removed, or whenever a design decision changes, update `PLAN.md`'s Status
section (and the rest of the file, if the change affects architecture/stack/data-model) in the
same turn as the change itself -- not as an afterthought later. If it isn't reflected there, treat
the work as not actually finished.

## Architecture at a glance

- `core/` — transport-agnostic voice-agent runtime (Transport interface, STT/LLM/TTS provider
  wiring, generic policy state machine, tool registry, guardrails check-pipeline). Only one
  consumer exists today (`domains/med_adherence`), but the boundary is real: domain code never
  imports Daily or Sarvam SDKs directly.
- `domains/med_adherence/` — the actual agent: prompts, concrete policy states, tools
  (`log_dose_event`, `escalate_to_doctor`, `notify_caregiver`, ...), escalation rules, guardrail
  rules.
- `backend/` — FastAPI app: patient/doctor/caregiver/prescription CRUD, admin form, call
  triggering, doctor dashboard, MongoDB persistence.
- `eval/` — scripted scenarios replayed against the live agent to check it takes the correct
  tool-call path.
- `reference_transcripts/` — sample Hindi/Hinglish call transcripts used as prompt/eval grounding
  material. Not exact scripts.

## Mongo id convention

`backend/models.py`'s `MongoDocument` base stores the domain UUID as Mongo's own `_id` (aliased to
`id` in the model) instead of carrying a duplicate `id` field alongside `_id`. Always write with
`db.model_to_doc(...)` (aliases `id` -> `_id`) and read with `db.doc_to_model(Model, doc)`. Every
FastAPI route returning one of these models needs `response_model_by_alias=False`, otherwise the
JSON API leaks `_id` instead of `id`.

## Local MongoDB

Uses whatever `mongod` is already running on `localhost:27017` on this machine (there's an
existing native Windows MongoDB install here, shared with other local projects — data lives in
the `voicemitra` database, separate from other projects' databases on the same server). No Docker
container needed; `MONGODB_URI`/`MONGODB_DB_NAME` in `.env` point at it.

## Transport swap path

The call medium for the POC is browser-based WebRTC via Daily.co (`core/transport/daily_transport.py`).
A future phone-call version swaps in a Twilio-backed transport implementing the same
`core/transport/base.py` interface — no changes needed in `core/agent/` or `domains/`.

## Git workflow — important

Claude may create branches, run `git add`, `git status`, `git diff`, `git log`, and other
non-publishing git commands freely.

**Claude must never run `git commit` or `git push`.** The user commits and pushes themselves
(their SSH signing setup requires a local passphrase Claude doesn't have). Stage changes and
describe what's ready to commit; let the user do the commit/push.
