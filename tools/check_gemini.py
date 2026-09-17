"""
Find out which Gemini models this key can actually use.

    python -m tools.check_gemini

The models endpoint is not trustworthy here: it lists models that then return
404 "no longer available to new users". So this makes a real, minimal
generateContent call against each candidate and reports what came back.

    OK      usable — put it in config/settings.yaml
    404     listed but not available to this key
    429     available, but quota is exhausted right now
"""
from pathlib import Path
import sys

import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.run import _load_env                        # noqa: E402
from src.generate import ENDPOINT                    # noqa: E402

CANDIDATES = [
    "gemini-3.5-flash-lite",
    "gemini-3.5-flash",
    "gemini-3.1-flash",
    "gemini-3.1-pro-preview",
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash",
]


def probe(model: str, key: str) -> tuple[str, str]:
    try:
        r = requests.post(
            ENDPOINT.format(model=model), timeout=45,
            headers={"x-goog-api-key": key, "Content-Type": "application/json"},
            json={"contents": [{"parts": [{"text": "Reply with the word OK."}]}],
                  "generationConfig": {"maxOutputTokens": 8}})
    except requests.RequestException as exc:
        return "ERR", str(exc)[:70]

    if r.status_code == 200:
        try:
            text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
            return "OK", text.strip()[:40]
        except (KeyError, IndexError):
            # Reached the model but the response shape differs from what
            # src/generate.py expects — worth knowing before a real run.
            return "OK?", "200, but unexpected response shape"
    try:
        msg = r.json()["error"]["message"][:70]
    except Exception:
        msg = r.text[:70]
    return str(r.status_code), msg


def main() -> None:
    _load_env()
    import os
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise SystemExit("GEMINI_API_KEY is not set — add it to .env")

    settings = yaml.safe_load(
        (ROOT / "config" / "settings.yaml").read_text(encoding="utf-8")) or {}
    current = (settings.get("generation", {}) or {}).get("model", "")

    print(f"Current setting: {current or '(none)'}\n")
    usable = []
    for m in CANDIDATES:
        status, detail = probe(m, key)
        mark = " <- current" if m == current else ""
        print(f"  {status:<5} {m:<26} {detail}{mark}")
        if status.startswith("OK"):
            usable.append(m)

    print()
    if usable:
        print(f"Set config/settings.yaml -> generation.model: \"{usable[0]}\"")
        print("Flash tiers carry far higher free quota than pro, and drafting "
              "four Arabic sentences does not need pro.")
    else:
        print("Nothing usable right now. A 429 everywhere means quota, not "
              "access — wait for the reset and re-run.")


if __name__ == "__main__":
    main()
