# VoiceMitra iPhone app

SwiftUI app built on this Windows PC with **xtool** inside WSL (Ubuntu), signed with a free Apple ID. It rings
(CallKit) **only while the app is open** -- a free Apple ID gives no push. Spec and status: `SPEC.md`. Contract with
the backend: `../API.md`.

| Folder | What |
|---|---|
| `VoiceMitra/` | the app (SwiftPM package + `xtool.yml`; `Support/Info.plist` is merged into the app's) |
| `LiveKitHello/` | I1 toolchain probe: the smallest app that links the LiveKit Swift SDK |
| `tools/` | `wsl-build.sh` (copy a package into WSL, run xtool), `build-ipa.sh` + `make-ipa.py` (unsigned .ipa for SideStore), the usbmux relay (`muxrelay.py`, `muxbridge_win.py`, `muxprobe.py`) |
| `dist/` | `VoiceMitra.ipa` after `build-ipa.sh` (gitignored) |

## One-time setup on the PC (done 2026-11-04)

- WSL Ubuntu 26.04 with Swift 6.4.2 (`~/toolchains/`) and xtool 1.24 (`~/.local/bin/xtool`);
  `source ~/voicemitra-ios-env.sh` puts both on `PATH`. Swift's system libraries came from:
  ```bash
  sudo apt-get update && sudo apt-get install -y libncurses6 libncurses-dev libc6-dev libcurl4-openssl-dev libgcc-15-dev libstdc++-15-dev libpython3-dev libxml2-dev libz3-dev pkg-config zip unzip zlib1g-dev gnupg2 libimobiledevice-utils
  ```
- iOS SDK: `xtool sdk install /mnt/c/Users/apoor/Downloads/Xcode_27.2.xip` (the `.xip` from
  <https://developer.apple.com/download/all/?q=Xcode>; Xcode itself never runs).
- Apple ID: `xtool auth login` with a **spare** Apple ID (password mode uses private Apple APIs). Check with
  `xtool auth status`; the login lasts a year.
- iPhone link: Apple Mobile Device Service (installed with iTunes / Apple Devices) owns the USB connection on
  Windows and listens on 127.0.0.1:27015. **No `usbipd`, no admin step:** `tools/muxrelay.py` (inside WSL) relays
  xtool's device traffic there through a Windows Python (`tools/muxbridge_win.py`, `C:\Python314\python.exe`).
  `wsl-build.sh` starts it; `python3 tools/muxprobe.py` lists the phones it can see.

## Develop on your own iPhone (xtool)

Once per phone: plug it in by USB, unlock it, tap **Trust** (iTunes / Apple Devices must see it). Then, in Ubuntu:

```bash
bash /mnt/d/dev/Projects/VoiceMitra/mobile/ios/tools/wsl-build.sh VoiceMitra build   # compile only (~10 s incremental)
bash /mnt/d/dev/Projects/VoiceMitra/mobile/ios/tools/wsl-build.sh VoiceMitra run     # build, sign, install, launch
```

The first `run` registers the phone with the Apple ID (signing is impossible before that: Apple answers "no
current iOS devices on this team"). Then on the phone, once: Settings -> General -> **VPN & Device Management** ->
the Apple ID under "Developer App" -> **Trust**, and Settings -> Privacy & Security -> **Developer Mode** -> on (the
phone restarts). Debug builds also show a "Developer: pick a patient" list on the sign-in screen.

The package is copied to `~/voicemitra-ios/<name>` in WSL first (building on `/mnt/d` is slow); exact dependency
versions are kept in the committed `Package.resolved`. A free-account install **expires after 7 days** -- re-run
`run`, or use SideStore.

## Install on the household iPhones (SideStore)

SideStore is an app on the iPhone that installs our `.ipa` and **re-signs it by itself every week** over Wi-Fi,
so the phone doesn't need the PC again. Free Apple ID limits: 3 sideloaded apps per phone (SideStore is one of
them), 10 new app IDs per week per Apple ID. Use the same spare Apple ID for every phone.

**1. Build the .ipa (PC, Ubuntu):**
```bash
bash /mnt/d/dev/Projects/VoiceMitra/mobile/ios/tools/build-ipa.sh
```
-> `mobile/ios/dist/VoiceMitra.ipa` (~10 MB, unsigned release build; no developer patient list).

**2. Put SideStore on the phone (PC, once per phone; from docs.sidestore.io):**
1. On the iPhone, install **LocalDevVPN** from the App Store, open it, tap Connect and allow the VPN profile.
2. On the PC, install **iloader** (MSI from its GitHub releases page, linked from docs.sidestore.io).
3. Plug the iPhone in, unlock it, Trust. In iloader: sign in with the spare Apple ID (case-sensitive), pick the
   phone, **Install SideStore (Stable)**. (iloader should also set up SideStore's pairing file; if SideStore
   asks for one, follow the pairing-file page on docs.sidestore.io.)
4. On the iPhone: Settings -> General -> VPN & Device Management -> the Apple ID -> **Trust**; Settings -> Privacy &
   Security -> **Developer Mode** -> on (restarts).
5. Open LocalDevVPN -> Connect, then open SideStore, sign in with the same Apple ID, and in My Apps tap the
   "7 DAYS" button next to SideStore once (say yes to a new certificate if asked).

**3. Install VoiceMitra (phone):**
1. Get `VoiceMitra.ipa` onto the phone's Files app. Easiest on the same Wi-Fi: on the PC run
   ```bash
   python -m http.server 8765 --directory D:\dev\Projects\VoiceMitra\mobile\ios\dist
   ```
   (allow it through the Windows firewall for private networks), open `http://<pc-ip>:8765/VoiceMitra.ipa` in
   Safari on the iPhone -> Download -> it lands in Files -> Downloads. Stop the server afterwards (Ctrl+C).
   Sending the file to yourself (WhatsApp, Google Drive) and saving it to Files works too.
2. LocalDevVPN -> Connect. SideStore -> My Apps -> **+** -> pick `VoiceMitra.ipa`. It installs and appears on the
   home screen.
3. Open VoiceMitra: allow the **microphone**, then sign in (username + password from the patient's Me tab on the
   web, "Phone app login"), or "Use a code instead" (Me tab -> "Connect a phone"). Settings (gear) has the
   server address; the default is the tunnel, `https://test-voicemitra.apoorvm.com`.

**Refresh (every 7 days):** SideStore re-signs its apps in the background when LocalDevVPN is connected and the
phone is on Wi-Fi. To be safe, open LocalDevVPN -> Connect, then SideStore -> My Apps -> **Refresh All** once a
week; the day counter next to each app shows the time left. If it reaches 0, VoiceMitra won't open until refreshed
(the sign-in should survive a refresh, since the app stays signed by the same Apple ID -- to be confirmed in the
device test). If SideStore complains about the
pairing file (after an iOS update or a reset), make a new one with iloader on the PC.

**Updating the app:** build a new `.ipa` (step 1) and install it over the old one the same way (step 3); the
sign-in is kept.

## Ringing: what to expect

- VoiceMitra must be **open on screen** to ring (CallKit's normal call screen/banner). Locked or closed: no ring;
  the agent waits 120 s, then the caregiver gets the "couldn't be reached" alert.
- A call already in progress keeps going when the screen locks (background audio).
- "Not connected: VoiceMitra can't ring this phone right now" on the home screen = the live connection to the
  server is down (it retries by itself).
