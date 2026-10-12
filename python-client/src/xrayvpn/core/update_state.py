"""Persistent update state (skip-version) in the per-user state folder.

`banner_hint` must stay fail-silent, so every read is tolerant: a missing,
unreadable or malformed state file behaves like "no state". Writes are
atomic (temp file + replace) and report success instead of raising.
"""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Mapping
from pathlib import Path

from xrayvpn.core import runtime_paths

STATE_FILENAME = "update-state.json"
STATE_DIR_ENV = "XRAYVPN_STATE_DIR"
SKIPPED_VERSION_KEY = "skipped_version"


def normalize_tag(tag: str) -> str:
    return tag.strip().lstrip("vV").split("_")[0].split("+")[0].split("-")[0]


def default_state_path(
    *,
    env: Mapping[str, str] | None = None,
    home: Path | None = None,
    platform: str | None = None,
) -> Path:
    environment = os.environ if env is None else env
    override = (environment.get(STATE_DIR_ENV) or "").strip()
    if override:
        return Path(override).expanduser() / STATE_FILENAME
    return runtime_paths.state_workspace(env=environment, home=home, platform=platform) / (
        STATE_FILENAME
    )


def read_state(path: Path) -> dict[str, object]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(raw, dict):
        return {}
    return raw


def write_state(path: Path, data: Mapping[str, object]) -> bool:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        handle, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".")
    except OSError:
        return False
    tmp = Path(tmp_name)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(dict(data), stream, ensure_ascii=False)
        os.replace(tmp, path)
    except OSError:
        tmp.unlink(missing_ok=True)
        return False
    return True


def skipped_version(path: Path) -> str | None:
    value = read_state(path).get(SKIPPED_VERSION_KEY)
    if not isinstance(value, str):
        return None
    return normalize_tag(value) or None


def skip_version(path: Path, version: str) -> bool:
    data = read_state(path)
    data[SKIPPED_VERSION_KEY] = normalize_tag(version)
    return write_state(path, data)


def clear_skip(path: Path) -> bool:
    data = read_state(path)
    data.pop(SKIPPED_VERSION_KEY, None)
    return write_state(path, data)
