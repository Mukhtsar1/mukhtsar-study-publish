"""
One-time asset setup. Run once after cloning:

    python -m tools.setup_assets

Downloads the two brand fonts, generates the grid/checker tiles for both
themes, and extracts the pixel wordmark if a source image is supplied.
"""
from pathlib import Path
import sys
import urllib.request

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
FONTS = ASSETS / "fonts"
TILES = ASSETS / "tiles"

CAIRO_VAR = ("https://raw.githubusercontent.com/google/fonts/main/ofl/cairo/"
             "Cairo%5Bslnt%2Cwght%5D.ttf")
PRESS_START = ("https://raw.githubusercontent.com/google/fonts/main/ofl/"
               "pressstart2p/PressStart2P-Regular.ttf")

WEIGHTS = (600, 700, 800, 900)


def fetch_fonts() -> None:
    FONTS.mkdir(parents=True, exist_ok=True)
    var = FONTS / "Cairo-Variable.ttf"
    if not var.exists():
        print("  downloading Cairo…")
        urllib.request.urlretrieve(CAIRO_VAR, var)
    ps = FONTS / "PressStart2P.ttf"
    if not ps.exists():
        print("  downloading Press Start 2P…")
        urllib.request.urlretrieve(PRESS_START, ps)

    # instance static weights (WeasyPrint handles static faces more reliably)
    try:
        from fontTools.varLib import instancer
        from fontTools.ttLib import TTFont
        for w in WEIGHTS:
            out = FONTS / f"Cairo-{w}.ttf"
            if out.exists():
                continue
            font = TTFont(var)
            inst = instancer.instantiateVariableFont(font, {"wght": w, "slnt": 0})
            inst.save(out)
            print(f"  built Cairo-{w}.ttf")
    except Exception as exc:                      # pragma: no cover
        print(f"  ! could not instance Cairo weights: {exc}")
        print("    falling back to the variable font for all weights")
        for w in WEIGHTS:
            out = FONTS / f"Cairo-{w}.ttf"
            if not out.exists():
                out.write_bytes(var.read_bytes())


def build_tiles() -> None:
    TILES.mkdir(parents=True, exist_ok=True)

    # blueprint grid — dark theme (faint white lines)
    t = Image.new("RGBA", (54, 54), (0, 0, 0, 0))
    d = ImageDraw.Draw(t)
    d.line([(0, 0), (53, 0)], fill=(255, 255, 255, 12))
    d.line([(0, 0), (0, 53)], fill=(255, 255, 255, 12))
    t.save(TILES / "grid_dark.png")

    # blueprint grid — light theme (faint navy lines)
    t = Image.new("RGBA", (54, 54), (0, 0, 0, 0))
    d = ImageDraw.Draw(t)
    d.line([(0, 0), (53, 0)], fill=(0, 11, 88, 20))
    d.line([(0, 0), (0, 53)], fill=(0, 11, 88, 20))
    t.save(TILES / "grid_light.png")

    # arcade checker strips
    c = Image.new("RGB", (44, 22), (121, 0, 43))          # red
    ImageDraw.Draw(c).rectangle([0, 0, 21, 21], fill=(245, 168, 0))   # gold
    c.save(TILES / "checker_dark.png")

    c = Image.new("RGB", (44, 22), (4, 132, 128))         # teal
    ImageDraw.Draw(c).rectangle([0, 0, 21, 21], fill=(0, 11, 88))     # navy
    c.save(TILES / "checker_light.png")
    print("  tiles built")


def extract_logo(source: str | None = None) -> None:
    """
    Extract the pixel wordmark with a transparent background.
    Pass a source image that contains the logo on a flat background.
    If assets/logo_big.png already exists this is skipped.
    """
    out = ASSETS / "logo_big.png"
    if out.exists():
        print("  logo already present")
        return
    if not source:
        print("  ! no logo source given — place your wordmark at assets/logo_big.png")
        print("    (transparent PNG, pixel art, ~1240px wide)")
        return
    im = Image.open(source).convert("RGBA")
    px = im.load()
    bg = im.getpixel((2, 2))
    w, h = im.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if abs(r - bg[0]) < 28 and abs(g - bg[1]) < 28 and abs(b - bg[2]) < 28:
                px[x, y] = (0, 0, 0, 0)
    im.save(out)
    print(f"  logo extracted -> {out}")


def main() -> None:
    print("Setting up Mukhtsar carousel assets…")
    fetch_fonts()
    build_tiles()
    extract_logo(sys.argv[1] if len(sys.argv) > 1 else None)
    print("Done.")


if __name__ == "__main__":
    main()
