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

**2026-11-04 -- I1 passed on the build side (xtool builds and links LiveKit; no fallback needed). I2-I5 code
compiles cleanly. Nothing has run on a phone yet: waiting on the user's `xtool auth login` (spare Apple ID) and
the iPhone plugged in (README "What the user does", steps 3-4).**

- **I1 toolchain (done except on-device):** WSL Ubuntu 26.04 with Swift 6.4.2 and xtool 1.24 in the user's home
  (`source ~/voicemitra-ios-env.sh`); Swift's system libraries installed; iOS SDK from `Xcode_27.2.xip`
  (`xtool sdk install`, iPhoneOS 27.2). `LiveKitHello/` (LiveKit 2.19, WebRTC xcframework 150.7871.04,
  RustLiveKitFFI) builds in ~2 min to an arm64 iOS `.app` (28 MB) with both frameworks embedded and linked via
  `@rpath`. Device link without usbipd or admin: Apple Mobile Device Service on Windows (127.0.0.1:27015) is reached
  from WSL through `tools/muxrelay.py` + `tools/muxbridge_win.py` (verified: the device list comes back, empty so
  far). Still to verify: sign, install, launch on the phone.
- **I2-I5 (compiles -- `tools/wsl-build.sh VoiceMitra build`, merged Info.plist checked; not run on a device):**
  - Sign-in: the main screen is **username + password** (`POST /api/auth/login`, API.md "Identity: login";
    username trimmed, password as typed; 401 wrong, 429 too many). "Use a code instead" -> the 6-digit pairing pad
    (`POST /api/devices/pair`, `platform: "ios"`, `push_token: null`; 400 wrong/expired, 429). Either way the
    device is stored in the Keychain; `GET /api/devices/{id}` on launch, 401/404 -> back to sign-in; "Sign out" in
    Settings = `DELETE /api/devices/{id}`. Server URL setting (default the tunnel
    `https://test-voicemitra.apoorvm.com`). Debug builds also have a "pick a patient" list (`DEV_PICKER`,
    `/api/app/people`).
  - Home: greeting, next dose, today's doses, how-doing, upcoming reminder calls, big Talk button (`POST
    .../voice-call` with `X-Device-Token`; join from the socket's `voice_call` or `GET .../voice-call`).
    Hindi/English toggle, Dynamic Type fonts.
  - Ringing: patient socket while in the foreground only (backoff 1-30 s, ping 20 s); `voice_call` /
    `snapshot.voice` -> CallKit incoming call; answer -> LiveKit join; decline/hang-up -> `POST .../call/end`;
    `voice_call_ended` or room disconnect -> CallKit call ended. In-app full-screen ring if CallKit refuses.
  - Call screen: timer, mute, speaker (on by default), big hang-up. Audio: LiveKit's automatic session config off,
    its engine only enabled between CallKit's didActivate/didDeactivate; `.playAndRecord` / `.voiceChat`.
    Info.plist: microphone text, `UIBackgroundModes` audio + voip, local-network ATS.
- **Not done:** run on the phone and test everything in "Done means" (sign in with a test patient's login, not
  "Apoorv"); I6 (SideStore install + README section).
