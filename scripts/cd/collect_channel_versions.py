"""Collect the live version of each publishing channel and of the latest release.

Consumed by the badges pipeline: queries the public sources (the GitHub Releases
API, PyPI JSON, the tap formula, the apt package index), prints a JSON map of the
channel versions and optionally writes it to --out for render_badges.py and
bump_readme_badge_queries.py. A source that cannot answer yields null; the run
itself always succeeds.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request
from collections.abc import Callable
from pathlib import Path

from release_common import normalized_version

Fetch = Callable[[str, dict[str, str]], str]

REPO = "lifestreamy/xrayvpn"
USER_AGENT = "xrayvpn-badges"
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
BREW_URL_RE = re.compile(r"releases/download/v(\d+\.\d+\.\d+)/")

SOURCES = {
    "release": f"https://api.github.com/repos/{REPO}/releases/latest",
    "pip": "https://pypi.org/pypi/xrayvpn/json",
    "brew": "https://raw.githubusercontent.com/lifestreamy/homebrew-tap/main/Formula/xrayvpn.rb",
    "apt": "https://lifestreamy.github.io/xrayvpn/apt/dists/noble/main/binary-amd64/Packages",
}
ORDER = ("release", "pip", "uv", "brew", "apt")


def http_get(url: str, headers: dict[str, str]) -> str:
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


def _valid(value: object) -> str | None:
    return value if isinstance(value, str) and VERSION_RE.match(value) else None


def parse_release(payload: str) -> str | None:
    tag = json.loads(payload).get("tag_name") or ""
    try:
        return _valid(normalized_version(tag))
    except SystemExit:
        return None


def parse_pypi(payload: str) -> str | None:
    return _valid(json.loads(payload)["info"]["version"])


def parse_brew(payload: str) -> str | None:
    match = BREW_URL_RE.search(payload)
    return match.group(1) if match else None


def parse_apt(payload: str) -> str | None:
    for block in payload.replace("\r\n", "\n").split("\n\n"):
        fields: dict[str, str] = {}
        for line in block.splitlines():
            key, sep, value = line.partition(": ")
            if sep:
                fields[key] = value
        if fields.get("Package") == "xrayvpn":
            return _valid(fields.get("Version"))
    return None


PARSERS: dict[str, Callable[[str], str | None]] = {
    "release": parse_release,
    "pip": parse_pypi,
    "brew": parse_brew,
    "apt": parse_apt,
}


def _collect_one(key: str, fetch: Fetch) -> str | None:
    headers = {"User-Agent": USER_AGENT}
    if key == "release":
        headers["Accept"] = "application/vnd.github+json"
        token = os.environ.get("GITHUB_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"
    try:
        version = PARSERS[key](fetch(SOURCES[key], headers))
    except (OSError, ValueError, KeyError, TypeError, AttributeError, SystemExit) as error:
        print(f"warning: {key}: {error}", file=sys.stderr)
        return None
    if version is None:
        print(f"warning: {key}: no version found", file=sys.stderr)
    return version


def collect_versions(fetch: Fetch | None = None) -> dict[str, str | None]:
    fetcher = fetch or http_get
    versions: dict[str, str | None] = {key: _collect_one(key, fetcher) for key in PARSERS}
    versions["uv"] = versions["pip"]
    return {key: versions[key] for key in ORDER}


def main(argv: list[str] | None = None, fetch: Fetch | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, help="also write the JSON here, e.g. build/versions.json")
    args = parser.parse_args(argv)
    versions = collect_versions(fetch=fetch)
    text = json.dumps(versions, indent=2, ensure_ascii=False) + "\n"
    print(text, end="")
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8", newline="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
