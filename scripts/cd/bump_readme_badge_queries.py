"""Set the ?v= cache-buster of each README badge to that badge's live version.

Consumed by the badges pipeline after render_badges.py: for the five channel badges
(release, brew, apt, pip, uv) it replaces the ?v= value in the READMEs with the
version collected from the channel; badges without a known version are left
untouched.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

BADGES = {
    "release": "release.svg",
    "brew": "brew.svg",
    "apt": "apt.svg",
    "pip": "pip.svg",
    "uv": "uv.svg",
}
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")


def load_versions(path: Path) -> dict[str, str | None]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise SystemExit(f"versions JSON must be an object: {path}")
    versions: dict[str, str | None] = {}
    for key in BADGES:
        value = raw.get(key)
        versions[key] = value if isinstance(value, str) and VERSION_RE.match(value) else None
    return versions


def bump_text(text: str, versions: dict[str, str | None]) -> str:
    for key, name in BADGES.items():
        version = versions.get(key)
        if not (isinstance(version, str) and VERSION_RE.match(version)):
            continue
        pattern = re.compile(rf"(assets/badges/{re.escape(name)}\?v=)\d+\.\d+\.\d+")
        text = pattern.sub(rf"\g<1>{version}", text)
    return text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--versions-json", type=Path, required=True)
    parser.add_argument("readmes", nargs="+", type=Path)
    args = parser.parse_args(argv)
    versions = load_versions(args.versions_json)
    for path in args.readmes:
        with path.open(encoding="utf-8", newline="") as handle:
            text = handle.read()
        updated = bump_text(text, versions)
        if updated == text:
            print(f"unchanged {path}")
            continue
        with path.open("w", encoding="utf-8", newline="") as handle:
            handle.write(updated)
        print(f"bumped {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
