"""
Gemini-backed topic drafting.

Turns an idea from content/ideas.yaml into a full Arabic topic draft. What it
does NOT do is let a generated figure reach a slide unchecked: every number in
the output is wrapped in VERIFY[...] before the draft is written, and `approve`
refuses while any VERIFY marker remains. A model that writes "RM 1,200 - 1,800"
for tuition is not lying deliberately, but the number is still made up, and it
would carry the brand's name on it.
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]
SETTINGS = ROOT / "config" / "settings.yaml"

ENDPOINT = ("https://generativelanguage.googleapis.com/v1beta/models/"
            "{model}:generateContent")

# Pin the model explicitly. Never an alias: '-latest' silently repoints to
# newly launched, heavily contended models, which changes output and latency
# underneath a pipeline that was tuned against something else.
DEFAULT_MODEL = "gemini-2.5-pro"


class GenerationError(RuntimeError):
    pass


def _cfg() -> dict:
    if not SETTINGS.exists():
        return {}
    data = yaml.safe_load(SETTINGS.read_text(encoding="utf-8")) or {}
    return data.get("generation", {}) or {}


def timeout_s() -> int:
    return int(_cfg().get("timeout", 180))


def retries() -> int:
    return int(_cfg().get("retries", 2))


def model_name() -> str:
    name = _cfg().get("model", DEFAULT_MODEL)
    if name.endswith("-latest"):
        raise GenerationError(
            f"settings.yaml pins the model to '{name}'. Aliases ending in "
            "'-latest' repoint without warning — use an explicit version.")
    return name


def timeout_seconds() -> int:
    return int(_cfg().get("timeout", 180))


def retries() -> int:
    return int(_cfg().get("retries", 2))


def _key() -> str:
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise GenerationError(
            "GEMINI_API_KEY is not set. Add it to .env — the same key the "
            "news pipeline uses works here.")
    return key


# ------------------------------------------------------------------ prompt
BRAND_RULES = """\
أنت تكتب محتوى لحساب "مختصر" — استشارات تعليمية في كوالالمبور تخدم عائلات خليجية.

قواعد إلزامية:
1. لا تذكر أي رقم هاتف إطلاقاً.
2. الاستشارة وحدها مجانية. اكتب "خدماتنا الاستشارية مجانية" ولا تكتب أبداً أن جميع الخدمات مجانية.
3. لا تستخدم أي إيموجي.
4. اللغة عربية فصيحة واضحة، بنبرة مباشرة تخاطب الطالب وولي أمره.
5. لا تخترع إحصائيات أو نسباً أو تصنيفات. إن لم تكن متأكداً من رقم، اكتب الجملة بدون رقم.
6. لا تنسب شراكات أو اعترافات غير مؤكدة.
"""

SCHEMA = """\
Return ONLY a JSON object, no markdown fences, no commentary:

{
  "tag": "short Arabic chip label, 2-3 words",
  "hook": "one Arabic line, the caption opener",
  "hashtags": ["3 to 5 Arabic hashtags, no # sign, underscores for spaces"],
  "cover": {
    "headline": "Arabic, 2-3 words",
    "highlight": "Arabic, 2-3 words, the emphasised second line",
    "subline": "one or two Arabic lines, use <br> between them"
  },
  "items": [
    {
      "title": "Arabic, 2-4 words",
      "subtitle": "Arabic, short qualifier",
      "body": "one Arabic sentence. Wrap ONE phrase in <span class='hl'>...</span>",
      "tip": "optional, start with 'نصيحة مختصر:'"
    }
  ],
  "cta": {
    "headline": "Arabic, ends with a dash",
    "highlight": "Arabic, 2-3 words",
    "body": "two Arabic lines separated by <br>",
    "button": "Arabic call to action, 3-5 words"
  }
}
"""


NO_FIGURES = """\
7. لا تكتب أي رقم إطلاقاً: لا أسعار، ولا رسوم، ولا نسب، ولا مدد زمنية، ولا تواريخ.
   اكتب الجملة بصياغة وصفية بدون أرقام. هذا شرط إلزامي.
