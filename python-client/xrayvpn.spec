# -*- mode: python ; coding: utf-8 -*-
# PyInstaller fallback spec (MYXRAY-30): same staged payload contract as Nuitka.

import os
import sys
from pathlib import Path

sys.path.insert(0, SPECPATH)

import build_support

version = os.environ.get("XRAYVPN_BUILD_VERSION", "")
if not version:
    sys.path.insert(0, str(Path(SPECPATH, "src")))
    from xrayvpn import __version__ as version

staged = build_support.stage_payload()
datas = [(str(src), arc) for src, arc in build_support.payload_map(staged)]

icon = str(build_support.ICON_ICO) if build_support.ICON_ICO.is_file() else None

a = Analysis(
    [str(Path(SPECPATH, "src", "xrayvpn", "__main__.py"))],
    pathex=[str(Path(SPECPATH, "src"))],
    datas=datas,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name=build_support.artifact_name(version),
    icon=icon,
    debug=False,
    strip=False,
    upx=False,
    console=True,
)
