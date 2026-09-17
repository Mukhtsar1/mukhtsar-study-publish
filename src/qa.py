"""
Automated QA. Every check we previously did by hand is enforced here.

A run that fails any BLOCKING check must not publish.
"""
import re
from pathlib import Path

from PIL import Image

from config.themes import CANVAS

# Phone numbers must never appear on brand assets — CTAs use the bio link.
PHONE_RE = re.compile(r"(\+?60\s*1\d[\s\-]?\d{3,4}[\s\-]?\d{4})|(\b7025\s*9952\b)")
EMOJI_RE = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF]")

MAGENTA = (255, 0, 255)
FOOTER_TOP, FOOTER_BOTTOM = CANVAS["footer_band"]
MIN_CLEARANCE = CANVAS["min_clearance"]

# The optional source-attribution line is a designed element that deliberately
# sits just above the footer. Exclude its band from the collision scan.
SOURCE_BAND = (1212, 1266)


class QAResult:
    def __init__(self):
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def err(self, msg): self.errors.append(msg)
    def warn(self, msg): self.warnings.append(msg)

    @property
    def ok(self) -> bool:
        return not self.errors

    def report(self) -> str:
        out = []
        for e in self.errors:
            out.append(f"  FAIL  {e}")
        for w in self.warnings:
            out.append(f"  warn  {w}")
        return "\n".join(out) or "  all checks passed"


# ---------------------------------------------------------------- helpers
def _is_magenta(px, tol=40):
    r, g, b = px[:3]
    return r > 255 - tol and b > 255 - tol and g < tol + 40


def _brightness(px):
    return (px[0] + px[1] + px[2]) / 3


# ---------------------------------------------------------------- checks
def check_dimensions(img: Image.Image, name: str, res: QAResult) -> None:
    if img.size != (CANVAS["w"], CANVAS["h"]):
        res.err(f"{name}: size {img.size}, expected {(CANVAS['w'], CANVAS['h'])}")


def check_no_magenta(img: Image.Image, name: str, res: QAResult) -> None:
    """An unfilled photo window would publish as a bright magenta block."""
    px = img.convert("RGB").load()
    x0, y0, x1, y1 = CANVAS["window"]
    hits = sum(1 for y in range(y0, y1, 6) for x in range(x0, x1, 6)
               if _is_magenta(px[x, y]))
    if hits > 4:
        res.err(f"{name}: unfilled photo window ({hits} magenta samples)")


def check_footer_clearance(img: Image.Image, name: str, res: QAResult,
                           dark_theme: bool) -> None:
    """Content must not collide with the footer band."""
    px = img.convert("RGB").load()
    bg = px[10, 700]
    last = 0
    for y in range(FOOTER_TOP - 4, 250, -2):
        if SOURCE_BAND[0] <= y <= SOURCE_BAND[1]:
            continue
        row_has_content = False
        for x in range(120, CANVAS["w"] - 120, 4):
            p = px[x, y]
            diff = abs(p[0] - bg[0]) + abs(p[1] - bg[1]) + abs(p[2] - bg[2])
            if diff > 90:
                row_has_content = True
                break
        if row_has_content:
            last = y
            break
    gap = FOOTER_TOP - last
    if last and gap < MIN_CLEARANCE:
        res.err(f"{name}: content {gap}px from the footer band "
                f"(min {MIN_CLEARANCE})")


def check_frame_border(img: Image.Image, name: str, res: QAResult,
                       border_rgb: tuple) -> None:
    """If the slide has a photo window, its frame must survive compositing."""
    px = img.convert("RGB").load()
    x0, y0, x1, y1 = CANVAS["window"]
    def close(p):
        return sum(abs(a - b) for a, b in zip(p[:3], border_rgb)) < 120
    top = sum(1 for x in range(x0 + 10, x1 - 10, 10) if close(px[x, y0 - 2]))
    left = sum(1 for y in range(y0 + 10, y1 - 10, 10) if close(px[x0 - 2, y]))
    if top < 20 or left < 10:
        res.warn(f"{name}: photo frame border looks incomplete "
                 f"(top={top}, left={left})")


def check_text(text: str, where: str, res: QAResult) -> None:
    if PHONE_RE.search(text):
        res.err(f"{where}: contains a phone number — CTAs must use the bio link")
    if EMOJI_RE.search(text):
        res.warn(f"{where}: contains an emoji — brand assets use SVG icons")


def check_caption(caption: str, res: QAResult) -> None:
    if len(caption) > 2200:
        res.err(f"caption too long ({len(caption)} chars, max 2200)")
    tags = caption.count("#")
    if tags > 30:
        res.err(f"caption has {tags} hashtags (Instagram max 30)")
    if tags > 8:
        res.warn(f"caption has {tags} hashtags — 3–5 performs better")
    # the caption is the one place a single emoji is allowed (📌)
    if PHONE_RE.search(caption):
        res.err("caption contains a phone number")


def check_cover_number(topic: dict, res: QAResult) -> None:
    """A numeric cover badge must equal the number of item slides."""
    pixel = str(topic.get("cover", {}).get("pixel", "")).strip()
    if not pixel.isdigit():
        return                      # non-numeric badges like "RM" or "APU" are fine
    n_items = len(topic.get("items", []))
    if int(pixel) != n_items:
        res.err(f"cover badge says '{pixel}' but the carousel has "
                f"{n_items} item slides")


def check_carousel(paths: list, res: QAResult) -> None:
    n = len(paths)
    if n < 3:
        res.err(f"carousel has {n} slides — Instagram needs at least 2, "
                f"and 3 is our minimum")
    if n > 10:
        res.err(f"carousel has {n} slides — Instagram allows at most 10")
    for p in paths:
        mb = Path(p).stat().st_size / 1_048_576
        if mb > 8:
            res.err(f"{Path(p).name}: {mb:.1f}MB exceeds the 8MB limit")


# ---------------------------------------------------------------- runner
def run(paths: list, caption: str, slide_html: list | None = None,
        theme_tokens: dict | None = None, topic: dict | None = None) -> QAResult:
    res = QAResult()
    check_carousel(paths, res)
    check_caption(caption, res)
    if topic:
        check_cover_number(topic, res)

    if slide_html:
        for name, html in slide_html:
            check_text(html, f"slide {name}", res)

    border_rgb = (245, 168, 0)
    dark = True
    if theme_tokens:
        hexv = theme_tokens.get("frame_border", "#F5A800").lstrip("#")
        border_rgb = tuple(int(hexv[i:i + 2], 16) for i in (0, 2, 4))
        dark = theme_tokens.get("name") == "Option A"

    for p in paths:
        img = Image.open(p)
        name = Path(p).name
        before = len(res.errors)
        check_dimensions(img, name, res)
        if len(res.errors) > before:
            # wrong canvas size: pixel-position checks below are meaningless
            continue
        check_no_magenta(img, name, res)
        check_footer_clearance(img, name, res, dark)

    return res