"""


def build_prompt(idea: dict, no_figures: bool = True) -> str:
    rules = BRAND_RULES + (NO_FIGURES if no_figures else "")
    return (
        f"{rules}\n"
        f"اكتب محتوى منشور عن: {idea.get('hook') or idea['id']}\n"
        f"عدد النقاط المطلوبة: {idea.get('items', 4)}\n\n"
        f"{SCHEMA}"
    )


# ------------------------------------------------------------------- call
def call_gemini(prompt: str, timeout: int | None = None) -> str:
    """
    One generation call, retried on the failures that are worth retrying.

    A read timeout or a 5xx means the request never produced anything, so
    repeating it is safe. A 429 is quota: retried once with a longer pause,
    then given up on, because hammering a exhausted quota only delays the
    reset. A 404 is access and never retried — the model will not appear
    between attempts.
    """
    url = ENDPOINT.format(model=model_name())
    timeout = timeout or timeout_seconds()
    attempts = retries() + 1
    last = ""

    for attempt in range(1, attempts + 1):
        try:
            r = requests.post(
                url, timeout=timeout,
                headers={"x-goog-api-key": _key(),
                         "Content-Type": "application/json"},
                json={"contents": [{"parts": [{"text": prompt}]}],
                      "generationConfig": {
                          "temperature": 0.7,
                          "responseMimeType": "application/json"}})
        except requests.Timeout:
            last = f"read timed out after {timeout}s"
        except requests.RequestException as exc:
            last = f"request failed: {exc}"
        else:
            if r.status_code == 200:
                break
            if r.status_code == 404:
                raise GenerationError(
                    f"Gemini returned 404: {r.text[:300]}\n"
                    "  Run  python -m tools.check_gemini  to see what this "
                    "key can reach.")
            last = f"HTTP {r.status_code}: {r.text[:200]}"
            if r.status_code < 500 and r.status_code != 429:
                raise GenerationError(f"Gemini returned {last}")

        if attempt < attempts:
            pause = 20 if "429" in last else 5 * attempt
            print(f"  {'':<20} attempt {attempt} — {last[:60]}; "
                  f"retrying in {pause}s")
            time.sleep(pause)
    else:
        raise GenerationError(
            f"Gemini failed after {attempts} attempts — {last}\n"
            "  If this is a timeout, raise generation.timeout in "
            "config/settings.yaml, or try a lighter model.")

    data = r.json()
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as exc:
        raise GenerationError(
            f"Unexpected Gemini response shape: {json.dumps(data)[:300]}"
        ) from exc


def parse_json(text: str) -> dict:
    """Tolerate markdown fences even though the schema forbids them."""
    cleaned = re.sub(r"^```(?:json)?|```$", "", text.strip(),
                     flags=re.MULTILINE).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise GenerationError(
            f"Gemini did not return valid JSON: {exc}\n{cleaned[:300]}") from exc


# ------------------------------------------------------------------ verify
# Any digit sequence that reads as a claim: money, counts, percentages, years,
# durations. Bare list markers inside a sentence are rare enough to accept the
# occasional false positive — over-flagging costs a keystroke, under-flagging
# puts an invented number on a slide.
FIGURE = re.compile(
    # currency-led, optionally a range and a trailing plus: "RM 450 – 1,500+"
    r"(?:RM|ريال|رينغيت|\$)\s*[\d\u0660-\u0669][\d\u0660-\u0669,.]*"
    r"(?:\s*[\u2013\u2014-]\s*[\d\u0660-\u0669][\d\u0660-\u0669,.]*)?\s*\+?"
    # number followed by a unit: "85%", "3 سنوات"
    r"|[\d\u0660-\u0669][\d\u0660-\u0669,.]*\s*"
    r"(?:RM|ريال|رينغيت|%|\u066A|سنة|سنوات|شهر|أشهر|يوم|أيام|ساعة|ساعات|أسبوع|أسابيع)"
    # grouped thousands on their own: "50,000" — must beat the bare rule below,
    # which would otherwise split it into "50" and "000"
    r"|[\d\u0660-\u0669]{1,3}(?:[,\u060C][\d\u0660-\u0669]{3})+"
    # any bare number. Over-flagging costs one keystroke; under-flagging puts
    # an invented figure on a slide, so a lone "3 مستندات" is flagged too.
    r"|[\d\u0660-\u0669]+"
)


def flag_figures(text: str) -> tuple[str, int]:
    """Wrap every figure in VERIFY[...]. Returns (text, count)."""
    if not text:
        return text, 0
    count = 0

    def _wrap(m: re.Match) -> str:
        nonlocal count
        count += 1
        return f"VERIFY[{m.group(0).strip()}]"

    return FIGURE.sub(_wrap, text), count


def flag_all(obj):
    """Walk the generated structure and flag every figure in every string."""
    total = 0
    if isinstance(obj, str):
        out, n = flag_figures(obj)
        return out, n
    if isinstance(obj, list):
        result = []
        for v in obj:
            r, n = flag_all(v)
            result.append(r)
            total += n
        return result, total
    if isinstance(obj, dict):
        result = {}
        for k, v in obj.items():
            r, n = flag_all(v)
            result[k] = r
            total += n
        return result, total
    return obj, 0


# ------------------------------------------------------------------- draft
def to_draft_yaml(idea: dict, gen: dict, flagged: int,
                  with_images: bool) -> str:
    icon = idea.get("icon", "check")
    kw = idea.get("keywords") or []

    topic = {
        "id": idea["id"],
        "path": idea.get("path", "A"),
        "tag": gen.get("tag", idea.get("tag", "مختصر")),
        "hook": gen.get("hook", ""),
        "hashtags": gen.get("hashtags", ["الدراسة_في_ماليزيا", "مختصر"]),
        "cover": {
            "eyebrow": idea.get("eyebrow", ""),
            "icon": icon,
            "headline": gen.get("cover", {}).get("headline", ""),
            "highlight": gen.get("cover", {}).get("highlight", ""),
            "subline": gen.get("cover", {}).get("subline", ""),
        },
        "items": [],
        "cta": {
            "eyebrow": "TALK TO US",
            "icon": icon,
            "headline": gen.get("cta", {}).get("headline", ""),
            "highlight": gen.get("cta", {}).get("highlight", ""),
            "body": gen.get("cta", {}).get("body", ""),
            "button": gen.get("cta", {}).get("button", ""),
            "save": "احفظ المنشور — وأرسله لمن يخطط للدراسة في ماليزيا",
        },
    }
    if with_images and kw:
        topic["cover"]["keywords"] = kw

    for it in gen.get("items", []):
        entry = {
            "icon": icon,
            "title": it.get("title", ""),
            "subtitle": it.get("subtitle", ""),
            "body": it.get("body", ""),
        }
        if it.get("tip"):
            entry["tip"] = it["tip"]
        if with_images and kw:
            entry["keywords"] = kw
        topic["items"].append(entry)

    header = f"""\
