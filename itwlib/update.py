"""Self-update: check the latest GitHub Release and upgrade in place.

The CLI ships from git (`uv tool install git+…`), not PyPI, so there's no package
index to poll — we read the repo's latest GitHub Release and compare its tag to the
running version. Stdlib `urllib` only (no extra dependency), mirroring generate.py.
The actual upgrade shells out to whichever tool manages the install (uv / pipx).
"""
from __future__ import annotations

import json
import shutil
import urllib.error
import urllib.request
from typing import NamedTuple

from itwlib.config import USER_AGENT

REPO = "mattsilv/itw-cli"
RELEASES_API = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_URL = f"https://github.com/{REPO}/releases"


class UpdateError(Exception):
    """Raised when an update step fails in a way worth surfacing."""


class Release(NamedTuple):
    tag: str       # e.g. "v0.2.0"
    url: str       # html_url of the release page


def _parse(v: str) -> tuple[int, ...]:
    """Numeric version tuple from a `vX.Y.Z` / `X.Y.Z` string for a correct compare
    (`0.10.0 > 0.9.0`, which a string compare gets wrong). Non-numeric trailing parts
    like `+local` are ignored; missing/garbage yields `(0,)`."""
    core = v.strip().lstrip("vV").split("+", 1)[0].split("-", 1)[0]
    out = []
    for part in core.split("."):
        if part.isdigit():
            out.append(int(part))
        else:
            break
    return tuple(out) or (0,)


def latest_release(timeout: int = 10) -> Release | None:
    """Latest GitHub Release for the repo, or None if there are no releases yet or
    GitHub is unreachable (offline / rate-limited) — callers treat None as 'can't
    tell', never an error."""
    req = urllib.request.Request(
        RELEASES_API,
        headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 404:  # repo exists but has cut no releases yet
            return None
        return None
    except Exception:  # URLError, SSL, timeout, JSON — all 'can't tell'
        return None
    tag = data.get("tag_name")
    if not tag:
        return None
    return Release(tag=tag, url=data.get("html_url") or RELEASES_URL)


def is_newer(latest: str, current: str) -> bool:
    """True when release tag `latest` is a newer version than `current`."""
    return _parse(latest) > _parse(current)


def upgrade_cmd() -> list[str] | None:
    """The argv to upgrade this tool, picking the manager that's on PATH (uv preferred,
    then pipx). None when neither is found — the caller shows a manual command."""
    if shutil.which("uv"):
        return ["uv", "tool", "upgrade", "itw-cli"]
    if shutil.which("pipx"):
        return ["pipx", "upgrade", "itw-cli"]
    return None


MANUAL_CMD = f"uv tool install --force git+https://github.com/{REPO}"
