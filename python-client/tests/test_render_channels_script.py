"""Tests for scripts/cd/render_channels.py (CD glue, channel packaging)."""

from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "cd" / "render_channels.py"
sys.path.insert(0, str(_SCRIPT.parent))
_spec = importlib.util.spec_from_file_location("render_channels", _SCRIPT)
assert _spec and _spec.loader
render_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(render_mod)

_ROOT = _SCRIPT.parents[2]
_ASSETS = (
    "xrayvpn-0.4.1-linux-x64-portable",
    "xrayvpn-0.4.1-macos-arm64-portable",
    "xrayvpn-0.4.1-windows-x64-portable.exe",
)
_SUMS = "\n".join(
    f"{hashlib.sha256(name.encode()).hexdigest()}  {name}" for name in _ASSETS
)


def sha256sums(pkgbuild: str) -> list[str]:
    block = pkgbuild.split("sha256sums=(", 1)[1].split(")", 1)[0]
    return [line.strip().strip("'") for line in block.strip().splitlines()]


def test_normalized_version() -> None:
    assert render_mod.normalized_version("v0.4.1") == "0.4.1"
    assert render_mod.normalized_version("v0.4.1_experimental") == "0.4.1"


def test_normalized_version_rejects_plain_tag() -> None:
    with pytest.raises(SystemExit):
        render_mod.normalized_version("0.4.1")


def test_asset_name() -> None:
    assert render_mod.asset_name("0.4.1", "windows-x64") == (
        "xrayvpn-0.4.1-windows-x64-portable.exe"
    )
    assert render_mod.asset_name("0.4.1", "linux-x64") == "xrayvpn-0.4.1-linux-x64-portable"


def test_asset_name_rejects_unknown_token() -> None:
    with pytest.raises(SystemExit):
        render_mod.asset_name("0.4.1", "linux-arm64")


def test_parse_sums() -> None:
    sums = render_mod.parse_sums(_SUMS + "\n")
    expected = hashlib.sha256(_ASSETS[0].encode()).hexdigest()
    assert sums[_ASSETS[0]] == expected
    assert set(sums) == set(_ASSETS)


def test_require_asset_rejects_missing() -> None:
    sums = render_mod.parse_sums(_SUMS)
    del sums[_ASSETS[1]]
    with pytest.raises(SystemExit):
        render_mod.require_asset(sums, "0.4.1", "macos-arm64")


def test_substitute_rejects_unknown_placeholder() -> None:
    with pytest.raises(SystemExit):
        render_mod.substitute("{{Nope}}", {})


def test_print_winget_dir(capsys: pytest.CaptureFixture[str]) -> None:
    code = render_mod.main(["--print-winget-dir", "--tag", "v0.4.1", "--out", "build/channels"])
    assert code == 0
    printed = capsys.readouterr().out.strip()
    assert Path(printed) == Path("build/channels") / "winget" / "manifests" / "l" / (
        "Lifestreamy"
    ) / "XrayVpn" / "0.4.1"


def test_render_winget_set() -> None:
    sums = render_mod.parse_sums(_SUMS)
    files = render_mod.render_winget(_ROOT, "0.4.1", "v0.4.1", sums)
    base = Path("winget") / "manifests" / "l" / "Lifestreamy" / "XrayVpn" / "0.4.1"
    assert set(files) == {
        base / "Lifestreamy.XrayVpn.yaml",
        base / "Lifestreamy.XrayVpn.installer.yaml",
        base / "Lifestreamy.XrayVpn.locale.en-US.yaml",
        base / "Lifestreamy.XrayVpn.locale.ru-RU.yaml",
    }
    version = files[base / "Lifestreamy.XrayVpn.yaml"].decode()
    installer = files[base / "Lifestreamy.XrayVpn.installer.yaml"].decode()
    default_locale = files[base / "Lifestreamy.XrayVpn.locale.en-US.yaml"].decode()
    ru_locale = files[base / "Lifestreamy.XrayVpn.locale.ru-RU.yaml"].decode()
    assert "ManifestType: version" in version
    assert "PackageVersion: 0.4.1" in version
    assert "ManifestType: installer" in installer
    assert "Commands:\n- xrayvpn" in installer
    assert f"InstallerSha256: {sums[_ASSETS[2]]}" in installer
    assert "/releases/download/v0.4.1/xrayvpn-0.4.1-windows-x64-portable.exe" in installer
    assert "ManifestType: defaultLocale" in default_locale
    assert "ManifestType: locale" in ru_locale
    assert "PackageLocale: ru-RU" in ru_locale


def test_render_aur_uses_license_checksum(tmp_path: Path) -> None:
    sums = render_mod.parse_sums(_SUMS)
    license_file = tmp_path / "LICENSE"
    license_file.write_bytes(b"license text\n")
    digest = hashlib.sha256(b"license text\n").hexdigest()
    files = render_mod.render_aur(_ROOT, "0.4.1", "v0.4.1", sums, license_file)
    pkgbuild = files[Path("aur/PKGBUILD")].decode()
    assert "pkgver=0.4.1" in pkgbuild
    assert f"'{sums[_ASSETS[0]]}'" in pkgbuild
    assert "raw.githubusercontent.com/lifestreamy/xrayvpn/v0.4.1/LICENSE" in pkgbuild
    assert sha256sums(pkgbuild) == [sums[_ASSETS[0]], digest, "SKIP", "SKIP"]
    icon = _ROOT / "assets" / "icon" / "icon-preview.png"
    assert files[Path("aur/xrayvpn.png")] == icon.read_bytes()
    assert files[Path("aur/xrayvpn.desktop")].decode().startswith("[Desktop Entry]")


def test_render_aur_skips_missing_license() -> None:
    sums = render_mod.parse_sums(_SUMS)
    files = render_mod.render_aur(_ROOT, "0.4.1", "v0.4.1", sums, None)
    assert sha256sums(files[Path("aur/PKGBUILD")].decode())[1] == "SKIP"


def test_render_brew_formula() -> None:
    sums = render_mod.parse_sums(_SUMS)
    files = render_mod.render_brew(_ROOT, "0.4.1", "v0.4.1", sums)
    formula = files[Path("brew/xrayvpn.rb")].decode()
    assert f'sha256 "{sums[_ASSETS[1]]}"' in formula
    assert "/releases/download/v0.4.1/xrayvpn-0.4.1-macos-arm64-portable" in formula
    assert '\n  version "' not in formula


def test_rendered_text_files_are_lf_only() -> None:
    sums = render_mod.parse_sums(_SUMS)
    files = {
        **render_mod.render_winget(_ROOT, "0.4.1", "v0.4.1", sums),
        **render_mod.render_aur(_ROOT, "0.4.1", "v0.4.1", sums, None),
        **render_mod.render_brew(_ROOT, "0.4.1", "v0.4.1", sums),
    }
    for path, data in files.items():
        if path.suffix == ".png":
            continue
        assert b"\r\n" not in data, path
        assert b"{{" not in data, path
