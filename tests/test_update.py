"""Self-update: version compare, GitHub release lookup, manager detection, and the
`itw update` command — all mocked, no real network or subprocess."""
from __future__ import annotations

import json

import pytest

from itwlib import update as upd
from itwlib import cli
from itwlib.config import console


class _Resp:
    def __init__(self, payload):
        self._payload = json.dumps(payload).encode()

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _release_payload(tag="v0.2.0"):
    return {"tag_name": tag, "html_url": f"https://github.com/{upd.REPO}/releases/tag/{tag}"}


# ---- _parse / is_newer ----------------------------------------------------------

def test_parse_strips_v_and_local():
    assert upd._parse("v0.2.0") == (0, 2, 0)
    assert upd._parse("0.2.0") == (0, 2, 0)
    assert upd._parse("0.0.0+local") == (0, 0, 0)


def test_is_newer_numeric_not_string():
    # the classic string-compare trap: "0.9.0" > "0.10.0" lexically, but not numerically
    assert upd.is_newer("v0.10.0", "0.9.0") is True
    assert upd.is_newer("v0.9.0", "0.10.0") is False
    assert upd.is_newer("v0.2.0", "0.2.0") is False
    assert upd.is_newer("v0.2.0", "0.0.0+local") is True


# ---- latest_release -------------------------------------------------------------

def test_latest_release_parses_tag_and_url(monkeypatch):
    monkeypatch.setattr(upd.urllib.request, "urlopen",
                        lambda req, timeout=0: _Resp(_release_payload("v1.3.0")))
    rel = upd.latest_release()
    assert rel.tag == "v1.3.0"
    assert "v1.3.0" in rel.url


def test_latest_release_none_on_404(monkeypatch):
    import urllib.error

    def _raise(req, timeout=0):
        raise urllib.error.HTTPError(upd.RELEASES_API, 404, "Not Found", {}, None)

    monkeypatch.setattr(upd.urllib.request, "urlopen", _raise)
    assert upd.latest_release() is None


def test_latest_release_none_on_network_error(monkeypatch):
    def _raise(req, timeout=0):
        raise OSError("offline")

    monkeypatch.setattr(upd.urllib.request, "urlopen", _raise)
    assert upd.latest_release() is None


# ---- upgrade_cmd ----------------------------------------------------------------

def test_upgrade_cmd_prefers_uv(monkeypatch):
    monkeypatch.setattr(upd.shutil, "which", lambda exe: f"/bin/{exe}")  # both present
    assert upd.upgrade_cmd() == ["uv", "tool", "upgrade", "itw-cli"]


def test_upgrade_cmd_falls_back_to_pipx(monkeypatch):
    monkeypatch.setattr(upd.shutil, "which", lambda exe: f"/bin/{exe}" if exe == "pipx" else None)
    assert upd.upgrade_cmd() == ["pipx", "upgrade", "itw-cli"]


def test_upgrade_cmd_none_when_neither(monkeypatch):
    monkeypatch.setattr(upd.shutil, "which", lambda exe: None)
    assert upd.upgrade_cmd() is None


# ---- cli `update` command -------------------------------------------------------

def _no_subprocess(monkeypatch):
    """Trip if anything tries to actually run an upgrade."""
    import subprocess
    monkeypatch.setattr(subprocess, "run",
                        lambda *a, **k: pytest.fail("subprocess.run should not be called"))


def test_update_check_reports_without_upgrading(monkeypatch):
    _no_subprocess(monkeypatch)
    monkeypatch.setattr("itwlib.update.latest_release",
                        lambda *a, **k: upd.Release("v9.9.9", "https://x/9.9.9"))
    with console.capture() as cap:
        rc = cli.main(["update", "--check"])
    out = cap.get()
    assert rc == 0
    assert "update available" in out
    assert "9.9.9" in out


def test_update_up_to_date(monkeypatch):
    _no_subprocess(monkeypatch)
    monkeypatch.setattr(cli, "__version__", "9.9.9")
    monkeypatch.setattr("itwlib.update.latest_release",
                        lambda *a, **k: upd.Release("v0.0.1", "https://x/0.0.1"))
    with console.capture() as cap:
        rc = cli.main(["update"])
    out = cap.get()
    assert rc == 0
    assert "latest" in out


def test_update_none_release_graceful(monkeypatch):
    _no_subprocess(monkeypatch)
    monkeypatch.setattr("itwlib.update.latest_release", lambda *a, **k: None)
    with console.capture() as cap:
        rc = cli.main(["update"])
    out = cap.get()
    assert rc == 0
    assert "GitHub" in out or "releases" in out
