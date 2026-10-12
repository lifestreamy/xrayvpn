"""Tests for scripts/cd/collect_channel_versions.py (CD glue, README badges)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "cd" / "collect_channel_versions.py"
sys.path.insert(0, str(_SCRIPT.parent))
_spec = importlib.util.spec_from_file_location("collect_channel_versions", _SCRIPT)
assert _spec and _spec.loader
collect_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(collect_mod)

RELEASES = json.dumps({"tag_name": "v0.4.2", "prerelease": False})
PYPI = json.dumps({"info": {"name": "xrayvpn", "version": "0.4.1"}})
BREW = (
    "class Xrayvpn < Formula\n"
    '  url "https://github.com/lifestreamy/xrayvpn/releases/download/v0.4.1/'
    'xrayvpn-0.4.1-macos-arm64-portable"\n'
    "end\n"
)
APT = (
    "Package: other\n"
    "Version: 9.9.9\n"
    "\n"
    "Package: xrayvpn\n"
    "Version: 0.4.1\n"
    "Architecture: amd64\n"
)
ALL = {"release": RELEASES, "pip": PYPI, "brew": BREW, "apt": APT}


def _fetch(payloads: dict[str, str]):
    urls = {collect_mod.SOURCES[key]: value for key, value in payloads.items()}

    def fetch(url: str, headers: dict[str, str]) -> str:
        try:
            return urls[url]
        except KeyError:
            raise OSError(f"unreachable: {url}") from None

    return fetch


def test_collect_full() -> None:
    versions = collect_mod.collect_versions(fetch=_fetch(ALL))
    assert versions == {
        "release": "0.4.2",
        "pip": "0.4.1",
        "uv": "0.4.1",
        "brew": "0.4.1",
        "apt": "0.4.1",
    }
    assert list(versions) == ["release", "pip", "uv", "brew", "apt"]


def test_collect_source_failure_is_null() -> None:
    versions = collect_mod.collect_versions(
        fetch=_fetch({"release": RELEASES, "pip": PYPI, "apt": APT})
    )
    assert versions["brew"] is None
    assert versions["pip"] == "0.4.1"
    assert versions["uv"] == "0.4.1"


def test_collect_rejects_bad_payloads() -> None:
    versions = collect_mod.collect_versions(
        fetch=_fetch(
            {
                "release": json.dumps({"tag_name": "0.4.2"}),
                "pip": "not json",
                "brew": "class Xrayvpn < Formula\nend\n",
                "apt": "Package: other\nVersion: 9.9.9\n",
            }
        )
    )
    assert set(versions.values()) == {None}


def test_collect_rejects_short_versions() -> None:
    versions = collect_mod.collect_versions(
        fetch=_fetch(
            {
                "release": RELEASES,
                "pip": json.dumps({"info": {"version": "0.4"}}),
                "brew": BREW,
                "apt": APT,
            }
        )
    )
    assert versions["pip"] is None
    assert versions["uv"] is None
    assert versions["release"] == "0.4.2"


def test_collect_apt_skips_other_packages() -> None:
    payload = "Package: xrayvpn-extra\nVersion: 9.9.9\n\nPackage: xrayvpn\nVersion: 0.4.1\n"
    versions = collect_mod.collect_versions(
        fetch=_fetch({"release": RELEASES, "pip": PYPI, "brew": BREW, "apt": payload})
    )
    assert versions["apt"] == "0.4.1"


def test_main_writes_out(tmp_path: Path, capsys) -> None:
    out = tmp_path / "build" / "versions.json"
    code = collect_mod.main(["--out", str(out)], fetch=_fetch(ALL))
    assert code == 0
    written = json.loads(out.read_text(encoding="utf-8"))
    assert written["release"] == "0.4.2"
    assert written["uv"] == "0.4.1"
    assert '"release"' in capsys.readouterr().out
    assert b"\r\n" not in out.read_bytes()


def test_main_survives_total_failure(tmp_path: Path) -> None:
    out = tmp_path / "versions.json"
    code = collect_mod.main(["--out", str(out)], fetch=_fetch({}))
    assert code == 0
    written = json.loads(out.read_text(encoding="utf-8"))
    assert set(written.values()) == {None}
    assert list(written) == ["release", "pip", "uv", "brew", "apt"]
