"""
Instagram carousel publishing via the Graph API.

Flow (3 stages, per Meta's content publishing docs):
  1. POST /{ig-user-id}/media  ... once per slide, with is_carousel_item=true
  2. POST /{ig-user-id}/media  ... once, media_type=CAROUSEL, children=[ids]
  3. POST /{ig-user-id}/media_publish  ... with the carousel container id

Images must be reachable at a public https URL — Instagram fetches them
itself, you cannot upload bytes.
"""
from __future__ import annotations

import os
import time
from pathlib import Path

import requests

GRAPH = "https://graph.facebook.com/v21.0"
POLL_INTERVAL = 3
POLL_MAX = 40


class PublishError(RuntimeError):
    pass


def _cfg() -> tuple[str, str]:
    token = os.environ.get("IG_ACCESS_TOKEN", "").strip()
    user = os.environ.get("IG_USER_ID", "").strip()
    if not token or not user:
        raise PublishError(
            "IG_ACCESS_TOKEN and IG_USER_ID must be set (see .env.example).")
    return token, user


def _post(path: str, params: dict) -> dict:
    r = requests.post(f"{GRAPH}/{path}", data=params, timeout=60)
    if not r.ok:
        raise PublishError(f"POST {path} failed {r.status_code}: {r.text}")
    return r.json()


def _get(path: str, params: dict) -> dict:
    r = requests.get(f"{GRAPH}/{path}", params=params, timeout=60)
    if not r.ok:
        raise PublishError(f"GET {path} failed {r.status_code}: {r.text}")
    return r.json()


def rate_limit_usage() -> dict:
    """How many API posts have been published in the rolling 24h window."""
    token, user = _cfg()
    return _get(f"{user}/content_publishing_limit",
                {"access_token": token, "fields": "config,quota_usage"})


def _wait_ready(container_id: str, token: str) -> None:
    for _ in range(POLL_MAX):
        data = _get(container_id, {"access_token": token,
                                   "fields": "status_code,status"})
        code = data.get("status_code")
        if code == "FINISHED":
            return
        if code == "ERROR":
            raise PublishError(f"Container {container_id} errored: {data}")
        time.sleep(POLL_INTERVAL)
    raise PublishError(f"Container {container_id} not ready after "
                       f"{POLL_MAX * POLL_INTERVAL}s")


def create_item(image_url: str) -> str:
    token, user = _cfg()
    res = _post(f"{user}/media", {
        "image_url": image_url,
        "is_carousel_item": "true",
        "access_token": token,
    })
    return res["id"]


def create_carousel(children: list[str], caption: str) -> str:
    token, user = _cfg()
    res = _post(f"{user}/media", {
        "media_type": "CAROUSEL",
        "children": ",".join(children),
        "caption": caption,
        "access_token": token,
    })
    return res["id"]


def publish_container(container_id: str) -> str:
    token, user = _cfg()
    res = _post(f"{user}/media_publish", {
        "creation_id": container_id,
        "access_token": token,
    })
    return res["id"]


def publish_carousel(image_urls: list[str], caption: str,
                     dry_run: bool = False) -> dict:
    """Full publish. Returns {'media_id', 'container_id', 'children'}."""
    if not 2 <= len(image_urls) <= 10:
        raise PublishError(f"Carousel needs 2–10 images, got {len(image_urls)}")

    if dry_run:
        return {"dry_run": True, "images": image_urls,
                "caption_preview": caption[:120]}

    token, _ = _cfg()

    children = []
    for url in image_urls:
        cid = create_item(url)
        _wait_ready(cid, token)
        children.append(cid)

    carousel_id = create_carousel(children, caption)
    _wait_ready(carousel_id, token)
    media_id = publish_container(carousel_id)

    return {"media_id": media_id, "container_id": carousel_id,
            "children": children}


def public_urls(out_dir: Path, run_id: str, dry_run: bool = False) -> list[str]:
    """
    Build the public URLs Instagram will fetch.
    IMAGE_BASE_URL should point at the repo/bucket that serves out/, e.g.
      https://raw.githubusercontent.com/<user>/<repo>/main/out
    """
    base = os.environ.get("IMAGE_BASE_URL", "").rstrip("/")
    if not base:
        if dry_run:
            print("  ! IMAGE_BASE_URL not set — using a placeholder for the "
                  "dry run. A real publish will fail until it is configured.")
            base = "https://IMAGE_BASE_URL_NOT_SET/out"
        else:
            raise PublishError("IMAGE_BASE_URL is not set — Instagram must "
                               "fetch images from a public URL.")
    pngs = sorted(Path(out_dir).glob("*.png"))
    return [f"{base}/{run_id}/{p.name}" for p in pngs]


def check_reachable(urls: list[str]) -> None:
    """
    Confirm the images are actually served before asking Instagram for them.

    A build that has not been pushed yet 404s, and Instagram reports that as
    "Only photo or video can be accepted as media type" — which says nothing
    about the real cause. One HEAD request turns that into a clear message.
    """
    if not urls:
        raise PublishError("No images to publish.")

    url = urls[0]
    try:
        r = requests.head(url, timeout=15, allow_redirects=True)
        if r.status_code == 405:                      # HEAD not allowed
            r = requests.get(url, timeout=20, stream=True)
    except requests.RequestException as exc:
        raise PublishError(
            f"Could not reach {url}\n  {exc}\n"
            f"  Instagram fetches images over the internet — if you cannot "
            f"reach this, neither can it.") from exc

    if r.status_code == 404:
        raise PublishError(
            f"{url}\n  returns 404 — this build is not published to the "
            f"image host yet.\n"
            f"  If you are hosting on GitHub, push it first:\n"
            f"    git add -A\n"
            f"    git commit -m \"Add carousel\"\n"
            f"    git push")
    if r.status_code != 200:
        raise PublishError(
            f"{url}\n  returns HTTP {r.status_code}. Instagram needs a public "
            f"URL that answers 200.")

    ctype = (r.headers.get("Content-Type") or "").lower()
    if "image" not in ctype:
        raise PublishError(
            f"{url}\n  answers 200 but serves '{ctype}', not an image. "
            f"A GitHub *blob* URL returns HTML — use raw.githubusercontent.com.")