# DRAFT — generated by {model_name()}, NOT reviewed.
#
# {flagged} figure(s) were wrapped in VERIFY[...]. Each one was written by a
# language model and is unverified. Check it against a real source, then
# replace the whole VERIFY[...] marker with the confirmed value — or rewrite
# the sentence without a number.
#
# `approve` refuses while any VERIFY marker remains:
#     python -m src.run approve --id {idea['id']}
#
# Also read the wording itself. The model follows the brand rules it was given,
# but it has no way to know what is true about Malaysian universities today.

"""
    body = yaml.safe_dump({"topics": [topic]}, allow_unicode=True,
                          sort_keys=False, width=100)
    return header + body


MARKER = re.compile(r"VERIFY\[([^\]]*)\]")


def strip_markers(text: str) -> tuple[str, list[str]]:
    """
    Remove VERIFY[...] wrappers so the text can render, and return what was
    inside them. The markers cannot survive into a slide — they would print
    literally — so the record of what is unchecked moves into meta.json and
    the publish gate instead.
    """
    # Comment lines are skipped: the draft header explains the convention by
    # writing VERIFY[...] literally, and matching that reported the
    # instructions as invented figures.
    out, figures = [], []
    for line in text.splitlines():
        if line.lstrip().startswith("#"):
            out.append(line)
            continue
        figures.extend(MARKER.findall(line))
        out.append(MARKER.sub(r"\1", line))
    return "\n".join(out), figures


def find_figures(obj) -> list[str]:
    """Every figure in the generated structure, for reporting."""
    found = []
    if isinstance(obj, str):
        found += [m.group(0).strip() for m in FIGURE.finditer(obj)]
    elif isinstance(obj, list):
        for v in obj:
            found += find_figures(v)
    elif isinstance(obj, dict):
        for v in obj.values():
            found += find_figures(v)
    return found


def generate(idea: dict, with_images: bool = False,
             no_figures: bool = True) -> tuple[str, list[str]]:
    """
    Idea -> (draft YAML text, list of figures that survived).

    In no_figures mode the prompt forbids numbers outright and one retry is
    made if any appear. That is what makes an unattended build defensible:
    with no figures there is no invented statistic to publish. Whatever
    survives two attempts is returned so the caller can warn about it — it is
    NOT silently accepted.
    """
    gen = parse_json(call_gemini(build_prompt(idea, no_figures)))
    figures = find_figures(gen)

    if no_figures and figures:
        stricter = (build_prompt(idea, True) +
                    "\n\nالمحاولة السابقة احتوت أرقاماً. أعد الكتابة بدون أي "
                    "رقم على الإطلاق.")
        gen2 = parse_json(call_gemini(stricter))
        if len(find_figures(gen2)) < len(figures):
            gen, figures = gen2, find_figures(gen2)

    if not no_figures:
        gen, _ = flag_all(gen)

    return to_draft_yaml(idea, gen, len(figures), with_images), figures
