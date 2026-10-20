"""Draw the app icons into web/public/icons/ (a sound-wave on the brand blue). Run from the repo root
with the backend venv, which already has Pillow:

    .venv/Scripts/python.exe web/scripts/make_icons.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent.parent / "public" / "icons"
BLUE = (37, 106, 191)
WHITE = (255, 255, 255)
BARS = [0.28, 0.5, 0.72, 0.5, 0.28]  # relative heights of the five bars


def draw(size: int, *, inset: float, rounded: bool) -> Image.Image:
    """`inset` shrinks the artwork toward the middle (maskable icons keep it inside the safe zone)."""
    scale = 4  # draw big, shrink for smooth edges
    s = size * scale
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if rounded:
        d.rounded_rectangle([0, 0, s - 1, s - 1], radius=int(s * 0.22), fill=BLUE)
    else:
        d.rectangle([0, 0, s, s], fill=BLUE)

    art = s * (1 - 2 * inset)
    left = s * inset
    bar_w = art / (len(BARS) * 2 - 1)
    for i, h in enumerate(BARS):
        bar_h = art * h
        x0 = left + i * 2 * bar_w
        y0 = s / 2 - bar_h / 2
        d.rounded_rectangle([x0, y0, x0 + bar_w, y0 + bar_h], radius=int(bar_w / 2), fill=WHITE)
    return img.resize((size, size), Image.LANCZOS)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    draw(192, inset=0.24, rounded=True).save(OUT / "icon-192.png")
    draw(512, inset=0.24, rounded=True).save(OUT / "icon-512.png")
    # Maskable: full-bleed square, artwork inside the central 60% so any mask shape keeps it.
    draw(512, inset=0.32, rounded=False).save(OUT / "icon-maskable-512.png")
    # iOS rounds the corners itself and wants no transparency.
    draw(180, inset=0.26, rounded=False).convert("RGB").save(OUT / "apple-touch-icon.png")
    print("wrote", sorted(p.name for p in OUT.iterdir()))
