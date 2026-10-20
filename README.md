# VoiceMitra

Voice-first medicine-adherence agent. See `CLAUDE.md` for the architecture and `PLAN.md` for status.

Two programs, one repo:

- **API + agent** (`backend/`, `core/`, `domains/`) — FastAPI, MongoDB, Pipecat voice agent. Serves JSON and
  WebSockets only, no HTML.
- **Web app** (`web/`) — Next.js (React, TypeScript). The patient app (installable, Hindi/English), the doctor
  screens and the operator screens. It talks to the API over `/api/*` and live WebSockets.

## Run everything

1. One-time setup:
   ```
   python -m venv .venv
   .venv\Scripts\activate        # (or `source .venv/bin/activate` on macOS/Linux)
   pip install -r requirements.txt
   ```
   Copy `.env.example` to `.env` and fill in `SARVAM_API_KEY` (or `GEMINI_API_KEY` + `LLM_PROVIDER=gemini`) and the
   `LIVEKIT_*` values for voice calls (a free project at https://cloud.livekit.io). Have MongoDB running on
   `localhost:27017`. Node 20+ is needed for the web app.
2. Install the runner (and the web app's packages) once: `npm install` in the repo root.
3. Start everything with one command, in one terminal. The API (:8000), the web app (:3000) and the HTTPS
   tunnel run together with colour-coded `[api]` `[web]` `[tunnel]` logs, and **Ctrl+C stops all of it**:

   | Command | Web app | Database |
   |---|---|---|
   | `npm run dev` | hot reload (use while changing the frontend; the installable app is off) | your real one |
   | `npm run demo` | hot reload | the demo database (below) |
   | `npm start` | production build (the installable app works; builds first, ~30 s) | your real one |
   | `npm run start:demo` | production build | the demo database |

   `npm run dev:local` and `npm run start:local` are the same without the tunnel. The tunnel
   also starts only if `cloudflared` is installed; otherwise you just get no phone URL. Open
   http://localhost:3000, or on a phone `https://test-voicemitra.apoorvm.com` (see "Phone and install").
   If a port is already taken (a server left over from earlier), it tells you and stops instead of starting a
   second one.

There are no accounts: the first screen asks who you are (patient, doctor or staff) and the device remembers it.

## Data

- `python -m backend.seed` — one demo patient, doctor and prescription. **Wipes** the database it points at.
- `MONGODB_DB_NAME=voicemitra_demo python -m backend.seed_demo` — five patients with two weeks of history, a
  resolved emergency and transcripts, for demos and for seeing every screen state. Refuses to run against the
  default `voicemitra` database. It is a separate database on the same local MongoDB, so it never touches your
  real test calls; start the stack on it with `npm run demo`.

## Phone and install

Phone browsers only allow the microphone on HTTPS, so voice calls need the tunnel. One public hostname serves both
programs: Cloudflare Tunnel sends `/api`, `/ws` and `/health` to :8000 and everything else to :3000 (config in
`%USERPROFILE%\.cloudflared\config.yml`; install with `winget install Cloudflare.cloudflared`, then
`cloudflared tunnel login`, `tunnel create voicemitra-test`, `tunnel route dns voicemitra-test <hostname>`).
The URL is public and there is no login, so close the tunnel window when you're not testing.

On the phone, "Me → Install" (Android) or Share → Add to Home Screen (iPhone) puts it on the home screen. The
service worker only runs in the production build (`npm start`, not `npm run dev`).

## Changing the API

The web app's TypeScript types are generated from the API's schema, so after changing a response model in
`backend/views.py`:

```
python -m backend.dump_openapi      # writes web/openapi.json
cd web && npm run gen:api           # regenerates web/src/lib/api-schema.d.ts
```

## Tests

```
pytest                              # backend: schedule/adherence logic and the screen read-models
cd web && npm run lint && npx tsc --noEmit
```

## Chat-only agent (no audio, no web app)

`python -m domains.med_adherence.bot <patient_id>` talks to the agent in the terminal.
