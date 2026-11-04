# VoiceMitra iPhone app

SwiftUI app built on this Windows PC with **xtool** inside WSL (Ubuntu), signed with a free Apple ID.
Spec and status: `SPEC.md`. Contract with the backend: `../API.md`.

| Folder | What |
|---|---|
| `LiveKitHello/` | I1 toolchain probe: the smallest app that links the LiveKit Swift SDK |
| `VoiceMitra/` | the app (SwiftPM package + `xtool.yml`) |
| `tools/` | `wsl-build.sh` (copy a package into WSL and run xtool there), the usbmux relay |

## One-time setup

### What's already done on this PC
- WSL Ubuntu 26.04 exists. Swift 6.4.2 is unpacked in `~/toolchains/`, xtool 1.24 is at `~/.local/bin/xtool`;
  `source ~/voicemitra-ios-env.sh` puts both on `PATH`.
- Apple Mobile Device Service (from iTunes / Apple Devices) runs on Windows and owns the USB connection to the
  iPhone. **No `usbipd`, no admin step:** `tools/muxrelay.py` (run inside WSL) relays xtool's device traffic to that
  service through a Windows Python (`tools/muxbridge_win.py`, uses `C:\Python314\python.exe`).
  `tools/wsl-build.sh` starts the relay for you.

### What the user does (once)
Steps 1-2 were done on 2026-11-04 (with `Xcode_27.2.xip`); 3-4 are still to do.

1. **System libraries for Swift** -- in an Ubuntu (WSL) terminal (asks for your Linux password):
   ```bash
   sudo apt-get update && sudo apt-get install -y libncurses6 libncurses-dev libc6-dev libcurl4-openssl-dev libgcc-15-dev libstdc++-15-dev libpython3-dev libxml2-dev libz3-dev pkg-config unzip zlib1g-dev gnupg2 libimobiledevice-utils
   ```
2. **Xcode 27.1** -- download `Xcode_27.1.xip` (~3-4 GB) from
   <https://developer.apple.com/download/all/?q=Xcode> in the browser (sign in with any Apple ID, accept the
   licence) into `C:\Users\apoor\Downloads`. xtool only extracts the iOS SDK from it; Xcode never runs.
3. **Apple ID sign-in** (use a spare Apple ID: xtool's password login uses private Apple APIs) -- in Ubuntu:
   ```bash
   source ~/voicemitra-ios-env.sh && xtool auth login
   ```
   Pick `1: Password`, then the Apple ID, password and the 2FA code. Credentials go only to Apple.
4. **iPhone** -- plug it into the PC by USB, unlock it, tap **Trust**. After the first install: Settings ->
   Privacy & Security -> **Developer Mode** -> on (the phone restarts), and Settings -> General -> VPN & Device
   Management -> trust the developer profile of the spare Apple ID.

Then (the agent can run these): `xtool sdk install /mnt/c/Users/apoor/Downloads/Xcode_27.2.xip` and
`tools/wsl-build.sh LiveKitHello run`.

## Build and run (development)

```bash
# in Ubuntu (WSL), from anywhere
bash /mnt/d/dev/Projects/VoiceMitra/mobile/ios/tools/wsl-build.sh VoiceMitra build   # compile only
bash /mnt/d/dev/Projects/VoiceMitra/mobile/ios/tools/wsl-build.sh VoiceMitra run     # build, sign, install, launch
```

The package is copied to `~/voicemitra-ios/<name>` in WSL first (building on `/mnt/d` is slow and SwiftPM's
symlinks misbehave there). Free-account signing expires after 7 days: re-run `run` with the phone plugged in, or
use SideStore (below).

## Install on the household iPhones (SideStore)

Filled in at step I6.
