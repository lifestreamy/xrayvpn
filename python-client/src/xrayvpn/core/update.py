"""Release discovery for the explicit `xrayvpn update` path.

The banner hint in `update_check` stays fail-silent and 2s-bounded; the
explicit command must surface failures instead, so this module raises
`UpdateError`. Discovery uses the GitHub releases API (stable releases by
default) plus the per-release `latest.json` asset the release pipeline
publishes with `{name, url, sha256}` per platform. Parsers are pure and
network access is injectable.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Any

from xrayvpn.core import install_source, update_check

STANDALONE = install_source.STANDALONE
DEV = install_source.DEV
UV_TOOL = install_source.UV_TOOL
PIPX = install_source.PIPX
PIP = install_source.PIP
PIP_DIRECT = install_source.PIP_DIRECT
BREW = install_source.BREW
APT = install_source.APT
PACMAN = install_source.PACMAN
WINGET = install_source.WINGET
UNKNOWN = install_source.UNKNOWN

RELEASES_API_URL = f"https://api.github.com/repos/{update_check.RELEASE_OWNER_REPO}/releases"
RELEASE_DOWNLOAD_BASE = f"https://github.com/{update_check.RELEASE_OWNER_REPO}/releases/download"

LATEST_JSON_NAME = "latest.json"
SUMS_NAME = "SHA256SUMS.txt"
NETWORK_TIMEOUT_SECONDS = 10.0
LIST_LIMIT_DEFAULT = 10
LIST_LIMIT_MAX = 20
SHA256_HEX_LENGTH = 64
DOWNLOAD_MAX_BYTES = 512 * 1024 * 1024
DOWNLOAD_CHUNK_BYTES = 256 * 1024
STAGING_SUFFIX = ".new"
BACKUP_SUFFIX = ".old"
STATUS_UPDATED = "updated"
STATUS_UP_TO_DATE = "up-to-date"

PLATFORM_TOKENS = {
    ("win32", "x86_64"): "windows-x64",
    ("win32", "amd64"): "windows-x64",
    ("linux", "x86_64"): "linux-x64",
    ("linux", "amd64"): "linux-x64",
    ("linux", "aarch64"): "linux-arm64",
    ("linux", "arm64"): "linux-arm64",
    ("darwin", "arm64"): "macos-arm64",
    ("darwin", "aarch64"): "macos-arm64",
}


class UpdateError(RuntimeError):
    """Explicit update-path failure (network, HTTP status, malformed data)."""


@dataclass(frozen=True)
class Release:
    tag: str
    version: str
    prerelease: bool
    published_at: str
    html_url: str


@dataclass(frozen=True)
class Asset:
    name: str
    url: str
    sha256: str


def http_get(url: str, *, timeout: float = NETWORK_TIMEOUT_SECONDS) -> bytes:
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "xrayvpn-update"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return bytes(response.read())
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise UpdateError(f"network error for {url}: {exc}") from exc


def normalize_tag(tag: str) -> str:
    return tag.strip().lstrip("vV").split("_")[0].split("+")[0].split("-")[0]


def parse_release(payload: Mapping[str, Any]) -> Release | None:
    if payload.get("draft"):
        return None
    tag = str(payload.get("tag_name") or "").strip()
    if not tag:
        return None
    return Release(
        tag=tag,
        version=normalize_tag(tag),
        prerelease=bool(payload.get("prerelease")),
        published_at=str(payload.get("published_at") or ""),
        html_url=str(payload.get("html_url") or ""),
    )


def parse_releases(payload: Any, *, include_prerelease: bool = False) -> list[Release]:
    if not isinstance(payload, list):
        raise UpdateError("malformed releases payload")
    releases: list[Release] = []
    for item in payload:
        if not isinstance(item, Mapping):
            continue
        release = parse_release(item)
        if release is None or (release.prerelease and not include_prerelease):
            continue
        releases.append(release)
    return releases


def parse_sums(text: str) -> dict[str, str]:
    sums: dict[str, str] = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) != 2:
            continue
        digest, name = parts[0].strip().lower(), parts[1].strip().lstrip("*")
        if len(digest) != SHA256_HEX_LENGTH or not name:
            continue
        try:
            int(digest, 16)
        except ValueError:
            continue
        sums.setdefault(name, digest)
    return sums


def parse_latest_json(payload: Any) -> dict[str, Asset]:
    if not isinstance(payload, Mapping):
        raise UpdateError("malformed latest.json payload")
    raw_assets = payload.get("assets")
    if not isinstance(raw_assets, Mapping):
        raise UpdateError("latest.json has no assets map")
    assets: dict[str, Asset] = {}
    for token, entry in raw_assets.items():
        if not isinstance(entry, Mapping):
            continue
        name = str(entry.get("name") or "").strip()
        url = str(entry.get("url") or "").strip()
        sha256 = str(entry.get("sha256") or "").strip().lower()
        if not name or not url or len(sha256) != SHA256_HEX_LENGTH:
            continue
        assets[str(token)] = Asset(name=name, url=url, sha256=sha256)
    if not assets:
        raise UpdateError("latest.json lists no usable assets")
    return assets


def platform_token(platform: str, machine: str) -> str | None:
    return PLATFORM_TOKENS.get((platform.lower(), machine.lower()))


def select_asset(assets: Mapping[str, Asset], *, platform: str, machine: str) -> Asset | None:
    token = platform_token(platform, machine)
    if token is None:
        return None
    return assets.get(token)


def release_download_url(tag: str, name: str) -> str:
    return f"{RELEASE_DOWNLOAD_BASE}/{tag}/{name}"


def fetch_releases(
    *,
    http: Callable[[str], bytes] | None = None,
    per_page: int = 100,
    page: int = 1,
) -> list[Release]:
    get = http or http_get
    url = f"{RELEASES_API_URL}?per_page={int(per_page)}&page={int(page)}"
    return parse_releases(_read_json(get, url), include_prerelease=True)


def fetch_latest_release(*, http: Callable[[str], bytes] | None = None) -> Release | None:
    get = http or http_get
    payload = _read_json(get, update_check.RELEASES_LATEST_API_URL)
    if not isinstance(payload, Mapping):
        raise UpdateError("malformed latest release payload")
    return parse_release(payload)


def list_versions(
    *,
    limit: int = LIST_LIMIT_DEFAULT,
    include_prerelease: bool = False,
    http: Callable[[str], bytes] | None = None,
) -> list[Release]:
    bound = max(1, min(int(limit), LIST_LIMIT_MAX))
    releases = fetch_releases(http=http)
    visible = [release for release in releases if include_prerelease or not release.prerelease]
    return visible[:bound]


def fetch_latest_json(
    tag: str,
    *,
    http: Callable[[str], bytes] | None = None,
) -> dict[str, Asset]:
    get = http or http_get
    url = release_download_url(tag, LATEST_JSON_NAME)
    return parse_latest_json(_read_json(get, url))


def fetch_sums(
    tag: str,
    *,
    http: Callable[[str], bytes] | None = None,
) -> dict[str, str]:
    get = http or http_get
    url = release_download_url(tag, SUMS_NAME)
    raw = _get(get, url)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise UpdateError(f"non-UTF-8 checksum file from {url}") from exc
    return parse_sums(text)


def _get(http: Callable[[str], bytes], url: str) -> bytes:
    try:
        return http(url)
    except UpdateError:
        raise
    except Exception as exc:
        raise UpdateError(f"network error for {url}: {exc}") from exc


def _read_json(http: Callable[[str], bytes], url: str) -> Any:
    raw = _get(http, url)
    try:
        return json.loads(raw)
    except ValueError as exc:
        raise UpdateError(f"malformed JSON from {url}") from exc


def open_url_stream(url: str) -> IO[bytes]:
    request = urllib.request.Request(url, headers={"User-Agent": "xrayvpn-update"})
    try:
        return urllib.request.urlopen(request, timeout=NETWORK_TIMEOUT_SECONDS)
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise UpdateError(f"network error for {url}: {exc}") from exc


def cross_check_sums(name: str, sha256: str, sums: Mapping[str, str]) -> None:
    expected = sums.get(name)
    if expected is None:
        raise UpdateError(f"{name} is not listed in {SUMS_NAME}")
    if expected != sha256:
        raise UpdateError(f"checksum mismatch for {name}: {SUMS_NAME} has {expected}")


def download_asset(
    url: str,
    dest: Path,
    *,
    expected_sha256: str,
    opener: Callable[[str], IO[bytes]] | None = None,
    max_bytes: int = DOWNLOAD_MAX_BYTES,
    chunk_size: int = DOWNLOAD_CHUNK_BYTES,
) -> str:
    open_stream = opener or open_url_stream
    digest = hashlib.sha256()
    written = 0
    try:
        with open_stream(url) as source, dest.open("wb") as sink:
            while True:
                chunk = source.read(chunk_size)
                if not chunk:
                    break
                written += len(chunk)
                if written > max_bytes:
                    raise UpdateError(f"download exceeds {max_bytes} bytes")
                digest.update(chunk)
                sink.write(chunk)
    except UpdateError:
        dest.unlink(missing_ok=True)
        raise
    except OSError as exc:
        dest.unlink(missing_ok=True)
        raise UpdateError(f"download failed for {url}: {exc}") from exc
    actual = digest.hexdigest()
    if actual != expected_sha256:
        dest.unlink(missing_ok=True)
        raise UpdateError(f"checksum mismatch for {url}: got {actual}")
    return actual


def backup_path(target: Path) -> Path:
    return target.with_name(target.name + BACKUP_SUFFIX)


def cleanup_backup(target: Path) -> bool:
    try:
        backup_path(target).unlink()
    except FileNotFoundError:
        return True
    except OSError:
        return False
    return True


def swap_in_place(staged: Path, target: Path) -> Path:
    """Rename-then-replace; a running image can be renamed on Windows."""
    backup = backup_path(target)
    cleanup_backup(target)
    try:
        os.replace(target, backup)
    except OSError as exc:
        raise UpdateError(
            f"cannot move {target} aside (another instance may be running): {exc}"
        ) from exc
    try:
        os.replace(staged, target)
    except OSError as exc:
        try:
            os.replace(backup, target)
        except OSError:
            pass
        raise UpdateError(f"cannot install the new binary: {exc}") from exc
    return backup


def relaunch(target: Path, *, spawner: Callable[[list[str]], Any] | None = None) -> None:
    spawn = spawner or subprocess.Popen
    try:
        spawn([str(target)])
    except OSError as exc:
        raise UpdateError(f"cannot restart {target}: {exc}") from exc


@dataclass(frozen=True)
class UpdateOutcome:
    status: str
    version: str
    target: Path
    backup: Path | None = None


def perform_standalone_update(
    target: Path,
    *,
    current: str,
    platform: str,
    machine: str,
    requested_version: str | None = None,
    http: Callable[[str], bytes] | None = None,
    opener: Callable[[str], IO[bytes]] | None = None,
) -> UpdateOutcome:
    if not target.is_file():
        raise UpdateError(f"target binary not found: {target}")
    parent = target.parent
    if not os.access(parent, os.W_OK):
        raise UpdateError(
            f"no write access to {parent}: the install directory must be user-writable"
        )

    release = _resolve_release(requested_version, http=http)
    if requested_version is None and not update_check.is_newer(release.tag, current):
        return UpdateOutcome(STATUS_UP_TO_DATE, release.version, target)

    assets = fetch_latest_json(release.tag, http=http)
    asset = select_asset(assets, platform=platform, machine=machine)
    if asset is None:
        raise UpdateError(f"release {release.tag} has no build for {platform}/{machine}")
    sums = fetch_sums(release.tag, http=http)
    cross_check_sums(asset.name, asset.sha256, sums)

    staged = target.with_name(target.name + STAGING_SUFFIX)
    staged.unlink(missing_ok=True)
    download_asset(asset.url, staged, expected_sha256=asset.sha256, opener=opener)
    try:
        staged.chmod(0o755)
        backup = swap_in_place(staged, target)
    except Exception:
        staged.unlink(missing_ok=True)
        raise
    return UpdateOutcome(STATUS_UPDATED, release.version, target, backup)


def _resolve_release(
    requested_version: str | None,
    *,
    http: Callable[[str], bytes] | None = None,
) -> Release:
    if requested_version:
        plain = requested_version.strip()
        wanted_tags = {plain, f"v{plain.lstrip('vV')}"}
        wanted_versions = {normalize_tag(plain)}
        for release in fetch_releases(http=http):
            if release.tag in wanted_tags or release.version in wanted_versions:
                return release
        raise UpdateError(f"release {requested_version} not found")
    release = fetch_latest_release(http=http)
    if release is None:
        raise UpdateError("no stable release found")
    return release


MANAGER_TIMEOUT_SECONDS = 1800.0
EXECUTABLE_KINDS = frozenset({UV_TOOL, PIPX})

_MANAGER_COMMANDS: dict[str, tuple[tuple[str, ...], ...]] = {
    UV_TOOL: (("uv", "tool", "upgrade", "xrayvpn"),),
    PIPX: (("pipx", "upgrade", "xrayvpn"),),
    PIP: (("python", "-m", "pip", "install", "--upgrade", "xrayvpn"),),
    BREW: (("brew", "upgrade", "xrayvpn"),),
    APT: (
        ("sudo", "apt", "update"),
        ("sudo", "apt", "install", "--only-upgrade", "xrayvpn"),
    ),
    WINGET: (("winget", "upgrade", "--id", "Lifestreamy.XrayVpn", "--exact", "--source", "winget"),),
    PACMAN: (("yay", "-S", "xrayvpn-bin"),),
}

_PIN_HINTS = {
    PIP: 'python -m pip install "xrayvpn=={version}"',
    UV_TOOL: "uv tool install xrayvpn=={version}",
    PIPX: 'pipx install --force "xrayvpn=={version}"',
    BREW: "brew pin xrayvpn",
    APT: "sudo apt install xrayvpn={version} && sudo apt-mark hold xrayvpn",
    WINGET: "winget pin add --id Lifestreamy.XrayVpn --version {version}",
    PACMAN: "yay -S xrayvpn-bin",
}


@dataclass(frozen=True)
class ManagerPlan:
    kind: str
    commands: tuple[tuple[str, ...], ...]
    executable: bool


def manager_plan(kind: str) -> ManagerPlan | None:
    commands = _MANAGER_COMMANDS.get(kind)
    if commands is None:
        return None
    return ManagerPlan(kind=kind, commands=commands, executable=kind in EXECUTABLE_KINDS)


def pin_hint(kind: str, version: str) -> str | None:
    template = _PIN_HINTS.get(kind)
    if template is None:
        return None
    return template.format(version=version)


def run_manager_command(
    kind: str,
    command: Sequence[str],
    *,
    runner: Callable[[list[str]], Any] | None = None,
    timeout: float = MANAGER_TIMEOUT_SECONDS,
) -> int:
    if kind not in EXECUTABLE_KINDS:
        raise UpdateError(f"refusing to run {kind} commands automatically")
    run = runner or subprocess.run
    try:
        result = run(list(command), check=False, timeout=timeout)
    except (OSError, subprocess.SubprocessError) as exc:
        raise UpdateError(f"manager command failed: {' '.join(command)}: {exc}") from exc
    return int(getattr(result, "returncode", 1))
