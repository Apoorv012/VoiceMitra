# Mobile apps <-> backend contract

What the Android and iPhone apps call. **Existing** = already in the backend today; **New** = built by the
Android agent (it owns `backend/`), see `android/SPEC.md` step B1-B3. The iPhone agent builds against this file
and never edits the backend.

Base URL: the tunnel's public HTTPS hostname (README: "Cloudflare Tunnel sends `/api`, `/ws` and `/health` to
:8000"), configurable in each app (a settings field, or a build constant for the pilot). Local dev on the same
Wi-Fi: `http://<pc-ip>:8000` (Android needs cleartext allowed for that host in debug builds only).

**The apps talk to the API host only, never the website.** Cloud (live since 2026-11-07, the apps' default since
2026-11-11): `https://voicemitra-api.apoorvm.com` (API only). Development: the home tunnel
`https://test-voicemitra.apoorvm.com`. The website (`voicemitra.apoorvm.com`, on Vercel) is for browsers; the apps
never load or call it.

The app's only credential is a **device token**, which it gets either by logging in (the main way) or by pairing
(the fallback). Both return the same thing; everything after that is the same.

**Send `X-Device-Token` on every request once signed in -- and on the patient socket's handshake** (since
2026-11-11, `backend/access.py`). Without it the API answers **401** to everything about a patient; with another
patient's id in the path, **403**. The token only ever goes to the configured API host. Login, pairing and
`/health` are the only calls that need no token.

## Identity: login (username + password) (Built -- login agent)

**The main way in.** The patient (or their family) sets a username and password on the patient's **Me** tab in the
web app ("Phone app login" card); the app shows a login screen with just those two fields. Pairing (below) stays
as a fallback, e.g. "Use a code instead" on the login screen.

| | |
|---|---|
| `POST /api/auth/login` | App. Body `{"username": "sunita", "password": "...", "platform": "android" \| "ios", "push_token": "<FCM token or null>", "name": "Pixel 7"}` -> **exactly the pairing response** `{"device_id", "device_token", "role", "patient_id", "patient_name", "caregiver_id", "caregiver_name"}` (a patient's login: `role` `patient`; a family contact's: `role` `caregiver`, see "Caregivers in the apps"). Username is trimmed and case-insensitive; the password is taken as typed. **401** `wrong username or password` (same for an unknown username and a wrong password); **429** after too many failed logins (paused ~10 min, counted across all phones, like wrong pairing codes). Same `push_token` replaces that phone's old record, as with pairing. **403** `staff_login`: the password was right, but it is a staff login, which works on the website only -- tell them to use voicemitra.apoorvm.com. (`family_login` is no longer sent since C1; keep handling it the same way.) |
| `DELETE /api/devices/{device_id}` | **Log out** = the existing unpair call (header `X-Device-Token`). 204. Then show the login screen. |
| `PUT /api/patients/{patient_id}/login` | Web only (staff, or the patient changing their own). Body `{"username", "password"}` -> 204. Sets or changes the login (the same one the patient signs in to the website with). Username 3-40 characters (after trimming), password at least 6 -- otherwise **400**; **409** if another patient has that username. 404 unknown patient. Phones already logged in stay logged in. |
| `GET /api/patients/{patient_id}/login` | Web only (staff or the patient). -> `{"username"}`, or 404 if none is set. The password is never returned (only an scrypt hash is stored). |
| `DELETE /api/patients/{patient_id}/login` | Web, staff only. 204. Removes the login (phones already logged in stay connected). |

After a successful login the app stores `device_id`, `device_token`, `patient_id` exactly as after pairing, and
the `X-Device-Token` rules below apply unchanged (on 404/401 forget them and show the login screen).

## Caregivers in the apps (New -- C1, decided 2026-11-15; built by the Android agent, iPhone builds against it)

