"""Nuitka-first standalone binary driver with a PyInstaller fallback (MYXRAY-30).

Debug loop: iterate with ``--mode standalone`` (onedir), ship with ``onefile``.
Run through ``build-binary.ps1`` / ``build-binary.sh`` (uv-synced build group).
"""

from __future__ import annotations

import argparse
import os
import platform
import subprocess
import sys
from pathlib import Path

import build_support

ENTRY = build_support.CLIENT_DIR / "src" / "xrayvpn" / "__main__.py"
DIST_DIR = build_support.CLIENT_DIR / "dist-binary"
ONEFILE_TEMPDIR_SPEC = "{CACHE_DIR}/xrayvpn/{VERSION}"


def nuitka_args(args: argparse.Namespace, staged: Path, version: str, outdir: Path) -> list[str]:
    argv = [
        sys.executable,
        "-m",
        "nuitka",
        f"--mode={args.mode}",
        "--assume-yes-for-downloads",
        f"--company-name={build_support.COMPANY_NAME}",
        f"--product-name={build_support.PRODUCT_NAME}",
        f"--file-version={version}",
        f"--product-version={version}",
        f"--file-description={build_support.FILE_DESCRIPTION}",
        f"--copyright={build_support.COPYRIGHT}",
        f"--output-filename={build_support.artifact_name(version)}",
        f"--output-dir={outdir}",
        "--include-package=xrayvpn",
    ]
    if args.mode == "onefile":
        argv.append(f"--onefile-tempdir-spec={ONEFILE_TEMPDIR_SPEC}")
    if platform.system().lower() == "windows":
        argv.append("--windows-console-mode=force")
        if build_support.ICON_ICO.is_file():
            argv.append(f"--windows-icon-from-ico={build_support.ICON_ICO}")
    for source, arc in build_support.payload_map(staged):
        flag = "--include-data-dir" if source.is_dir() else "--include-data-files"
        argv.append(f"{flag}={source.as_posix()}={arc}")
    argv.append(str(ENTRY))
    return argv


def pyinstaller_args(outdir: Path) -> list[str]:
    return [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        f"--distpath={outdir}",
        f"--workpath={build_support.BUILD_DIR / 'pyi'}",
        str(build_support.CLIENT_DIR / "xrayvpn.spec"),
    ]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", choices=("nuitka", "pyinstaller"), default="nuitka")
    parser.add_argument("--mode", choices=("onefile", "standalone"), default="onefile")
    parser.add_argument("--version", default="", help="release version (default: __version__)")
    parser.add_argument("--output-dir", type=Path, default=DIST_DIR)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    version = args.version
    if not version:
        sys.path.insert(0, str(build_support.CLIENT_DIR / "src"))
        from xrayvpn import __version__

        version = __version__
    staged = build_support.stage_payload()
    outdir = args.output_dir.resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    os.environ["XRAYVPN_BUILD_VERSION"] = version
    argv_cmd = (
        nuitka_args(args, staged, version, outdir)
        if args.engine == "nuitka"
        else pyinstaller_args(outdir)
    )
    print("+ " + " ".join(argv_cmd))
    return subprocess.run(argv_cmd, cwd=args.output_dir.parent, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
