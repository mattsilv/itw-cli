"""Stdlib HTTP client (no requests/httpx) + slug/avatar helpers + on-disk avatar
cache. Retries transient network errors; HTTPError is a real server response and is
not retried."""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from itwlib.config import BASE, USER_AGENT, console, AVATAR_FMT, cache_dir

# Pixel avatars we generated ourselves (image model + quantize), bundled with the
# package so the long tail of names the site doesn't host still gets an avatar —
# offline, no API key, no per-image cost for end users.
_BUNDLED_AVATARS = Path(__file__).parent / "avatars"

_RETRIES = 3  # transient SSL EOF / connection resets are common; retry with backoff


def _open(req, timeout):
    """urlopen with retries on transient network errors. HTTPError is NOT retried
    (it's a real server response) and is re-raised for the caller to handle."""
    last = None
    for attempt in range(_RETRIES):
        try:
            return urllib.request.urlopen(req, timeout=timeout)
        except urllib.error.HTTPError:
            raise
        except Exception as e:  # URLError, ssl.SSLError, socket timeout, ...
            last = e
            if attempt < _RETRIES - 1:
                time.sleep(0.4 * (attempt + 1))
    raise last


def get(path: str):
    url = f"{BASE}{path}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with _open(req, timeout=15) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        console.print(f"[red]HTTP {e.code}[/] for {path}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]request failed after {_RETRIES} tries:[/] {e}\n"
                      f"[dim]intheweights.com may be rate-limiting or briefly down — retry shortly.[/]")
        sys.exit(1)


def slugify(name: str) -> str:
    return name.strip().lower().replace(" ", "-")


def avatar_url(slug: str) -> str:
    return AVATAR_FMT.format(slug=slug)


def local_avatar(slug: str) -> bytes | None:
    """Bytes of our own bundled pixel avatar for `slug`, or None if we don't ship
    one. Preferred over the hosted avatar so generated art wins where it exists.
    Trailing dots are stripped so names like "Martin Luther King Jr." resolve."""
    p = _BUNDLED_AVATARS / f"{slug.rstrip('.')}.png"
    try:
        return p.read_bytes()
    except OSError:
        return None


def avatar_exists(url: str) -> bool:
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": USER_AGENT})
    try:
        with _open(req, timeout=10) as r:
            return r.status == 200
    except Exception:
        return False


def _cache_path(slug: str):
    return cache_dir() / f"{slug}.png"


def fetch_bytes(url: str, slug: str | None = None) -> bytes | None:
    """Fetch avatar PNG bytes. When `slug` is given, an on-disk cache is consulted
    first (instant, offline-friendly re-renders) and populated on a successful miss.
    Returns None on 404 / transient failure so callers can show a graceful message."""
    cache_file = _cache_path(slug) if slug else None
    if cache_file and cache_file.exists():
        try:
            return cache_file.read_bytes()
        except OSError:
            pass  # unreadable cache -> fall through to network

    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with _open(req, timeout=15) as r:
            data = r.read()
    except Exception:
        return None

    if cache_file and data:
        try:
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_file.write_bytes(data)
        except OSError:
            pass  # cache is best-effort; never fail a render over it
    return data
