"""
Rendering: HTML -> PDF (WeasyPrint) -> PNG (PyMuPDF).

PyMuPDF is used instead of poppler/pdftoppm because it installs from pip on
Windows with no system dependencies.
"""
from pathlib import Path
import fitz  # PyMuPDF
from weasyprint import HTML

from config.themes import CANVAS

ROOT = Path(__file__).resolve().parents[1]
FONTS = ROOT / "assets" / "fonts"
REQUIRED_FONTS = ["Cairo-600.ttf", "Cairo-700.ttf", "Cairo-800.ttf",
                  "Cairo-900.ttf", "PressStart2P.ttf"]
# A correctly instanced Cairo weight is ~160KB; the variable font is ~600KB.
# If instancing silently fell back to copying the variable font, every weight
# renders at Cairo's default 400 and headlines lose their Black weight.
VARIABLE_SIZE_HINT = 400_000


class FontsMissing(RuntimeError):
    pass


def check_fonts() -> None:
    """
    Fail loudly if the brand fonts are absent or wrong.

    WeasyPrint does not error on a missing @font-face — it quietly substitutes
    a default sans, so slides render successfully and look wrong. That failure
    is invisible until someone compares the output to older assets, so it is
    checked before every render instead.
    """
    missing = [f for f in REQUIRED_FONTS if not (FONTS / f).exists()]
    if missing:
        raise FontsMissing(
            "Brand fonts are missing from assets/fonts: "
            + ", ".join(missing)
            + "\n  Slides would render in a fallback sans, not Cairo."
            + "\n  Run:  python -m tools.setup_assets")

    fat = [f for f in REQUIRED_FONTS
           if f.startswith("Cairo-")
           and (FONTS / f).stat().st_size > VARIABLE_SIZE_HINT]
    if fat:
        raise FontsMissing(
            "These Cairo weights look like unmodified copies of the variable "
            "font: " + ", ".join(fat)
            + "\n  Headlines would render at weight 400 instead of Black."
            + "\n  Delete assets/fonts and re-run:  python -m tools.setup_assets")


def html_to_png(html: str, out_png: Path, base_url: str = ".") -> Path:
    """Render one slide's HTML to a 1080x1350 PNG."""
    out_png = Path(out_png)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    pdf_bytes = HTML(string=html, base_url=str(base_url)).write_pdf()

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc[0]
    # scale so the raster matches the CSS pixel canvas exactly
    zoom_x = CANVAS["w"] / page.rect.width
    zoom_y = CANVAS["h"] / page.rect.height
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom_x, zoom_y), alpha=False)
    pix.save(out_png)
    doc.close()
    return out_png


def render_slides(slides: list, out_dir: Path, base_url: str = ".") -> list:
    """Render a list of (name, html) tuples. Returns the PNG paths in order."""
    check_fonts()
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for i, (name, html) in enumerate(slides):
        p = out_dir / f"{i:02d}_{name}.png"
        html_to_png(html, p, base_url)
        paths.append(p)
    return paths
