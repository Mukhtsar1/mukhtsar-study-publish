"""
Look at a photo before it goes on a slide.

Pexels gives text only — alt text and a URL slug — so every filter in
images.py is guessing from a description that is often vague, sometimes wrong
and frequently absent. That is how a bus stop "with diverse passengers" and a
plaza full of seated people reached finished carousels.

This module sends the downloaded image to a vision model and asks what is
actually in it. It is the only check in the pipeline that sees the picture.

It still is not perfect: a model can misjudge a small or blurred figure. Treat
it as a strong filter, not a guarantee, and keep reviewing the slides.
"""
from __future__ import annotations

import base64
import json
import re
from pathlib import Path

import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]
SETTINGS = ROOT / "config" / "settings.yaml"

ENDPOINT = ("https://generativelanguage.googleapis.com/v1beta/models/"
            "{model}:generateContent")

PROMPT = """\
Look at this photograph and answer about what is VISIBLE in it.

Return ONLY this JSON, no other text:
{
  "people": true if any human figure is visible at all, even small or distant,
  "faces_identifiable": true if any face is clear enough to recognise,
  "women": true if any person appears to be a woman,
  "women_hair_uncovered": true if any woman's hair is visible or uncovered,
  "immodest_clothing": true if anyone wears swimwear, shorts, sleeveless or
                       otherwise revealing clothing,
  "alcohol_or_bar": true if alcohol, a bar or a nightclub is visible,
  "description": "one short factual sentence describing the image"
}

Judge only what you can see. If you are unsure whether something is present,
answer true — a rejected photo costs nothing, a wrong one is published."""


class VisionError(RuntimeError):
    pass


def _cfg() -> dict:
    if not SETTINGS.exists():
        return {}
    data = yaml.safe_load(SETTINGS.read_text(encoding="utf-8")) or {}
    return (data.get("images", {}) or {}).get("vision", {}) or {}


def enabled() -> bool:
    return bool(_cfg().get("enabled", True))


def model_name() -> str:
    return _cfg().get("model", "gemini-3.5-flash-lite")


def _rules() -> dict:
    """Which findings reject a photo. Defaults suit a Gulf family audience."""
    return {
        "women_hair_uncovered": _cfg().get("reject_uncovered_hair", True),
        "immodest_clothing": _cfg().get("reject_immodest", True),
        "alcohol_or_bar": _cfg().get("reject_alcohol", True),
        "faces_identifiable": _cfg().get("reject_identifiable_faces", True),
        "people": _cfg().get("reject_any_people", False),
    }


def inspect(image_path: Path, timeout: int = 60) -> dict:
    """Ask the model what is in the image. Raises VisionError on failure."""
    import os

    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise VisionError("GEMINI_API_KEY is not set")

    data = base64.b64encode(Path(image_path).read_bytes()).decode()
    suffix = Path(image_path).suffix.lower()
    mime = "image/png" if suffix == ".png" else "image/jpeg"

    try:
        r = requests.post(
            ENDPOINT.format(model=model_name()), timeout=timeout,
            headers={"x-goog-api-key": key, "Content-Type": "application/json"},
            json={"contents": [{"parts": [
                {"inline_data": {"mime_type": mime, "data": data}},
                {"text": PROMPT}]}],
                "generationConfig": {"temperature": 0,
                                     "responseMimeType": "application/json"}})
    except requests.RequestException as exc:
        raise VisionError(str(exc)) from exc

    if r.status_code != 200:
        raise VisionError(f"HTTP {r.status_code}: {r.text[:160]}")

    try:
        text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as exc:
        raise VisionError("unexpected response shape") from exc

    cleaned = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE)
    try:
        return json.loads(re.sub(r",(\s*[}\]])", r"\1", cleaned.strip()))
    except json.JSONDecodeError as exc:
        raise VisionError(f"unparseable answer: {cleaned[:160]}") from exc


def check(image_path: Path) -> tuple[bool, str]:
    """
    (ok, reason). A photo that cannot be checked is REJECTED, not accepted:
    an unchecked image is exactly the case this exists to catch, and there is
    always another candidate.
    """
    if not enabled():
        return True, "vision check disabled"

    try:
        found = inspect(image_path)
    except VisionError as exc:
        return False, f"could not be checked ({exc})"

    for field, active in _rules().items():
        if active and found.get(field):
            return False, field.replace("_", " ")
    return True, (found.get("description") or "")[:90]
