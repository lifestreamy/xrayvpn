"""Tests for core/config.py: repo discovery, settings load, override merge."""

from __future__ import annotations

from pathlib import Path

import pytest

from xrayvpn.core.config import find_repo_root, load_settings, merge_overrides


def _make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "config").mkdir(parents=True)
    (repo / "roles" / "xray_vpn").mkdir(parents=True)
    (repo / "config" / "settings.yml").write_text(
        "one: 1\ntwo: 2\n", encoding="utf-8"
    )
    (repo / "deploy.yml").write_text("---\n", encoding="utf-8")
    return repo


def test_find_repo_root_from_nested_dir(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    nested = repo / "python-client" / "src" / "xrayvpn"
    nested.mkdir(parents=True)
    assert find_repo_root(nested) == repo


def test_find_repo_root_raises_without_deploy(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="repository root not found"):
        find_repo_root(tmp_path)


def test_load_settings(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    assert load_settings(repo) == {"one": 1, "two": 2}


def test_load_settings_missing_file(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    (repo / "config" / "settings.yml").unlink()
    with pytest.raises(RuntimeError, match="not found"):
        load_settings(repo)


def test_merge_overrides_precedence() -> None:
    settings = {"a": 1, "b": 2}
    merged = merge_overrides(settings, {"b": 3})
    assert merged == {"a": 1, "b": 3}
    assert merged is not settings  # copy, no aliasing of the input dict


def test_merge_overrides_empty() -> None:
    assert merge_overrides({"a": 1}, {}) == {"a": 1}