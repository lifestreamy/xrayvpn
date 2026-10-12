"""Tests for core/update_state.py: tolerant skip-version state."""

from __future__ import annotations

import json
from pathlib import Path

from xrayvpn.core import update_state


def test_default_state_path_per_platform(tmp_path: Path) -> None:
    home = tmp_path / "home"
    win = update_state.default_state_path(
        env={"LOCALAPPDATA": str(tmp_path / "LocalAppData")},
        home=home,
        platform="win32",
    )
    assert win == tmp_path / "LocalAppData" / "xrayvpn" / "update-state.json"
    mac = update_state.default_state_path(env={}, home=home, platform="darwin")
    assert mac == home / "Library" / "Application Support" / "xrayvpn" / "update-state.json"
    linux = update_state.default_state_path(env={}, home=home, platform="linux")
    assert linux == home / ".local" / "share" / "xrayvpn" / "update-state.json"
    xdg = update_state.default_state_path(
        env={"XDG_DATA_HOME": str(tmp_path / "xdg")}, home=home, platform="linux"
    )
    assert xdg == tmp_path / "xdg" / "xrayvpn" / "update-state.json"


def test_state_dir_env_override(tmp_path: Path) -> None:
    path = update_state.default_state_path(env={"XRAYVPN_STATE_DIR": str(tmp_path / "state")})
    assert path == tmp_path / "state" / "update-state.json"


def test_skip_roundtrip_and_normalization(tmp_path: Path) -> None:
    state = tmp_path / "update-state.json"
    assert update_state.skipped_version(state) is None
    assert update_state.skip_version(state, "v0.4.3")
    assert update_state.skipped_version(state) == "0.4.3"
    assert json.loads(state.read_text(encoding="utf-8")) == {"skipped_version": "0.4.3"}
    assert update_state.skip_version(state, "0.5.0_experimental")
    assert update_state.skipped_version(state) == "0.5.0"
    assert update_state.clear_skip(state)
    assert update_state.skipped_version(state) is None


def test_read_state_tolerant(tmp_path: Path) -> None:
    state = tmp_path / "update-state.json"
    assert update_state.read_state(state) == {}
    state.write_text("not json", encoding="utf-8")
    assert update_state.read_state(state) == {}
    state.write_text("[1, 2]", encoding="utf-8")
    assert update_state.read_state(state) == {}
    state.write_text("{}", encoding="utf-8")
    assert update_state.skipped_version(state) is None


def test_skip_version_keeps_other_keys(tmp_path: Path) -> None:
    state = tmp_path / "update-state.json"
    state.write_text(json.dumps({"other": "kept"}), encoding="utf-8")
    assert update_state.skip_version(state, "0.4.3")
    data = json.loads(state.read_text(encoding="utf-8"))
    assert data == {"other": "kept", "skipped_version": "0.4.3"}


def test_write_state_reports_failure(tmp_path: Path) -> None:
    state = tmp_path / "file-as-dir"
    state.mkdir()
    assert update_state.write_state(state, {}) is False
