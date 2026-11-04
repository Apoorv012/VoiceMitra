# iPhone app -- build spec

Owner: the **iPhone agent**. It owns `mobile/ios/` **only** -- never edits `backend/`, `web/`, `tests/` or
`mobile/android/`; anything it needs from the backend goes to the lead agent (see `../README.md`). Read
`../README.md`, `../API.md` (the contract), `../../PLAN.md` and `../../CLAUDE.md` (git rules: **never commit or
push**) first.

**Goal for now: the iPhone gets a call only while the app is open (in the foreground).** A free Apple ID gives no
push notifications, so a closed app can't ring -- that's accepted for now (later options: Zadarma app,
Groundwire $9.99, AlarmKit, or Apple's $99/yr account; see PLAN.md). If the app isn't open, the backend's
existing behaviour applies: the agent waits 120 s, then the caregiver gets the "couldn't be reached" alert.

## Toolchain (see `../README.md` for xtool vs SideStore)

SwiftUI app as a **Swift Package built with xtool** (WSL on this Windows PC), signed with a free Apple ID (use a
spare Apple ID: xtool's password login uses private Apple APIs). Develop with `xtool dev` over USB; install on the
household iPhones through **SideStore** so it re-signs every 7 days. Free-account limits: 3 sideloaded apps per
phone (SideStore is one), 10 app IDs a week, Developer Mode on.

## Steps

- **I1 Toolchain check (do first, timebox half a day).** xtool installed in WSL with the iOS SDK from Xcode
  (downloaded once from Apple), the iPhone reachable from WSL (USB passthrough with `usbipd-win`, or whatever
  xtool's Linux/WSL guide says), and a hello-world app **that links the LiveKit Swift SDK**
  (`client-sdk-swift`, SwiftPM; it pulls a WebRTC binary framework -- the main xtool risk) running on the phone.
  If xtool can't build it: fall back to building an unsigned .ipa on a free GitHub Actions macOS runner (public
  repo) and installing it through SideStore. Report the outcome to the lead agent before going further.
- **I2 Shell + pairing.** Server URL setting; pairing screen (6-digit code -> `POST /api/devices/pair` with
  `platform: "ios"`, `push_token: null`), store the device in the Keychain. Until the Android agent's pairing
  endpoint exists: a dev "pick a patient" list from `/api/app/people`.
- **I3 Home.** Same content as Android's: greeting, next medicine, today's doses, big **"Talk to VoiceMitra"**
  (`POST .../voice-call` with `X-Device-Token`, then join). Hindi/English, large text (Dynamic Type), high contrast.
- **I4 Ringing while open.** Keep the patient socket (`/ws/patients/{id}/chat`) connected while the app is in the
  foreground (reconnect with backoff; drop it in the background). On `voice_call` (or a `snapshot` with `voice`):
  show the **native call screen via CallKit** (`CXProvider.reportNewIncomingCall` -- needs no push or paid
  capability while the app is running) with ringtone; answer -> join LiveKit with that event's `url`/`token`;
  decline -> `POST .../call/end`; `voice_call_ended` -> end the CallKit call. If CallKit misbehaves without
  PushKit, use a full-screen in-app ringing view instead.
- **I5 Call screen.** LiveKit room, microphone, speaker on by default, big hang-up/mute, timer. Info.plist:
  `NSMicrophoneUsageDescription`, `UIBackgroundModes` `audio` (and `voip` if CallKit needs it) so a call already
  in progress survives the screen locking. AVAudioSession `.playAndRecord` / `.voiceChat`.
- **I6 Install for the house pilot** via SideStore; a short `mobile/ios/README.md` (build, install, refresh).

## Done means

With the app open on an iPhone: Call now from the web rings it (CallKit screen), answering connects to the agent
and the conversation works both ways, decline ends the call; Talk now works; pairing works; it runs after a
SideStore refresh. Closed app -> no ring (expected). This file's Status section updated.

## Things you need from the user

A spare Apple ID, the Xcode download (Apple ID sign-in), the iPhone with Developer Mode on, SideStore installed
on it (needs a pairing file made on the PC once).

## Status

Not started.
