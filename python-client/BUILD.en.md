# Building standalone xrayvpn binaries

Summary: `xrayvpn` is packaged by Nuitka (`--mode=onefile`) into a single
executable `xrayvpn-<os>-<arch>[.exe]` carrying the bundled payload (`roles/`,
`config/`, `deploy.yml`, `inventory.yml.example` → `xrayvpn/payload/…`; the same
allowlist used for server uploads). The PyInstaller spec `xrayvpn.spec` is a
fallback with the identical payload contract (shared staging in `build_support.py`).

## Requirements

- `uv` (same pin as CI) — the wrapper syncs the `build` dependency group itself.
- C compiler: Windows — Visual Studio 2022 (or Nuitka auto-downloads MinGW),
  Linux — gcc, macOS — clang (Xcode CLT).
- Python 3.12+ (`requires-python` in `pyproject.toml`).

## Commands

```
# Windows
.\build-binary.ps1                       # onefile, canonical
.\build-binary.ps1 -Mode standalone      # debug mode (onedir folder)
.\build-binary.ps1 -Engine pyinstaller   # fallback spec
.\build-binary.ps1 -Version 0.4.1        # release version fed to metadata/--version (default: __version__)

# Linux/macOS
./build-binary.sh
./build-binary.sh --mode standalone
./build-binary.sh --engine pyinstaller --version 0.4.1
```

Artifacts land in `dist-binary/`. Contract: identical payload paths for both
engines, `--version` = the version passed, file name = `xrayvpn-<os>-<arch>[.exe]`.

## Debug loop

1. `--mode standalone` → inspect `dist-binary/xrayvpn-*.dist/` by hand.
2. No complaints → `--mode onefile` (default) → smoke below.
3. Nuitka surprises (bcrypt/cffi/plugin deps) — fix with flags/`--include-package`,
   not client code; as a last resort use the PyInstaller spec (payload contract unchanged).

## Onefile cache

Extraction goes to `{CACHE_DIR}/xrayvpn/{VERSION}` (a stable path so Windows
Firewall does not treat every run as a new program; repeat launches skip
re-extraction). A version change creates a fresh cache directory.

## Smoke set (MUST run from a NEUTRAL cwd)

Outside the repo checkout — `--dry-run` would otherwise find the bundle via the
composite clone marker `roles/xray_vpn` inside the repo and the check would not count:

```
cd $TMPDIR/some-empty-dir
XRAYVPN_UPDATE_CHECK=0 ./xrayvpn-… --version          # first line: xrayvpn <version>
XRAYVPN_UPDATE_CHECK=0 ./xrayvpn-… deploy --dry-run --no-interactive --host 127.0.0.1
XRAYVPN_LANG=ru XRAYVPN_UPDATE_CHECK=0 ./xrayvpn-… --ru --help   # RU output (l10n-patch sentinel in freeze)
XRAYVPN_REPL_SELFTEST=1 ./xrayvpn-… repl               # stdin feeding: help\nexit\n → rc 0
# Windows: double-click on the .exe = same entry with a console (--windows-console-mode=force);
# on a fatal error the window stays open with the message until you press Enter.
```

## Known environment notes

- Unsigned Windows exe → SmartScreen “More info”; macOS → `chmod +x`,
  Gatekeeper → right-click Open / `xattr -d com.apple.quarantine`.
- Reset the onefile cache: delete `{CACHE_DIR}/xrayvpn/<version>`.
- On low-memory hosts add `--low-memory` / `--jobs=1` inside `build_binary.py`.
