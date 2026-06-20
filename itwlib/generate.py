"""Optional self-service avatar generation: turn a name into a pixel avatar with an
image model (via OpenRouter) using your OWN API key, save it locally, and let the
normal render path quantize it. This is the only part of the CLI that needs a key and
costs money (~$0.04/image); everything else is free and key-less.

Stdlib HTTP only (urllib) — no extra dependency. Locked recipe lives in render.py
(NEAREST + FASTOCTREE at render time); here we just fetch and store a 256px source.
"""
from __future__ import annotations

import base64
import io
import json
import urllib.error
import urllib.request

from PIL import Image

from itwlib.api import slugify
from itwlib.config import generated_dir, USER_AGENT

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "google/gemini-2.5-flash-image"  # value winner (~$0.04); see the design doc

# Prompt v1.1-lean — concise beat verbose in testing; the shoulders clause stops the
# bottom edge from clipping.
PROMPT = (
    "256x256 pixel-art avatar of {SUBJECT}, social media profile picture. "
    "Chunky retro pixel art, flat colors, hard blocky edges, no anti-aliasing. "
    "Accurate, recognizable face. Plain top, no logos or text. "
    "Head and shoulders fully in frame, shoulders not cropped, with a little space "
    "below the shoulders. Centered, small headroom, solid background."
)


class GenerateError(Exception):
    """Raised when generation fails (no key, network error, no image in response)."""


def _extract_image(data: dict) -> bytes | None:
    msg = (data.get("choices") or [{}])[0].get("message") or {}
    images = msg.get("images") or []
    if not images:
        return None
    url = images[0].get("image_url", {}).get("url", "")
    if "," not in url:
        return None
    return base64.b64decode(url.split(",", 1)[1])


def generate_avatar(name: str, api_key: str, model: str = MODEL):
    """Generate + store a pixel avatar for `name`. Returns (path, cost_usd).
    Saves a 256px PNG under the user's generated-avatar dir, which the render path
    prefers over the bundled set. Raises GenerateError on failure."""
    slug = slugify(name).rstrip(".")
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": PROMPT.format(SUBJECT=name)}],
        "modalities": ["image", "text"],
    }).encode()
    req = urllib.request.Request(
        OPENROUTER_URL, data=body, method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
            "X-Title": "itw-cli",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            data = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raise GenerateError(f"OpenRouter HTTP {e.code} — check your key / credit") from e
    except Exception as e:  # noqa: BLE001
        raise GenerateError(f"request failed: {e}") from e

    raw = _extract_image(data)
    if not raw:
        raise GenerateError("no image in the model response")

    dest = generated_dir() / f"{slug}.png"
    dest.parent.mkdir(parents=True, exist_ok=True)
    Image.open(io.BytesIO(raw)).convert("RGB").resize((256, 256), Image.LANCZOS).save(dest)
    cost = float((data.get("usage") or {}).get("cost", 0) or 0)
    return dest, cost
