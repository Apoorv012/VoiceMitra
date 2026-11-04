# VoiceMitra phone apps

Native apps that let the patient's phone **ring like a normal call** and connect them to the same voice agent as
the web app (LiveKit room; the agent side doesn't change). Decided 2026-11-03/04 -- background in `../PLAN.md`
("Pilot" -> platform).

| | Android (`android/`) | iPhone (`ios/`) |
|---|---|---|
| Rings when | always, even locked/closed (FCM push -> full-screen call screen) | **only while the app is open** (for now) |
| Cost | free (sideloaded APK, free FCM) | free (free Apple ID; xtool + SideStore) |
| Priority | **make it perfect** -- the main demo | basic: works while open |
| Spec | `android/SPEC.md` | `ios/SPEC.md` |

Shared contract: `API.md`. Why the iPhone can't ring when closed: a free Apple ID has no push notifications, so
nothing can wake the app. Ruled out / parked: PWA (can't ring), Twilio trial (strips the audio stream), WhatsApp
(not free), Exotel (7-day trial), Linphone (tested: rings but never connects, and even its own app-to-app calls had
no audio; code removed). Later options for a closed iPhone: Zadarma's free app/PBX (untested), Groundwire
($9.99 once), AlarmKit (iOS 26), or Apple's $99/yr account (PushKit + CallKit, the proper way).

## How the agents work (one lead agent, two builders)

The user starts **one lead agent**; it starts and coordinates the **Android agent** and the **iPhone agent**.

- **Same checkout, no worktrees, nobody commits.** CLAUDE.md: Claude never runs `git commit`/`git push` (the
  user signs commits). Separate branches would need commits to merge, so both builders work in this checkout
  and keep to their own files. They may `git add`; the user commits.
- **File ownership (never edit outside it):**
  - Android agent: `mobile/android/`, `backend/`, `tests/`, `web/`, `requirements.txt`, `.env.example`, `mobile/API.md`.
  - iPhone agent: `mobile/ios/` only.
  - Login agent (added 2026-11-04, username + password for the apps): new files `backend/auth.py` /
    `backend/routers/auth.py`, `tests/test_auth.py`, a new web component; small Edit-only additions to
    `backend/models.py`, `backend/main.py`, `backend/routers/devices.py`, the patient Me page, `web/src/lib/i18n.tsx`,
    `mobile/API.md` and the generated API types. The Android agent keeps everything else in its list. In shared
    files both use Edit only and re-read before editing.
  - Lead agent: `PLAN.md`, `mobile/README.md`, `CLAUDE.md`; it relays anything one builder needs from the other's area.
- **Order:** start both at once. The Android agent does the backend steps B1 (pairing) -> B2 (join info) -> B3
  (push) first, because the iPhone app needs B1-B2 too; the iPhone agent starts with its toolchain check (I1) and
  a dev patient picker, so it isn't blocked. When B1/B2 land, the lead tells the iPhone agent.
- **Don't break each other:** the backend must keep working for the web app and the iPhone app at every point
  (run `python -m pytest`); contract changes go into `API.md` first and the lead tells the iPhone agent.
- **Status:** each builder keeps the Status section of its own SPEC.md current. The lead mirrors progress into
  `PLAN.md` (the project's source of truth) as steps finish, and reports to the user.
- **Stop and ask the user** for accounts and devices (Claude doesn't create accounts): Firebase project + files,
  a spare Apple ID, the Xcode download, phones in Developer Mode / USB debugging.
- Shared test data: the real `voicemitra` DB has patients (e.g. "Apoorv"); for destructive tests use a throwaway
  DB name ending in `test` and drop it afterwards.
- Running the stack: `npm run dev` (API :8000 + web :3000 + tunnel). Phones reach it through the tunnel's HTTPS
  hostname (README).

## xtool vs SideStore (iPhone)

They aren't alternatives -- they do different jobs, and the plan uses both.

| | **xtool** | **SideStore** |
|---|---|---|
| What it is | A cross-platform Xcode replacement: **builds**, signs and installs an iOS app | An app **on the iPhone** that installs and **re-signs** sideloaded apps |
| Runs on | Linux / WSL on Windows (or macOS) | the iPhone (a PC is needed once to make a pairing file) |
| Builds code? | Yes -- SwiftPM packages (SwiftUI) | No -- installs a ready-made `.ipa` |
| Signing | free Apple ID (password login via private Apple APIs: use a spare ID) or a paid account's API key | the free Apple ID you sign into it |
| 7-day expiry | you re-run it (phone plugged in / reachable) every week | **refreshes by itself** over Wi-Fi (local VPN), no PC |
| Best for | development: build -> install -> run on your own phone | the household pilot phones: install once, keeps working |
| Risks | Windows only via WSL (USB passthrough to WSL); SwiftPM only; untested with LiveKit's WebRTC binary framework | refresh can fail silently (app won't open until re-signed); counts as 1 of the 3 free sideloaded apps |

**Use:** xtool to build (and install on the dev phone while coding); SideStore to install the `.ipa` on the
household iPhones so they stay signed. If xtool can't build the LiveKit SDK, build the `.ipa` on a free GitHub
Actions macOS runner instead and still install it with SideStore.
