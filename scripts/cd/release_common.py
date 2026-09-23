"""Shared helpers for the release and channel scripts (release tag and asset names)."""

from __future__ import annotations

PLATFORM_EXTENSIONS = {
    "windows-x64": ".exe",
    "linux-x64": "",
    "macos-arm64": "",
}


def normalized_version(tag: str) -> str:
    if not tag.startswith("v"):
        raise SystemExit(f"tag must start with 'v': {tag}")
    return tag.removeprefix("v").split("_", 1)[0]


def asset_name(version: str, token: str) -> str:
    if token not in PLATFORM_EXTENSIONS:
        raise SystemExit(f"unknown platform token: {token}")
    return f"xrayvpn-{version}-{token}-portable{PLATFORM_EXTENSIONS[token]}"


def asset_key(name: str, version: str = "") -> str:
    if name.endswith(".whl"):
        return "wheel"
    if name.endswith(".tar.gz"):
        return "sdist"
    stem = name.removeprefix("xrayvpn-")
    if version:
        stem = stem.removeprefix(f"{version}-")
    stem = stem.removesuffix(".exe")
    return stem.removesuffix("-portable")
