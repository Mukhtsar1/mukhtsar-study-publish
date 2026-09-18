"""
Automatic image sourcing from Pexels.

Pexels images are free for commercial use and need no attribution, but we
record the photographer and source URL in credits.json for every run anyway.

Safety rails exist because generic stock search returns plenty of images that
are wrong for a Gulf family audience or legally risky.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import requests
from PIL import Image

from config.themes import CANVAS

API = "https://api.pexels.com/v1/search"
WIN = CANVAS["window"]
WIN_W, WIN_H = CANVAS["window_size"]
TARGET_AR = WIN_W / WIN_H

MIN_WIDTH = 1200

# Reject any result whose description hints at content that is wrong for a
# Gulf family audience, or that is legally risky.
BANNED = {
    # immodest / revealing
    "bikini", "swimsuit", "swimwear", "lingerie", "underwear", "nude",
    "naked", "topless", "sexy", "seductive", "sensual", "erotic",
    "cleavage", "bare shoulders", "sleeveless", "crop top", "mini skirt",
    "shorts", "yoga pants", "leggings", "spa", "massage", "sauna",
    "beach", "pool party", "sunbathing", "tanning", "bathing",
    # haram context
    "beer", "wine", "alcohol", "cocktail", "bar", "pub", "whisky",
    "champagne", "drunk", "pork", "bacon", "ham", "casino", "gambling",
    "nightclub", "clubbing", "party drinks", "tattoo", "piercing",
    # intimacy
    "kiss", "kissing", "couple in bed", "romance", "romantic", "dating",
    "hugging", "embrace", "lovers", "boyfriend", "girlfriend",
    # other
    "dancing", "dance", "yoga", "fitness model", "lingerie model",
}

# Words that indicate a woman is the subject of the photo.
WOMAN_WORDS = {
    "woman", "women", "girl", "girls", "lady", "ladies", "female",
    "her ", "she ", "mother", "daughter", "sister", "wife", "bride",
    "businesswoman", "schoolgirl", "actress", "model posing",
}

# Words that indicate any identifiable person is the subject.
PERSON_WORDS = WOMAN_WORDS | {
    "man", "men", "boy", "boys", "person", "people", "portrait", "face",
    "selfie", "smiling", "posing", "model", "student holding",
    "he ", "his ", "guy", "father", "son", "brother", "couple", "family",
    # roles and crowds — these slipped through the first version
    "passenger", "passengers", "commuter", "commuters", "traveler",
    "travellers", "travelers", "pedestrian", "pedestrians", "crowd",
    "crowded", "shopper", "shoppers", "customer", "customers", "worker",
    "workers", "staff", "employee", "teacher", "child", "children", "kid",
    "kids", "teen", "adult", "group of", "friends", "colleagues",
    "waiting", "walking", "sitting", "standing", "holding", "wearing",
}

# Stock search for "train station" returns the whole world. For content about
# Malaysia, a photo that names another country is a mislabel waiting to happen.
FOREIGN_PLACES = {
    "japan", "tokyo", "osaka", "kyoto", "izumisano", "shibuya", "japanese",
    "china", "chinese", "shanghai", "beijing", "hong kong", "taiwan",
    "korea", "korean", "seoul", "busan",
    "switzerland", "basel", "zurich", "geneva", "swiss",
    "london", "england", "britain", "british", "uk ", "paris", "france",
    "french", "germany", "german", "berlin", "munich", "italy", "italian",
    "rome", "milan", "spain", "madrid", "barcelona", "netherlands",
    "amsterdam", "belgium", "vienna", "austria", "prague", "budapest",
    "poland", "sweden", "norway", "denmark", "finland", "russia", "moscow",
    "new york", "chicago", "california", "texas", "usa", "united states",
    "us passport", "u.s.", "american passport", "british passport",
    "america", "american", "canada", "toronto", "vancouver", "mexico",
    "brazil", "argentina", "australia", "sydney", "melbourne",
    "new zealand", "india", "delhi", "mumbai", "pakistan", "bangladesh",
    "thailand", "bangkok", "vietnam", "hanoi", "philippines", "manila",
    "indonesia", "jakarta", "bali", "singapore", "dubai", "abu dhabi",
    "qatar", "doha", "turkey", "istanbul", "egypt", "cairo",
}


class PexelsError(RuntimeError):
    pass


def _key() -> str:
    key = os.environ.get("PEXELS_API_KEY", "").strip()
    if not key:
        raise PexelsError(
            "PEXELS_API_KEY is not set. Put it in .env or the environment.")
    return key


def _blob(photo: dict) -> str:
    """All the text Pexels gives us about a photo: alt text and URL slug."""
    return " ".join([
        (photo.get("alt") or ""),
        (photo.get("url") or "").replace("-", " ").replace("/", " "),
    ]).lower() + " "


def _banned(photo: dict) -> bool:
    blob = _blob(photo)
    return any(b in blob for b in BANNED)


def _foreign_hit(photo: dict) -> bool:
    """
    True if the description names a country or city that is not Malaysia.

    LIMIT: this only catches photos Pexels bothered to label with a place. A
    generic "modern railway station interior" could be anywhere on earth and
    passes untouched. Location accuracy still needs your eye.
    """
    blob = _blob(photo)
    if "malaysia" in blob or "kuala lumpur" in blob:
        return False
    return any(w in blob for w in FOREIGN_PLACES)


def _people_hit(photo: dict, policy: str) -> bool:
    """
    True if the photo should be rejected under the people policy.

    IMPORTANT LIMIT: Pexels exposes only alt text and a URL slug. There is no
    way to ask it whether a woman in a photo is dressed modestly, and plenty
    of photos carry vague or missing alt text. So this filter works by
    rejecting photos whose description indicates a person at all — it cannot
    judge what a person is wearing. Anything that slips through with no
    useful description is caught only by the human review step.
    """
    if policy == "allow":
        return False
    blob = _blob(photo)
    words = WOMAN_WORDS if policy == "no_women" else PERSON_WORDS
    return any(w in blob for w in words)


def search(keywords: list[str], per_page: int = 15) -> list[dict]:
    """Query Pexels for each keyword in turn; return pooled candidates."""
    headers = {"Authorization": _key()}
    pool: list[dict] = []
    seen: set[int] = set()
    for kw in keywords:
        try:
            r = requests.get(
                API, headers=headers, timeout=20,
                params={"query": kw, "orientation": "landscape",
                        "size": "large", "per_page": per_page})
            r.raise_for_status()
        except requests.RequestException as exc:
            raise PexelsError(f"Pexels request failed for '{kw}': {exc}") from exc
        for p in r.json().get("photos", []):
            if p["id"] in seen:
                continue
            seen.add(p["id"])
            pool.append(p)
        time.sleep(0.3)          # be polite; limit is 200/hour
    return pool


def score(photo: dict) -> float:
    """Higher is better. Prefers wide, high-resolution, well-proportioned shots."""
    w, h = photo["width"], photo["height"]
    if w < MIN_WIDTH or h >= w:
        return -1.0
    ar = w / h
    ar_penalty = abs(ar - TARGET_AR) * 2.0        # closeness to 952x512
    res_bonus = min(w / 4000, 1.0)                # cap the resolution reward
    return res_bonus - ar_penalty


def _image_cfg() -> dict:
    try:
        import yaml
        cfg = yaml.safe_load(
            (Path(__file__).resolve().parents[1] / "config" / "settings.yaml")
            .read_text(encoding="utf-8")) or {}
        return cfg.get("images", {}) or {}
    except Exception:
        return {}


def people_policy() -> str:
    """Read the people policy from settings.yaml. Default: no people at all."""
    return _image_cfg().get("people", "none")


def reject_foreign() -> bool:
    """Reject photos that name a country other than Malaysia. Default: on."""
    return bool(_image_cfg().get("reject_foreign_places", True))


# Words that make a search return photos of people, which the people policy
# then rejects wholesale — "students walking on Kuala Lumpur university campus"
# returned 15 results and every one was rejected.
_PEOPLE_QUERY_WORDS = {
    "student", "students", "people", "person", "man", "men", "woman", "women",
    "family", "families", "crowd", "group", "staff", "team", "worker",
    "workers", "customer", "customers", "passenger", "passengers", "friends",
    "walking", "sitting", "standing", "studying", "working", "talking",
    "meeting", "smiling", "portrait", "lifestyle",
}


def fallback_queries() -> list[str]:
    """
    Last-resort searches when a slide's own subject keeps returning people.
    Deliberately dull and reliably empty of human figures.
    """
    cfg = _image_cfg().get("fallback_queries")
    return cfg or [
        "Kuala Lumpur city skyline",
        "Malaysia modern building exterior",
        "documents and pen on desk",
    ]


def depopulate(query: str) -> str:
    """Strip the words that pull a search toward photos of people."""
    kept = [w for w in query.split()
            if w.lower().strip(",.") not in _PEOPLE_QUERY_WORDS]
    return " ".join(kept).strip()


def candidates(keywords: list[str], exclude_ids: set[int] | None = None,
               limit: int = 15) -> list[dict]:
    """Ranked candidates rather than just the winner, so a photo rejected by
    the vision check can be replaced without searching again."""
    exclude_ids = exclude_ids or set()
    policy = people_policy()
    no_foreign = reject_foreign()
    raw = search(keywords, per_page=40)
    pool = [p for p in raw
            if p["id"] not in exclude_ids
            and not _banned(p)
            and not _people_hit(p, policy)
            and not (no_foreign and _foreign_hit(p))]
    scored = sorted(((score(p), p) for p in pool), key=lambda x: x[0],
                    reverse=True)
    ranked = [p for sc, p in scored if sc > 0]
    if not ranked:
        raise PexelsError(
            f"No usable Pexels result for {keywords!r} — "
            f"{len(raw)} found, {len(raw) - len(pool)} rejected by the content "
            f"filters, none of the rest met the size/aspect bar. "
            f"Try more specific keywords (a place, not a person).")
    return ranked[:limit]


def pick(keywords: list[str], exclude_ids: set[int] | None = None) -> dict:
    """Choose the best candidate for one slide."""
    exclude_ids = exclude_ids or set()
    policy = people_policy()
    no_foreign = reject_foreign()
    raw = search(keywords)
    pool = [p for p in raw
            if p["id"] not in exclude_ids
            and not _banned(p)
            and not _people_hit(p, policy)
            and not (no_foreign and _foreign_hit(p))]
    ranked = sorted(((score(p), p) for p in pool), key=lambda x: x[0],
                    reverse=True)
    ranked = [(s, p) for s, p in ranked if s > 0]
    if not ranked:
        raise PexelsError(
            f"No usable Pexels result for {keywords!r} — "
            f"{len(raw)} found, {len(raw) - len(pool)} rejected by the content "
            f"filters, none of the rest met the size/aspect bar. "
            f"Try more specific keywords (a place, not a person).")
    return ranked[0][1]


def download(photo: dict, dest: Path) -> Path:
    url = photo["src"].get("large2x") or photo["src"]["large"]
    r = requests.get(url, timeout=40)
    r.raise_for_status()
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(r.content)
    return dest


def fit_to_window(img: Image.Image, y_bias: float = 0.5) -> Image.Image:
    """Centre-crop to the window aspect, then resize to exactly 952x512."""
    w, h = img.size
    if w / h > TARGET_AR:
        nw = int(h * TARGET_AR)
        x0 = (w - nw) // 2
        img = img.crop((x0, 0, x0 + nw, h))
    elif w / h < TARGET_AR:
        nh = int(w / TARGET_AR)
        y0 = int((h - nh) * y_bias)
        img = img.crop((0, y0, w, y0 + nh))
    return img.resize((WIN_W, WIN_H), Image.LANCZOS)


def composite(frame_png: Path, photo_img: Image.Image, out_png: Path,
              bg_hex: str) -> Path:
    """Place the photo behind the keyed frame."""
    bg = bg_hex.lstrip("#")
    rgb = tuple(int(bg[i:i + 2], 16) for i in (0, 2, 4))
    canvas = Image.new("RGBA", (CANVAS["w"], CANVAS["h"]), rgb + (255,))
    canvas.paste(photo_img.convert("RGB"), (WIN[0], WIN[1]))
    frame = Image.open(frame_png).convert("RGBA")
    Image.alpha_composite(canvas, frame).convert("RGB").save(out_png)
    return out_png


def key_out_window(png: Path) -> Path:
    """Turn the magenta placeholder block transparent so a photo can show through."""
    im = Image.open(png).convert("RGBA")
    px = im.load()
    w, h = im.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if r > 200 and b > 200 and g < 80:
                px[x, y] = (0, 0, 0, 0)
    im.save(png)
    return png


def fill_windows(slide_pngs: list[Path], keyword_map: dict[int, list[str]],
                 bg_hex: str, work_dir: Path) -> dict:
    """
    For every slide index that has keywords, source a photo and composite it.
    Returns a credits dict for the run log.
    """
    work_dir = Path(work_dir)
    credits: dict[str, dict] = {}
    used: set[int] = set()

    # Check the configuration once, rather than letting every photo fail the
    # vision check for the same reason.
    import os

    from src import vision
    if vision.enabled() and not os.environ.get("GEMINI_API_KEY", "").strip():
        raise PexelsError(
            "The image check needs GEMINI_API_KEY, which is not set.\n"
            "  Add it to .env, or turn the check off in config/settings.yaml "
            "(images.vision.enabled: false).\n"
            "  With it off, nothing looks at the photos — only their "
            "descriptions.")

    for idx, keywords in keyword_map.items():
        png = Path(slide_pngs[idx])
        key_out_window(png)
        # Try candidates in rank order until one passes the vision check.
        # Text filters cannot see the photo; this is the only step that does.
        from src import vision

        # If the query itself asks for people, every result is rejected by
        # the people policy. Retry once with those words removed rather than
        # failing the whole build.
        # Try progressively wider searches. A single slide exhausting its
        # candidates used to fail the whole build after every other slide had
        # already been sourced, which is a poor trade for one photo.
        attempts = [list(keywords)]
        cleaned = [depopulate(k) for k in keywords]
        cleaned = [c for c in cleaned if len(c.split()) >= 2]
        if cleaned and cleaned != list(keywords):
            attempts.append(cleaned)
        attempts.extend([q] for q in fallback_queries())

        photo, verdict = None, ""
        for n, query in enumerate(attempts):
            if n:
                print(f"    widening search: {query[0]!r}")
            try:
                pool = candidates(query, exclude_ids=used)
            except PexelsError:
                continue
            for cand in pool:
                raw = download(cand, work_dir / f"raw_{idx:02d}.jpg")
                ok, why = vision.check(raw)
                if ok:
                    photo, verdict = cand, why
                    break
                print(f"    rejected {cand['id']}: {why}")
            if photo:
                break

        if photo is None:
            raise PexelsError(
                f"No photo passed the image check for {keywords!r}, even after "
                f"widening the search.\n"
                f"  Either the subject always returns people, or the vision "
                f"check is unavailable.\n"
                f"  Build it text-only, or set a different photo query on this "
                f"slide in content/topics.yaml.")

        used.add(photo["id"])
        fitted = fit_to_window(Image.open(raw))
        composite(png, fitted, png, bg_hex)
        alt = (photo.get("alt") or "").strip()
        described = bool(alt)
        placed = "malaysia" in alt.lower() or "kuala lumpur" in alt.lower()
        credits[png.name] = {
            "pexels_id": photo["id"],
            "photographer": photo.get("photographer"),
            "source": photo.get("url"),
            "keywords": keywords,
            "description": photo.get("alt") or "",
            # No description means the content filters had nothing to read,
            # so this photo passed unchecked and needs a human look.
            "needs_review": not (described and placed),
            "place_confirmed": placed,
            "vision": verdict,
        }
        if not described:
            flag = "   <- NO DESCRIPTION, CHECK THIS ONE"
        elif not placed:
            flag = "   <- location not stated, check it fits"
        else:
            flag = ""
        print(f"    {png.name}: {alt or '(no description)'}{flag}")
    return credits


def write_credits(credits: dict, out_dir: Path) -> Path:
    p = Path(out_dir) / "credits.json"
    p.write_text(json.dumps(credits, ensure_ascii=False, indent=2),
                 encoding="utf-8")
    return p
