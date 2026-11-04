# Android app (+ the backend pieces the phones need) -- build spec

Owner: the **Android agent**. It owns `mobile/android/`, `backend/`, `tests/`, `web/` and `mobile/API.md`
(keep the contract in sync with what you build). It never touches `mobile/ios/`. Read `../README.md` (how the
agents work together), `../API.md` (the contract), `../../PLAN.md` and `../../CLAUDE.md` (git rules: **never
commit or push**; stage and describe) first.

**Goal: make this app perfect** -- the main demo. A locked Android phone rings like a normal call at dose time
(or when someone presses Call now), the patient swipes to answer and talks to the same VoiceMitra voice agent
as the web app. Free: sideloaded APK + Firebase Cloud Messaging (FCM). Users are elderly and not tech-savvy.

## Backend first (B1-B3 unblock the iPhone agent too -- tell the lead agent when each lands)

- **B1 Pairing + devices.** Models `Device` (patient_id, platform, push_token, name, token_hash, created_at,
  last_seen) and `PairingCode` (code, patient_id, expires_at, used) in `backend/models.py`, following the Mongo
  id convention in CLAUDE.md. `backend/routers/devices.py` with the endpoints in `../API.md`. Web: a "Connect a
  phone" button on the patient's page (`web/src/app/patients/[id]/`) that shows the code big, with a countdown,
  Hindi/English via `web/src/lib/i18n.tsx`. Regenerate API types (`python -m backend.dump_openapi`, then
  `npm run gen:api` in `web/`). Tests in `tests/`.
- **B2 Join info.** `GET /api/patients/{id}/voice-call` -> `{call_id, url, token}` / 404, from
  `live_calls.get_voice_call`.
- **B3 Ring push.** `backend/push_fcm.py` with `firebase-admin` (add to `requirements.txt`); credentials from
  `FIREBASE_CREDENTIALS` (path to the service-account JSON, add to `.env.example`; push is skipped with a log line
  when it's unset, so nothing breaks without it). In `live_calls.start_voice_call`, send the `ring` data message
  in `../API.md` to the patient's Android devices, except the one that started the call (`X-Device-Token`). Drop
  tokens FCM reports as unregistered. Test with a fake sender.
- **B4 Reminders ring the phone.** `live_calls._fire_reminder` still starts a **chat** call (`start_call`);
  make it start a voice call so "remind me in an hour" rings the phone.
- **B5 Dose-time ringing (pilot step 4) + retry (step 5)** -- after the app works end to end: `backend/dose_scheduler.py`
  arms a timer per upcoming dose slot (`insights.build_slots`; same asyncio-timer pattern as `arm_reminder`,
  re-armed on startup and when prescriptions change) and starts a voice call for that slot
  (`start_voice_call(slot_at=..., dosage_ids=...)`). Not answered -> ring again after 5 min once -> then the
  existing caregiver "couldn't be reached" alert (today it fires after the agent's 120 s join wait). Update
  PLAN.md's pilot steps 4-5 through the lead agent.

## The app (`mobile/android/`)

Kotlin, Jetpack Compose, Gradle (Android Studio), minSdk 26, target the latest stable SDK. LiveKit Android SDK
(`io.livekit:livekit-android`, latest stable) for the call; Firebase Messaging; OkHttp/Retrofit (or Ktor) +
kotlinx.serialization for the API. Application id e.g. `in.voicemitra.patient`. Sideloaded debug/release APK,
no Play Store.

- **A1 Shell + pairing.** Settings: server URL (default from a build constant). Pairing screen: enter the 6-digit
  code (big number pad) -> `POST /api/devices/pair` with the FCM token -> store device_id/token/patient_id
  (DataStore / EncryptedSharedPreferences). Debug builds also offer "pick a patient" from `/api/app/people`.
- **A2 Home.** From `GET /api/app/patients/{id}/home`: greeting, next medicine (time + names), today's doses with
  their state, and one big **"Talk to VoiceMitra"** button (`POST .../voice-call` with `X-Device-Token`, then
  join). Refresh on resume; optional live updates from the patient socket.
- **A3 Call screen.** Join LiveKit with the token, microphone on, speaker by default (elderly users), big
  hang-up and mute buttons, call timer, optional live transcript from `log_entry`. Runs in a foreground service
  (`phoneCall|microphone` type) so it survives the screen locking. Hang up -> `POST .../call/end`.
- **A4 Ringing (the core).** `FirebaseMessagingService` gets `ring` -> post a **CallStyle** notification with a
  full-screen intent to an `IncomingCallActivity` (shows over the lock screen and turns the screen on:
  `setShowWhenLocked`, `setTurnScreenOn`), ringtone + vibration, auto-stop after ~60 s. Answer ->
  `GET .../voice-call` -> call screen. Decline -> `POST .../call/end`. Also ring from the socket's `voice_call`
  while the app is open (one code path). Consider Jetpack `androidx.core:core-telecom` (self-managed calls) so
  the system treats it as a real call (audio focus, Bluetooth, the call shows in the status bar).
- **A5 First-run setup checklist** (screen with green ticks, re-checked on every launch): notifications
  permission (Android 13+), **full-screen intent permission** (Android 14+, user grants it in settings), microphone,
  **battery optimisation off** (`REQUEST_IGNORE_BATTERY_OPTIMIZATIONS` + a hint for Xiaomi/Oppo/Vivo/Realme
  autostart pages). Without these the phone may not ring when locked.
- **A6 Polish for elderly users.** Large text (honour system font size), high contrast, everything Hindi/English
  (same wording as the web app's i18n where it exists), plain-language errors with a retry, works on slow
  networks, TalkBack labels, no dead ends. Reconnect if the network drops mid-call.

## Done means

- On a real locked Android phone: the operator's **Call now** (web) and a dose-time slot both make it ring with
  the full-screen call screen; swipe to answer -> the agent greets the patient and the conversation works; decline
  -> the call ends; not answered -> retried once, then the caregiver alert.
- Talk now from the app works; pairing via the web code works; unpair works.
- Backend tests pass (`python -m pytest`), web `npx tsc --noEmit` + lint pass, APK builds (`./gradlew assembleDebug`).
- A short "how to build and install the APK" section in `mobile/android/README.md`; this file's Status section updated.

## Things you need from the user (Claude doesn't create accounts)

A Firebase project (free) with an Android app for the application id -> `google-services.json` (in
`mobile/android/app/`, gitignored) and a service-account JSON for the backend (path in `.env`). An Android phone
with USB debugging, or sharing the APK file.

## Status

Not started.
