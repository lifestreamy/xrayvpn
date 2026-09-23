"""Tests for scripts/cd/render_badges.py (CD glue, README badges)."""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "cd" / "render_badges.py"
sys.path.insert(0, str(_SCRIPT.parent))
_spec = importlib.util.spec_from_file_location("render_badges", _SCRIPT)
assert _spec and _spec.loader
badges_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(badges_mod)

_ROOT = _SCRIPT.parents[2]
_NAMES = {
    "release.svg",
    "brew.svg",
    "winget-ru.svg",
    "winget-en.svg",
    "apt.svg",
    "pip.svg",
    "uv.svg",
    "python.svg",
    "license.svg",
    "lang-ru.svg",
    "lang-ru-muted.svg",
    "lang-en.svg",
    "lang-en-muted.svg",
}


def test_channel_badges_winget_soon() -> None:
    badges = {row[0]: row for row in badges_mod.channel_badges("0.4.1", False)}
    assert badges["release.svg"][2] == "v0.4.1"
    assert badges["winget-ru.svg"][2] == "скоро"
    assert badges["winget-en.svg"][2] == "soon"
    assert badges["winget-ru.svg"][3] == "warn"


def test_channel_badges_winget_live() -> None:
    badges = {row[0]: row for row in badges_mod.channel_badges("0.4.1", True)}
    assert badges["winget-ru.svg"][2] == "v0.4.1"
    assert badges["winget-en.svg"][2] == "v0.4.1"
    assert badges["winget-ru.svg"][3] == "accent"


def test_segment_width_fits_text() -> None:
    for text in ("release", "v0.4.1", "Русский", "AGPL-3.0"):
        assert badges_mod.segment_width(text, 400) > badges_mod.text_width(text, 400) + 16
        assert badges_mod.segment_width(text, 700) > badges_mod.text_width(text, 700) + 16


def test_shade_darkens_palette_colors() -> None:
    assert badges_mod.shade("#00D587") == "#00B371"
    assert badges_mod.shade("#FFFFFF", 0.5) == "#808080"


def test_badge_files_complete() -> None:
    files = badges_mod.badge_files(_ROOT, "0.4.1", False)
    assert {path.name for path in files} == _NAMES


def test_badge_files_use_palette() -> None:
    palette = badges_mod.load_palette(_ROOT)
    files = badges_mod.badge_files(_ROOT, "0.4.1", False)
    release = files[Path("release.svg")].decode()
    winget = files[Path("winget-ru.svg")].decode()
    python = files[Path("python.svg")].decode()
    assert palette["accent"] in release
    assert palette["warn"] in winget
    assert palette["muted"] in python
    assert "url(#g)" in release


def test_language_badges_pick_tone() -> None:
    palette = badges_mod.load_palette(_ROOT)
    files = badges_mod.badge_files(_ROOT, "0.4.1", False)
    active = files[Path("lang-ru.svg")].decode()
    inactive = files[Path("lang-ru-muted.svg")].decode()
    assert palette["accent"] in active
    assert palette["muted"] in inactive
    assert "Русский" in active


def test_two_segment_geometry() -> None:
    template = badges_mod.read_template(_ROOT / "packaging" / "badges" / "badge.svg")
    gradient = ("#00D587", "#00B371")
    svg = badges_mod.render_two_segment(
        template, "uv tool", "v0.4.1", gradient, badges_mod.INK, "uv tool v0.4.1"
    )
    total = int(re.search(r'width="(\d+)"', svg).group(1))
    label_width = int(re.search(r'<path d="M(\d+) ', svg).group(1))
    label_x = 8
    value_x = int(re.search(r'<text x="(\d+)"[^>]*font-weight="700"', svg).group(1))
    assert value_x == label_width + 8
    assert label_x + badges_mod.text_width("uv tool", 400) <= label_width - 8 + 0.5
    assert value_x + badges_mod.text_width("v0.4.1", 700) <= total - 8 + 0.5


def test_rendered_files_are_lf_and_resolved() -> None:
    files = badges_mod.badge_files(_ROOT, "0.4.1", False)
    for path, data in files.items():
        assert b"\r\n" not in data, path
        assert b"{{" not in data, path
        assert b"</svg>" in data, path


def test_main_writes_files(tmp_path: Path) -> None:
    code = badges_mod.main(["--tag", "v0.4.1", "--out", str(tmp_path)])
    assert code == 0
    assert {path.name for path in tmp_path.iterdir()} == _NAMES
    expected = badges_mod.badge_files(_ROOT, "0.4.1", False)[Path("release.svg")]
    assert (tmp_path / "release.svg").read_bytes() == expected


def test_main_winget_live(tmp_path: Path) -> None:
    badges_mod.main(["--tag", "v0.4.1", "--winget-live", "--out", str(tmp_path)])
    winget = (tmp_path / "winget-ru.svg").read_text(encoding="utf-8")
    assert "v0.4.1" in winget
    assert "скоро" not in winget


def test_main_rejects_plain_tag(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        badges_mod.main(["--tag", "0.4.1", "--out", str(tmp_path)])