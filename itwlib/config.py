"""Shared constants, the Rich console, color maps, and the avatar cache dir.
Imported by every module."""
from __future__ import annotations

import os
import shutil
from pathlib import Path

from rich.console import Console

BASE = "https://intheweights.com"
USER_AGENT = "itw-cli"

# honor COLUMNS / ITW_WIDTH; sane fallback when piped (Rich would otherwise use 80)
_W = int(os.environ.get("ITW_WIDTH") or shutil.get_terminal_size((110, 40)).columns)
console = Console(width=max(_W, 90))

# category -> color
CAT_COLOR = {
    "music": "magenta",
    "writing": "cyan",
    "film-tv": "bright_blue",
    "politics": "red",
    "arts": "bright_magenta",
    "sports": "green",
    "science": "yellow",
}

# displayTier -> color, for inspect view
TIER_COLOR = {"frontier": "bright_green", "good": "cyan", "noisy": "bright_black"}

# avatars are deterministic from the slug; only popular names have one (else 404)
AVATAR_FMT = "https://storage.googleapis.com/intheweights-avatars/avatars/{slug}/v1.png"


def cat_style(cat: str | None) -> str:
    return CAT_COLOR.get(cat or "", "white")


def cache_dir() -> Path:
    """Platform cache dir for avatar bytes. Honors ITW_CACHE_DIR / XDG_CACHE_HOME.
    Re-renders are instant and offline-friendly once an avatar is cached."""
    override = os.environ.get("ITW_CACHE_DIR")
    if override:
        base = Path(override)
    else:
        xdg = os.environ.get("XDG_CACHE_HOME")
        base = Path(xdg) if xdg else Path.home() / ".cache"
    return base / "itw" / "avatars"
