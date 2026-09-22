"""Single source of the binary payload contract (MYXRAY-30).

Nuitka data-flags and the PyInstaller spec consume the same staged tree produced
here, so both packagers ship the identical ``xrayvpn/payload`` contract. Staging
reuses the upload-manifest allowlist and never redefines it.
"""

from __future__ import annotations

import platform
import shutil
import sys
from pathlib import Path

CLIENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = CLIENT_DIR.parent
BUILD_DIR = CLIENT_DIR / "build"
STAGED_PAYLOAD_DIR = BUILD_DIR / "payload"

PAYLOAD_ROOT = "xrayvpn/payload"
PAYLOAD_ITEMS = ("roles", "config", "deploy.yml", "inventory.yml.example")

COMPANY_NAME = "korelov.dev"
PRODUCT_NAME = "xrayvpn"
ICON_ICO = REPO_ROOT / "assets" / "icon" / "windows" / "xrayvpn.ico"
FILE_DESCRIPTION = (
    "xrayvpn - Ansible-based toolkit that deploys VLESS REALITY VPN "
    "and generates Amnezia, Clash Verge and FlClash configs"
)
COPYRIGHT = "Copyright 2026 Tim Korelov"


def _manifest():
    src = CLIENT_DIR / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
    from xrayvpn.core import manifest

    return manifest


def stage_payload(dest: Path = STAGED_PAYLOAD_DIR, repo_root: Path = REPO_ROOT) -> Path:
    """Fresh copy of the allowlisted repo tree that binaries bundle."""
    manifest = _manifest()
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    for entry in manifest.allowlist_entries(repo_root):
        for member in manifest._iter_files(entry):
            rel = member.relative_to(repo_root)
            if manifest._should_skip(rel):
                continue
            target = dest / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(member, target)
    example = repo_root / "inventory.yml.example"
    if not example.is_file():
        raise RuntimeError(f"payload example missing: {example}")
    shutil.copy2(example, dest / example.name)
    return dest


def payload_map(staged: Path) -> list[tuple[Path, str]]:
    """Staged source -> payload arc for every required bundle item."""
    mapping: list[tuple[Path, str]] = []
    for name in PAYLOAD_ITEMS:
        source = staged / name
        if not source.exists():
            raise RuntimeError(f"staged payload item missing: {source}")
        mapping.append((source, f"{PAYLOAD_ROOT}/{name}"))
    return mapping


def platform_token(system: str | None = None, machine: str | None = None) -> str:
    osname = {
        "windows": "windows",
        "linux": "linux",
        "darwin": "macos",
    }.get((system or platform.system()).lower())
    arch = {
        "x86_64": "x64",
        "amd64": "x64",
        "aarch64": "arm64",
        "arm64": "arm64",
    }.get((machine or platform.machine()).lower())
    if osname is None or arch is None:
        raise RuntimeError(f"unsupported build platform: {system or platform.system()}/"
                           f"{machine or platform.machine()}")
    return f"{osname}-{arch}"


def artifact_name(version: str, system: str | None = None, machine: str | None = None) -> str:
    token = platform_token(system=system, machine=machine)
    ext = ".exe" if token.startswith("windows") else ""
    return f"{PRODUCT_NAME}-{version}-{token}-portable{ext}"
