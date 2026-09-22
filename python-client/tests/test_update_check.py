"""Tests for core/update_check.py (card B7 + review fix): fail-silent release hint."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
from typer.testing import CliRunner

import xrayvpn.cli.main as main_mod
from xrayvpn import i18n
from xrayvpn.core import update_check

runner = CliRunner()


def test_is_newer_numeric_cores() -> None:
    assert update_check.is_newer("v0.5.0", "0.4.0")
    assert update_check.is_newer("0.4.1", "0.4.0")
    assert update_check.is_newer("v1.0", "0.9.9")
    assert update_check.is_newer("v0.40.0", "0.9.0")
    assert not update_check.is_newer("v0.4.0_experimental", "0.4.0")
    assert not update_check.is_newer("v0.3.9", "0.4.0")
    assert not update_check.is_newer("not-a-version", "0.4.0")
    assert not update_check.is_newer("v1.0.0", "dev")


def test_fetch_latest_tag_transport_injection() -> None:
    payload = json.dumps({"tag_name": "v9.9.9"}).encode()
    assert update_check.fetch_latest_tag(http=lambda url: payload) == "v9.9.9"


def test_fetch_latest_tag_silent_on_failures() -> None:
    def boom(url: str) -> bytes:
        raise OSError("rate limited")

    assert update_check.fetch_latest_tag(http=boom) is None
    assert update_check.fetch_latest_tag(http=lambda url: b"not json") is None
    assert update_check.fetch_latest_tag(http=lambda url: b"{}") is None
    assert update_check.fetch_latest_tag(http=lambda url: b'{"tag_name": ""}') is None


def test_fetch_latest_tag_wall_clock_bound_covers_dns(tmp_path: Path) -> None:
    def slow(url: str) -> bytes:
        time.sleep(1.5)
        return b'{"tag_name": "v9"}'

    started = time.monotonic()
    assert update_check.fetch_latest_tag(http=slow, timeout=0.1) is None
    assert time.monotonic() - started < 1.0


def test_check_enabled_rules() -> None:
    assert update_check.check_enabled(packaged=True, env={})
    assert not update_check.check_enabled(packaged=True, env={"XRAYVPN_UPDATE_CHECK": "0"})
    assert not update_check.check_enabled(packaged=False, env={})
    assert update_check.check_enabled(packaged=False, env={"XRAYVPN_UPDATE_CHECK": "1"})


def test_banner_hint_newer_only(tmp_path: Path) -> None:
    hint = update_check.banner_hint(
        packaged=True,
        env={},
        current="0.4.0",
        fetch=lambda: "v9.9.9",
        cache_path=tmp_path / "c1.json",
    )
    assert hint and "v9.9.9" in hint and "github.com" in hint
    assert (
        update_check.banner_hint(
            packaged=True, env={}, current="0.4.0", fetch=lambda: None,
            cache_path=tmp_path / "c2.json",
        )
        is None
    )
    assert (
        update_check.banner_hint(
            packaged=True, env={}, current="0.4.0", fetch=lambda: "v0.3.0",
            cache_path=tmp_path / "c3.json",
        )
        is None
    )
    assert (
        update_check.banner_hint(
            packaged=False, env={}, fetch=lambda: "v9.9.9", cache_path=tmp_path / "c4.json"
        )
        is None
    )


def test_banner_hint_cache_hit_skips_network(tmp_path: Path) -> None:
    cache = tmp_path / "cache.json"
    cache.write_text(json.dumps({"checked_at": time.time(), "tag": "v9.9.9"}), encoding="utf-8")

    def network() -> str:
        raise AssertionError("fresh cache must not hit the network")

    hint = update_check.banner_hint(
        packaged=True, env={}, current="0.4.0", fetch=network, cache_path=cache
    )
    assert hint and "v9.9.9" in hint


def test_banner_hint_cache_stores_reuses_and_expires(tmp_path: Path) -> None:
    cache = tmp_path / "cache.json"
    calls: list[int] = []

    def fetch() -> str:
        calls.append(1)
        return "v5.0.0"

    now = 1_000_000.0
    assert "v5.0.0" in update_check.banner_hint(
        packaged=True, env={}, current="0.4.0", fetch=fetch, cache_path=cache, now=now
    )
    assert "v5.0.0" in update_check.banner_hint(
        packaged=True, env={}, current="0.4.0", fetch=fetch, cache_path=cache,
        now=now + 60,
    )
    assert len(calls) == 1
    assert "v5.0.0" in update_check.banner_hint(
        packaged=True, env={}, current="0.4.0", fetch=fetch, cache_path=cache,
        now=now + update_check.CACHE_TTL_SECONDS + 10,
    )
    assert len(calls) == 2  # stale entry forces a recheck


def test_banner_hint_negative_cache_also_bounded(tmp_path: Path) -> None:
    cache = tmp_path / "cache.json"
    calls: list[int] = []

    def fetch() -> None:
        calls.append(1)

    update_check.banner_hint(packaged=True, env={}, fetch=fetch, cache_path=cache, now=5.0)
    update_check.banner_hint(packaged=True, env={}, fetch=fetch, cache_path=cache, now=6.0)
    assert len(calls) == 1


def test_banner_hint_spoofed_cache_is_display_filtered(tmp_path: Path) -> None:
    cache = tmp_path / "cache.json"
    cache.write_text(
        json.dumps({"checked_at": time.time(), "tag": "garbage"}), encoding="utf-8"
    )
    assert update_check.banner_hint(packaged=True, env={}, current="0.4.0", cache_path=cache) is None


def test_banner_hint_ru_string_guard(tmp_path: Path) -> None:
    try:
        i18n.set_ru(True)
        hint = update_check.banner_hint(
            packaged=True,
            env={},
            current="0.4.0",
            fetch=lambda: "v9.9.9",
            cache_path=tmp_path / "c.json",
        )
        assert hint and "доступно обновление: v9.9.9" in hint
    finally:
        i18n.set_ru(False)


def _isolate_cache(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(update_check, "_cache_path", lambda: tmp_path / "wiring-cache.json")


def test_version_quiet_in_dev_and_with_kill_switch(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _isolate_cache(monkeypatch, tmp_path)

    def network() -> str:
        raise AssertionError("dev mode must not touch the network")

    monkeypatch.setattr(update_check, "fetch_latest_tag", network)
    monkeypatch.delenv(update_check.KILL_SWITCH_ENV, raising=False)
    result = runner.invoke(main_mod.app, ["--version"])
    assert result.exit_code == 0
    assert "update available" not in result.output


def test_version_opt_in_prints_hint(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _isolate_cache(monkeypatch, tmp_path)
    monkeypatch.setenv(update_check.KILL_SWITCH_ENV, "1")
    monkeypatch.setattr(update_check, "fetch_latest_tag", lambda: "v9.9.9")
    result = runner.invoke(main_mod.app, ["--version"])
    assert result.exit_code == 0
    assert "update available: v9.9.9" in result.output


def test_version_cached_between_invocations(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _isolate_cache(monkeypatch, tmp_path)
    monkeypatch.setenv(update_check.KILL_SWITCH_ENV, "1")
    calls: list[int] = []

    def fetch() -> str:
        calls.append(1)
        return "v9.9.9"

    monkeypatch.setattr(update_check, "fetch_latest_tag", fetch)
    assert runner.invoke(main_mod.app, ["--version"]).exit_code == 0
    assert runner.invoke(main_mod.app, ["--version"]).exit_code == 0
    assert len(calls) == 1


def test_banner_hint_silent_when_fetch_finds_nothing(tmp_path: Path) -> None:
    assert (
        update_check.banner_hint(
            packaged=True, env={}, fetch=lambda: None, cache_path=tmp_path / "c.json"
        )
        is None
    )
