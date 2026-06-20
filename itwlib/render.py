"""Pure Rich renderers — no network.

Avatars render as colored half-block pixel art (rich-pixels): every glyph is a real
text cell, so the result composes cleanly inside Rich panels / tables / alignment and
renders identically across every terminal and when piped. This is deliberately *not*
a terminal graphics protocol (kitty / iTerm2): those paint at the cursor and ignore a
surrounding panel's interior offset, so an inline-image avatar overflows and corrupts
the bordered share card. Half-block is the guaranteed-correct, on-brand baseline.
"""
from __future__ import annotations

import io

from rich.text import Text


def bar(value: float, vmax: float, width: int = 22, color: str = "green") -> Text:
    filled = 0 if vmax <= 0 else round(width * value / vmax)
    filled = max(0, min(width, filled))
    t = Text()
    t.append("█" * filled, style=color)
    t.append("░" * (width - filled), style="bright_black")
    return t


def pixel_art(img_bytes: bytes, cols: int = 38, colors: int = 32):
    """Render PNG bytes as terminal pixel art (2 px per text row, half-block).

    Uses the locked quantize recipe from the avatar pipeline: NEAREST downscale +
    FASTOCTREE color-quantize, no dither. This gives hard, chunky pixel-art edges and
    a flat cohesive palette — smoother filters (LANCZOS) read blurry at this size.
    rich-pixels half-block keeps pixels square and composes into panels / table cells.
    """
    from PIL import Image
    from rich_pixels import Pixels

    img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    h = max(2, round(img.height * (cols / img.width)))
    h -= h % 2  # even height -> clean half-block rows
    img = img.resize((cols, h), Image.NEAREST)
    img = img.quantize(colors=colors, method=Image.FASTOCTREE,
                       dither=Image.Dither.NONE).convert("RGB")
    return Pixels.from_image(img)


def render_avatar(img_bytes: bytes, cols: int = 38):
    """Render an avatar for embedding in the card / inline output. Half-block pixel
    art — composable and terminal-agnostic. Kept as the single entry point so callers
    don't depend on the rendering strategy."""
    return pixel_art(img_bytes, cols=cols)
