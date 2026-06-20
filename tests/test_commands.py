"""Command behavior with mocked network, plus the on-disk avatar cache. No real HTTP."""
from __future__ import annotations

import io

import pytest
from PIL import Image

from itwlib import api, commands
from itwlib import card as cardlib
from itwlib.config import console


def _png(w=16, h=16, color=(1, 2, 3)):
    buf = io.BytesIO()
    Image.new("RGB", (w, h), color).save(buf, format="PNG")
    return buf.getvalue()


def _result_payload():
    models = [
        {"id": "openai/gpt-5.5", "label": "GPT-5.5", "displayTier": "frontier"},
        {"id": "x-ai/grok-4.20", "label": "Grok-4.20", "displayTier": "good"},
        {"id": "qwen/qwen3-8b", "label": "Qwen3-8B", "displayTier": "noisy"},
    ]
    cells = {
        "openai/gpt-5.5": {"status": "ok", "recognitionScore": 100, "confidence": 90,
                           "evidenceSnippets": [{"text": "top model evidence"}]},
        "x-ai/grok-4.20": {"status": "ok", "recognitionScore": 60, "confidence": 50,
                           "evidenceSnippets": [{"text": "mid evidence"}]},
        "qwen/qwen3-8b": {"status": "ok", "recognitionScore": 20, "confidence": 10,
                          "evidenceSnippets": [{"text": "low evidence"}]},
    }
    ref = {
        "canonicalName": "Paul McCartney",
        "canonicalDescriptor": "Beatles bassist",
        "category": "music",
        "cells": cells,
        "weightRank": {"rank": 1, "total": 100},
        "displaySnippet": {"modelId": "openai/gpt-5.5", "text": "english musician"},
    }
    return {"query": "paul mccartney", "models": models, "referents": [ref],
            "promptVersion": "p1", "rosterVersion": "r1",
            "clusteringModel": {"label": "kimi", "method": "grade"}}


# --- cmd_lookup (default card) ---------------------------------------------
def test_lookup_renders_one_bar_row_per_model(monkeypatch):
    payload = _result_payload()
    monkeypatch.setattr(commands, "get", lambda path: payload)
    monkeypatch.setattr(commands, "local_avatar", lambda slug: None)  # header-only
    monkeypatch.setattr(commands, "avatar_exists", lambda url: False)
    with console.capture() as cap:
        commands.cmd_lookup("paul mccartney")
    out = cap.get()
    for m in payload["models"]:
        assert m["label"].upper() in out  # one labeled row per model
    assert "P A U L   M C C A R T N E Y" in out  # spaced-uppercase name


def test_lookup_strength_line_matches_card_strength(monkeypatch):
    payload = _result_payload()
    monkeypatch.setattr(commands, "get", lambda path: payload)
    monkeypatch.setattr(commands, "avatar_exists", lambda url: False)
    expected = cardlib.strength(payload["referents"][0], payload["models"])
    with console.capture() as cap:
        commands.cmd_lookup("paul mccartney")
    assert f"{expected} STRENGTH" in cap.get()


def test_lookup_graceful_when_not_searched(monkeypatch):
    monkeypatch.setattr(commands, "get", lambda path: None)  # 404
    with console.capture() as cap:
        commands.cmd_lookup("nobody")
    assert "no result for" in cap.get() and "hasn't been searched" in cap.get()


def test_lookup_renders_card_when_no_avatar(monkeypatch):
    payload = _result_payload()
    monkeypatch.setattr(commands, "get", lambda path: payload)
    monkeypatch.setattr(commands, "avatar_exists", lambda url: False)
    with console.capture() as cap:
        commands.cmd_lookup("paul mccartney")
    assert "STRENGTH" in cap.get()  # card body still renders without an avatar


def test_lookup_default_omits_evidence_and_snippet(monkeypatch):
    """The clean default card must NOT carry the --detail content."""
    payload = _result_payload()
    monkeypatch.setattr(commands, "get", lambda path: payload)
    monkeypatch.setattr(commands, "avatar_exists", lambda url: False)
    with console.capture() as cap:
        commands.cmd_lookup("paul mccartney")  # no detail
    out = cap.get()
    assert "top model evidence" not in out
    assert "english musician" not in out  # the displaySnippet text
    assert "says" not in out.lower()


