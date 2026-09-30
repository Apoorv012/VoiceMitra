# VoiceMitra

Voice-first medicine-adherence agent. See `CLAUDE.md` for the architecture.

## Try the chat demo

1. Set up a venv and install deps:
   ```
   python -m venv .venv
   .venv\Scripts\activate   # (or `source .venv/bin/activate` on macOS/Linux)
   pip install -r requirements.txt
   ```
2. Copy `.env.example` to `.env` and fill in `SARVAM_API_KEY` (get one from https://sarvam.ai)
   or Gemini's `GEMINI_API_KEY` + `LLM_PROVIDER=gemini`.
3. Have a MongoDB instance running at `mongodb://localhost:27017` (install MongoDB locally if
   you don't have one — no Docker setup here yet).
4. Seed a demo patient/prescription: `python -m backend.seed`. It prints a patient id.
5. Chat with the agent: `python -m domains.med_adherence.bot <patient_id>`

## Try a voice call

Voice uses a LiveKit room with Sarvam STT/TTS (all native, no Docker).

1. Create a free project at https://cloud.livekit.io and put its URL (`wss://<project>.livekit.cloud`),
   API key and API secret in `.env` as `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`.
2. `pip install -r requirements.txt`, start the backend (`uvicorn backend.main:app`).
3. Open `/operator`, click **Voice call** for a patient, open that patient's window (`/patients/<id>`)
   and allow the microphone.
