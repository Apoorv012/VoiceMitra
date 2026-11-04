#!/usr/bin/env python3
"""Packs a built .app into an unsigned .ipa (Payload/<Name>.app, zipped) for SideStore, which re-signs it.

    python3 make-ipa.py ~/voicemitra-ios/VoiceMitra/xtool/VoiceMitra.app VoiceMitra.ipa

Same layout `xtool dev build --ipa` makes; this avoids needing the `zip` package in WSL. Keeps file modes
(the app's executable bit) and symlinks.
"""
import os
import stat
import sys
import zipfile


def main(app: str, out: str) -> None:
    app = os.path.abspath(os.path.expanduser(app)).rstrip("/")
    if not app.endswith(".app") or not os.path.isdir(app):
        sys.exit(f"not an .app folder: {app}")
    root = os.path.dirname(app)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for folder, dirs, files in os.walk(app, followlinks=False):
            dirs.sort()
            for name in sorted(files) + [d for d in dirs if os.path.islink(os.path.join(folder, d))]:
                path = os.path.join(folder, name)
                arc = os.path.join("Payload", os.path.relpath(path, root))
                st = os.lstat(path)
                info = zipfile.ZipInfo(arc)
                info.external_attr = (st.st_mode & 0xFFFF) << 16
                info.create_system = 3  # Unix, so the modes above are honoured
                if stat.S_ISLNK(st.st_mode):
                    z.writestr(info, os.readlink(path))
                else:
                    info.compress_type = zipfile.ZIP_DEFLATED
                    with open(path, "rb") as f:
                        z.writestr(info, f.read())
    print(f"wrote {out} ({os.path.getsize(out) / 1e6:.1f} MB)")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
