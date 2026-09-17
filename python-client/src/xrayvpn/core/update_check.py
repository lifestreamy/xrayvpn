"""Update-available hint (v0.4.1: hint only, no self-update).

Checks the GitHub `releases/latest` API (which excludes pre-releases and
drafts, so pre-experimental tags never chatter), prints a pointer to the
release page under the REPL banner and after `--version`. Fail-silent by
design; a 24h disk cache keeps double-click launches off the network (the
wall-clock bound also covers DNS stalls); kill-switch
`XRAYVPN_UPDATE_CHECK=0`, explicit `=1` also enables it in dev clones.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
import time
import urllib.request
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from xrayvpn import __version__, i18n

RELEASE_OWNER_REPO = "lifestreamy/xrayvpn"
PROFILE_URL = "https://github.com/lifestreamy"
REPO_URL = f"https://github.com/{RELEASE_OWNER_REPO}"
RELEASES_LATEST_API_URL = f"https://api.github.com/repos/{RELEASE_OWNER_REPO}/releases/latest"
LATEST_RELEASE_PAGE = f"https://github.com/{RELEASE_OWNER_REPO}/releases/latest"
CHECK_TIMEOUT_SECONDS = 2.0
CACHE_TTL_SECONDS = 24 * 3600
CACHE_FILENAME = "xrayvpn-update-check.json"
KILL_SWITCH_ENV = "XRAYVPN_UPDATE_CHECK"


def http_get(url: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "xrayvpn-update-check",
        },
    )
    with urllib.request.urlopen(request, timeout=CHECK_TIMEOUT_SECONDS) as response:
        return bytes(response.read())


def fetch_latest_tag(
    *,
    http: Callable[[str], bytes] | None = None,
    url: str = RELEASES_LATEST_API_URL,
    timeout: float = CHECK_TIMEOUT_SECONDS,
) -> str | None:
    """Silent; runs in a daemon thread so the wall-clock bound also covers DNS."""
    get = http or http_get
    outcome: dict[str, str | None] = {}

    def work() -> None:
        try:
            data: Any = json.loads(get(url))
        except Exception:  # noqa: BLE001 - any transport/API failure stays silent
            outcome["tag"] = None
            return
        tag = str(data.get("tag_name") or "").strip() if isinstance(data, dict) else ""
        outcome["tag"] = tag or None

    worker = threading.Thread(target=work, daemon=True)
    worker.start()
    worker.join(timeout)
    return outcome.get("tag")


def _core_version(text: str) -> tuple[int, ...] | None:
    core = text.strip().lstrip("vV").split("_")[0].split("+")[0].split("-")[0]
    parts = core.split(".")
    if len(parts) < 2 or len(parts) > 3:
        return None
    try:
        numbers = [int(part) for part in parts]
    except ValueError:
        return None
    while len(numbers) < 3:
        numbers.append(0)
    return tuple(numbers)


def is_newer(latest_tag: str, current: str) -> bool:
    """stdlib semantic compare on numeric cores (ma[.min][.patch])."""
    latest = _core_version(latest_tag)
    now = _core_version(current)
    if latest is None or now is None:
        return False
    return latest > now


def check_enabled(*, packaged: bool, env: Mapping[str, str] | None = None) -> bool:
    environment = os.environ if env is None else env
    switch = (environment.get(KILL_SWITCH_ENV) or "").strip()
    if switch == "0":
        return False
    return packaged or switch == "1"


def _cache_path() -> Path:
    return Path(tempfile.gettempdir()) / CACHE_FILENAME


def _cached_tag(path: Path, now: float) -> tuple[bool, str | None]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        age = now - float(raw["checked_at"])
    except (OSError, ValueError, TypeError, KeyError):
        return False, None
    if not isinstance(raw, dict) or age > CACHE_TTL_SECONDS or age < 0:
        return False, None
    tag = str(raw.get("tag") or "").strip()
    return True, tag or None


def _store_tag(path: Path, tag: str | None, now: float) -> None:
    try:
        path.write_text(json.dumps({"checked_at": now, "tag": tag}), encoding="utf-8")
    except OSError:
        pass


def banner_hint(
    *,
    packaged: bool,
    env: Mapping[str, str] | None = None,
    current: str = __version__,
    fetch: Callable[[], str | None] | None = None,
    cache_path: Path | None = None,
    now: float | None = None,
) -> str | None:
    """One-line user hint, or None when disabled/silent/no update (24h cached)."""
    if not check_enabled(packaged=packaged, env=env):
        return None
    cache = Path(cache_path) if cache_path is not None else _cache_path()
    moment = time.time() if now is None else now
    fresh, tag = _cached_tag(cache, moment)
    if not fresh:
        tag = (fetch or fetch_latest_tag)()
        _store_tag(cache, tag, moment)
    if not tag or not is_newer(tag, current):
        return None
    return i18n.t("EXEC_UPDATE_AVAILABLE", tag=tag, page=LATEST_RELEASE_PAGE)
