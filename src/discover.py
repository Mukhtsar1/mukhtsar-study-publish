"""
Topic discovery — keeps the bank stocked without repeating itself.

Three jobs:
  1. propose ideas the account has not covered
  2. refuse anything too close to an existing or published topic
  3. draft it into topic YAML for review

What it will NOT do is put a topic straight into the queue. Every slide
carries fee ranges, rankings and process claims; standing rule 7 says those
are verified before they go out. A generator that writes them unattended
would break that rule on the first run, so drafts land in content/drafts/
and only `approve` moves them into the bank.
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
TOPICS = ROOT / "content" / "topics.yaml"
IDEAS = ROOT / "content" / "ideas.yaml"
STATE = ROOT / "content" / "state.json"
DRAFTS = ROOT / "content" / "drafts"

# Arabic diacritics and tatweel carry no meaning for similarity.
_DIACRITICS = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u0640]")

# Words that appear in nearly every topic this account publishes. Left in,
# they make unrelated topics look similar — "study in Malaysia" is in all of
# them. Removing them is what separates a genuine repeat from a new angle.
STOPWORDS = {
    "في", "من", "على", "الى", "الي", "عن", "مع", "او", "ما", "هل", "كل",
    "بين", "هذا", "هذه", "التي", "الذي", "كيف", "وش", "عند", "بعد", "قبل",
    "ماليزيا", "ماليزي", "الماليزيه", "كوالالمبور", "الطالب", "الطلاب",
    "طالب", "طلاب", "الدراسه", "دراسه", "تدرس", "الجامعه", "الجامعات",
    "مختصر", "السعودي", "السعوديه", "todo", "study", "malaysia", "kuala",
    "lumpur", "student", "students",
}


class DiscoveryError(RuntimeError):
    pass


# ------------------------------------------------------------------ text
def normalise(text: str) -> str:
    """Strip markup, diacritics and orthographic variation from Arabic text."""
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = unicodedata.normalize("NFKC", text)
    text = _DIACRITICS.sub("", text)
    text = (text.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
                .replace("ى", "ي").replace("ة", "ه").replace("ؤ", "و")
                .replace("ئ", "ي"))
    text = re.sub(r"[^\w\u0600-\u06FF]+", " ", text)
    return re.sub(r"\s+", " ", text).strip().lower()


def _core(text: str) -> str:
    """Normalised text with the account's ever-present vocabulary removed."""
    words = [w for w in normalise(text).split()
             if len(w) > 2 and w not in STOPWORDS]
    return " ".join(words)


def _grams(text: str, n: int = 3) -> set[str]:
    t = _core(text)
    if len(t) < n:
        return {t} if t else set()
    return {t[i:i + n] for i in range(len(t) - n + 1)}


def similarity(a: str, b: str) -> float:
    """
    Overlap coefficient of character trigrams: |A n B| / min(|A|, |B|).

    Not Jaccard. A one-line idea compared against a full topic is a heavy
    length mismatch, and Jaccard reads that as dissimilarity — a reworded
    duplicate of an existing topic scored 0.235 against a 0.172 ceiling for
    genuinely unrelated pairs, which is not a usable gap. The overlap
    coefficient divides by the shorter side instead, so a short idea that is
    wholly contained in an existing topic scores high.

    Measured on the current bank:
        unrelated topics     0.13 - 0.26
        new angles           0.15 - 0.22
        reworded duplicates  0.42 - 0.67
        verbatim             1.00
    Hence a default threshold of 0.35, sitting in the gap.
    """
    ga, gb = _grams(a), _grams(b)
    if not ga or not gb:
        return 0.0
    return len(ga & gb) / min(len(ga), len(gb))


# --------------------------------------------------------------- corpus
def topic_text(topic: dict) -> str:
    """Everything about a topic that defines what it is about."""
    parts = [topic.get("id", ""), topic.get("hook", ""),
             topic.get("tag", "")]
    cover = topic.get("cover", {}) or {}
    parts += [cover.get("headline", ""), cover.get("highlight", ""),
              cover.get("subline", "")]
    for it in topic.get("items", []) or []:
        parts += [it.get("title", ""), it.get("subtitle", "")]
    return " ".join(p for p in parts if p)


def load_topics() -> list[dict]:
    if not TOPICS.exists():
        return []
    return (yaml.safe_load(TOPICS.read_text(encoding="utf-8")) or {}).get(
        "topics", [])


def load_ideas() -> list[dict]:
    if not IDEAS.exists():
        return []
    return (yaml.safe_load(IDEAS.read_text(encoding="utf-8")) or {}).get(
        "ideas", [])


def published_ids() -> set[str]:
    if not STATE.exists():
        return set()
    state = json.loads(STATE.read_text(encoding="utf-8"))
    return {p["topic"] for p in state.get("published", [])}


def draft_ids() -> set[str]:
    if not DRAFTS.exists():
        return set()
    return {p.stem for p in DRAFTS.glob("*.yaml")}


