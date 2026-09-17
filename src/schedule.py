"""
The publish queue.

A built carousel is not posted immediately. It is reviewed, then given a slot,
then published when that slot arrives. This module owns the queue file that
holds those slots, so `schedule --list` can show what goes out when.

Times are stored in UTC and displayed in both KSA and Malaysia, because the
audience is in one and you are in the other — 21:00 KSA is 02:00 the next day
in Kuala Lumpur, and that difference has bitten this project before.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "content" / "schedule.json"
SETTINGS = ROOT / "config" / "settings.yaml"
OUT = ROOT / "out"

KSA = timezone(timedelta(hours=3))
MYT = timezone(timedelta(hours=8))

DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday",
        "sunday"]


class ScheduleError(RuntimeError):
    pass


# ------------------------------------------------------------------- store
def load() -> list[dict]:
    if not QUEUE.exists():
        return []
    try:
        return json.loads(QUEUE.read_text(encoding="utf-8")).get("queue", [])
    except json.JSONDecodeError:
        return []


def save(queue: list[dict]) -> None:
    queue = sorted(queue, key=lambda e: e["at"])
    QUEUE.parent.mkdir(parents=True, exist_ok=True)
    QUEUE.write_text(json.dumps({"queue": queue}, ensure_ascii=False, indent=2),
                     encoding="utf-8")


def _settings() -> dict:
    if not SETTINGS.exists():
        return {}
    return (yaml.safe_load(SETTINGS.read_text(encoding="utf-8")) or {})


# -------------------------------------------------------------------- time
def parse_when(raw: str) -> datetime:
    """
    Accept '2026-09-20', '2026-09-20 21:00' or a full ISO string.

    A bare date or a date+time is read as KSA local, not UTC — the schedule is
    built around when the audience is awake, so that is the timezone you are
    thinking in when you type it.
    """
    raw = raw.strip()
    for fmt, tz in (("%Y-%m-%d %H:%M", KSA), ("%Y-%m-%dT%H:%M", KSA),
                    ("%Y-%m-%d", KSA)):
        try:
            d = datetime.strptime(raw, fmt)
            if fmt == "%Y-%m-%d":
                hour = int(_settings().get("schedule", {}).get("utc_hour", 18))
                d = d.replace(hour=hour, minute=0) + timedelta(hours=3)
            return d.replace(tzinfo=tz).astimezone(timezone.utc)
        except ValueError:
            continue
    try:
        d = datetime.fromisoformat(raw)
        return (d if d.tzinfo else d.replace(tzinfo=KSA)).astimezone(
            timezone.utc)
    except ValueError as exc:
        raise ScheduleError(
            f"Could not read '{raw}' as a date. Use 2026-09-20 or "
            f"'2026-09-20 21:00' (KSA time).") from exc


def next_slot(queue: list[dict]) -> datetime:
    """The next configured posting slot that is free and still in the future."""
    cfg = _settings().get("schedule", {})
    days = [d.lower() for d in cfg.get("days", ["sunday", "tuesday", "thursday"])]
    hour = int(cfg.get("utc_hour", 18))
    taken = {e["at"][:16] for e in queue if e.get("status") == "pending"}

    now = datetime.now(timezone.utc)
    probe = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    for _ in range(90):
        if (probe > now + timedelta(minutes=5)
                and DAYS[probe.weekday()] in days
                and probe.isoformat()[:16] not in taken):
            return probe
        probe += timedelta(days=1)
    raise ScheduleError("No free slot found in the next 90 days.")


def fmt(dt_utc: str) -> tuple[str, str]:
    d = datetime.fromisoformat(dt_utc)
    return (d.astimezone(KSA).strftime("%a %d %b  %H:%M"),
            d.astimezone(MYT).strftime("%H:%M"))


# ------------------------------------------------------------------ queue
def add(run_id: str, when: datetime, topic: str = "") -> dict:
    queue = load()
    if any(e["run_id"] == run_id and e["status"] == "pending" for e in queue):
        raise ScheduleError(f"'{run_id}' is already scheduled. "
                            f"Cancel it first, or use a different build.")
    if not (OUT / run_id).exists():
        raise ScheduleError(f"No build at out/{run_id}")

    entry = {"run_id": run_id, "topic": topic,
             "at": when.astimezone(timezone.utc).isoformat(timespec="minutes"),
             "status": "pending", "media_id": None}
    queue.append(entry)
    save(queue)
    return entry


def cancel(run_id: str) -> None:
    queue = load()
    kept = [e for e in queue
            if not (e["run_id"] == run_id and e["status"] == "pending")]
    if len(kept) == len(queue):
        raise ScheduleError(f"Nothing pending for '{run_id}'.")
    save(kept)


def mark(run_id: str, status: str, media_id: str | None = None) -> None:
    queue = load()
    for e in queue:
        if e["run_id"] == run_id and e["status"] == "pending":
            e["status"] = status
            e["media_id"] = media_id
            e["done_at"] = datetime.now(timezone.utc).isoformat(
                timespec="minutes")
            break
    save(queue)


def due(now: datetime | None = None) -> list[dict]:
    now = now or datetime.now(timezone.utc)
    return [e for e in load()
            if e["status"] == "pending"
            and datetime.fromisoformat(e["at"]) <= now]
