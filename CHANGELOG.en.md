# Changelog

Version history by shipped release. Русская версия: [CHANGELOG.md](CHANGELOG.md).
Release policy — [docs/dev/RELEASE.en.md](docs/dev/RELEASE.en.md).

Format:

- Newest versions first; one section per release: `## vX.Y.Z — YYYY-MM-DD`.
- Inside a section — categories: **Added**, **Changed**, **Fixed**, **Removed**.
- A `Status:` line appears only on released versions, when the status is not the regular one.
- Entries are built from commits and land in the release commit; no auto-bump.
- The RU/EN pair is updated in the same commit; section structure is mirrored.

## v0.4.1 — 2026-09-22

There was no v0.4.0 release: this section covers the whole 0.4.x line.

### Added
- Console session (REPL): running `xrayvpn` with no arguments opens the same interactive wizard
  as a session — `deploy`/`help`/`version`/`lang ru|en`/`exit`, CLI syntax without the prefix;
  a selftest mode drives it in CI.
- Standalone binaries in Releases (Windows x64, Linux x64/arm64, macOS arm64): Nuitka onefile
  with the embedded payload (roles/playbooks/config template), unpacked into a stable cache
  folder — the client works without Python, uv or a repository clone; the version is stamped into
  the exe properties.
- The Python wheel ships the payload inside (`xrayvpn/payload/…`): a fresh-environment install
  gives a working `deploy --dry-run` outside any repository. Published on PyPI — `pip install
  xrayvpn`.
- A `.deb` package among the release assets plus an apt repository (`apt install xrayvpn`,
  Ubuntu/Debian): signed metadata, a public key at a stable URL; the package carries a `.desktop`
  entry with `Terminal=true` and the icon (double-click launch).
- New-release checks in binary builds: a hint under the banner and after `--version` (24h cache;
  a failed request prints nothing); disable with `XRAYVPN_UPDATE_CHECK=0`.
- The `xrayvpn service` command (`status`/`restart`/`logs`/`reboot`): server maintenance over SSH
  with a command whitelist; `status` shows a detailed slice of service and version state.
- `deploy --no-config-download`: client configs stay on the server.
- The role keeps Xray logs in journald only and persists the journal on disk; the xray-obs black
  box (state snapshots every 10 minutes) and the egress watchdog with journal-storm detection —
  procedures live in the RUNBOOK.
- Build and distribution: a four-platform matrix with smokes from a neutral directory, versioned
  asset names, `SHA256SUMS.txt` and `latest.json` (a manifest for a future self-update command).
- Anti-hairpin: generated Clash/Mihomo profiles pin the server IP with a DIRECT rule so the tunnel
  never intercepts the client's own connection to the VPS.
- A fatal double-click error in a packaged build stays on screen until Enter.
- Icons: a 3072×3072 raster master and a generator for the derivatives (Windows ICO, previews)
  with a byte-equality test.
- The RUNBOOK (disaster recovery) and the split of the documentation into user and developer
  guides.

### Changed
- **Breaking**: `xrayvpn deploy` now defaults to `--execution remote` (was `local`): a no-argument
  run provisions a remote VPS (asks for the IP and the password); local mode requires the explicit
  `--execution local`.
- `--ru` (global and on `deploy`) and the `XRAYVPN_LANG` environment variable: a fully Russian
  CLI interface — prompts, messages, errors and `--help`; the flag works in any argument position.
  Windows double-click launchers (`xrayvpn-deploy.pyw` / `xrayvpn-deploy-ru.pyw`) start the
  interpreter directly without a `pwsh -c` wrapper.
- Coloured interface: semantic colour tokens, a truecolor palette, banner v2.2, themed `--help`
  panels; the client enables VT on its own, including in a classic conhost window.
- A host can be given as a `~/.ssh/config` alias — in `deploy` (local mode included) and `service`.
- Remote deploy: bootstrap progress with a heartbeat; low-memory guard — with < 1024 MB RAM and no
  active swap the client offers to create a 1 GB swap file (explicit opt-in; an existing
  swap/fstab configuration is never touched).
- Installing the command onto PATH: `uv tool install` — a bare `xrayvpn` without the `uv run`
  prefix.
