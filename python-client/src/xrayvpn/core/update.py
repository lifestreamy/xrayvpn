"""Release discovery for the explicit `xrayvpn update` path.

The banner hint in `update_check` stays fail-silent and 2s-bounded; the
explicit command must surface failures instead, so this module raises
`UpdateError`. Discovery uses the GitHub releases API (stable releases by
default) plus the per-release `latest.json` asset the release pipeline
publishes with `{name, url, sha256}` per platform. Parsers are pure and
network access is injectable.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from xrayvpn.core import update_check

RELEASES_API_URL = f"https://api.github.com/repos/{update_check.RELEASE_OWNER_REPO}/releases"
RELEASE_DOWNLOAD_BASE = f"https://github.com/{update_check.RELEASE_OWNER_REPO}/releases/download"

LATEST_JSON_NAME = "latest.json"
SUMS_NAME = "SHA256SUMS.txt"
NETWORK_TIMEOUT_SECONDS = 10.0
LIST_LIMIT_DEFAULT = 10
LIST_LIMIT_MAX = 20
SHA256_HEX_LENGTH = 64

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
