"""Write latest.json for the release assets (MYXRAY-31; used by the CI job).

The future self-update command consumes {version, date, release_url,
assets{platform:{name,url,sha256}}}; this tag runs right after the artifacts
were downloaded, so hashes are recomputed from bytes, not trusted from files.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path


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


def normalized_version(tag: str) -> str:
    version = tag.removeprefix("v")
    return version.split("_", 1)[0]


def build_manifest(release: str, tag: str, directory: Path) -> dict[str, object]:
    names = sorted(
        p.name
        for p in directory.iterdir()
        if p.name.startswith(("xrayvpn-", "xrayvpn_")) and not p.name.endswith(".deb")
    )
    if not names:
        raise SystemExit("no xrayvpn release assets found to describe")
    version = normalized_version(tag)
    assets = {
        asset_key(name, version): {
            "name": name,
            "url": f"https://github.com/{release}/releases/download/{tag}/{name}",
            "sha256": hashlib.sha256((directory / name).read_bytes()).hexdigest(),
        }
        for name in names
    }
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "version": version,
        "date": stamp,
        "release_url": f"https://github.com/{release}/releases/tag/{tag}",
        "assets": assets,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", type=Path, default=Path("."))
    parser.add_argument("--release", required=True)
    parser.add_argument("--tag", required=True)
    args = parser.parse_args()
    manifest = build_manifest(args.release, args.tag, args.dir)
    (args.dir / "latest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
