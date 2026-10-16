#!/usr/bin/env python3
"""Refresh the "Lately on Instagram" strip on the homepage.

Reads the Behold JSON feed (BEHOLD_FEED_URL), keeps a rolling archive of the
newest posts in data/instagram.json, downloads each thumbnail into
site/images/instagram/, and rewrites the strip in site/index.html between the
<!-- instagram:start --> and <!-- instagram:end --> markers.

The free Behold plan only returns the newest 6 posts; the archive is what lets
the page show 10. Standard library only, so it runs on a bare Actions runner.
If the feed can't be fetched, nothing changes and the site deploys as-is.
"""
from __future__ import annotations

import html
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

MAX_POSTS = 10
PROFILE_URL = "https://www.instagram.com/pfibiger/"
HANDLE = "@pfibiger"

ROOT = Path(__file__).resolve().parent.parent
ARCHIVE = ROOT / "data" / "instagram.json"
IMG_DIR = ROOT / "site" / "images" / "instagram"
INDEX = ROOT / "site" / "index.html"
MARKERS = re.compile(r"(<!-- instagram:start -->)(.*?)(<!-- instagram:end -->)", re.S)


def warn(msg: str) -> None:
    # Shows up as an annotation on the Actions run.
    print(f"::warning::{msg}")


def parse_ts(value: str) -> datetime:
    value = value.strip().replace("Z", "+00:00")
    # Accept +0000 as well as +00:00
    value = re.sub(r"([+-]\d{2})(\d{2})$", r"\1:\2", value)
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "fibiger.org-build"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def make_alt(post: dict) -> str:
    text = post.get("altText") or post.get("prunedCaption") or post.get("caption") or ""
    text = " ".join(text.split())
    if len(text) > 140:
        text = text[:140].rsplit(" ", 1)[0].rstrip(",.;:—-") + "…"
    return text or "Instagram post"


def update_archive(archive: list[dict], feed: dict) -> list[dict]:
    posts = [p for p in feed.get("posts", []) if p.get("id") and p.get("permalink")]
    if not posts:
        warn("Behold feed returned no posts; leaving the strip unchanged.")
        return archive

    by_id = {item["id"]: item for item in archive}
    IMG_DIR.mkdir(parents=True, exist_ok=True)

    for post in posts:
        size = (post.get("sizes") or {}).get("small") or {}
        url = size.get("mediaUrl")
        if not url:
            continue
        suffix = Path(url.split("?")[0]).suffix.lower()
        ext = suffix if suffix in {".webp", ".jpg", ".jpeg", ".png"} else ".webp"
        filename = f"{post['id']}{ext}"
        if not (IMG_DIR / filename).exists():
            try:
                (IMG_DIR / filename).write_bytes(fetch(url))
            except Exception as exc:  # keep going; a missing image just skips that post
                warn(f"Could not download image for {post['permalink']}: {exc}")
                continue
        by_id[post["id"]] = {
            "id": post["id"],
            "timestamp": post.get("timestamp", ""),
            "permalink": post["permalink"],
            "file": filename,
            "width": size.get("width"),
            "height": size.get("height"),
            "alt": make_alt(post),
        }

    # A post that falls inside the feed's window but isn't in it was deleted or
    # archived on Instagram, so drop it here too.
    feed_ids = {p["id"] for p in posts}
    oldest_in_feed = min(parse_ts(p.get("timestamp", "")) for p in posts)
    for post_id, item in list(by_id.items()):
        if post_id not in feed_ids and parse_ts(item["timestamp"]) >= oldest_in_feed:
            del by_id[post_id]

    newest = sorted(by_id.values(), key=lambda i: parse_ts(i["timestamp"]), reverse=True)
    return newest[:MAX_POSTS]


def prune_images(archive: list[dict]) -> None:
    keep = {item["file"] for item in archive}
    if IMG_DIR.exists():
        for path in IMG_DIR.iterdir():
            if path.is_file() and path.name not in keep:
                path.unlink()


def render(archive: list[dict]) -> str:
    esc = lambda s: html.escape(str(s), quote=True)
    lines = [
        '',
        '  <section id="instagram" class="insta" aria-labelledby="insta-heading">',
        '    <div class="insta-head">',
        '      <h2 id="insta-heading">Lately on Instagram</h2>',
        f'      <a href="{PROFILE_URL}">Follow {HANDLE} →</a>',
        '    </div>',
    ]
    if archive:
        lines.append('    <ul class="insta-grid">')
        for item in archive:
            dims = ""
            if item.get("width") and item.get("height"):
                dims = f' width="{int(item["width"])}" height="{int(item["height"])}"'
            lines.append(
                f'      <li><a href="{esc(item["permalink"])}">'
                f'<img src="images/instagram/{esc(item["file"])}" alt="{esc(item["alt"])}"{dims} '
                f'loading="lazy" decoding="async"></a></li>'
            )
        lines.append('    </ul>')
    lines += ['  </section>', '  ']
    return "\n".join(lines)


def main() -> int:
    archive: list[dict] = json.loads(ARCHIVE.read_text()) if ARCHIVE.exists() else []

    feed_url = os.environ.get("BEHOLD_FEED_URL", "").strip()
    if not feed_url:
        warn("BEHOLD_FEED_URL is not set; rendering the strip from the saved archive.")
    else:
        try:
            feed = json.loads(fetch(feed_url))
        except Exception as exc:
            warn(f"Could not fetch the Behold feed ({exc}); leaving the strip unchanged.")
        else:
            archive = update_archive(archive, feed)
            prune_images(archive)

    ARCHIVE.parent.mkdir(parents=True, exist_ok=True)
    ARCHIVE.write_text(json.dumps(archive, indent=2, ensure_ascii=False) + "\n")

    page = INDEX.read_text()
    if not MARKERS.search(page):
        print("::error::Instagram markers not found in site/index.html")
        return 1
    new_page = MARKERS.sub(lambda m: m.group(1) + render(archive) + m.group(3), page, count=1)
    if new_page != page:
        INDEX.write_text(new_page)
    print(f"Instagram strip: {len(archive)} post(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
