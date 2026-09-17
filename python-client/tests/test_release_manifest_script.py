"""Tests for scripts/ci/make_release_manifest.py (CI glue, MYXRAY-31)."""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "ci" / "make_release_manifest.py"
_spec = importlib.util.spec_from_file_location("make_release_manifest", _SCRIPT)
assert _spec and _spec.loader
manifest_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(manifest_mod)


def test_asset_key_mapping() -> None:
    key = manifest_mod.asset_key
    assert key("xrayvpn-0.4.1-windows-x64-portable.exe", "0.4.1") == "windows-x64"
    assert key("xrayvpn-0.4.1-linux-arm64-portable", "0.4.1") == "linux-arm64"
    assert key("xrayvpn-0.4.1-macos-arm64-portable", "0.4.1") == "macos-arm64"
    assert key("xrayvpn_client-0.4.1-py3-none-any.whl", "0.4.1") == "wheel"
    assert key("xrayvpn_client-0.4.1.tar.gz", "0.4.1") == "sdist"
    assert key("xrayvpn-windows-x64.exe") == "windows-x64"


def test_normalized_version() -> None:
    assert manifest_mod.normalized_version("v0.4.1_experimental") == "0.4.1"
    assert manifest_mod.normalized_version("v0.4.1") == "0.4.1"


def test_build_manifest_urls_and_hashes(tmp_path: Path) -> None:
    (tmp_path / "xrayvpn-0.4.1-windows-x64-portable.exe").write_bytes(b"win")
    (tmp_path / "xrayvpn_client-0.4.1-py3-none-any.whl").write_bytes(b"whl")
    manifest = manifest_mod.build_manifest(
        "lifestreamy/xrayvpn", "v0.4.1_experimental", tmp_path
    )
    assert manifest["version"] == "0.4.1"
    assets = manifest["assets"]
    assert set(assets) == {"windows-x64", "wheel"}
    win = assets["windows-x64"]
    assert win["url"].endswith(
        "/releases/download/v0.4.1_experimental/xrayvpn-0.4.1-windows-x64-portable.exe"
    )
    assert win["sha256"] == hashlib.sha256(b"win").hexdigest()
    assert "releases/tag/v0.4.1_experimental" in manifest["release_url"]