# ------------------------------------------------------------------ dedup
def nearest(candidate: str, corpus: list[tuple[str, str]]) -> tuple[str, float]:
    """Return (id, score) of the closest existing topic."""
    best_id, best = "", 0.0
    for tid, text in corpus:
        s = similarity(candidate, text)
        if s > best:
            best_id, best = tid, s
    return best_id, best


def build_corpus() -> list[tuple[str, str]]:
    """Existing topics plus anything already drafted, so drafts don't collide."""
    corpus = [(t["id"], topic_text(t)) for t in load_topics()]
    for p in sorted(DRAFTS.glob("*.yaml")) if DRAFTS.exists() else []:
        try:
            d = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            continue
        t = (d.get("topics") or [d])[0]
        if isinstance(t, dict) and t.get("id"):
            corpus.append((t["id"], topic_text(t)))
    return corpus


def is_duplicate(text: str, threshold: float,
                 corpus: list[tuple[str, str]] | None = None
                 ) -> tuple[bool, str, float]:
    corpus = build_corpus() if corpus is None else corpus
    tid, score = nearest(text, corpus)
    return score >= threshold, tid, score


# ----------------------------------------------------------------- propose
def propose(count: int, threshold: float) -> tuple[list[dict], list[dict]]:
    """
    Pick unused ideas from the backlog.
    Returns (accepted, rejected) — rejected entries carry the clash reason.
    """
    ideas = load_ideas()
    if not ideas:
        raise DiscoveryError(
            f"No idea backlog at {IDEAS.relative_to(ROOT)}. "
            "Add ideas there, or write topics directly in topics.yaml.")

    corpus = build_corpus()
    in_bank = {t["id"] for t in load_topics()}
    done = published_ids()
    drafted = draft_ids()
    taken = in_bank | done | drafted

    accepted: list[dict] = []
    rejected: list[dict] = []
    for idea in ideas:
        if len(accepted) >= count:
            break
        iid = idea.get("id", "")
        blob = " ".join(str(v) for v in idea.values())

        if iid in taken:
            if iid in done:
                why = "already published"
            elif iid in in_bank:
                why = "already in topics.yaml"
            else:
                why = "draft waiting in content/drafts"
            rejected.append({**idea, "reason": why, "clash": iid, "score": 1.0})
            continue
        dup, clash, score = is_duplicate(blob, threshold, corpus)
        if dup:
            rejected.append({**idea, "reason": "too close to an existing topic",
                             "clash": clash, "score": round(score, 3)})
            continue

        accepted.append({**idea, "nearest": clash, "score": round(score, 3)})
        corpus.append((iid, blob))          # block near-twins inside one run
    return accepted, rejected


# ------------------------------------------------------------------ draft
SKELETON = """# DRAFT — not in the queue yet.
#
# Every figure below is a PLACEHOLDER. Replace each one with a verified
# number and cite where it came from, then run:
#     python -m src.run approve --id {id}
#
# Standing rule 7: no invented statistics, percentages or rankings.

topics:
  - id: {id}
    path: {path}
    tag: "{tag}"
    hook: "{hook}"
    hashtags: [{hashtags}]
    cover:
      eyebrow: "{eyebrow}"
      icon: {icon}
      headline: "{headline}"
      highlight: "{highlight}"
      subline: "TODO — one or two lines on why this matters"
{cover_keywords}    source: "TODO — where these figures come from, or delete this line"
    items:
{items}    cta:
      eyebrow: "TALK TO US"
      icon: {icon}
      headline: "TODO —"
      highlight: "TODO"
      body: "TODO<br>استشارتك الأولى مجانية"
      button: "TODO"
      save: "احفظ المنشور — وأرسله لمن يخطط للدراسة في ماليزيا"
"""

ITEM = """      - icon: {icon}
        title: "TODO — point {n}"
        subtitle: "TODO"
        body: "TODO — <span class='hl'>keep one phrase emphasised</span>"
{keywords}"""


def write_draft(idea: dict, with_images: bool = False) -> Path:
    DRAFTS.mkdir(parents=True, exist_ok=True)
    n_items = int(idea.get("items", 4))
    icon = idea.get("icon", "check")

    # Catch a bad icon name here rather than three steps later at render time.
    from config.icons import available
    if icon not in available():
        raise DiscoveryError(
            f"Idea '{idea['id']}' uses icon '{icon}', which does not exist.\n"
            f"  Available: {', '.join(available())}")

    slides = 1 + n_items + 1                       # cover + items + cta
    if not 3 <= slides <= 10:
        raise DiscoveryError(
            f"Idea '{idea['id']}' asks for {n_items} items = {slides} slides. "
            "Instagram carousels take 3-10.")

    kw = idea.get("keywords") or []
    kw_line = ("        keywords: [" +
               ", ".join(f'"{k}"' for k in kw) + "]\n") if (with_images and kw) else ""
    cover_kw = ("      keywords: [" +
                ", ".join(f'"{k}"' for k in kw) + "]\n") if (with_images and kw) else ""

    items = "".join(ITEM.format(icon=icon, n=i + 1, keywords=kw_line)
                    for i in range(n_items))
    tags = ", ".join(f'"{h}"' for h in idea.get("hashtags",
                     ["الدراسة_في_ماليزيا", "مختصر"]))

    text = SKELETON.format(
        id=idea["id"], path=idea.get("path", "A"), tag=idea.get("tag", "مختصر"),
        hook=idea.get("hook", "TODO"), hashtags=tags,
        eyebrow=idea.get("eyebrow", "TODO"), icon=icon,
        headline=idea.get("headline", "TODO"),
        highlight=idea.get("highlight", "TODO"),
        cover_keywords=cover_kw, items=items)

    path = DRAFTS / f"{idea['id']}.yaml"
    path.write_text(text, encoding="utf-8")
    return path


