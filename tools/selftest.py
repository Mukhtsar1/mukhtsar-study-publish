"""
Pipeline test suite.

  python -m tools.selftest          # all tests, stubbed Pexels
  python -m tools.selftest --live   # also hits the real Pexels API (needs key)

Exits non-zero if anything fails.
"""
from __future__ import annotations

import shutil
import sys
import traceback
from pathlib import Path
from unittest.mock import patch

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config.themes import CANVAS, PATHS, theme          # noqa: E402
from src import images, vision, qa                              # noqa: E402
from src.build import (build_caption, build_slides,      # noqa: E402
                       get_topic, load_topics)
from src.render import render_slides                    # noqa: E402

TMP = ROOT / "out" / "_selftest"
PASS, FAIL = [], []


def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        PASS.append(name)
        print(f"  PASS  {name}")
    else:
        FAIL.append((name, detail))
        print(f"  FAIL  {name}  {detail}")


# --------------------------------------------------------------- stubs
def _fake_photo(i: int) -> dict:
    return {"id": i, "width": 3000, "height": 1600, "alt": "stub",
            "url": "https://pexels.test/x", "photographer": "Stub",
            "src": {"large2x": "file://stub"}}


def _stub_pick(counter):
    def inner(keywords, exclude_ids=None):
        counter["n"] += 1
        return _fake_photo(counter["n"])
    return inner


def _stub_candidates(counter):
    """Ranked candidates, stubbed. fill_windows now walks a list."""
    def inner(keywords, exclude_ids=None, limit=6):
        return [_stub_pick(counter)(keywords, exclude_ids)]
    return inner


def _stub_vision(path):
    """The vision check needs a live model; tests assert the plumbing only."""
    return True, "stubbed"


def _stub_download(photo, dest):
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shade = 40 + (photo["id"] * 25) % 180
    Image.new("RGB", (3000, 1600), (shade, 90, 150)).save(dest)
    return dest


# --------------------------------------------------------------- tests
def test_all_paths_render() -> None:
    print("\n[1] every topic renders on its declared path")
    for topic in load_topics():
        pk = topic.get("path", "A")
        out = TMP / f"{topic['id']}-{pk}"
        shutil.rmtree(out, ignore_errors=True)
        slides = build_slides(topic, pk)
        pngs = render_slides(slides, out, base_url=str(ROOT))

        expected = (1 + len(topic.get("items", []))
                    + (1 if topic.get("checklist") else 0) + 1)
        check(f"{topic['id']:<12} {pk:<6} slide count",
              len(pngs) == expected, f"got {len(pngs)}, expected {expected}")

        sizes_ok = all(Image.open(p).size == (CANVAS["w"], CANVAS["h"])
                       for p in pngs)
        check(f"{topic['id']:<12} {pk:<6} canvas size", sizes_ok)


def test_four_paths_same_topic() -> None:
    print("\n[2] one topic builds on all four paths")
    topic = get_topic("housing")
    for pk in PATHS:
        out = TMP / f"paths-{pk}"
        shutil.rmtree(out, ignore_errors=True)
        try:
            slides = build_slides(topic, pk)
            pngs = render_slides(slides, out, base_url=str(ROOT))
            check(f"path {pk:<6} renders", len(pngs) > 0)
        except Exception as exc:                        # noqa: BLE001
            check(f"path {pk:<6} renders", False, str(exc))


def test_qa_passes_clean() -> None:
    print("\n[3] QA passes on clean builds")
    for topic in load_topics():
        pk = topic.get("path", "A")
        out = TMP / f"{topic['id']}-{pk}"
        pngs = sorted(out.glob("*.png"))
        if not pngs:
            continue
        # image paths need their windows filled before QA
        if PATHS[pk]["images"]:
            counter = {"n": 0}
            kw = {}
            if topic["cover"].get("keywords"):
                kw[0] = topic["cover"]["keywords"]
            for i, it in enumerate(topic.get("items", []), 1):
                if it.get("keywords"):
                    kw[i] = it["keywords"]
            with patch.object(images, "pick", _stub_pick(counter)), \
                 patch.object(images, "candidates", _stub_candidates(counter)), \
                 patch.object(vision, "check", _stub_vision), \
         patch.object(vision, "enabled", lambda: False), \
                 patch.object(vision, "enabled", lambda: False), \
                 patch.object(images, "download", _stub_download):
                images.fill_windows(pngs, kw, theme(pk)["bg"], out / "_work")
            shutil.rmtree(out / "_work", ignore_errors=True)

        res = qa.run([str(p) for p in pngs], build_caption(topic),
                     theme_tokens=theme(pk), topic=topic)
        check(f"{topic['id']:<12} QA clean", res.ok, res.report())


