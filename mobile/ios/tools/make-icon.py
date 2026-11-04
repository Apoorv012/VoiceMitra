#!/usr/bin/env python3
"""Draws the app icon: the web app's mark (white voice-wave bars on the theme blue, web/public/icons) as a
full-bleed, opaque 1024x1024 PNG -- iOS rounds the corners itself and rejects transparency.

    python tools/make-icon.py   (writes VoiceMitra/Resources/AppIcon.png; needs Pillow)
"""
from pathlib import Path

from PIL import Image, ImageDraw

SIZE = 1024
SCALE = 4  # draw big, then downsample for smooth edges
BLUE = (0x25, 0x6A, 0xBF)  # web/src/app/manifest.ts theme_color
WHITE = (255, 255, 255)

# Bars as in web/public/icons/icon-512.png, scaled to 1024: (centre x, height)
BARS = [(276, 150), (394, 270), (512, 384), (630, 270), (748, 150)]
BAR_WIDTH = 64


def main() -> None:
    s = SIZE * SCALE
    img = Image.new("RGB", (s, s), BLUE)
    d = ImageDraw.Draw(img)
    w = BAR_WIDTH * SCALE
    for cx, h in BARS:
        cx, h = cx * SCALE, h * SCALE
        top = s // 2 - h // 2
        d.rounded_rectangle((cx - w // 2, top, cx + w // 2, top + h), radius=w // 2, fill=WHITE)
    img = img.resize((SIZE, SIZE), Image.LANCZOS)
    out = Path(__file__).resolve().parent.parent / "VoiceMitra" / "Resources" / "AppIcon.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, optimize=True)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