# ----------------------------------------------------------------- approve
TODO = re.compile(r"\bTODO\b")
# Figures written by the generator. Same gate as TODO: unverified content
# cannot reach the queue, whether a human left it blank or a model filled it in.
VERIFY = re.compile(r"VERIFY\[")


def draft_status(topic_id: str) -> tuple[bool, int, str]:
    """
    (ready, placeholders_left, note) for a draft, without raising.
    Used by the watcher to poll a file being edited in another window.
    """
    path = DRAFTS / f"{topic_id}.yaml"
    if not path.exists():
        return False, -1, "draft file is gone"
    raw = path.read_text(encoding="utf-8")
    body = "\n".join(l for l in raw.splitlines()
                     if not l.lstrip().startswith("#"))
    left = len(TODO.findall(body)) + len(VERIFY.findall(body))
    if left:
        return False, left, f"{left} placeholder(s) left"
    try:
        parsed = yaml.safe_load(raw) or {}
    except yaml.YAMLError as exc:
        return False, 0, f"YAML is not valid yet: {str(exc).splitlines()[0]}"
    if not (parsed.get("topics") or []):
        return False, 0, "no topic block found"
    return True, 0, "ready"


def approve(topic_id: str) -> str:
    """Move a reviewed draft into topics.yaml. Refuses if TODOs remain."""
    path = DRAFTS / f"{topic_id}.yaml"
    if not path.exists():
        raise DiscoveryError(f"No draft at {path.relative_to(ROOT)}")

    raw = path.read_text(encoding="utf-8")
    body = "\n".join(l for l in raw.splitlines() if not l.lstrip().startswith("#"))
    left = len(TODO.findall(body))
    if left:
        raise DiscoveryError(
            f"{left} TODO placeholder(s) still in {path.name}. "
            "Fill in and verify every one before approving.")

    unchecked = len(VERIFY.findall(body))
    if unchecked:
        raise DiscoveryError(
            f"{unchecked} unverified figure(s) still in {path.name}.\n"
            "  Each VERIFY[...] was written by a language model and has not "
            "been checked.\n"
            "  Confirm it against a real source and replace the marker, or "
            "rewrite the sentence without the number.")

    try:
        parsed = yaml.safe_load(raw) or {}
    except yaml.YAMLError as exc:
        raise DiscoveryError(f"{path.name} is not valid YAML: {exc}") from exc

    new = (parsed.get("topics") or [])
    if not new:
        raise DiscoveryError(f"{path.name} contains no topic.")
    topic = new[0]

    existing = load_topics()
    if any(t["id"] == topic["id"] for t in existing):
        raise DiscoveryError(
            f"'{topic['id']}' is already in topics.yaml — nothing overwritten.")

    # Append the draft's own text rather than re-dumping the parsed bank.
    # yaml.safe_dump would rewrite the whole file and throw away every comment
    # and hand-set line break in it.
    lines = raw.splitlines()
    marker = re.compile(r"^(\s*)-\s+id:")
    start, indent = None, 0
    for i, line in enumerate(lines):
        m = marker.match(line)
        if m:
            start, indent = i, len(m.group(1))
            break
    if start is None:
        raise DiscoveryError(f"Could not find the topic block in {path.name}")

    # yaml.safe_dump writes list items flush left while the hand-written bank
    # indents them two spaces. Re-indent so the merged file stays consistent
    # rather than mixing both styles.
    shift = 2 - indent
    block_lines = []
    for line in lines[start:]:
        if not line.strip():
            block_lines.append("")
        elif shift > 0:
            block_lines.append(" " * shift + line)
        elif shift < 0:
            block_lines.append(line[-shift:] if line[:-shift].isspace()
                               or not line[:-shift].strip() else line)
        else:
            block_lines.append(line)
    block = "\n".join(block_lines).rstrip()

    current = TOPICS.read_text(encoding="utf-8").rstrip()
    TOPICS.write_text(current + "\n\n" + block + "\n", encoding="utf-8")

    # Re-parse to prove the merged file is still valid before dropping the draft.
    try:
        after = load_topics()
    except yaml.YAMLError as exc:
        TOPICS.write_text(current + "\n", encoding="utf-8")
        raise DiscoveryError(
            f"Appending {path.name} broke topics.yaml, so it was rolled back: "
            f"{exc}") from exc
    if not any(t["id"] == topic["id"] for t in after):
        TOPICS.write_text(current + "\n", encoding="utf-8")
        raise DiscoveryError(
            f"'{topic['id']}' did not survive the merge — rolled back.")

    path.unlink()
    return topic["id"]
