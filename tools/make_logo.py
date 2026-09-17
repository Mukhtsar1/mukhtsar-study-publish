"""
Regenerate the Mukhtsar Study wordmark as clean transparent PNGs.

    python -m tools.make_logo

Produces two variants, both 1240x312 RGBA with proper alpha (no baked-in
background, so they composite on any colour):

    assets/logo_big.png        dark themes  — gold wordmark, red offset, cyan STUDY
    assets/logo_big_light.png  Option B     — navy wordmark, gold offset, teal STUDY

Type: Orbitron Black, tracked wide, with a hard (no-blur) offset shadow —
the same construction as the pixel numerals.
"""
from pathlib import Path
import sys
import urllib.request

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
FONTS = ASSETS / "fonts"

ORBITRON = ("https://raw.githubusercontent.com/google/fonts/main/ofl/orbitron/"
            "Orbitron%5Bwght%5D.ttf")

W, H = 1240, 312
SS = 4                         # supersample factor, downsampled at the end

VARIANTS = {
    "logo_big.png": {           # dark backgrounds (Option A)
        "word": "#F5A800",
        "offset": "#79002B",
        "sub": "#00AADD",
        "cursor": "#00AADD",
    },
    "logo_big_light.png": {     # cream background (Option B)
        "word": "#000B58",
        "offset": "#F5A800",
        "sub": "#048480",
        "cursor": "#048480",
    },
}


def orbitron(weight: int, size: int) -> ImageFont.FreeTypeFont:
    path = FONTS / "Orbitron-Variable.ttf"
    if not path.exists():
        print("  downloading Orbitron…")
        FONTS.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(ORBITRON, path)
    f = ImageFont.truetype(str(path), size)
    try:
        f.set_variation_by_axes([weight])
    except Exception:                                   # pragma: no cover
        print("  ! variable axes unavailable — using default weight")
    return f


def _tracked(draw, xy, text, font, fill, track):
    """Draw text with manual letter-spacing. Returns the drawn width."""
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=font, fill=fill)
        x += draw.textlength(ch, font=font) + track
    return x - track - xy[0]


def _tracked_width(draw, text, font, track):
    return sum(draw.textlength(c, font=font) for c in text) + track * (len(text) - 1)


def _cursor(draw, x, y, s, fill):
    """Blocky arrow cursor — the brand's pixel pointer."""
    pts = [(0, 0), (0, 15), (3.6, 11.6), (6.2, 17), (9, 15.6), (6.4, 10.4),
           (11, 10.4)]
    draw.polygon([(x + px * s, y + py * s) for px, py in pts], fill=fill)


def build(name: str, c: dict) -> None:
    img = Image.new("RGBA", (W * SS, H * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    word_font = orbitron(900, 152 * SS)
    sub_font = orbitron(900, 60 * SS)

    track = 3 * SS
    word = "MUKHTSAR"
    ww = _tracked_width(d, word, word_font, track)
    wx = (W * SS - ww) / 2
    wy = 22 * SS
    off = 9 * SS                                   # hard offset, no blur

    _tracked(d, (wx + off, wy + off), word, word_font, c["offset"], track)
    _tracked(d, (wx, wy), word, word_font, c["word"], track)

    sub, sub_track = "STUDY", 9 * SS
    sw = _tracked_width(d, sub, sub_font, sub_track)
    cur_s = 3.4 * SS                               # cursor scale
    cur_w = 11 * cur_s
    gap = 34 * SS
    block = sw + gap + cur_w
    sx = (W * SS - block) / 2
    sy = 196 * SS
    _tracked(d, (sx, sy), sub, sub_font, c["sub"], sub_track)
    _cursor(d, sx + sw + gap, sy + 8 * SS, cur_s, c["cursor"])

    img.resize((W, H), Image.LANCZOS).save(ASSETS / name)
    print(f"  wrote {name}")


def main() -> None:
    print("Building Mukhtsar wordmarks…")
    ASSETS.mkdir(parents=True, exist_ok=True)
    for name, colours in VARIANTS.items():
        build(name, colours)
    print("Done.")


if __name__ == "__main__":
    sys.exit(main())