# --- cmd_lookup --detail ---------------------------------------------------
def test_lookup_detail_shows_snippet_and_sorted_evidence(monkeypatch):
    payload = _result_payload()
    monkeypatch.setattr(commands, "get", lambda path: payload)
    monkeypatch.setattr(commands, "avatar_exists", lambda url: False)
    with console.capture() as cap:
        commands.cmd_lookup("paul mccartney", detail=True)
    out = cap.get()
    # snippet present in readable (non-uppercased) form
    assert "says" in out.lower() and "english musician" in out
    # evidence rows sorted by recognitionScore desc
    assert out.index("top model evidence") < out.index("mid evidence") < out.index("low evidence")


# --- bundled (our generated) avatar precedence -----------------------------
def test_lookup_prefers_our_bundled_avatar(monkeypatch):
    """When we ship a generated avatar for a slug, the card uses it and never
    touches the hosted one."""
    payload = _result_payload()
    monkeypatch.setattr(commands, "get", lambda path: payload)
    monkeypatch.setattr(commands, "local_avatar", lambda slug: _png())

    def _no_hosted(url):
        raise AssertionError("hosted avatar must not be probed when ours exists")

    monkeypatch.setattr(commands, "avatar_exists", _no_hosted)
    with console.capture() as cap:
        commands.cmd_lookup("paul mccartney")
    assert "STRENGTH" in cap.get()  # rendered without hitting the hosted path


def test_lookup_falls_back_to_hosted_when_no_bundled(monkeypatch):
    payload = _result_payload()
    monkeypatch.setattr(commands, "get", lambda path: payload)
    monkeypatch.setattr(commands, "local_avatar", lambda slug: None)
    monkeypatch.setattr(commands, "avatar_exists", lambda url: False)  # no hosted either
    with console.capture() as cap:
        commands.cmd_lookup("paul mccartney")
    assert "STRENGTH" in cap.get()  # card still renders, just no image


@pytest.mark.parametrize("slug", ["alan-turing", "paul-mccartney", "albert-einstein",
                                  "hans-moleman", "thomas-dimson"])
def test_bundled_avatars_ship(slug):
    """Smoke test that our generated avatars are actually bundled + loadable at 256px.

    Regression guard: hans-moleman / thomas-dimson are manual ref-image avatars for
    names the hosted set lacks; if they stop resolving the card silently falls back
    to the grey hosted silhouette (the bug this locks down)."""
    from itwlib.api import local_avatar
    from PIL import Image
    import io
    data = local_avatar(slug)
    assert data and len(data) > 1000
    assert Image.open(io.BytesIO(data)).size == (256, 256)


@pytest.mark.parametrize("name", ["hans moleman", "Hans Moleman", "thomas dimson",
                                  "Thomas Dimson"])
def test_manual_avatar_resolves_from_display_name(name):
    """The card looks avatars up via _avatar_slug(name); these manual ones must
    resolve from the user-typed name (the path that regressed to a silhouette)."""
    from itwlib.api import local_avatar
    assert local_avatar(commands._avatar_slug(name)) is not None


def test_hitler_avatar_not_bundled():
    """We intentionally did not generate Adolf Hitler; the gallery shows a ✕ instead."""
    from itwlib.api import local_avatar
    assert local_avatar("adolf-hitler") is None


def test_silhouette_placeholder_bundled():
    """A generic generated silhouette ships as the card's no-avatar fallback."""
    from itwlib.api import local_avatar
    from PIL import Image
    import io
    data = local_avatar("_placeholder")
    assert data and Image.open(io.BytesIO(data)).size == (256, 256)


def test_lookup_uses_silhouette_when_no_real_avatar(monkeypatch):
    """A name with no bundled/hosted avatar still shows the silhouette, not empty space."""
    payload = _result_payload()
    monkeypatch.setattr(commands, "get", lambda path: payload)
    monkeypatch.setattr(commands, "avatar_exists", lambda url: False)
    # no avatar for the name, but the _placeholder silhouette is available
    monkeypatch.setattr(commands, "local_avatar",
                        lambda slug: _png() if slug == "_placeholder" else None)
    with console.capture() as cap:
        commands.cmd_lookup("nobody famous")
    assert "▄" in cap.get()  # an avatar (the silhouette) was rendered


