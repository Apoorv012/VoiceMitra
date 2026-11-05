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

**2026-11-04 -- Works on the user's iPhone (iOS 26.5, installed with xtool `run`): sign-in, Talk now (both ways,
speaker and earpiece), Call now from the web ringing CallKit while the app is open, answer, decline. Closed app ->
no ring (expected; free Apple ID). Not yet: SideStore install (I6) and the skipped checklist items below.**

- **UI redesign (2026-11-05, builds cleanly; on-device check pending):** the first version "looked horrendous", so
  the app now matches the web patient app: `Theme.swift` holds the web's colours (`globals.css`, light + dark,
  good/warn/serious/crit) and shared pieces (cards, pills, primary button, EN/हि switch, Dynamic Type page titles).
  Four tabs like `web/src/app/patients/[id]/`: **Today** (greeting, the "Talk to VoiceMitra" card with the one big
  button, next dose, today's medicines, the week with legend, how you're doing, calls coming up, family line,
  "Ready for calls" line), **Medicines** (allergies, current/finished with schedule, days left, taken this week),
  **History** (check-ins and family alerts in one timeline, doctor chips as on the web), **Me** (profile,
  language, server, family contact with a Call button, allergies, this iPhone, Sign out). `SignInView` replaces
  `PairingView` (password first, 6-box code pad). Call screen: dark full-screen, big round buttons, the web's call
  wording. New app icon. Wording from `web/src/lib/i18n.tsx`.
