"""Tests for scripts/cd/update_e2e.py helpers (no network)."""

from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path

import pytest

from xrayvpn.core import update

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "cd" / "update_e2e.py"
sys.path.insert(0, str(_SCRIPT.parent))
_spec = importlib.util.spec_from_file_location("update_e2e", _SCRIPT)
assert _spec and _spec.loader
e2e = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(e2e)


def test_cached_digest_matches(tmp_path: Path) -> None:
    data = b"binary-bytes"
    path = tmp_path / "asset"
    assert e2e.cached_digest_matches(path, hashlib.sha256(data).hexdigest()) is False
    path.write_bytes(data)
    assert e2e.cached_digest_matches(path, hashlib.sha256(data).hexdigest()) is True
    assert e2e.cached_digest_matches(path, "0" * 64) is False


def test_platform_parts_shape() -> None:
    plat, machine = e2e.platform_parts()
    assert isinstance(plat, str) and isinstance(machine, str)


def test_main_skips_without_token(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(e2e, "platform_parts", lambda: ("plan9", "pdp-11"))
    assert e2e.main(["--tag", "v0.0.0"]) == 0
    assert "skip" in capsys.readouterr().out


def test_main_reports_update_errors(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(e2e, "platform_parts", lambda: ("linux", "x86_64"))

    def boom(tag: str, *, http: object = None) -> dict:
        raise update.UpdateError("offline")

    monkeypatch.setattr(update, "fetch_latest_json", boom)
    assert e2e.main(["--tag", "v0.0.0", "--cache-dir", str(tmp_path)]) == 1
    assert "fail: offline" in capsys.readouterr().out


def test_main_fails_when_asset_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(e2e, "platform_parts", lambda: ("win32", "amd64"))
    monkeypatch.setattr(update, "fetch_latest_json", lambda tag, http=None: {})
    monkeypatch.setattr(update, "fetch_sums", lambda tag, http=None: {})
    assert e2e.main(["--tag", "v0.0.0", "--cache-dir", str(tmp_path)]) == 1
    assert "no asset" in capsys.readouterr().out
