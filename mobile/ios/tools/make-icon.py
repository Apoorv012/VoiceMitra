#!/usr/bin/env python3
"""Draws the app icon: the web app's header mark (a white microphone on the brand sage green,
web/src/app/globals.css --accent) as a full-bleed, opaque 1024x1024 PNG -- iOS rounds the corners itself and
rejects transparency.

    python tools/make-icon.py   (writes VoiceMitra/Resources/AppIcon.png; needs Pillow)
"""
from pathlib import Path

from PIL import Image, ImageDraw

SIZE = 1024
SCALE = 4  # draw big, then downsample for smooth edges
GREEN_TOP = (0x5A, 0x8A, 0x42)
GREEN_BOTTOM = (0x41, 0x6B, 0x2E)  # around --accent #4d7a37
WHITE = (255, 255, 255)


def main() -> None:
    s = SIZE * SCALE
    k = SCALE

    # Subtle top-to-bottom gradient.
    img = Image.new("RGB", (s, s))
    d = ImageDraw.Draw(img)
    for y in range(s):
        t = y / (s - 1)
        d.line([(0, y), (s, y)], fill=tuple(round(a + (b - a) * t) for a, b in zip(GREEN_TOP, GREEN_BOTTOM)))

    cx = 512
    # Microphone capsule
    d.rounded_rectangle(((cx - 112) * k, 196 * k, (cx + 112) * k, 540 * k), radius=112 * k, fill=WHITE)
    # Holder: the lower half of a ring around the capsule
    r, w = 205, 50
    d.arc(((cx - r) * k, (425 - r) * k, (cx + r) * k, (425 + r) * k), start=0, end=180, fill=WHITE, width=w * k)
    # Round the arc's two ends
    for ex in (cx - r + w // 2, cx + r - w // 2):
        d.ellipse(((ex - w // 2) * k, (425 - w // 2) * k, (ex + w // 2) * k, (425 + w // 2) * k), fill=WHITE)
    # Stem and base
    d.rectangle(((cx - 25) * k, 620 * k, (cx + 25) * k, 770 * k), fill=WHITE)
    d.rounded_rectangle(((cx - 125) * k, 760 * k, (cx + 125) * k, 810 * k), radius=25 * k, fill=WHITE)

    img = img.resize((SIZE, SIZE), Image.LANCZOS)
    out = Path(__file__).resolve().parent.parent / "VoiceMitra" / "Resources" / "AppIcon.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, optimize=True)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
