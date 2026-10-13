"""End-to-end check of the update path against a real GitHub release (CI e2e).

Resolves the release's latest.json, cross-checks SHA256SUMS, reuses a cached
asset while its hash still matches, downloads otherwise, and optionally runs
the fresh binary with --version. Stdlib plus the local client package; exits
0 on success, 1 on failure, 0 with a skip note when the platform has no asset.
Run under `uv run` from python-client (deps from the lockfile).
"""

from __future__ import annotations

import argparse
import hashlib
import os
import platform
import subprocess
import sys
import urllib.request
from pathlib import Path

from xrayvpn.core import update

CHUNK_BYTES = 256 * 1024
DOWNLOAD_TIMEOUT_SECONDS = 120


def platform_parts() -> tuple[str, str]:
    return sys.platform, platform.machine()


def cached_digest_matches(path: Path, sha256: str) -> bool:
    if not path.is_file():
        return False
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest() == sha256


def run_version(target: Path, tag: str) -> int:
    if os.name != "nt":
        target.chmod(0o755)
    env = dict(os.environ)
    env["XRAYVPN_UPDATE_CHECK"] = "0"
    result = subprocess.run(
        [str(target), "--version"],
        capture_output=True,
        text=True,
        timeout=DOWNLOAD_TIMEOUT_SECONDS,
        check=False,
        env=env,
    )
    expected = tag.lstrip("vV").split("_")[0]
    output = (result.stdout or "").strip()
    print(output)
    if result.returncode != 0 or expected not in output:
        print(f"{target} --version did not report {expected} (rc={result.returncode})")
        return 1
    return 0


def _opener(url: str):
    return urllib.request.urlopen(url, timeout=DOWNLOAD_TIMEOUT_SECONDS)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", required=True)
    parser.add_argument("--cache-dir", type=Path, default=Path.home() / "xrayvpn-e2e-cache")
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args(argv)
    token = update.platform_token(*platform_parts())
    if token is None:
        print(f"skip: no update asset for {platform_parts()}")
        return 0
    try:
        assets = update.fetch_latest_json(args.tag)
        sums = update.fetch_sums(args.tag)
        asset = assets.get(token)
        if asset is None:
            print(f"no asset for {token} in {args.tag}")
            return 1
        update.cross_check_sums(asset.name, asset.sha256, sums)
        target = args.cache_dir / asset.name
        if cached_digest_matches(target, asset.sha256):
            print(f"cache hit: {target}")
        else:
            args.cache_dir.mkdir(parents=True, exist_ok=True)
            target.unlink(missing_ok=True)
            update.download_asset(
                asset.url, target, expected_sha256=asset.sha256, opener=_opener
            )
            print(f"downloaded: {asset.name}")
    except update.UpdateError as exc:
        print(f"fail: {exc}")
        return 1
    if args.run:
        return run_version(target, args.tag)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
