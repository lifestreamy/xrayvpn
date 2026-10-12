"""Tests for scripts/cd/bump_readme_badge_queries.py (CD glue, README badges)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "cd" / "bump_readme_badge_queries.py"
sys.path.insert(0, str(_SCRIPT.parent))
_spec = importlib.util.spec_from_file_location("bump_readme_badge_queries", _SCRIPT)
assert _spec and _spec.loader
bump_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bump_mod)

README = (
    "[![release](assets/badges/release.svg?v=0.4.1)](https://example/releases)\n"
    "[![winget скоро](assets/badges/winget-ru.svg)](https://example/pr)\n"
    "[![pip](assets/badges/pip.svg?v=0.4.1)](https://pypi.org/project/xrayvpn/)\n"
    "[![license AGPL-3.0](assets/badges/license.svg)](LICENSE)\n"
)
FULL = {"release": "0.4.2", "pip": "0.4.1", "uv": "0.4.1", "brew": "0.4.1", "apt": "0.4.1"}


def test_bump_sets_each_badge_version() -> None:
    text = (
        "[![release](assets/badges/release.svg?v=0.1.0)](x)\n"
        "[![brew](assets/badges/brew.svg?v=0.1.0)](x)\n"
        "[![apt](assets/badges/apt.svg?v=0.1.0)](x)\n"
        "[![uv tool](assets/badges/uv.svg?v=0.1.0)](x)\n"
    )
    updated = bump_mod.bump_text(text, FULL)
    assert "release.svg?v=0.4.2" in updated
    assert "brew.svg?v=0.4.1" in updated
    assert "apt.svg?v=0.4.1" in updated
    assert "uv.svg?v=0.4.1" in updated


def test_bump_skips_missing_versions_and_other_lines() -> None:
    updated = bump_mod.bump_text(README, {"release": "0.4.2", "pip": None})
    assert "release.svg?v=0.4.2" in updated
    assert "pip.svg?v=0.4.1" in updated
    assert "pip.svg?v=0.4.2" not in updated
    assert "winget-ru.svg)" in updated
    assert "license.svg)" in updated


def test_bump_is_idempotent() -> None:
    once = bump_mod.bump_text(README, FULL)
    twice = bump_mod.bump_text(once, FULL)
    assert once == twice


def test_bump_ignores_invalid_versions() -> None:
    assert bump_mod.bump_text(README, {"pip": "0.4"}) == README


def test_main_updates_both_readmes(tmp_path: Path) -> None:
    versions = tmp_path / "versions.json"
    versions.write_text(json.dumps(FULL), encoding="utf-8")
    ru = tmp_path / "README.md"
    en = tmp_path / "README.en.md"
    ru.write_text(README, encoding="utf-8", newline="")
    en.write_text(
        README.replace("release.svg?v=0.4.1", "release.svg?v=0.4.0"),
        encoding="utf-8",
        newline="",
    )
    code = bump_mod.main(["--versions-json", str(versions), str(ru), str(en)])
    assert code == 0
    assert "release.svg?v=0.4.2" in ru.read_text(encoding="utf-8")
    assert "release.svg?v=0.4.2" in en.read_text(encoding="utf-8")
    assert b"\r\n" not in ru.read_bytes()


def test_load_versions_rejects_non_object(tmp_path: Path) -> None:
    path = tmp_path / "versions.json"
    path.write_text("[]", encoding="utf-8")
    with pytest.raises(SystemExit):
        bump_mod.load_versions(path)
