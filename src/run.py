"""
Mukhtsar carousel pipeline — command line.

  python -m src.run go                         <- everything, one command
  python -m src.run schedule                   <- show the publish queue
  python -m src.run schedule --id <run> --checked
  python -m src.run discover [--count 3]       <- propose new topics
  python -m src.run approve  --id visa         <- move a reviewed draft in
  python -m src.run new                        <- guided: topic, design, images
  python -m src.run build   --topic housing [--path B-img]
  python -m src.run build   --next
  python -m src.run publish --id 2026-09-14-housing [--dry-run]
  python -m src.run auto    [--dry-run]        <- what the scheduler runs
  python -m src.run status
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _load_env() -> None:
    """Read .env into the environment. Real environment variables always win,
    so CI secrets are never overridden by a stale local file."""
    path = ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip().strip('"').strip("'")
        if key and val and key not in os.environ:
            os.environ[key] = val


_load_env()

from config.themes import theme, uses_images          # noqa: E402
from src import qa                                    # noqa: E402
from src.build import (build_caption, build_slides,    # noqa: E402
                       get_topic, load_topics)
from src.render import render_slides                  # noqa: E402

OUT = ROOT / "out"
STATE = ROOT / "content" / "state.json"
SETTINGS = ROOT / "config" / "settings.yaml"


# ------------------------------------------------------------------ state
def _state() -> dict:
    if STATE.exists():
        return json.loads(STATE.read_text(encoding="utf-8"))
    return {"published": [], "rotation_index": 0}


def _save_state(s: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(s, ensure_ascii=False, indent=2),
                     encoding="utf-8")


def _settings() -> dict:
    if SETTINGS.exists():
        return yaml.safe_load(SETTINGS.read_text(encoding="utf-8"))
    return {}


def _next_topic() -> dict:
    done = {p["topic"] for p in _state()["published"]}
    for t in load_topics():
        if t["id"] not in done:
            return t
    raise SystemExit("Every topic in topics.yaml has been published. "
                     "Add more topics or clear content/state.json.")


def _rotation_path() -> str:
    cfg = _settings().get("rotation", ["A", "B-img", "A-img", "B"])
    s = _state()
    p = cfg[s.get("rotation_index", 0) % len(cfg)]
    return p


# ------------------------------------------------------------------ build
def cmd_build(args) -> str:
    if args.topic:
        try:
            topic = get_topic(args.topic)
        except KeyError:
            known = ", ".join(t["id"] for t in load_topics())
            draft = ROOT / "content" / "drafts" / f"{args.topic}.yaml"
            hint = ""
            if draft.exists():
                hint = (f"\n  It is still a draft at content/drafts/"
                        f"{args.topic}.yaml — fill in every TODO, then:"
                        f"\n    python -m src.run approve --id {args.topic}")
            raise SystemExit(
                f"\nNo topic '{args.topic}' in topics.yaml.{hint}"
                f"\n  In the bank: {known}")
    else:
        topic = _next_topic()
    path_key = args.path or topic.get("path") or _rotation_path()

    run_id = _unique_run_id(topic["id"])
    out_dir = OUT / run_id
    if out_dir.exists():
        shutil.rmtree(out_dir)

    print(f"Building '{topic['id']}' on path {path_key} -> {run_id}")
    slides = build_slides(topic, path_key)
    pngs = render_slides(slides, out_dir, base_url=str(ROOT))
    caption = build_caption(topic)

    credits = {}
    if uses_images(path_key):
        from src import images                        # imported lazily
        kw_map = {}
        if topic["cover"].get("keywords"):
            kw_map[0] = topic["cover"]["keywords"]
        for i, it in enumerate(topic.get("items", []), start=1):
            if it.get("keywords"):
                kw_map[i] = it["keywords"]
        if kw_map:
            print(f"  sourcing {len(kw_map)} images from Pexels…")
            credits = images.fill_windows(
                pngs, kw_map, theme(path_key)["bg"], out_dir / "_work")
            images.write_credits(credits, out_dir)
            shutil.rmtree(out_dir / "_work", ignore_errors=True)

    (out_dir / "caption.txt").write_text(caption, encoding="utf-8")
    (out_dir / "meta.json").write_text(json.dumps({
        "run_id": run_id, "topic": topic["id"], "path": path_key,
        "slides": [p.name for p in pngs], "built": dt.datetime.now().isoformat(),
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"  rendered {len(pngs)} slides")

    result = qa.run([str(p) for p in pngs], caption, slides,
                    theme(path_key), topic=topic)
    print("QA:")
    print(result.report())
    if not result.ok:
        raise SystemExit("QA failed — nothing will be published.")
    return run_id


# ---------------------------------------------------------------- publish
def cmd_publish(args) -> None:
    from src import publish
    run_id = args.id
    out_dir = OUT / run_id
    if not out_dir.exists():
        raise SystemExit(f"No build at {out_dir}")

    caption = (out_dir / "caption.txt").read_text(encoding="utf-8")
    pngs = sorted(out_dir.glob("*.png"))
    meta = json.loads((out_dir / "meta.json").read_text(encoding="utf-8"))

    result = qa.run([str(p) for p in pngs], caption,
                    theme_tokens=theme(meta["path"]))
    if not result.ok:
        print(result.report())
        raise SystemExit("QA failed — refusing to publish.")

    # QA checks the artwork, not the truth of the words on it. A run that was
    # written automatically has been read by nobody, so it does not go out
    # until someone says they have read it.
    if meta.get("reviewed") is False and not getattr(args, "checked", False):
        figs = meta.get("figures") or []
        extra = ("\n  It also contains numbers nothing has verified: "
                 + ", ".join(figs)) if figs else ""
        raise SystemExit(
            f"\n'{run_id}' was written automatically and has not been read."
            f"{extra}\n"
            f"  Open out/{run_id}/ and read every slide, then:\n"
            f"    python -m src.run publish --id {run_id} --checked")

    # Content that was written automatically has been read by nobody. QA
    # checks pixels and rules; it cannot tell whether a fee or a date is true.
    # This is the gate that moved here when `go` stopped waiting on drafts.
    if not meta.get("verified", True) and not args.dry_run:
        figs = meta.get("unverified_figures", [])
        print("\n" + "!" * 66)
        print(f"  '{run_id}' was written by a model and not checked by anyone.")
        if figs:
            print("  Figures it invented: " + ", ".join(figs[:8]))
        print(f"  Read every slide in out/{run_id} before this goes out.")
        print("!" * 66)
        if not args.checked:
            raise SystemExit(
                "Refusing to publish unchecked content.\n"
                "  Once you have read the slides and fixed anything wrong:\n"
                f"    python -m src.run publish --id {run_id} --checked")
        meta["verified"] = True
        meta["verified_at"] = dt.datetime.now().isoformat()
        (out_dir / "meta.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")

    urls = publish.public_urls(out_dir, run_id, dry_run=args.dry_run)
    if not args.dry_run:
        publish.check_reachable(urls)
    print(f"Publishing {len(urls)} slides for {run_id}…")
    res = publish.publish_carousel(urls, caption, dry_run=args.dry_run)
    print(json.dumps(res, ensure_ascii=False, indent=2))

    if not args.dry_run:
        s = _state()
        s["published"].append({
            "topic": meta["topic"], "run_id": run_id, "path": meta["path"],
            "media_id": res.get("media_id"),
            "at": dt.datetime.now().isoformat(),
        })
        s["rotation_index"] = s.get("rotation_index", 0) + 1
        _save_state(s)
        print("state updated")


# ------------------------------------------------------------------- auto
def cmd_auto(args) -> None:
    args.topic = None
    args.path = None
    run_id = cmd_build(args)
    args.id = run_id
    cmd_publish(args)


# ----------------------------------------------------------------- status
def cmd_status(_args) -> None:
    s = _state()
    topics = load_topics()
    done = {p["topic"] for p in s["published"]}
    print(f"Topics: {len(topics)} total, {len(done)} published, "
          f"{len(topics) - len(done)} queued")
    print(f"Next up: {_next_topic()['id'] if len(done) < len(topics) else '—'}")
    print(f"Rotation position: {s.get('rotation_index', 0)}")
    if s["published"]:
        print("\nRecent:")
        for p in s["published"][-5:]:
            # entries added by hand (backfilling posts made before the
            # pipeline existed) carry no path or media_id
            note = p.get("media_id") or p.get("note", "")
            print(f"  {p.get('at', '')[:10]}  {p.get('topic', '?'):<20} "
                  f"{p.get('path', '—'):<6} {note}")
    try:
        from src import publish
        print("\nPublishing quota:", publish.rate_limit_usage())
    except Exception as exc:
        print(f"\n(quota check unavailable: {exc})")


# ------------------------------------------------------------------- new
def _unique_run_id(topic_id: str) -> str:
    """
    <date>-<topic>, with -v2, -v3 ... if that folder already exists.

    Two builds of one topic on one day are a normal thing to want — a second
    angle, or the same topic on the other theme to compare. Overwriting the
    first silently is not.
    """
    base = f"{dt.date.today().isoformat()}-{topic_id}"
    if not (OUT / base).exists():
        return base
    n = 2
    while (OUT / f"{base}-v{n}").exists():
        n += 1
    return f"{base}-v{n}"


def _built_runs() -> dict:
    """topic id -> list of run ids already rendered in out/."""
    found = {}
    if OUT.exists():
        for d in sorted(OUT.iterdir()):
            meta = d / "meta.json"
            if d.is_dir() and meta.exists():
                try:
                    m = json.loads(meta.read_text(encoding="utf-8"))
                except Exception:
                    continue
                found.setdefault(m.get("topic"), []).append(
                    (d.name, m.get("path", "?")))
    return found


def _ask(prompt: str, valid: list[str], default: str | None = None) -> str:
    """Prompt until the answer is one of `valid` (case-insensitive)."""
    show = "/".join(v.upper() if v == default else v for v in valid)
    while True:
        try:
            raw = input(f"{prompt} [{show}]: ").strip()
        except (EOFError, KeyboardInterrupt):
            raise SystemExit("\nCancelled.")
        if not raw and default:
            return default
        for v in valid:
            if raw.lower() == v.lower():
                return v
        print(f"  Please answer one of: {', '.join(valid)}")


def _confirm(prompt: str) -> bool:
    return _ask(prompt, ["y", "n"], "n") == "y"


def cmd_new(args) -> None:
    """Guided build: pick a topic, check it does not clash, pick the look."""
    topics = load_topics()
    published = {p["topic"]: p for p in _state()["published"]}
    built = _built_runs()

    print("\nTopics")
    print("-" * 62)
    for i, t in enumerate(topics, 1):
        if t["id"] in published:
            mark = "PUBLISHED " + published[t["id"]]["at"][:10]
        elif t["id"] in built:
            mark = "built     " + ", ".join(r for r, _ in built[t["id"]])
        else:
            mark = "free"
        kw = "photos ok" if _has_keywords(t) else "no keywords"
        print(f"  {i:>2}. {t['id']:<14} {mark:<28} {kw}")
    print("-" * 62)

    # --- topic ----------------------------------------------------------
    choice = _ask("Topic number", [str(i) for i in range(1, len(topics) + 1)])
    topic = topics[int(choice) - 1]
    tid = topic["id"]

    if tid in published:
        when = published[tid]["at"][:10]
        print(f"\n  ! '{tid}' was already published on {when}.")
        print("    Reposting the same topic is what the algorithm reads as")
        print("    aggregator behaviour — it hurts reach.")
        if not _confirm("    Build it anyway?"):
            raise SystemExit("Cancelled.")
    elif tid in built:
        runs = ", ".join(f"{r} ({pk})" for r, pk in built[tid])
        print(f"\n  ! '{tid}' is already built locally: {runs}")
        print("    Building again overwrites today's render for this topic.")
        if not _confirm("    Continue?"):
            raise SystemExit("Cancelled.")

    # --- design ---------------------------------------------------------
    print("\n  A = dark  (navy background, gold accents, red offset)")
    print("  B = light (cream background, navy text, teal accents)")
    pinned = topic.get("path", "")
    default_design = "B" if pinned.startswith("B") else "A"
    design = _ask("Design", ["A", "B"], default_design).upper()

    # --- images ---------------------------------------------------------
    has_kw = _has_keywords(topic)
    print("\n  Y = photo window on each slide, filled from Pexels")
    print("  N = text only, no photos")
    if not has_kw:
        print(f"  ! '{tid}' has no keywords in topics.yaml, so photo windows")
        print("    would render empty. Add keywords first to use photos.")
    default_img = "y" if (has_kw and pinned.endswith("-img")) else "n"
    want_img = _ask("With images", ["y", "n"], default_img).lower() == "y"

    if want_img and not has_kw:
        print("  Falling back to text only — nothing to search Pexels with.")
        want_img = False

    path_key = f"{design}-img" if want_img else design

    # --- confirm --------------------------------------------------------
    run_id = _unique_run_id(tid)
    print("\n" + "-" * 62)
    print(f"  Topic   {tid}")
    print(f"  Path    {path_key}")
    print(f"  Output  out/{run_id}")
    print("-" * 62)
    if not _confirm("Build this?"):
        raise SystemExit("Cancelled.")

    args.topic = tid
    args.path = path_key
    print()
    cmd_build(args)


def _has_keywords(topic: dict) -> bool:
    if topic.get("cover", {}).get("keywords"):
        return True
    return any(it.get("keywords") for it in topic.get("items", []))


# --------------------------------------------------------------- discover
def _dedup_threshold() -> float:
    return float((_settings().get("discovery", {}) or {}).get("threshold", 0.35))


def cmd_discover(args) -> None:
    from src import discover as dsc

    accepted, rejected = dsc.propose(args.count, _dedup_threshold())

    if rejected:
        print(f"\nSkipped {len(rejected)} — already covered:")
        for r in rejected:
            print(f"  {r['id']:<20} {r['reason']} ({r['clash']}, {r['score']})")

    if not accepted:
        print("\nNothing new in the backlog. Add ideas to content/ideas.yaml.")
        return

    print(f"\nProposing {len(accepted)}:")
    written = []
    for idea in accepted:
        with_img = bool(idea.get("keywords"))
        if args.generate:
            from src import generate as gen
            print(f"  {idea['id']:<20} drafting with {gen.model_name()}…")
            text, flagged = gen.generate(idea, with_images=with_img)
            path = dsc.DRAFTS / f"{idea['id']}.yaml"
            dsc.DRAFTS.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            note = f"{flagged} figure(s) flagged VERIFY" if flagged \
                else "no figures"
            print(f"  {'':<20} written, {note}")
        else:
            path = dsc.write_draft(idea, with_images=with_img)
            print(f"  {idea['id']:<20} nearest existing: "
                  f"{idea['nearest'] or '-'} ({idea['score']})")
        written.append(path)

    if args.generate:
        print("\nDrafts written to content/drafts/ — read every line, and "
              "check\nevery VERIFY[...] against a real source before approving.")
    else:
        print("\nDrafts written to content/drafts/ — every figure is a TODO.")
    print("Then:")
    for path in written:
        print(f"  python -m src.run approve --id {path.stem}")


def cmd_approve(args) -> None:
    from src import discover as dsc
    tid = dsc.approve(args.id)
    print(f"'{tid}' added to topics.yaml. Build it with:")
    print(f"  python -m src.run build --topic {tid}")


# --------------------------------------------------------------------- go
def _pick_look(topic: dict, tid: str) -> str:
    """Design + images prompts, shared by `new` and `go`."""
    print("\n  A = dark  (navy background, gold accents, red offset)")
    print("  B = light (cream background, navy text, teal accents)")
    pinned = topic.get("path", "")
    design = _ask("Design", ["A", "B"],
                  "B" if pinned.startswith("B") else "A").upper()

    has_kw = _has_keywords(topic)
    print("\n  Y = photo window on each slide, filled from Pexels")
    print("  N = text only, no photos")
    if not has_kw:
        print(f"  ! '{tid}' has no keywords, so photo windows would be empty.")
    default_img = "y" if (has_kw and pinned.endswith("-img")) else "n"
    want = _ask("With images", ["y", "n"], default_img).lower() == "y"
    if want and not has_kw:
        print("  Falling back to text only — nothing to search Pexels with.")
        want = False
    return f"{design}-img" if want else design



def _wait_for_draft(dsc, tid: str, path) -> None:
    """
    Watch the draft and continue the moment it validates.

    Automating the keystroke, not the judgement: the pipeline can tell that a
    placeholder is gone and the YAML parses, and that is all it checks here.
    Whether a fee, a date or a process claim is TRUE is not something any of
    this can verify — that part stays with you, which is why the draft has to
    be edited by a person before this loop lets it through.
    """
    import time

    print(f"\n  Opening {path.name}…")
    try:
        os.startfile(str(path))                       # noqa: S606 (Windows)
    except AttributeError:
        print(f"  Open it yourself: {path}")
    except OSError:
        print(f"  Could not open an editor. Open it yourself: {path}")

    print("  Fill in every TODO and check every VERIFY[...] against a real")
    print("  source. Save the file — this continues on its own.")
    print("  Ctrl+C to stop.\n")

    last_note, last_mtime = None, None
    try:
        while True:
            try:
                mtime = path.stat().st_mtime
            except OSError:
                print("  Draft file disappeared.")
                raise SystemExit("Stopped.")

            ready, _, note = dsc.draft_status(tid)
            if ready:
                dsc.approve(tid)
                print(f"  Draft is clean — '{tid}' added to the bank.")
                return
            if note != last_note or mtime != last_mtime:
                print(f"  waiting… {note}")
                last_note, last_mtime = note, mtime
            time.sleep(2)
    except KeyboardInterrupt:
        raise SystemExit("\nStopped — the draft is still in drafts/.")


def cmd_go(args) -> None:
    """
    One list, one choice, straight to a built carousel.

    Fresh topics come from the backlog and from live feeds, merged into a
    single list — where an idea came from does not change what you do with it.
    Picking one writes the Arabic, adds it to the bank and builds it without
    stopping.

    The verification gate does not disappear, it moves. Generated content is
    written under a no-numbers rule, so there is no invented fee or percentage
    to publish, and the build is marked `reviewed: false`. `publish` refuses
    such a run until you pass --checked, which is where a person reads it.
    """
    from src import discover as dsc

    topics = load_topics()
    published = {p["topic"]: p for p in _state()["published"]}
    built = _built_runs()
    ready = [t for t in topics if t["id"] not in published]

    print("\nLooking for fresh topics…")
    try:
        backlog, _ = dsc.propose(args.fresh, _dedup_threshold())
    except dsc.DiscoveryError as exc:
        print(f"  ({exc})")
        backlog = []

    news = []
    if not args.no_news:
        try:
            from src import sources as src_
            found, problems = src_.gather(args.news)
            for name, why in problems:
                print(f"  ! {name}: {why}")
            corpus = dsc.build_corpus()
            taken = ({t["id"] for t in topics} | set(published)
                     | dsc.draft_ids() | {i["id"] for i in backlog})
            for item in found:
                if item["id"] in taken:
                    continue
                dup, _, _ = dsc.is_duplicate(f"{item['hook']} {item['id']}",
                                             _dedup_threshold(), corpus)
                if not dup:
                    news.append(item)
                    corpus.append((item["id"], item["hook"]))
        except Exception as exc:                       # noqa: BLE001
            print(f"  (feeds unavailable: {exc})")

    rows = []
    print("\n" + "=" * 66)
    if ready:
        print("ALREADY WRITTEN")
        for t in ready:
            n = len(rows) + 1
            mark = "built" if t["id"] in built else ""
            print(f"  {n:>2}. {t['id']:<34} {mark}")
            rows.append(("ready", t))

    fresh = news + backlog
    if fresh:
        print("\nFRESH TOPICS")
        for item in fresh:
            n = len(rows) + 1
            title = item.get("_title") or item.get("hook", "")
            print(f"  {n:>2}. {item['id']:<34} {title[:44]}")
            rows.append(("fresh", item))
    print("=" * 66)

    if not rows:
        raise SystemExit("Nothing to build and nothing new to propose.")

    choice = _ask("Pick a number", [str(i) for i in range(1, len(rows) + 1)])
    kind, chosen = rows[int(choice) - 1]
    figures: list[str] = []

    if kind == "fresh":
        tid = chosen["id"]
        with_img = bool(chosen.get("keywords"))
        from src import generate as gen
        print(f"\n  Writing '{tid}' with {gen.model_name()}…")
        try:
            text, figures = gen.generate(chosen, with_images=with_img,
                                         no_figures=True)
        except Exception as exc:                       # noqa: BLE001
            raise SystemExit(
                f"\n  Could not write it: {exc}\n"
                f"  Nothing was added. Try again, or write it by hand with:\n"
                f"    python -m src.run discover --count 1")

        dsc.DRAFTS.mkdir(parents=True, exist_ok=True)
        path = dsc.DRAFTS / f"{tid}.yaml"
        if chosen.get("_source"):
            text = (f"# Prompted by: {chosen.get('_title','')}\n"
                    f"# Source:      {chosen['_source']}\n#\n") + text
            try:
                from src import sources as src_
                src_.mark_seen([{"link": chosen["_source"],
                                 "title": chosen.get("_title", "")}])
            except Exception:                          # noqa: BLE001
                pass
        path.write_text(text, encoding="utf-8")

        try:
            dsc.approve(tid)
        except dsc.DiscoveryError as exc:
            raise SystemExit(f"\n  Draft rejected: {exc}\n"
                             f"  It is at {path} if you want to fix it.")
        print(f"  Written and added to the bank.")
        chosen = get_topic(tid)

    tid = chosen["id"]
    path_key = _pick_look(chosen, tid)
    print()
    args.topic, args.path = tid, path_key
    run_id = cmd_build(args)

    # mark the run unreviewed so publish will not take it unread
    meta_path = OUT / run_id / "meta.json"
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        meta["reviewed"] = False
        meta["written_by"] = "model" if kind == "fresh" else "hand"
        if figures:
            meta["figures"] = figures
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2),
                             encoding="utf-8")

    if kind == "fresh":
        print("\n  " + "-" * 60)
        if figures:
            print("  ! Numbers survived the no-figures rule:")
            for f in figures:
                print(f"      {f}")
            print("  ! Nothing has checked whether these are true.")
        print("  Read the slides before publishing. Nobody has read them yet.")
        print(f"  When you have:  python -m src.run publish --id {run_id} "
              f"--checked")
        print("  " + "-" * 60)


# ---------------------------------------------------------------- sources
def cmd_sources(args) -> None:
    from src import sources as src_

    if args.check:
        cfg = src_.load_config()
        print("\nChecking feeds…", flush=True)
        for feed in cfg.get("feeds", []):
            name = feed.get("name", feed["url"])
            if not feed.get("enabled", True):
                print(f"  off   {name}")
                continue
            try:
                entries = src_.fetch_feed(feed["url"])
                hits = sum(1 for e in entries
                           if src_.relevant(e, cfg.get("topic_keywords", []),
                                            cfg.get("geo_keywords", []),
                                            cfg.get("exclude_keywords", [])))
                print(f"  OK    {name} — {len(entries)} entries, {hits} relevant")
            except src_.SourceError as exc:
                print(f"  FAIL  {name} — {exc}")
        print("\nA FAIL means the URL moved or died. Fix or disable it in "
              "config/sources.yaml —\na dead feed shrinks your ideas silently.")
        return

    ideas, problems = src_.gather(args.count)
    for name, why in problems:
        print(f"  ! {name}: {why}")
    if not ideas:
        print("\nNothing new from the feeds. Either nothing relevant was "
              "published,\nor you have seen it all already "
              "(content/seen_sources.json).")
        return
    print(f"\n{len(ideas)} story/stories worth a post:\n")
    for i in ideas:
        print(f"  {i['id']}")
        print(f"    {i['_title']}")
        print(f"    {i['_source']}\n")
    print("These are prompts, not facts. `go` offers them alongside the "
          "backlog.")


# --------------------------------------------------------------- schedule
def _mark_checked(run_id: str) -> None:
    """Record that a person read this build, so the queue may publish it."""
    meta_path = OUT / run_id / "meta.json"
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        meta["reviewed"] = True
        meta["reviewed_at"] = dt.datetime.now().isoformat(timespec="minutes")
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2),
                             encoding="utf-8")


def cmd_schedule(args) -> None:
    from src import schedule as sch

    if args.cancel:
        sch.cancel(args.cancel)
        print(f"Cancelled {args.cancel}.")
        return

    if args.id:
        out_dir = OUT / args.id
        if not out_dir.exists():
            raise SystemExit(f"No build at out/{args.id}")

        meta = {}
        meta_path = out_dir / "meta.json"
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))

        # The queue publishes unattended, so this is the moment a person
        # confirms they have read the slides. Nothing downstream asks again.
        if meta.get("reviewed") is False and not args.checked:
            raise SystemExit(
                f"\n'{args.id}' was written automatically and has not been "
                f"read.\n  Open out/{args.id}/ and read every slide, then:\n"
                f"    python -m src.run schedule --id {args.id} "
                f"--at \"{args.at or '2026-09-20 21:00'}\" --checked")
        if args.checked:
            _mark_checked(args.id)

        when = sch.parse_when(args.at) if args.at else sch.next_slot(sch.load())
        entry = sch.add(args.id, when, meta.get("topic", ""))
        ksa, myt = sch.fmt(entry["at"])
        print(f"Scheduled {args.id}")
        print(f"  {ksa} KSA   ({myt} Malaysia)")
        print("\nRemember to push before it fires — Instagram fetches the "
              "images\nfrom the public repo, not from this machine:")
        print("  git add -A; git commit -m \"Add carousel\"; git push")
        return

    # default: show the queue
    queue = sch.load()
    if not queue:
        print("\nNothing scheduled.\n")
        print("Schedule a build with:")
        print("  python -m src.run schedule --id <run-id> --checked")
        print("  python -m src.run schedule --id <run-id> --at "
              "\"2026-09-20 21:00\" --checked")
        return

    pending = [e for e in queue if e["status"] == "pending"]
    donelist = [e for e in queue if e["status"] != "pending"]

    if pending:
        print("\nSCHEDULED")
        print("-" * 74)
        print(f"  {'WHEN (KSA)':<22} {'MY':<7} {'RUN ID':<40}")
        print("-" * 74)
        for e in pending:
            ksa, myt = sch.fmt(e["at"])
            print(f"  {ksa:<22} {myt:<7} {e['run_id']:<40}")
    if donelist:
        print("\nDONE")
        print("-" * 74)
        for e in donelist[-5:]:
            ksa, _ = sch.fmt(e["at"])
            state = e["status"]
            print(f"  {ksa:<22} {state:<7} {e['run_id']:<40} "
                  f"{e.get('media_id') or ''}")
    print()
    overdue = sch.due()
    if overdue:
        print(f"{len(overdue)} post(s) past their slot and not published. "
              f"Run:  python -m src.run publish-due")


def cmd_publish_due(args) -> None:
    """Publish everything whose slot has passed. This is what cron runs."""
    from src import schedule as sch
    from src import publish

    ready = sch.due()
    if not ready:
        print("Nothing due.")
        return

    for entry in ready:
        run_id = entry["run_id"]
        ksa, _ = sch.fmt(entry["at"])
        print(f"\n{run_id}  (slot {ksa} KSA)")
        try:
            args.id, args.checked = run_id, True
            cmd_publish(args)
            meta_path = OUT / run_id / "meta.json"
            media = None
            if meta_path.exists():
                media = json.loads(
                    meta_path.read_text(encoding="utf-8")).get("media_id")
            sch.mark(run_id, "published", media)
        except SystemExit as exc:
            print(f"  failed: {exc}")
            sch.mark(run_id, "failed")
        except publish.PublishError as exc:
            print(f"  failed: {exc}")
            sch.mark(run_id, "failed")


# ------------------------------------------------------------------- main
def main() -> None:
    ap = argparse.ArgumentParser(prog="mukhtsar-carousel")
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build", help="render a carousel locally")
    b.add_argument("--topic")
    b.add_argument("--path", choices=["A", "A-img", "B", "B-img"])
    b.add_argument("--next", action="store_true")
    b.set_defaults(func=lambda a: cmd_build(a))

    p = sub.add_parser("publish", help="publish an already-built carousel")
    p.add_argument("--id", required=True)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--checked", action="store_true",
                   help="confirm you have read every slide of a generated run")
    p.set_defaults(func=cmd_publish)

    a = sub.add_parser("auto", help="build + QA + publish the next topic")
    a.add_argument("--dry-run", action="store_true")
    a.add_argument("--checked", action="store_true",
                   help="confirm you have read every slide of a generated run")
    a.set_defaults(func=cmd_auto)

    d = sub.add_parser("discover", help="propose new topics, skipping repeats")
    d.add_argument("--count", type=int, default=3)
    d.add_argument("--generate", action="store_true",
                   help="draft the Arabic with Gemini instead of TODO skeletons")
    d.set_defaults(func=cmd_discover)

    ap_ = sub.add_parser("approve", help="move a reviewed draft into the bank")
    ap_.add_argument("--id", required=True)
    ap_.set_defaults(func=cmd_approve)

    sc = sub.add_parser("schedule", help="queue a build, or show the queue")
    sc.add_argument("--id", help="run id to schedule")
    sc.add_argument("--at", help='when, KSA time: "2026-09-20 21:00"')
    sc.add_argument("--checked", action="store_true",
                    help="confirm you have read every slide")
    sc.add_argument("--cancel", help="run id to remove from the queue")
    sc.set_defaults(func=cmd_schedule)

    pd = sub.add_parser("publish-due",
                        help="publish everything past its slot (for cron)")
    pd.add_argument("--dry-run", action="store_true")
    pd.set_defaults(func=cmd_publish_due)

    so = sub.add_parser("sources", help="topic ideas from live feeds")
    so.add_argument("--check", action="store_true",
                    help="test every feed and report which answer")
    so.add_argument("--count", type=int, default=6)
    so.set_defaults(func=cmd_sources)

    g = sub.add_parser("go", help="everything in one: fresh topics, pick, build")
    g.add_argument("--fresh", type=int, default=6,
                   help="how many new topics to look for (default 6)")
    g.add_argument("--generate", action="store_true",
                   help="draft new topics with Gemini instead of a skeleton")
    g.add_argument("--news", type=int, default=3,
                   help="how many news stories to offer (default 3)")
    g.add_argument("--no-news", action="store_true",
                   help="skip the live feeds, use the backlog only")
    g.set_defaults(func=cmd_go)

    n = sub.add_parser("new", help="guided build — pick topic, design, images")
    n.set_defaults(func=cmd_new)

    s = sub.add_parser("status", help="queue and quota")
    s.set_defaults(func=cmd_status)

    args = ap.parse_args()
    from src import publish                            # noqa: E402
    from src.render import FontsMissing                # noqa: E402
    from src.discover import DiscoveryError            # noqa: E402
    from src.generate import GenerationError           # noqa: E402
    from src.schedule import ScheduleError             # noqa: E402

    try:
        args.func(args)
    except DiscoveryError as exc:
        raise SystemExit(f"\ndiscovery error: {exc}")
    except GenerationError as exc:
        raise SystemExit(f"\ngeneration error: {exc}")
    except ScheduleError as exc:
        raise SystemExit(f"\nschedule error: {exc}")
    except FontsMissing as exc:
        raise SystemExit(f"\nfont error: {exc}")
    except publish.PublishError as exc:
        raise SystemExit(f"publish error: {exc}")
    except KeyboardInterrupt:
        raise SystemExit("\nCancelled.")


if __name__ == "__main__":
    main()
