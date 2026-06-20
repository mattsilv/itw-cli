"""Self-service avatar generation — mocked HTTP, no real OpenRouter calls."""
from __future__ import annotations

import base64
import io
import json

import pytest
from PIL import Image

from itwlib import generate as gen
from itwlib import api
from itwlib.config import generated_dir


def _png_b64(w=64, h=64):
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (12, 34, 56)).save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


class _Resp:
    def __init__(self, payload):
        self._payload = json.dumps(payload).encode()

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _ok_payload():
    return {
        "choices": [{"message": {"images": [
            {"image_url": {"url": f"data:image/png;base64,{_png_b64()}"}}
        ]}}],
        "usage": {"cost": 0.0387},
    }


def test_generate_avatar_saves_256_png(monkeypatch, tmp_path):
    monkeypatch.setenv("ITW_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(gen.urllib.request, "urlopen", lambda req, timeout=0: _Resp(_ok_payload()))
    path, cost = gen.generate_avatar("Tiger Woods", "sk-or-test")
    assert path == generated_dir() / "tiger-woods.png"
    assert path.exists()
    assert Image.open(path).size == (256, 256)
    assert cost == pytest.approx(0.0387)


def test_generated_avatar_wins_over_bundled(monkeypatch, tmp_path):
    """A self-generated avatar overrides whatever shipped for that slug."""
    monkeypatch.setenv("ITW_CACHE_DIR", str(tmp_path))
    # alan-turing ships bundled; generate a replacement and assert local_avatar uses it
    before = api.local_avatar("alan-turing")
    monkeypatch.setattr(gen.urllib.request, "urlopen", lambda req, timeout=0: _Resp(_ok_payload()))
    gen.generate_avatar("Alan Turing", "sk-or-test")
    after = api.local_avatar("alan-turing")
    assert after != before  # now resolves to the generated file
    assert after == (generated_dir() / "alan-turing.png").read_bytes()


def test_generate_avatar_errors_without_image(monkeypatch, tmp_path):
    monkeypatch.setenv("ITW_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(gen.urllib.request, "urlopen",
                        lambda req, timeout=0: _Resp({"choices": [{"message": {}}]}))
    with pytest.raises(gen.GenerateError):
        gen.generate_avatar("Nobody", "sk-or-test")


def test_cli_generate_requires_key(monkeypatch):
    from itwlib import cli
    from itwlib.config import console
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with console.capture() as cap:
        rc = cli.main(["generate", "tiger woods"])
    assert rc == 2
    assert "OPENROUTER_API_KEY" in cap.get()
