"""Pure-logic regression tests — no network. The slugify/bar/pixel cases are carried
from the seed; strength/top_pct/brand_color guard the reverse-engineered formulas."""
from __future__ import annotations

import io

import pytest
from PIL import Image

from itwlib.api import slugify, avatar_url
from itwlib.render import bar, pixel_art
from itwlib import card as cardlib


# --- slugify ---------------------------------------------------------------
@pytest.mark.parametrize("name,expected", [
    ("Paul McCartney", "paul-mccartney"),
    ("  Albert Einstein  ", "albert-einstein"),
    ("ALL CAPS", "all-caps"),
    ("single", "single"),
])
def test_slugify(name, expected):
    assert slugify(name) == expected


def test_avatar_url_uses_slug():
    url = avatar_url("paul-mccartney")
    assert url.endswith("/avatars/paul-mccartney/v1.png")
    assert url.startswith("https://storage.googleapis.com/")


# --- bar() fill math -------------------------------------------------------
def test_bar_full_and_empty():
    assert bar(100, 100, width=10).plain == "█" * 10
    assert bar(0, 100, width=10).plain == "░" * 10


def test_bar_half():
    assert bar(50, 100, width=10).plain == "█" * 5 + "░" * 5


def test_bar_clamps_overflow():
    over = bar(200, 100, width=8)
    assert len(over.plain) == 8
    assert over.plain == "█" * 8


def test_bar_zero_max_safe():
    assert bar(5, 0, width=6).plain == "░" * 6


# --- pixel_art row/col geometry -------------------------------------------
def _png_bytes(w, h, color=(10, 20, 30)):
    buf = io.BytesIO()
    Image.new("RGB", (w, h), color).save(buf, format="PNG")
    return buf.getvalue()


def _render_text(renderable, width):
    from rich.console import Console
    c = Console(width=width, record=True)
    c.print(renderable)
    return c.export_text()


def test_pixel_art_line_count_is_half_the_even_rows():
    cols = 20
    art = pixel_art(_png_bytes(64, 64), cols=cols)
    txt = _render_text(art, width=cols)
    lines = [ln for ln in txt.split("\n") if ln.strip()]
    assert len(lines) == cols // 2  # square -> rows==cols, 2px/line -> cols/2


def test_pixel_art_uses_half_block_glyph():
    txt = _render_text(pixel_art(_png_bytes(32, 32), cols=8), width=8)
    assert "▄" in txt


# --- strength() (bundle kr()) ----------------------------------------------
def test_strength_known_value():
    # 2 ok models, recognition 100 each, confidence>0 -> mean=100, coverage=2
    # round(100/100*800 + (200/2)*2) = 800 + 200 = 1000
    ref = {"cells": {
        "a": {"status": "ok", "recognitionScore": 100, "confidence": 50},
        "b": {"status": "ok", "recognitionScore": 100, "confidence": 50},
    }}
    models = [{"id": "a"}, {"id": "b"}]
    assert cardlib.strength(ref, models) == 1000


def test_strength_no_models_is_zero():
    assert cardlib.strength({"cells": {}}, []) == 0


def test_strength_skips_non_ok_and_zero_confidence():
    # one ok cell w/ confidence 0 (no coverage bonus), one errored cell
    ref = {"cells": {
        "a": {"status": "ok", "recognitionScore": 50, "confidence": 0},
        "b": {"status": "error", "recognitionScore": 99, "confidence": 99},
    }}
    models = [{"id": "a"}, {"id": "b"}]
    # mean = (50+0)/2 = 25, coverage = 0 -> round(25/100*800) = 200
    assert cardlib.strength(ref, models) == 200


# --- top_pct() (bundle pt()) -----------------------------------------------
@pytest.mark.parametrize("rank,total,expected", [
    (1, 100, "Top 1%"),
    (50, 100, "Top 50%"),
    (100, 100, "Top 95%"),   # capped at 95
    (1, 0, None),            # total 0 -> None
    (5, None, None),
])
def test_top_pct(rank, total, expected):
    assert cardlib.top_pct(rank, total) == expected


# --- brand_color() (bundle Gn map + Tr() hashed fallback) ------------------
def test_brand_color_mapped_id():
    assert cardlib.brand_color("openai/gpt-5.5") == "#f2f2f2"


def test_brand_color_hashed_fallback():
    mid = "anthropic/claude-haiku-4.5"  # in the roster but not in BRAND_COLORS
    assert mid not in cardlib.BRAND_COLORS
    # recompute the bundle's Tr(): t=(t*31+ord(ch))%360, then hsl(t,72%,48%)
    t = 0
    for ch in mid:
        t = (t * 31 + ord(ch)) % 360
    assert cardlib.brand_color(mid) == cardlib._hsl_to_hex(t, 0.72, 0.48)


def test_brand_color_is_valid_hex():
    c = cardlib.brand_color("totally/unknown-model")
    assert len(c) == 7 and c[0] == "#"
    int(c[1:], 16)  # parses as hex


# --- bar_fill_pct() (bundle Rr()) ------------------------------------------
@pytest.mark.parametrize("conf,expected", [
    (0, 0), (4, 0), (5, 0), (6, 10), (44, 40), (95, 100), (200, 100), (None, 0),
])
def test_bar_fill_pct(conf, expected):
    assert cardlib.bar_fill_pct(conf) == expected
