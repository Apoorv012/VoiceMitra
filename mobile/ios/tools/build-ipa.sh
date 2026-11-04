#!/bin/bash
# Inside WSL: release build of the app -> unsigned mobile/ios/dist/VoiceMitra.ipa (for SideStore, which re-signs it).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
bash "$HERE/wsl-build.sh" VoiceMitra build -c release
mkdir -p "$HERE/../dist"
python3 "$HERE/make-ipa.py" "$HOME/voicemitra-ios/VoiceMitra/xtool/VoiceMitra.app" "$HERE/../dist/VoiceMitra.ipa"