# --- cmd_versus ------------------------------------------------------------
def _versus_payload(name, strong):
    """A result payload for `name` whose strength is high (strong=True) or low."""
    score = 100 if strong else 20
    conf = 90 if strong else 10
    models = [{"id": "openai/gpt-5.5", "label": "GPT-5.5"}]
    ref = {
        "canonicalName": name,
        "canonicalDescriptor": "desc",
        "cells": {"openai/gpt-5.5": {"status": "ok", "recognitionScore": score,
                                     "confidence": conf}},
        "weightRank": {"rank": 1, "total": 100},
    }
    return {"query": name.lower(), "models": models, "referents": [ref]}


def test_versus_winner_on_left(monkeypatch):
    monkeypatch.setattr(commands, "local_avatar", lambda slug: _png())
    monkeypatch.setattr(commands, "avatar_exists", lambda url: False)

    # case 1: A stronger -> A on the left (payload keyed by slug in the path)
    monkeypatch.setattr(commands, "get",
                        lambda path: _versus_payload("Alpha", True) if "alpha" in path
                        else _versus_payload("Bravo", False))
    with console.capture() as cap:
        commands.cmd_versus("Alpha", "Bravo")
    out = cap.get()
    assert "WINNER" in out
    assert out.index("ALPHA") < out.index("BRAVO")

    # case 2: B stronger -> B on the left
    monkeypatch.setattr(commands, "get",
                        lambda path: _versus_payload("Alpha", False) if "alpha" in path
                        else _versus_payload("Bravo", True))
    with console.capture() as cap:
        commands.cmd_versus("Alpha", "Bravo")
    out = cap.get()
    assert "WINNER" in out
    assert out.index("BRAVO") < out.index("ALPHA")


def test_versus_graceful_when_both_missing(monkeypatch):
    monkeypatch.setattr(commands, "get", lambda path: None)
    monkeypatch.setattr(commands, "local_avatar", lambda slug: _png())
    monkeypatch.setattr(commands, "avatar_exists", lambda url: False)
    with console.capture() as cap:
        commands.cmd_versus("nobody one", "nobody two")
    assert "neither name has been searched on the site yet" in cap.get()


def test_versus_cli_parsing(monkeypatch):
    captured = {}
    monkeypatch.setattr(commands, "cmd_versus",
                        lambda a, b: captured.update(a=a, b=b))
    from itwlib.cli import main
    assert main(["sam", "altman", "v", "hans", "moleman"]) == 0
    assert (captured["a"], captured["b"]) == ("sam altman", "hans moleman")


# --- cmd_board -------------------------------------------------------------
def test_cmd_board_orders_by_weight_with_medals(monkeypatch):
    rows = [
        {"rank": 1, "name": "Alpha", "weight": 900, "category": "music", "descriptor": "a"},
        {"rank": 2, "name": "Bravo", "weight": 500, "category": "sports", "descriptor": "b"},
        {"rank": 3, "name": "Charlie", "weight": 100, "category": "science", "descriptor": "c"},
    ]
    monkeypatch.setattr(commands, "get", lambda path: rows)
    with console.capture() as cap:
        commands.cmd_board()
    out = cap.get()
    assert "🥇" in out and "🥈" in out and "🥉" in out
    assert out.index("Alpha") < out.index("Bravo") < out.index("Charlie")


def test_cmd_board_empty(monkeypatch):
    monkeypatch.setattr(commands, "get", lambda path: [])
    with console.capture() as cap:
        commands.cmd_board("bogus")
    assert "empty" in cap.get()


# --- cmd_top gallery -------------------------------------------------------
def test_cmd_top_renders_tiles_with_placeholder(monkeypatch):
    rows = [{"rank": i + 1, "name": f"Person {i + 1}"} for i in range(20)]
    monkeypatch.setattr(commands, "get", lambda path: rows)
    # everyone has an avatar except #18 -> red ✕ placeholder
    monkeypatch.setattr(commands, "local_avatar",
                        lambda slug: None if slug == "person-18" else _png())
    with console.capture() as cap:
        commands.cmd_top()
    out = cap.get()
    assert "✕" in out                                   # placeholder rendered
    assert "#1" in out and "#20" in out                 # all ranks present
    assert out.index("#1") < out.index("#20")           # rank order preserved


