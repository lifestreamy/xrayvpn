"""Tests for core/install_source.py: install-source classification.

Every probe is injected: tests never touch real package databases, real
venvs or the network. detect() runs against tmp_path trees; classify()
receives Signals directly. Ambiguity must degrade to UNKNOWN, never to a
self-replaceable kind.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from xrayvpn.core import install_source as src


def _touch(path: Path, text: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _missing(name: str) -> None:
    raise LookupError(name)


def _detect(**overrides: object) -> src.InstallInfo:
    base: dict[str, object] = {
        "frozen": False,
        "platform": "linux",
        "argv": ["xrayvpn"],
        "prefix": Path("/nonexistent-venv"),
        "package_dir": Path("/nonexistent-pkg"),
        "cwd": Path("/nonexistent-cwd"),
        "env": {},
        "home": Path("/nonexistent-home"),
        "which": lambda name: None,
        "run": lambda command: None,
        "find_repo": lambda cwd: None,
        "dist_lookup": _missing,
    }
    base.update(overrides)
    return src.detect(**base)


def _owner_stdout(command: object) -> SimpleNamespace:
    return SimpleNamespace(stdout="xrayvpn: /usr/bin/xrayvpn\n")


def test_frozen_without_owner_is_standalone() -> None:
    info = _detect(frozen=True)
    assert info.kind == src.STANDALONE
    assert info.confidence == src.CONFIDENCE_HIGH


def test_frozen_skips_metadata_probes() -> None:
    def boom(name: str) -> None:
        raise AssertionError("frozen builds must not probe distribution metadata")

    info = _detect(frozen=True, dist_lookup=boom)
    assert info.kind == src.STANDALONE


def test_frozen_deb_is_apt_owned() -> None:
    info = _detect(
        frozen=True,
        argv=["/usr/bin/xrayvpn"],
        which=lambda name: "/usr/bin/dpkg-query" if name == "dpkg-query" else None,
        run=_owner_stdout,
    )
    assert info.kind == src.APT
    assert info.confidence == src.CONFIDENCE_HIGH


def test_dpkg_probe_skipped_off_linux() -> None:
    info = _detect(
        frozen=True,
        platform="darwin",
        argv=["/opt/homebrew/bin/xrayvpn"],
        which=lambda name: "/usr/bin/dpkg-query",
        run=_owner_stdout,
    )
    assert info.kind == src.STANDALONE


def test_frozen_winget_packages_path(tmp_path: Path) -> None:
    local_appdata = tmp_path / "AppData" / "Local"
    program = local_appdata / "Microsoft" / "WinGet" / "Packages" / "Lifestreamy.XrayVpn" / "xrayvpn.exe"
    _touch(program, "MZ")
    info = _detect(
        frozen=True,
        platform="win32",
        argv=[str(program)],
        env={"LOCALAPPDATA": str(local_appdata)},
    )
    assert info.kind == src.WINGET


def test_brew_keg_shape_and_classification() -> None:
    assert src._brew_keg(Path("/opt/homebrew/Cellar/xrayvpn/0.4.2/bin/xrayvpn"))
    assert not src._brew_keg(Path("/usr/local/bin/xrayvpn"))
    assert not src._brew_keg(Path("/opt/homebrew/Cellar/other/1.0/bin/other"))
    info = src.classify(src.Signals(platform="darwin", brew_owner=True))
    assert info.kind == src.BREW


def test_owner_conflict_is_unknown() -> None:
    info = src.classify(src.Signals(dpkg_owner=True, brew_owner=True))
    assert info.kind == src.UNKNOWN
    assert src.classify(src.Signals(dpkg_owner=True, winget_owner=True)).kind == src.UNKNOWN


def test_uv_tool_receipt(tmp_path: Path) -> None:
    prefix = tmp_path / "tools" / "xrayvpn"
    _touch(prefix / "uv-receipt.toml", "[tool]\n")
    info = _detect(prefix=prefix)
    assert info.kind == src.UV_TOOL
    assert info.confidence == src.CONFIDENCE_HIGH


def test_uv_tools_root_path(tmp_path: Path) -> None:
    home = tmp_path / "home"
    prefix = home / ".local" / "share" / "uv" / "tools" / "xrayvpn"
    prefix.mkdir(parents=True)
    info = _detect(prefix=prefix, home=home)
    assert info.kind == src.UV_TOOL


def test_uv_tool_dir_override(tmp_path: Path) -> None:
    tools = tmp_path / "custom-tools"
    prefix = tools / "xrayvpn"
    prefix.mkdir(parents=True)
    info = _detect(prefix=prefix, env={"UV_TOOL_DIR": str(tools)})
    assert info.kind == src.UV_TOOL


def test_pipx_metadata_main_package(tmp_path: Path) -> None:
    prefix = tmp_path / "venvs" / "xrayvpn"
    _touch(
        prefix / "pipx_metadata.json",
        json.dumps({"main_package": {"package": "xrayvpn==0.4.2"}}),
    )
    info = _detect(prefix=prefix)
    assert info.kind == src.PIPX
    assert info.confidence == src.CONFIDENCE_HIGH


def test_pipx_metadata_other_package_is_not_pipx(tmp_path: Path) -> None:
    prefix = tmp_path / "venvs" / "xrayvpn"
    _touch(
        prefix / "pipx_metadata.json",
        json.dumps({"main_package": {"package": "other-tool"}}),
    )
    info = _detect(prefix=prefix)
    assert info.kind == src.UNKNOWN


def test_pipx_home_venvs_path(tmp_path: Path) -> None:
    pipx_home = tmp_path / "pipx-home"
    prefix = pipx_home / "venvs" / "xrayvpn"
    prefix.mkdir(parents=True)
    info = _detect(prefix=prefix, env={"PIPX_HOME": str(pipx_home)})
    assert info.kind == src.PIPX


def test_uv_and_pipx_conflict_is_unknown() -> None:
    info = src.classify(src.Signals(uv_receipt=True, pipx_metadata=True))
    assert info.kind == src.UNKNOWN


def test_repo_checkout_is_dev(tmp_path: Path) -> None:
    repo = tmp_path / "clone"
    _touch(repo / "deploy.yml", "---\n")
    package = repo / "python-client" / "src" / "xrayvpn"
    package.mkdir(parents=True)
    info = _detect(cwd=repo, package_dir=package, find_repo=lambda cwd: repo)
    assert info.kind == src.DEV
    assert info.confidence == src.CONFIDENCE_HIGH


def test_editable_direct_url_is_dev() -> None:
    info = src.classify(src.Signals(direct_url={"dir_info": {"editable": True}}))
    assert info.kind == src.DEV


def test_vcs_direct_url_is_pip_direct() -> None:
    info = src.classify(
        src.Signals(
            direct_url={
                "url": "https://example.invalid/xrayvpn.git",
                "vcs_info": {"vcs": "git", "commit_id": "0" * 40},
            }
        )
    )
    assert info.kind == src.PIP_DIRECT
    assert info.confidence == src.CONFIDENCE_MEDIUM


def test_detect_reads_direct_url_metadata(tmp_path: Path) -> None:
    dist = SimpleNamespace(read_text=lambda name: json.dumps({"vcs_info": {"vcs": "git"}}))
    info = _detect(prefix=tmp_path / "venv", dist_lookup=lambda name: dist)
    assert info.kind == src.PIP_DIRECT


def test_plain_dist_is_pip_low_confidence(tmp_path: Path) -> None:
    info = src.classify(src.Signals(dist_found=True))
    assert info.kind == src.PIP
    assert info.confidence == src.CONFIDENCE_LOW
    dist = SimpleNamespace(read_text=lambda name: None)
    detected = _detect(prefix=tmp_path / "venv", dist_lookup=lambda name: dist)
    assert detected.kind == src.PIP


def test_no_signals_is_unknown() -> None:
    info = src.classify(src.Signals())
    assert info.kind == src.UNKNOWN
    assert info.confidence == src.CONFIDENCE_LOW


def test_dpkg_owner_parsing() -> None:
    assert src._dpkg_owner("xrayvpn: /usr/bin/xrayvpn\n")
    assert src._dpkg_owner("xrayvpn: /usr/bin/xrayvpn\nother: /x\n")
    assert not src._dpkg_owner("")
    assert not src._dpkg_owner("dpkg-query: no path found matching pattern /x")
    assert not src._dpkg_owner("other-package: /usr/bin/other\n")


def test_pacman_owner_parsing() -> None:
    assert src._pacman_owner("/usr/bin/xrayvpn is owned by xrayvpn 0.4.2-1\n")
    assert not src._pacman_owner("error: No package owns /usr/bin/xrayvpn\n")
    assert not src._pacman_owner("")


def test_under_casefold_for_windows_paths() -> None:
    assert src._under(Path("/A/B"), Path("/a"), casefold=True)
    assert not src._under(Path("/other"), Path("/a"), casefold=True)
    assert not src._under(None, Path("/a"), casefold=True)
    assert not src._under(Path("/a/b"), None, casefold=True)


def test_entry_targets_handles_empty_argv() -> None:
    assert src._entry_targets([]) == (None, None)
    assert src._entry_targets([""]) == (None, None)