- Rotation and key parameters are forwarded into the shell wrappers: `--rotate`/`--no-rotate`,
  `--runtime`, `-Warp/-NoWarp`, `-Rotate/-NoRotate`, port and client-count flags.
- `deploy --help` shows the effective defaults from `config/settings.yml` plus examples; switching
  languages replies with one line in the new language; interrupting a command (Ctrl-C) no longer
  closes the session.
- The role no longer installs `ufw`: the allow rule for `xray_port`/tcp is added only when `ufw`
  already exists on the server. The `xray_manage_firewall` variable and CLI flag renamed to
  `xray_manage_ufw` / `--manage-ufw/--no-ufw`.
- A deploy finishes with a banner listing the ready configs and their import hints; after an
  interrupted deploy the client suggests running it again (all steps are repeatable); concurrent
  deploys are serialized with a lock.
- Client tests run on Windows and macOS in CI too; uv is version-pinned; shell wrappers get their
  own smoke jobs.
- Author contact links moved to the korelov.dev domain; the repository was renamed to
  `lifestreamy/xrayvpn` (the old address redirects).

### Fixed
- Double-clicking `xrayvpn-deploy.pyw` on Windows failed (quote escaping inside the launcher):
  a direct interpreter start, a correct exit code, diagnostics when `.venv`/`uv` are missing.
- `set -e` no longer kills dry-runs and interactive prompts in the shell wrappers; the dry-run
  preview works with no inventory at all and never touches the personal `inventory.yml`.
- Clear messages on SSH failures; an empty password and a missing key file are rejected up front,
  with a hint.
- Double-clicking the packaged exe under conhost relaunches the client in a conhost window with
  the app icon (stay in Windows Terminal via `--wt`/`XRAYVPN_IN_WT`).
- Local deploy honours the `~/.ssh/config` entry (port and user) instead of the fixed `root:22`.
- Service logs and status: helper lines no longer clutter the output and `logs` can be interrupted.
- The role builds backup paths from `ansible_facts` (`date_time`) instead of the Ansible
  environment date; the vless inbound is tagged so a molecule assertion no longer fails on a
  missing attribute.
- `--help` shows boolean defaults as words (`default: enabled` / `default: disabled`).
- The banner adapts to the terminal width: long lines wrap, a narrow window (<72 columns) renders
  the screen without boxes, and the outer frame matches for RU and EN.

### Removed
- The `podman` runtime (experimental stub, never left experimental; not covered by molecule
  tests). Supported runtimes: `native` (default) and `docker`.

## v0.3 — 2026-09-05

Status: experimental.

### Added
- The primary CLI client `xrayvpn` (Python): remote mode over SSH and a local mode, common
  parameters as flags.
- GitHub Actions CI: `molecule` workflow — syntax check, molecule matrix on ubuntu 22.04/24.04 and
  debian 12, a full host run with the firewall and a mihomo-client e2e; `python-client` workflow —
  CLI tests and lint.
- Manual check runbook — `docs/dev/TEST-LOCAL.en.md`.
- Release policy — `docs/dev/RELEASE.en.md`: experimental/stable statuses, tag scheme, release
  sequence. The CHANGELOG pair (this file plus `CHANGELOG.md`).
- Hints for clients when `inventory.yml` is missing or incomplete.
- Enabling `xray.service` at boot and auto-install of `ufw` / `python3-venv` during deploy.

### Changed
- All role variables live in one file, `config/settings.yml`; `group_vars/` and role defaults
  are gone.
- Runtime choice: `native` (default), `docker`, `podman` (experimental).
- Docker and podman units run with `--network host`, no extra NAT hop.
- Repository layout: `shell-clients/`, `python-client/`, `scripts/`, `config/`; contributor
  tooling separated from client wrappers.
- README quick start: three run paths (the clients and bare Ansible) with direct file links,
  command details in collapsible blocks.

### Fixed
- Readable inventory error messages; `--use-inventory` parsing in the shell clients was broken
  since v0.2.

## v0.2 — 2026-08-03

First publicly documented release (predates the current release policy; tagged `v0.2_release`).
Detailed change history starts with v0.3.