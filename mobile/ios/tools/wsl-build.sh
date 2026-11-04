#!/bin/bash
# Usage (inside WSL): wsl-build.sh <package dir under mobile/ios> [build|run|...xtool dev args]
# Copies the package into ~/voicemitra-ios/<name> (fast native FS), starts the usbmux relay if needed, runs xtool.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
PKG="${1:?package name, e.g. VoiceMitra}"; shift || true
ACTION="${1:-build}"; shift || true
SRC="$HERE/../$PKG"
DST="$HOME/voicemitra-ios/$PKG"
source "$HOME/voicemitra-ios-env.sh"

mkdir -p "$DST"
# Mirror sources but keep the WSL-side build caches (.build, xtool/).
if command -v rsync >/dev/null; then
  rsync -a --delete --exclude .build --exclude xtool --exclude .swiftpm --exclude .bsp "$SRC/" "$DST/"
else
  find "$DST" -mindepth 1 -maxdepth 1 ! -name .build ! -name xtool ! -name .swiftpm -exec rm -rf {} +
  (cd "$SRC" && tar --exclude=.build --exclude=xtool --exclude=.swiftpm -cf - .) | (cd "$DST" && tar -xf -)
fi

export USBMUXD_SOCKET_ADDRESS=127.0.0.1:27015
if ! (exec 3<>/dev/tcp/127.0.0.1/27015) 2>/dev/null; then
  nohup python3 "$HERE/muxrelay.py" >/tmp/voicemitra-muxrelay.log 2>&1 &
  sleep 1
fi

cd "$DST"
status=0
xtool dev "$ACTION" "$@" || status=$?
# Keep the exact dependency versions in the repo (Package.resolved is committed).
if [ -f "$DST/Package.resolved" ] && ! cmp -s "$DST/Package.resolved" "$SRC/Package.resolved"; then
  cp "$DST/Package.resolved" "$SRC/Package.resolved"
fi
exit $status