def test_cmd_top_empty(monkeypatch):
    monkeypatch.setattr(commands, "get", lambda path: None)
    with console.capture() as cap:
        commands.cmd_top()
    assert "unavailable" in cap.get()


# --- card/gallery helpers --------------------------------------------------
def test_short_model_label():
    assert commands._short_model_label("Google Gemini 3.1 Flash Lite") == "Gemini 3.1 Flash Lite"
    assert commands._short_model_label("Meta Llama 3.3 70B Instruct") == "Llama 3.3 70B"
    assert commands._short_model_label("xAI Grok 4.20") == "Grok 4.20"
    # brand-as-org names are NOT stripped
    assert commands._short_model_label("DeepSeek V4 Flash") == "DeepSeek V4 Flash"
    assert commands._short_model_label("Mistral Small 3.2 24B Instruct") == "Mistral Small 3.2 24B"
    assert commands._short_model_label("GPT-5.5") == "GPT-5.5"


def test_short_name():
    assert commands._short_name("Paul McCartney") == "McCartney"
    assert commands._short_name("Queen Elizabeth II") == "Elizabeth"
    assert commands._short_name("Martin Luther King Jr.") == "King"
    assert commands._short_name("Plato") == "Plato"


def test_avatar_slug_strips_trailing_dot():
    assert commands._avatar_slug("Martin Luther King Jr.") == "martin-luther-king-jr"
    assert commands._avatar_slug("Paul McCartney") == "paul-mccartney"


# --- avatar cache (api.fetch_bytes) ---------------------------------------
def test_fetch_bytes_uses_cache_without_network(monkeypatch, tmp_path):
    monkeypatch.setenv("ITW_CACHE_DIR", str(tmp_path))
    cache_file = api.cache_dir() / "slugX.png"
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_bytes(b"CACHED")

    def _boom(*a, **k):
        raise AssertionError("network must not be hit when cache exists")

    monkeypatch.setattr(api.urllib.request, "urlopen", _boom)
    assert api.fetch_bytes("http://example/slugX.png", slug="slugX") == b"CACHED"


def test_fetch_bytes_writes_cache_on_miss(monkeypatch, tmp_path):
    monkeypatch.setenv("ITW_CACHE_DIR", str(tmp_path))
    png = _png()

    class _Resp:
        def read(self):
            return png

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(api.urllib.request, "urlopen", lambda *a, **k: _Resp())
    got = api.fetch_bytes("http://example/slugY.png", slug="slugY")
    assert got == png
    assert (api.cache_dir() / "slugY.png").read_bytes() == png  # written through


def test_fetch_bytes_no_slug_skips_cache(monkeypatch, tmp_path):
    monkeypatch.setenv("ITW_CACHE_DIR", str(tmp_path))
    png = _png()

    class _Resp:
        def read(self):
            return png

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(api.urllib.request, "urlopen", lambda *a, **k: _Resp())
    assert api.fetch_bytes("http://example/z.png") == png
    assert not any(api.cache_dir().glob("*.png")) if api.cache_dir().exists() else True


def test_fetch_bytes_returns_none_on_failure(monkeypatch, tmp_path):
    monkeypatch.setenv("ITW_CACHE_DIR", str(tmp_path))

    def _boom(*a, **k):
        raise OSError("connection reset")

    monkeypatch.setattr(api.urllib.request, "urlopen", _boom)
    assert api.fetch_bytes("http://example/none.png", slug="none") is None


# --- avatar_exists / get failure modes ------------------------------------
def test_avatar_exists_false_on_failure(monkeypatch):
    def _boom(*a, **k):
        raise OSError("dns")

    monkeypatch.setattr(api.urllib.request, "urlopen", _boom)
    assert api.avatar_exists("http://example/x.png") is False


def test_get_returns_none_on_404(monkeypatch):
    import urllib.error

    def _404(*a, **k):
        raise urllib.error.HTTPError("u", 404, "nf", {}, None)

    monkeypatch.setattr(api.urllib.request, "urlopen", _404)
    assert api.get("/api/result/nobody") is None