A family contact (caregiver) can now sign in to the apps with **their own website login** (the one staff set on the
patient's page). They see a caregiver home, not the patient's tabs. Staff logins still get 403 `staff_login`.
Pairing codes stay patient-only.

- `POST /api/auth/login` with a caregiver's username/password -> 200 instead of 403 `family_login`. The response
  (for patients too) gains a `role` field:

  ```json
  {"device_id": "...", "device_token": "...", "role": "caregiver",
   "patient_id": "<the patient they look after>", "patient_name": "Sunita Devi",
   "caregiver_id": "...", "caregiver_name": "Rahul"}
  ```

  Patients: `"role": "patient"`, `caregiver_id`/`caregiver_name` null. Pairing returns `"role": "patient"` too.
  An app that sees no `role` treats it as `patient`. 403 `family_login` is no longer sent (keep handling it as
  "use the website" for safety).
- `GET /api/devices/{device_id}` returns the same extra fields (`role`, `caregiver_id`, `caregiver_name`). On launch,
  open the screen that matches `role`. If the caregiver was removed as the family contact, this returns **404**
  (the device is gone) -> forget the login and show the login screen.
- A caregiver device's `X-Device-Token` makes the request the **caregiver** (`backend/access.py`), so it may call
  only the caregiver routes; patient routes answer 403.
- Caregiver calls (all Existing on the website, now also with `X-Device-Token`):
  - `GET /api/app/caregivers/{caregiver_id}/home` -> `CaregiverHome` (`backend/views.py`): `timezone`, `caregiver`,
    `patient`, `in_call`, `alerts[]` (newest first: `id`, `at`, `message`, `trigger` `unreachable`|`escalation`,
    `urgent`, `seen_at`, `call_id`), `unseen`, `today[]`, `next_dose`, `week[]`, `adherence`, `last_checkin`,
    `how_doing`. **404** = no longer this patient's family contact.
  - `POST /api/caregivers/{caregiver_id}/alerts/{alert_id}/seen` -> 204. `POST /api/caregivers/{caregiver_id}/alerts/seen`
    (all) -> 204.
  - Socket `wss://<host>/ws/caregivers/{caregiver_id}` with `X-Device-Token` on the handshake. Messages `snapshot`,
    `alert`, `alerts_seen`, `call_started`, `call_ended` -- each one just means "refetch the home".
    Close codes: **1008** at the access check (no/unknown token -- e.g. the family contact was removed, which deletes
    their phones -- or another caregiver's id); **4404** after the handshake when the caregiver record is gone. On
    either, don't keep reconnecting blindly: refetch the home / `GET /api/devices/{id}`; a **401/404** there is the
    sign-out signal (forget the login, show the login screen). Other closes (network): reconnect with backoff.
  - `DELETE /api/devices/{device_id}` = log out, as for patients.
- What the caregiver screen shows (mirror the website's `/caregivers/[id]` page and its `cg_*` strings in
  `web/src/lib/i18n.tsx`, Hindi + English): "Looking after <patient>" + greeting; "<patient> is on a call with
  VoiceMitra" while `in_call`; Alerts (new ones with Mark seen, Mark all seen, earlier ones folded away; labels
  Urgent / Couldn't be reached / Not feeling well); today's medicines with their state and the last check-in; this
  week's dots + legend; how they're doing; Log out. Read-only otherwise: no Talk now, no ringing.
- **Push (Android only):** when an alert is created for that caregiver, each of their Android devices gets an FCM
  data message (high priority, TTL 1 h, no health information):

  ```json
  {"type": "alert", "alert_id": "<id>", "caregiver_id": "<id>", "patient_id": "<id>"}
  ```

  The app shows an ordinary (not full-screen, not ringing) notification such as "Update about Sunita -- open
  VoiceMitra", which opens the caregiver home. Caregiver devices **never** get `ring` / `call_ended` pushes.
  The iPhone shows new alerts only while the app is open (the socket), as for ringing.
- Web: `GET /api/patients/{patient_id}/devices` lists the patient's own phones only (caregiver phones are not listed
  there).

## Identity: pairing (Built -- B1, now the fallback)

| | |
|---|---|
| `POST /api/patients/{patient_id}/pairing-code` | Web only (patient's **Me** tab, "Connect a phone" card). -> `{"code": "482913", "expires_at": "<iso, UTC with offset>", "expires_in": 600}`. 6 digits, valid 10 min (`expires_in` seconds -- count down from that, not from the clock), single use; asking again retires the previous code. 404 unknown patient. |
| `POST /api/devices/pair` | App. Body `{"code": "482913", "platform": "android" \| "ios", "push_token": "<FCM token or null>", "name": "Pixel 7"}` -> `{"device_id": "...", "device_token": "...", "patient_id": "...", "patient_name": "..."}`. Non-digits in `code` are ignored (spaces OK). 400 on a wrong/expired/used code; **429** after too many wrong codes (paused ~10 min). Pairing again with the same `push_token` replaces that phone's old record. |
| `GET /api/devices/{device_id}` | App, header `X-Device-Token`. -> `{"device_id", "role", "patient_id", "patient_name", "caregiver_id", "caregiver_name"}` (C1: `role` `patient` \| `caregiver`; the caregiver fields are null on a patient's phone). Use on launch to check the phone is still signed in and which screen to open. |
| `PUT /api/devices/{device_id}` | App, header `X-Device-Token`. Body `{"push_token": "..."}` (FCM rotates tokens). 204. |
| `DELETE /api/devices/{device_id}` | App ("Unpair"), header `X-Device-Token`. 204. |
| `GET /api/patients/{patient_id}/devices` | Web: the paired phones `[{"id", "platform", "name", "created_at", "last_seen"}]` (no tokens). |

Errors on the `X-Device-Token` endpoints: **404** = the device no longer exists (unpaired elsewhere) and **401** =
missing/wrong token -- either way the app forgets its pairing and shows the login screen.

The app stores `device_id`, `device_token`, `patient_id`. Every other call below is keyed by `patient_id`.

## Reading (Existing)

- `GET /api/app/patients/{patient_id}/home` -> `PatientHome` (`backend/views.py`; generated TS shape in
  `web/src/lib/api-schema.d.ts`): `timezone`, `patient`, `today[]` (slots with `at`, `medicine`, `dose`,
  `state`), `next_dose`, `week[]`, `adherence`, `last_checkin`, `how_doing`, `reminders[]`, `caregiver`.
  Times are ISO; show them in `timezone` (default Asia/Kolkata).
- `GET /api/app/patients/{patient_id}/medicines`, `.../history` -- same pattern, for later screens. Each medicine
  has `source`: `prescribed` (the doctor's, entered by the clinic -- show read-only) or `own` (the patient added it);
  missing on older servers = `prescribed`. Also `from_date` / `to_date` (`YYYY-MM-DD`).

## Own medicines (2026-11-17)

Patients add medicines they take on their own (not from the doctor's prescription) and change or remove them. Calls
and reminders treat them like any other medicine. Header `X-Device-Token` as usual; caregiver phones get 403.

- `POST /api/patients/{patient_id}/own-medicines` -> 201 with the stored dosage. Body:
  `{"medicine_name", "dosage", "frequency": "fixed_times" | "weekly" | "every_x_day", "times": ["08:00", ...],
  "interval_days": int | null, "from_date": "YYYY-MM-DD", "to_date": "YYYY-MM-DD" | null}`. `fixed_times` = every
  day at the times; `weekly` = on `from_date`'s weekday; `every_x_day` needs `interval_days` (2-90). At least one
  time (24-hour `HH:MM`), name and dose 1-80 characters, `to_date` not before `from_date`; otherwise 422. 409 after
  30 own medicines.
- `PUT /api/patients/{patient_id}/medicines/{dosage_id}` -> 200, same body. **403 for a `prescribed` one.**
- `DELETE /api/patients/{patient_id}/medicines/{dosage_id}` -> `{"outcome": "stopped" | "deleted"}`. One with doses
  on record that is still running is **stopped** (ends yesterday, stays under "Finished" with its history);
  otherwise it is **deleted**. 403 for a `prescribed` one.

Refetch `/api/app/patients/{id}/medicines` after any of these.
- `GET /api/app/people` -> everyone: **staff only** now (the apps' debug "pick a patient" was removed 2026-11-11).
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

Open it with the `X-Device-Token` header on the handshake (a socket without it, or for another patient, is refused
with close code 1008). The website opens the same socket with a short-lived `?ticket=` instead.

JSON messages (shapes in `web/src/lib/events.ts`). The ones the apps need:

- `{"type": "snapshot", ..., "voice": {"call_id", "url", "token"}?}` -- sent on connect; `voice` present if a
  voice call is waiting/in progress.
- `{"type": "voice_call", "call_id", "url", "token"}` -- a voice call just started for this patient: **ring**.
- `{"type": "voice_call_ended"}` -- stop ringing / leave the room.
- `{"type": "log_entry", "call_id", "entry": {"type", "channel", "content"}}` -- live transcript lines
  (`entry.type` `agent_said` / `patient_said` ...), optional to show.

The iPhone app (foreground only) rings from `voice_call`. The Android app rings from the push below and may also
use the socket while open.

## Push (Built -- B3, Android only)

FCM **data** messages (no `notification` block -- the app draws its own call screen), `priority: high`, TTL 60 s,
sent to every Android device of the patient that has a `push_token` (`backend/push_fcm.py`). All values are strings.
No health information in the payloads.

- **Ring** -- when a voice call starts (any trigger: Talk now from the web, the operator's Call now, a reminder,
  the dose-time scheduler), to every Android phone except the one that sent `X-Device-Token` when starting it:

  ```json
  {"type": "ring", "call_id": "<id>", "patient_id": "<id>"}
  ```

  The app then calls `GET .../voice-call` for the join details on answer (404 = the call is already over: stop).
- **Stop ringing** -- when that voice call ends for any reason (answered and finished, declined, operator hung
  up, nobody joined in 120 s), to every Android phone of the patient:

  ```json
  {"type": "call_ended", "call_id": "<id>", "patient_id": "<id>"}
  ```

  If the phone is ringing for `call_id`, stop; otherwise ignore it (an in-progress call ends through LiveKit).

Tokens FCM reports as unregistered are cleared (`push_token` -> null); the app sends a fresh one with
`PUT /api/devices/{id}` on launch and from `onNewToken`. Without `FIREBASE_CREDENTIALS` in `.env` nothing is sent
(one log line).
