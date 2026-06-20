"""Avatar rendering: half-block geometry + clean composition inside a bordered Panel
(the share card). No terminal graphics protocol is used, so there is nothing to
detect — the same renderable works everywhere and when piped."""
from __future__ import annotations

import io

from PIL import Image

from itwlib import render


def _png_bytes(w, h, color=(10, 20, 30)):
    buf = io.BytesIO()
    Image.new("RGB", (w, h), color).save(buf, format="PNG")
    return buf.getvalue()


def _render_text(renderable, width):
    from rich.console import Console
    c = Console(width=width, record=True)
    c.print(renderable)
    return c.export_text()


def test_render_avatar_geometry_matches_pixel_art():
    """A square PNG at cols=N yields N/2 non-blank lines (2 px per half-block row)."""
    cols = 20
    art = render.render_avatar(_png_bytes(64, 64), cols=cols)
    lines = [ln for ln in _render_text(art, width=cols).split("\n") if ln.strip()]
    assert len(lines) == cols // 2


def test_render_avatar_uses_half_block_glyph():
    txt = _render_text(render.render_avatar(_png_bytes(32, 32), cols=8), width=8)
    assert "▄" in txt


def test_render_avatar_composes_in_a_bordered_panel():
    """Regression: the avatar must sit *inside* a Panel without breaking its border
    (a terminal graphics-protocol image would overflow and corrupt the card)."""
    from rich.align import Align
    from rich.panel import Panel

    avatar = Align.center(render.render_avatar(_png_bytes(64, 64), cols=34))
    txt = _render_text(Panel(avatar, width=48), width=48)
    lines = txt.split("\n")
    # every non-empty rendered line stays within the panel's width (border intact)
    assert "╭" in txt and "╰" in txt
    for ln in lines:
        if ln.strip():
            assert ln.lstrip().startswith("│") or ln.lstrip().startswith("╭") \
                or ln.lstrip().startswith("╰")
