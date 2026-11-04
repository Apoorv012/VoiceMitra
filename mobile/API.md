# Mobile apps <-> backend contract

What the Android and iPhone apps call. **Existing** = already in the backend today; **New** = built by the
Android agent (it owns `backend/`), see `android/SPEC.md` step B1-B3. The iPhone agent builds against this file
and never edits the backend.

Base URL: the tunnel's public HTTPS hostname (README: "Cloudflare Tunnel sends `/api`, `/ws` and `/health` to
:8000"), configurable in each app (a settings field, or a build constant for the pilot). Local dev on the same
Wi-Fi: `http://<pc-ip>:8000` (Android needs cleartext allowed for that host in debug builds only).

There is no login yet (built last, by design). The only credential is the device token from pairing.

## Identity: pairing (New)

| | |
|---|---|
| `POST /api/patients/{patient_id}/pairing-code` | Web only (patient page, "Connect a phone" button). -> `{"code": "482913", "expires_at": "<iso>"}`. 6 digits, valid 10 min, single use. |
| `POST /api/devices/pair` | App. Body `{"code": "482913", "platform": "android" \| "ios", "push_token": "<FCM token or null>", "name": "Pixel 7"}` -> `{"device_id": "...", "device_token": "...", "patient_id": "...", "patient_name": "..."}`. 400 on a wrong/expired code. |
| `PUT /api/devices/{device_id}` | App, header `X-Device-Token`. Body `{"push_token": "..."}` (FCM rotates tokens). 204. |
| `DELETE /api/devices/{device_id}` | App ("Unpair"), header `X-Device-Token`. 204. |

The app stores `device_id`, `device_token`, `patient_id`. Every other call below is keyed by `patient_id`.

## Reading (Existing)

- `GET /api/app/patients/{patient_id}/home` -> `PatientHome` (`backend/views.py`; generated TS shape in
  `web/src/lib/api-schema.d.ts`): `timezone`, `patient`, `today[]` (slots with `at`, `medicine`, `dose`,
  `state`), `next_dose`, `week[]`, `adherence`, `last_checkin`, `how_doing`, `reminders[]`, `caregiver`.
  Times are ISO; show them in `timezone` (default Asia/Kolkata).
- `GET /api/app/patients/{patient_id}/medicines`, `.../history` -- same pattern, for later screens.
- `GET /api/app/people` -> everyone (dev-only patient picker until pairing exists).
- OpenAPI: `python -m backend.dump_openapi` writes `web/openapi.json` (the full schema).

## Calls

- `POST /api/patients/{patient_id}/voice-call` (Existing; New: optional header `X-Device-Token`, so the
  backend doesn't push a ring to the device that started the call) -> 204. Starts a voice call: LiveKit room + agent;
  the agent waits up to 120 s for the patient to join (`core/transport/voice_pipeline.py` JOIN_TIMEOUT_SECONDS),
  then gives up and sends the caregiver the "couldn't be reached" alert. Used for "Talk now" in the app.
- `GET /api/patients/{patient_id}/voice-call` (New) -> `{"call_id", "url", "token"}` for the call in progress,
  404 if none. What an app calls after the user answers a ring.
- `POST /api/patients/{patient_id}/call/end` (Existing) -> 204. Decline a ring / hang up.
- Joining: connect the LiveKit SDK to `url` with `token`, publish the microphone, play remote audio. The token's
  identity is `patient` -- the agent only listens to that identity. **Only one device may join**: a second
  `patient` (e.g. the patient's web page left open) pushes the first one out of the room.

## Live events (Existing): `wss://<host>/ws/patients/{patient_id}/chat`

JSON messages (shapes in `web/src/lib/events.ts`). The ones the apps need:

- `{"type": "snapshot", ..., "voice": {"call_id", "url", "token"}?}` -- sent on connect; `voice` present if a
  voice call is waiting/in progress.
- `{"type": "voice_call", "call_id", "url", "token"}` -- a voice call just started for this patient: **ring**.
- `{"type": "voice_call_ended"}` -- stop ringing / leave the room.
- `{"type": "log_entry", "call_id", "entry": {"type", "channel", "content"}}` -- live transcript lines
  (`entry.type` `agent_said` / `patient_said` ...), optional to show.

The iPhone app (foreground only) rings from `voice_call`. The Android app rings from the push below and may also
use the socket while open.

## Push (New, Android only)

FCM **data** message, `priority: high`, TTL 60 s, sent to every Android device of the patient when a voice call
starts (any trigger: Talk now from the web, the operator's Call now, a reminder, the dose-time scheduler):

```json
{"type": "ring", "call_id": "<id>", "patient_id": "<id>"}
```

No health information in the payload. The app then calls `GET .../voice-call` for the join details on answer.