def test_qa_catches_failures() -> None:
    print("\n[4] QA catches injected faults")
    src = sorted((TMP / "costs-A").glob("*.png"))
    bad = TMP / "_bad"
    bad.mkdir(parents=True, exist_ok=True)

    # unfilled photo window
    im = Image.open(src[0]).convert("RGB")
    x0, y0, x1, y1 = CANVAS["window"]
    for y in range(y0, y1, 2):
        for x in range(x0, x1, 2):
            im.putpixel((x, y), (255, 0, 255))
    im.save(bad / "magenta.png")
    r = qa.run([str(bad / "magenta.png")] * 3, "ok", theme_tokens=theme("A"))
    check("detects unfilled photo window", not r.ok)

    # wrong canvas
    Image.open(src[1]).resize((1080, 1080)).save(bad / "size.png")
    r = qa.run([str(bad / "size.png")] * 3, "ok", theme_tokens=theme("A"))
    check("detects wrong canvas size", not r.ok)

    # phone number in caption
    r = qa.run([str(p) for p in src], "راسلنا +60 11-7025 9952",
               theme_tokens=theme("A"))
    check("detects phone number in caption", not r.ok)

    # phone number in slide html
    r = qa.run([str(p) for p in src], "ok",
               [("x", "<div>+60 11-7025 9952</div>")], theme("A"))
    check("detects phone number in slide", not r.ok)

    # caption limits
    r = qa.run([str(p) for p in src], "x" * 2500, theme_tokens=theme("A"))
    check("detects over-long caption", not r.ok)
    r = qa.run([str(p) for p in src], "x" + " #a" * 40, theme_tokens=theme("A"))
    check("detects too many hashtags", not r.ok)

    # carousel bounds
    r = qa.run([str(src[0])], "ok", theme_tokens=theme("A"))
    check("detects too few slides", not r.ok)
    r = qa.run([str(src[0])] * 12, "ok", theme_tokens=theme("A"))
    check("detects too many slides", not r.ok)

    # cover badge vs item count
    t = dict(get_topic("mistakes"))
    t["cover"] = dict(t["cover"], pixel="9")
    r = qa.run([str(p) for p in src], "ok", theme_tokens=theme("A"), topic=t)
    check("detects cover badge mismatch", not r.ok)


def test_cover_number_autoderive() -> None:
    print("\n[5] cover badge auto-derives when omitted")
    t = dict(get_topic("mistakes"))
    t["cover"] = {k: v for k, v in t["cover"].items() if k != "pixel"}
    slides = build_slides(t, "A")
    cover_html = slides[0][1]
    n = len(t["items"])
    check(f"derived badge = {n}", f">{n}<" in cover_html)


def test_image_pipeline() -> None:
    print("\n[6] image path fills every window")
    topic = get_topic("dishes")
    out = TMP / "imgflow"
    shutil.rmtree(out, ignore_errors=True)
    slides = build_slides(topic, "A-img")
    pngs = render_slides(slides, out, base_url=str(ROOT))

    before = Image.open(pngs[1]).convert("RGB").getpixel((500, 400))
    check("window starts keyed (magenta)", before[0] > 200 and before[2] > 200)

    counter = {"n": 0}
    kw = {0: topic["cover"]["keywords"]}
    for i, it in enumerate(topic["items"], 1):
        kw[i] = it["keywords"]
    with patch.object(images, "pick", _stub_pick(counter)), \
         patch.object(images, "candidates", _stub_candidates(counter)), \
         patch.object(vision, "check", _stub_vision), \
         patch.object(vision, "enabled", lambda: False), \
         patch.object(images, "download", _stub_download):
        credits = images.fill_windows(pngs, kw, theme("A-img")["bg"],
                                      out / "_work")
    shutil.rmtree(out / "_work", ignore_errors=True)

    after = Image.open(pngs[1]).convert("RGB").getpixel((500, 400))
    check("window filled after compositing",
          not (after[0] > 200 and after[2] > 200), str(after))
    check("credits recorded per image", len(credits) == len(kw),
          f"{len(credits)} vs {len(kw)}")
    check("no duplicate photo in one carousel",
          len({c['pexels_id'] for c in credits.values()}) == len(credits))


def test_image_filters() -> None:
    print("\n[7] Pexels safety filters")
    bad = {"id": 1, "alt": "woman in bikini on beach", "url": "https://x",
           "width": 3000, "height": 1600}
    check("rejects banned content", images._banned(bad))
    good = {"id": 2, "alt": "train station platform", "url": "https://x",
            "width": 3000, "height": 1600}
    check("allows ordinary content", not images._banned(good))
    check("rejects portrait", images.score(
        {"width": 1200, "height": 1600}) < 0)
    check("rejects low resolution", images.score(
        {"width": 800, "height": 450}) < 0)
    check("accepts wide hi-res", images.score(
        {"width": 3000, "height": 1600}) > 0)


def test_caption() -> None:
    print("\n[8] captions")
    for topic in load_topics():
        cap = build_caption(topic)
        res = qa.QAResult()
        qa.check_caption(cap, res)
        check(f"{topic['id']:<12} caption valid", res.ok, res.report())
        check(f"{topic['id']:<12} no phone in caption",
              not qa.PHONE_RE.search(cap))


def test_publish_guards() -> None:
    print("\n[9] publish guards (no network)")
    from src import publish
    try:
        publish.publish_carousel(["https://x/1.png"], "cap", dry_run=True)
        check("rejects single-image carousel", False, "should have raised")
    except publish.PublishError:
        check("rejects single-image carousel", True)

    r = publish.publish_carousel(["https://x/1.png", "https://x/2.png"],
                                 "cap", dry_run=True)
    check("dry run returns without publishing", r.get("dry_run") is True)


def main() -> None:
    TMP.mkdir(parents=True, exist_ok=True)
    print("Mukhtsar pipeline self-test")
    print("=" * 60)
    for fn in (test_all_paths_render, test_four_paths_same_topic,
               test_qa_passes_clean, test_qa_catches_failures,
               test_cover_number_autoderive, test_image_pipeline,
               test_image_filters, test_caption, test_publish_guards):
        try:
            fn()
        except Exception:                                # noqa: BLE001
            FAIL.append((fn.__name__, "raised"))
            print(f"  ERROR in {fn.__name__}")
            traceback.print_exc()

    print("\n" + "=" * 60)
    print(f"{len(PASS)} passed, {len(FAIL)} failed")
    for name, detail in FAIL:
        print(f"  FAILED: {name} {detail}")
    shutil.rmtree(TMP, ignore_errors=True)
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