- **Device test so far (2026-11-04, test patient `05803d68-...`, login `testiphone`):** install OK (two Apple
  provisioning hiccups: a timeout, then HTTP 500 -- retry worked; needs the `zip` apt package). Login OK; the
  device registers (`platform: ios`) and the launch check works. Talk now connects and plays the agent.
  **Crash found and fixed:** every call crashed with `-[Room addDelegate:]: unrecognized selector` -- xtool can't
  pre-link with lld (`-r`), so each package target (`LiveKit.o`) is really a static archive and the final link
  dropped archive members only reachable through ObjC categories (21 of LiveKit's 116). Fix: `-Xlinker -ObjC` in
  `VoiceMitra/Package.swift` (all 118 categories now in the binary). The crash loop also left the call waiting on
  the backend, so it re-rang on every launch until declined -- gone with the fix.
  **Reply lag on one call (3.5 / 0.2 / 12.3 s) was the PC's network, not the app:** the backend log showed
  utterances arriving in bursts (START->END 30-45 ms) after a Sarvam keepalive error, plus 10.7 s of LLM time;
  the tunnel logged network errors at the same time. The next three iPhone calls replied in 0.2-0.6 s, like web
  calls, on speaker and on earpiece.
  **Closed app:** no ring (expected). Opening the app while the backend still waits (120 s) rings at once
  (`snapshot.voice`), which is useful: the patient can still take the call.
- **App icon:** `VoiceMitra/Resources/AppIcon.png` (`tools/make-icon.py`; the web app's blue voice-wave mark),
  `iconPath` in `xtool.yml`.

- **I1 toolchain (done except on-device):** WSL Ubuntu 26.04 with Swift 6.4.2 and xtool 1.24 in the user's home
  (`source ~/voicemitra-ios-env.sh`); Swift's system libraries installed; iOS SDK from `Xcode_27.2.xip`
  (`xtool sdk install`, iPhoneOS 27.2). `LiveKitHello/` (LiveKit 2.19, WebRTC xcframework 150.7871.04,
  RustLiveKitFFI) builds in ~2 min to an arm64 iOS `.app` (28 MB) with both frameworks embedded and linked via
  `@rpath`. Device link without usbipd or admin: Apple Mobile Device Service on Windows (127.0.0.1:27015) is reached
  from WSL through `tools/muxrelay.py` + `tools/muxbridge_win.py` (verified: the device list comes back, empty so
  far). Signing needs the phone: with no device registered, Apple refuses the free-account profile ("no current
  iOS devices on this team"); the first `wsl-build.sh VoiceMitra run` with the phone plugged in registers it.
  Unsigned release `.ipa` for SideStore builds without a device: `tools/build-ipa.sh` -> `dist/VoiceMitra.ipa`
  (~10 MB; `make-ipa.py` packs it, since WSL has no `zip`). Still to verify: install + launch on the phone.
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
  - Review fixes (2026-11-04): the socket stays open while the app is merely inactive (CallKit's ringing banner)
    and during a call in the background, so `voice_call_ended` isn't missed; the microphone is asked for on the
    home screen, and the audio engine is re-enabled once permission arrives (else the first call could be silent);
    "couldn't refresh" note when stale home data is shown.
- **I6 docs:** README "Install on the household iPhones (SideStore)": build the .ipa, iloader + LocalDevVPN to put
  SideStore on the phone, Trust + Developer Mode, install via SideStore's +, weekly refresh, updating.
- **Not done:** everything on a device (checklist below); I6's actual SideStore install on a household phone.

### On-device test checklist

Run with the backend + tunnel up (`npm run dev`). Use a **test patient** with a login set on its Me tab (not
"Apoorv" without asking the lead). Mark each one with the date when it passes.

1. [x] (2026-11-04) **Install:** `wsl-build.sh VoiceMitra run` installs and launches; Trust profile + Developer Mode done.
2. [x] (2026-11-04; calls have a working mic) **Microphone prompt** appears on the home screen the first time (not during a call).
3. [x] (2026-11-04, right password only; wrong-password case skipped by the user) **Login:** right username + password -> home. Wrong password -> "Wrong username or password". Username with
   different case / spaces still works.
4. [ ] (skipped) **Code pairing:** "Use a code instead", code from the web's Me tab -> home; an old/used code -> the
   "wrong or expired" message.
5. [~] (2026-11-04: stays signed in across relaunches and reinstalls; unpair/sign-out not tried) **Still paired after relaunch** (kill the app, reopen -> home). Unpair the phone on the web, reopen the app
   -> back to sign-in. Settings -> Sign out -> sign-in screen, and the phone is gone from the web's list.
6. [~] (2026-11-04: home loads; Hindi, large text, offline not tried) **Home:** name, next dose and today's doses match the web's patient page; Hindi toggle switches every label;
   largest Dynamic Type size still readable; airplane mode -> error banner / "not connected" line, recovers by
   itself when back online.
7. [x] (2026-11-04, speaker and earpiece) **Talk now:** the button starts a call, the call screen shows "Connecting…" then a timer; the agent's
   greeting is heard on the speaker; the agent hears the patient (check the transcript on the web).
8. [x] (2026-11-04) **Call now from the web (operator page) while the app is open:** CallKit banner rings with the ringtone.
   **Answer** -> connected both ways. Repeat and **decline** -> ringing stops and the web shows the call ended.
9. [ ] (skipped) **Caller gives up:** Call now, don't answer -> after ~120 s the ring stops by itself (voice_call_ended).
10. [~] (2026-11-04: speaker toggle and hang-up work; mute not confirmed) **During a call:** mute (agent stops hearing), speaker/phone toggle, hang up (call ends on the web too).
    The agent ending the call closes the call screen.
11. [x] (2026-11-04, user report) **Screen lock during a call:** press the side button mid-call -> the conversation keeps going; unlock ->
    still connected (green call pill).
12. [x] (2026-11-04: no ring, as expected; rings when reopened within 120 s) **App in background / closed:** Call now -> no ring (expected); the caregiver gets "couldn't be reached"
    after ~120 s.
13. [ ] (skipped) **Web page open at the same time:** answering on the phone while the patient's web page is open -> only
    one of them stays in the room (API.md: one `patient`); note which.
14. [ ] (not yet) **SideStore (I6):** `build-ipa.sh` -> install via SideStore -> sign in -> rings; after a SideStore refresh
    the app opens and is still signed in.
