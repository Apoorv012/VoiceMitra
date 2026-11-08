"""Draw the app icons into web/public/icons/: the same white microphone on dark green as the logo
(landing page `.logoMark`, `.brand-mark`). Run from the repo root with the backend venv, which already
has Pillow:

    .venv/Scripts/python.exe web/scripts/make_icons.py

The tab favicon is public/icons/icon.svg (hand-written, same artwork); keep the two in step.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent.parent / "public" / "icons"
GREEN = (18, 38, 26)  # --btn, #12261a
WHITE = (255, 255, 255)


def draw(size: int, *, inset: float, rounded: bool) -> Image.Image:
    """`inset` shrinks the artwork toward the middle (maskable icons keep it inside the safe zone)."""
    scale = 4  # draw big, shrink for smooth edges
    s = size * scale
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if rounded:
        d.rounded_rectangle([0, 0, s - 1, s - 1], radius=int(s * 0.3), fill=GREEN)
    else:
        d.rectangle([0, 0, s, s], fill=GREEN)

    # The mic is the logo's 24x24 SVG (Icon.tsx "mic"), stroke width 2, round caps.
    u = s * (1 - 2 * inset) / 24  # one SVG unit in pixels
    o = s * inset

    def p(x: float, y: float) -> tuple[float, float]:
        return (o + x * u, o + y * u)

    w = max(1, round(2 * u))
    r = w / 2

    def cap(x: float, y: float) -> None:
        cx, cy = p(x, y)
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=WHITE)

    # Capsule body: rect x=9 y=3 w=6 h=11 rx=3, stroked on its centre line.
    x0, y0 = p(9, 3)
    x1, y1 = p(15, 14)
    d.rounded_rectangle([x0 - r, y0 - r, x1 + r, y1 + r], radius=3 * u + r, outline=WHITE, width=w)
    # Holder: lower half-circle centre (12, 11) radius 7, then the stand from (12, 18) to (12, 21).
    a0, b0 = p(5, 4)
    a1, b1 = p(19, 18)
    d.arc([a0 - r, b0 - r, a1 + r, b1 + r], 0, 180, fill=WHITE, width=w)
    cap(5, 11)
    cap(19, 11)
    sx, sy0 = p(12, 18)
    _, sy1 = p(12, 21)
    d.rectangle([sx - r, sy0, sx + r, sy1], fill=WHITE)
    cap(12, 21)
    return img.resize((size, size), Image.LANCZOS)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    draw(192, inset=0.2, rounded=True).save(OUT / "icon-192.png")
    draw(512, inset=0.2, rounded=True).save(OUT / "icon-512.png")
    draw(32, inset=0.16, rounded=True).save(OUT / "favicon-32.png")
    # Maskable: full-bleed square, artwork inside the central 60% so any mask shape keeps it.
    draw(512, inset=0.28, rounded=False).save(OUT / "icon-maskable-512.png")
    # iOS rounds the corners itself and wants no transparency.
    draw(180, inset=0.22, rounded=False).convert("RGB").save(OUT / "apple-touch-icon.png")
    print("wrote", sorted(p.name for p in OUT.iterdir()))
