"""Settings loading plus deploy constants (PyYAML + pathlib, no regex).

Single source for the ansible-core pin, server-side paths and galaxy names;
CI pins are cross-checked by tests/test_config_constants.py.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from xrayvpn.core.runtime_paths import require_repo_root

ANSIBLE_CORE_PIN = "2.21.3"
ANSIBLE_VENV_APT_PKG = "python3-venv"
GALAXY_COLLECTION = "community.general"
GALAXY_COLLECTION_DIR = "ansible_collections/" + GALAXY_COLLECTION.replace(".", "/")

SERVER_VENV = "/opt/xrayvpn-venv"
# Staging lives in /tmp: the SFTP user must be able to write it (a non-root
# SSH user cannot write /opt). The playbook itself runs with become anyway.
SERVER_STAGING = "/tmp/xrayvpn"
SERVER_COLLECTIONS = f"{SERVER_VENV}/collections"
CONFIG_SOURCE = "/root/vpn-configs"

SWAPFILE = "/swapfile"
SWAP_GUARD_MIN_RAM_KB = 1024 * 1024

# Staging must be private (fresh mktemp per run, 0700, removed at the end):
# a fixed world-readable /tmp dir would leak generated client credentials on
# multi-user VPSes and survive the deploy silently.
SERVER_FETCH_PREFIX = "xrayvpn-fetch."
DEFAULT_WSL_VENV = "~/xray-venv"
COLLECTIONS_DIR = "xrayvpn-collections"
SSH_ARGS = "-o StrictHostKeyChecking=accept-new"

SETTINGS_FILE = "config/settings.yml"

find_repo_root = require_repo_root


def load_settings(repo_root: Path) -> dict[str, Any]:
    """Load config/settings.yml as a dict; errors are explicit."""
    settings_path = repo_root / SETTINGS_FILE
    if not settings_path.is_file():
        raise RuntimeError(f"settings file not found: {settings_path}")
    with settings_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise TypeError(f"settings file must contain a YAML mapping: {settings_path}")
    return data


def merge_overrides(settings: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    """Shallow merge; `overrides` win over `settings`."""
    merged = dict(settings)
    merged.update(overrides)
    return merged