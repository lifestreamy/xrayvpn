"""Payload-contract sentinels for the binary packagers (MYXRAY-30).

Both engines must bundle exactly the upload-manifest allowlist (+ example) under
``xrayvpn/payload``; these tests pin the golden arcs, staging hygiene and naming.
"""

from __future__ import annotations

import platform
import tomllib
import types
from pathlib import Path

import build_binary
import build_support
from xrayvpn.core import manifest

GOLDEN_ARCS = {
    "xrayvpn/payload/roles",
    "xrayvpn/payload/config",
    "xrayvpn/payload/deploy.yml",
    "xrayvpn/payload/inventory.yml.example",
}


def _expected_repo_files(repo_root: Path) -> set[str]:
    relative = {
        member.relative_to(repo_root).as_posix()
        for entry in manifest.allowlist_entries(repo_root)
        for member in manifest._iter_files(entry)
        if not manifest._should_skip(member.relative_to(repo_root))
    }
    relative.add("inventory.yml.example")
    return relative


def test_stage_payload_hygiene(tmp_path: Path) -> None:
    staged = build_support.stage_payload(tmp_path / "payload")
    got = {p.relative_to(staged).as_posix() for p in staged.rglob("*") if p.is_file()}
    assert got == _expected_repo_files(build_support.REPO_ROOT)
    top_level = {item.name for item in staged.iterdir()}
    assert top_level == {"roles", "config", "deploy.yml", "inventory.yml.example"}
    segments = {part for path in got for part in path.split("/")[:-1]}
    assert {s for s in segments if s in {"__pycache__", ".git"}} == set()
    assert "inventory.yml" not in {Path(path).name for path in got}
    assert not any(path.endswith((".pyc", ".retry")) for path in got)


def test_payload_map_is_golden(tmp_path: Path) -> None:
    staged = build_support.stage_payload(tmp_path / "payload")
    mapping = build_support.payload_map(staged)
    assert {arc for _, arc in mapping} == GOLDEN_ARCS
    assert all(source.exists() for source, _ in mapping)


def test_nuitka_flags_carry_golden_payload_and_metadata(tmp_path: Path) -> None:
    staged = build_support.stage_payload(tmp_path / "payload")
    ns = types.SimpleNamespace(mode="onefile")
    argv = build_binary.nuitka_args(ns, staged, "0.4.1", tmp_path / "out")
    data_arcs = {
        arg.rsplit("=", 1)[-1]
        for arg in argv
        if arg.startswith(("--include-data-dir=", "--include-data-files="))
    }
    assert data_arcs == GOLDEN_ARCS
    assert f"--onefile-tempdir-spec={build_binary.ONEFILE_TEMPDIR_SPEC}" in argv
    assert "--company-name=korelov.dev" in argv
    assert "--product-name=xrayvpn" in argv
    assert "--file-version=0.4.1" in argv and "--product-version=0.4.1" in argv
    assert f"--output-filename={build_support.artifact_name('0.4.1')}" in argv
    assert str(build_binary.ENTRY) in argv
    icon_flag = f"--windows-icon-from-ico={build_support.ICON_ICO}"
    expected = platform.system().lower() == "windows" and build_support.ICON_ICO.is_file()
    assert (icon_flag in argv) is expected


def test_engines_share_single_payload_source() -> None:
    spec = (build_support.CLIENT_DIR / "xrayvpn.spec").read_text(encoding="utf-8")
    assert "stage_payload" in spec and "payload_map" in spec
    assert "ICON_ICO" in spec and "icon=" in spec
    driver = (build_support.CLIENT_DIR / "build_binary.py").read_text(encoding="utf-8")
    assert "stage_payload" in driver and "payload_map" in driver
    assert spec.count("xrayvpn/payload") == 0 and driver.count("xrayvpn/payload") == 0


def test_platform_tokens_and_artifact_names() -> None:
    assert build_support.platform_token("Windows", "AMD64") == "windows-x64"
    assert build_support.artifact_name("0.4.1", "Windows", "AMD64") == (
        "xrayvpn-0.4.1-windows-x64-portable.exe"
    )
    assert build_support.artifact_name("0.4.1", "Linux", "aarch64") == (
        "xrayvpn-0.4.1-linux-arm64-portable"
    )
    assert build_support.artifact_name("0.4.1", "Linux", "x86_64") == (
        "xrayvpn-0.4.1-linux-x64-portable"
    )
    assert build_support.artifact_name("0.4.1", "Darwin", "arm64") == (
        "xrayvpn-0.4.1-macos-arm64-portable"
    )
    try:
        build_support.platform_token("FreeBSD", "riscv")
    except RuntimeError as exc:
        assert "unsupported" in str(exc)
    else:
        raise AssertionError("unsupported platform must raise")


def test_build_group_is_pinned() -> None:
    data = tomllib.loads(
        (build_support.CLIENT_DIR / "pyproject.toml").read_text(encoding="utf-8")
    )
    group = data["dependency-groups"]["build"]
    assert any(pin.startswith("nuitka==") for pin in group)
    assert any(pin.lower().startswith("pyinstaller==") for pin in group)


def test_build_wrappers_exist() -> None:
    ps1 = (build_support.CLIENT_DIR / "build-binary.ps1").read_text(encoding="utf-8")
    sh = (build_support.CLIENT_DIR / "build-binary.sh").read_text(encoding="utf-8")
    assert "build_binary.py" in ps1 and "build_binary.py" in sh
    assert "--group" in ps1 and "--group" in sh and "build" in sh.split("--group")[1][:20]
