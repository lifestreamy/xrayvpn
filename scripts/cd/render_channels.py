"""Render the channel packaging sets (winget, AUR, brew) from release assets.

Consumed by the publish-* pipelines and by verify-channels: reads the templates
under packaging/ plus SHA256SUMS.txt from a release and writes the complete
publishable set into --out (default build/channels).
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

from release_common import asset_name, normalized_version

REPO = "lifestreamy/xrayvpn"
TOKEN = re.compile(r"\{\{([A-Za-z0-9_]+)\}\}")


def parse_sums(text: str) -> dict[str, str]:
    sums: dict[str, str] = {}
    for line in text.splitlines():
        digest, _, name = line.strip().partition("  ")
        if not name:
            continue
        sums[name] = digest.lower()
    return sums


def require_asset(sums: dict[str, str], version: str, token: str) -> str:
    name = asset_name(version, token)
    if name not in sums:
        raise SystemExit(f"{name} is not listed in SHA256SUMS.txt")
    return sums[name]


def parse_metadata(text: str) -> dict[str, str]:
    meta: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        key, sep, value = line.partition(": ")
        if not sep:
            raise SystemExit(f"unsupported metadata line: {raw}")
        meta[key] = value
    return meta


def substitute(template: str, values: dict[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in values:
            raise SystemExit(f"unknown placeholder {{{{{key}}}}}")
        return values[key]

    rendered = TOKEN.sub(replace, template)
    if TOKEN.search(rendered):
        raise SystemExit("unresolved placeholder left in the rendered template")
    return rendered


def read_template(path: Path) -> str:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def release_values(version: str, tag: str) -> dict[str, str]:
    base = f"https://github.com/{REPO}"
    return {
        "Version": version,
        "ReleaseBaseUrl": f"{base}/releases/download/{tag}",
        "RawBaseUrl": f"https://raw.githubusercontent.com/{REPO}/{tag}",
        "ReleaseNotesUrl": f"{base}/releases/tag/{tag}",
    }


def winget_manifest_dir(package_id: str, version: str) -> Path:
    parts = package_id.split(".")
    return Path("manifests", parts[0][0].lower(), *parts, version)


def winget_package_id(root: Path) -> str:
    metadata = root / "packaging" / "winget" / "metadata.yml"
    return parse_metadata(read_template(metadata))["PackageIdentifier"]


def render_winget(root: Path, version: str, tag: str, sums: dict[str, str]) -> dict[Path, bytes]:
    templates = root / "packaging" / "winget"
    package_id = winget_package_id(root)
    values = {
        **parse_metadata(read_template(templates / "metadata.yml")),
        **release_values(version, tag),
        "Sha256WindowsX64": require_asset(sums, version, "windows-x64"),
    }
    out_dir = Path("winget") / winget_manifest_dir(package_id, version)
    sources = {
        out_dir / f"{package_id}.yaml": templates / "version.yml",
        out_dir / f"{package_id}.installer.yaml": templates / "installer.yml",
    }
    for locale_template in sorted(templates.glob("locale.*.yml")):
        locale = locale_template.name.removeprefix("locale.").removesuffix(".yml")
        sources[out_dir / f"{package_id}.locale.{locale}.yaml"] = locale_template
    return {
        path: substitute(read_template(source), values).encode("utf-8")
        for path, source in sources.items()
    }


def render_aur(
    root: Path,
    version: str,
    tag: str,
    sums: dict[str, str],
    license_file: Path | None,
) -> dict[Path, bytes]:
    templates = root / "packaging" / "aur"
    if license_file is None:
        print("LICENSE checksum: SKIP (no --license file given)", file=sys.stderr)
    values = {
        **release_values(version, tag),
        "Sha256LinuxX64": require_asset(sums, version, "linux-x64"),
        "LicenseSha256": (
            hashlib.sha256(license_file.read_bytes()).hexdigest() if license_file else "SKIP"
        ),
    }
    return {
        Path("aur/PKGBUILD"): substitute(read_template(templates / "PKGBUILD"), values).encode(
            "utf-8"
        ),
        Path("aur/xrayvpn.desktop"): read_template(templates / "xrayvpn.desktop").encode("utf-8"),
        Path("aur/xrayvpn.png"): (root / "assets" / "icon" / "icon-preview.png").read_bytes(),
    }


def render_brew(root: Path, version: str, tag: str, sums: dict[str, str]) -> dict[Path, bytes]:
    template = root / "packaging" / "brew" / "xrayvpn.rb"
    values = {
        **release_values(version, tag),
        "Sha256MacosArm64": require_asset(sums, version, "macos-arm64"),
    }
    return {Path("brew/xrayvpn.rb"): substitute(read_template(template), values).encode("utf-8")}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", required=True, help="released tag, e.g. v0.4.1")
    parser.add_argument("--sums", type=Path, help="SHA256SUMS.txt of the release")
    parser.add_argument("--out", type=Path, default=Path("build/channels"))
    parser.add_argument("--license", type=Path, help="LICENSE file of the tag (AUR checksum)")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument(
        "--print-winget-dir",
        action="store_true",
        help="print the rendered winget manifest directory and exit",
    )
    args = parser.parse_args(argv)
    version = normalized_version(args.tag)
    if args.print_winget_dir:
        package_id = winget_package_id(args.root)
        print(args.out / "winget" / winget_manifest_dir(package_id, version))
        return 0
    if args.sums is None:
        parser.error("--sums is required unless --print-winget-dir is used")
    sums = parse_sums(read_template(args.sums))
    files: dict[Path, bytes] = {}
    files.update(render_winget(args.root, version, args.tag, sums))
    files.update(render_aur(args.root, version, args.tag, sums, args.license))
    files.update(render_brew(args.root, version, args.tag, sums))
    for relative, data in sorted(files.items()):
        target = args.out / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        print(f"wrote {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
