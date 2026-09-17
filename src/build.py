"""
Build a topic into slide HTML.

The same builder serves all four paths — the theme tokens and the
with_image flag do all the work.
"""
import re
from pathlib import Path

import yaml

from config.themes import theme, uses_images
from config import layouts

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
FONTS = ASSETS / "fonts"

# A run of Latin letters/digits and the neutrals that belong with them.
# Without isolation, a trailing neutral ("+", "%") jumps to the other end of
# the run inside an RTL paragraph — "RM 450 – 1,500+" renders as "+RM 450 – 1,500".
_LTR_RUN = re.compile(
    r"[A-Za-z][A-Za-z0-9 ,.\u2013\u2014\-/+%:&']*[A-Za-z0-9+%]"
    r"|[0-9][0-9 ,.\u2013\u2014\-/]*[0-9][+%]"
)


def iso(text: str) -> str:
    """Wrap Latin/number runs in an LTR isolate. Safe on strings holding HTML:
    anything between < and > is left untouched."""
    if not text:
        return text
    out, i = [], 0
    for m in re.finditer(r"<[^>]*>", text):
        out.append(_LTR_RUN.sub(lambda r: f'<span class="ltr">{r.group(0)}</span>',
                                text[i:m.start()]))
        out.append(m.group(0))
        i = m.end()
    out.append(_LTR_RUN.sub(lambda r: f'<span class="ltr">{r.group(0)}</span>',
                            text[i:]))
    return "".join(out)


def load_topics(path: Path | None = None) -> list:
    path = path or ROOT / "content" / "topics.yaml"
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)["topics"]


def get_topic(topic_id: str, path: Path | None = None) -> dict:
    for t in load_topics(path):
        if t["id"] == topic_id:
            return t
    raise KeyError(f"No topic with id '{topic_id}' in topics.yaml")


def build_slides(topic: dict, path_key: str | None = None) -> list:
    """
    Return [(slide_name, html), ...] in carousel order.
    Photo windows are left transparent-keyed here; images.py fills them later.
    """
    path_key = path_key or topic.get("path", "A")
    t = theme(path_key)
    with_img = uses_images(path_key)
    assets = ASSETS.as_uri()
    fonts = FONTS.as_uri()
    tag = topic.get("tag", "مختصر")
    source = topic.get("source", "")

    slides = []

    # cover -----------------------------------------------------------------
    c = dict(topic["cover"])
    # If the cover's big pixel number is omitted, derive it from the item count
    # so the cover can never disagree with the slides.
    if "pixel" not in c or c["pixel"] is None:
        c["pixel"] = str(len(topic.get("items", [])))
    slides.append(("cover", layouts.cover(
        t, assets, fonts,
        eyebrow=c["eyebrow"], pixel=c["pixel"], headline=iso(c["headline"]),
        highlight=c["highlight"], subline=iso(c["subline"]), tag=tag,
        with_image=with_img, icon_name=c.get("icon"),
        source="" if with_img else source)))

    # items -----------------------------------------------------------------
    items = topic.get("items", [])
    for i, it in enumerate(items, 1):
        slides.append((f"item{i}", layouts.item(
            t, assets, fonts,
            index=i, total=len(items), icon_name=it["icon"],
            title=iso(it["title"]), subtitle=iso(it.get("subtitle", "")),
            body_html=iso(it["body"]), tip=iso(it.get("tip")),
            tag=f'<span class="ltr">{i} / {len(items)}</span>',
            with_image=with_img, source=source if not with_img else "")))

    # optional checklist ----------------------------------------------------
    if topic.get("checklist"):
        cl = topic["checklist"]
        slides.append(("checklist", layouts.checklist(
            t, assets, fonts,
            eyebrow=cl["eyebrow"], title=iso(cl["title"]),
            lines=[iso(x) for x in cl["lines"]],
            tag=topic.get("checklist_tag", "قائمة تحقق"))))

    # cta -------------------------------------------------------------------
    ct = topic["cta"]
    slides.append(("cta", layouts.cta(
        t, assets, fonts,
        eyebrow=ct["eyebrow"], icon_name=ct["icon"], headline=iso(ct["headline"]),
        highlight=ct["highlight"], body_text=iso(ct["body"]),
        button=iso(ct["button"]),
        save_line=iso(ct["save"]), tag="استشارة مجانية")))

    return slides


def build_caption(topic: dict) -> str:
    """Assemble the Instagram caption from the topic fields."""
    tags = " ".join(f"#{h}" for h in topic.get("hashtags", []))
    return (
        f"{topic['hook']}\n\n"
        f"{topic['cover']['subline'].replace('<br>', ' ')}\n\n"
        f"📌 احفظ المنشور — وأرسله لمن يخطط للدراسة في ماليزيا\n"
        f"الاستشارة مجانية — الرابط في البايو\n\n"
        f"{tags}"
    )
