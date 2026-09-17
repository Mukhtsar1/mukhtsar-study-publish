"""
Topic ideas from live sources instead of a fixed list.

Reads the feeds in config/sources.yaml, keeps entries that look relevant to
Gulf students in Malaysia, drops anything already covered or already seen, and
turns what is left into idea stubs the same shape as content/ideas.yaml.

A HEADLINE IS A PROMPT, NOT A FACT. Nothing fetched here goes on a slide. The
stub carries the headline and the source URL so you can read the original and
write the post yourself; the draft gate still applies afterwards.
"""
from __future__ import annotations

import json
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "config" / "sources.yaml"
SEEN = ROOT / "content" / "seen_sources.json"

UA = {"User-Agent": "Mozilla/5.0 (compatible; MukhtsarPipeline/1.0)"}
NS = {"atom": "http://www.w3.org/2005/Atom"}


class SourceError(RuntimeError):
    pass


# ------------------------------------------------------------------ config
def load_config() -> dict:
    if not SOURCES.exists():
        raise SourceError(f"No feed list at {SOURCES.relative_to(ROOT)}")
    return yaml.safe_load(SOURCES.read_text(encoding="utf-8")) or {}


def load_seen() -> dict:
    if not SEEN.exists():
        return {}
    try:
        return json.loads(SEEN.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def mark_seen(entries: list[dict]) -> None:
    """Record links so the same story is never proposed twice."""
    seen = load_seen()
    now = datetime.now(timezone.utc).isoformat()
    for e in entries:
        seen[e["link"]] = {"title": e["title"], "at": now}
    # keep the cache from growing without bound
    if len(seen) > 2000:
        seen = dict(sorted(seen.items(), key=lambda kv: kv[1]["at"])[-1500:])
    SEEN.parent.mkdir(parents=True, exist_ok=True)
    SEEN.write_text(json.dumps(seen, ensure_ascii=False, indent=1),
                    encoding="utf-8")


# ------------------------------------------------------------------- fetch
def _text(node, *paths) -> str:
    for p in paths:
        found = node.find(p) if not p.startswith("atom:") else node.find(p, NS)
        if found is not None:
            if found.text:
                return found.text.strip()
            if found.get("href"):
                return found.get("href").strip()
    return ""


def _parse_date(raw: str):
    if not raw:
        return None
    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z",
                "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            d = datetime.strptime(raw.strip(), fmt)
            return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def fetch_feed(url: str, timeout: int = 8) -> list[dict]:
    """Return entries from an RSS or Atom feed. Raises SourceError on failure."""
    try:
        r = requests.get(url, headers=UA, timeout=timeout)
    except requests.RequestException as exc:
        raise SourceError(f"{exc}") from exc
    if r.status_code != 200:
        raise SourceError(f"HTTP {r.status_code}")

    try:
        root = ET.fromstring(r.content)
    except ET.ParseError as exc:
        raise SourceError(f"not valid XML ({exc})") from exc

    nodes = root.findall(".//item") or root.findall(".//atom:entry", NS)
    if not nodes:
        raise SourceError("no items found — is this a feed URL?")

    out = []
    for n in nodes:
        title = _text(n, "title", "atom:title")
        link = _text(n, "link", "atom:link")
        if not title or not link:
            continue
        out.append({
            "title": re.sub(r"\s+", " ", title),
            "link": link,
            "summary": re.sub(r"<[^>]+>", " ",
                              _text(n, "description", "atom:summary"))[:400],
            "published": _parse_date(_text(n, "pubDate", "atom:updated",
                                           "atom:published")),
        })
    return out


# ------------------------------------------------------------------ filter
def _blob(entry: dict) -> str:
    return f"{entry['title']} {entry.get('summary','')}".lower()


def relevant(entry: dict, topic_words: list[str], geo_words: list[str],
             exclude: list[str]) -> bool:
    """
    An entry must name a TOPIC and a PLACE, not just one of them.

    Matching on "malaysia" alone was the bug: every article in a Malaysian
    news feed says Malaysia, so a bomb scare and an electricity bill came
    through as education topics. The country word qualifies a story, it does
    not make one.
    """
    text = _blob(entry)
    if any(x.lower() in text for x in exclude):
        return False
    if not any(t.lower() in text for t in topic_words):
        return False
    if geo_words and not any(g.lower() in text for g in geo_words):
        return False
    return True


def recent(entry: dict, max_age_days: int) -> bool:
    if not entry.get("published"):
        return True                      # undated: let it through, dedup catches repeats
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    return entry["published"] >= cutoff


# -------------------------------------------------------------------- slug
STOP_SLUG = {"the", "a", "an", "of", "in", "for", "to", "and", "on", "at",
             "with", "by", "from", "as", "is", "are", "be", "will", "new",
             "says", "said", "after", "over", "more"}


def slugify(title: str, fallback: str = "news-item") -> str:
    """Multi-word slug from a headline. Ids name the angle, so keep 3-5 words."""
    ascii_only = unicodedata.normalize("NFKD", title).encode(
        "ascii", "ignore").decode()
    words = [w for w in re.findall(r"[a-zA-Z]+", ascii_only.lower())
             if len(w) > 2 and w not in STOP_SLUG]
    slug = "-".join(words[:5])
    return slug or fallback


# -------------------------------------------------------------------- main
def gather(max_items: int = 6) -> tuple[list[dict], list[tuple[str, str]]]:
    """
    Returns (ideas, problems).
    ideas    — stubs shaped like content/ideas.yaml entries
    problems — (feed name, reason) for feeds that failed, so a dead feed is
               visible rather than silently shrinking the result
    """
    cfg = load_config()
    topic_words = cfg.get("topic_keywords", [])
    geo_words = cfg.get("geo_keywords", [])
    exclude = cfg.get("exclude_keywords", [])
    max_age = int(cfg.get("max_age_days", 45))
    seen = load_seen()

    ideas: list[dict] = []
    problems: list[tuple[str, str]] = []
    used_ids: set[str] = set()

    active = [f for f in cfg.get("feeds", []) if f.get("enabled", True)]
    if not active:
        return ideas, problems

    # Fetch in parallel. Sequentially, six feeds at an 8s timeout is 48s of
    # silence before the menu appears, and most of that is waiting on servers
    # rather than doing anything.
    def _one(feed):
        try:
            return feed, fetch_feed(feed["url"]), None
        except SourceError as exc:
            return feed, [], str(exc)

    with ThreadPoolExecutor(max_workers=min(8, len(active))) as pool:
        results = list(pool.map(_one, active))

    for feed, entries, err in results:
        if err:
            problems.append((feed.get("name", feed["url"]), err))
            continue

        for e in entries:
            if len(ideas) >= max_items:
                break
            if e["link"] in seen:
                continue
            if not recent(e, max_age) or not relevant(
                    e, topic_words, geo_words, exclude):
                continue

            slug = slugify(e["title"])
            if slug in used_ids:
                continue
            used_ids.add(slug)

            ideas.append({
                "id": slug,
                "tag": feed.get("tag", "مستجدات"),
                "hook": e["title"],
                "eyebrow": feed.get("eyebrow", "WHAT CHANGED"),
                "headline": "TODO",
                "highlight": "TODO",
                "icon": feed.get("icon", "alert"),
                "items": 4,
                "_source": e["link"],
                "_source_name": feed.get("name", ""),
                "_title": e["title"],
            })
    return ideas, problems
