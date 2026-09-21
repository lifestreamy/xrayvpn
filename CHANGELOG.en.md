# Changelog

Version history. Русская версия: [CHANGELOG.md](CHANGELOG.md).
Release policy and release statuses — [docs/dev/RELEASE.en.md](docs/dev/RELEASE.en.md).

Format:

- Newest versions first; one section per release: `## vX.Y.Z — YYYY-MM-DD`.
- Inside a section — categories: **Added**, **Changed**, **Fixed**, **Removed**.
- Each release section carries a `Status:` line (`experimental`; after promotion — `stable since YYYY-MM-DD`).
- Entries are built from commit messages and land in the release commit; no auto-bump.
- The RU/EN pair is updated in the same commit; section structure is mirrored.

## v0.4.1 — 2026-09-12

Status: in preparation (development finished on `staging`; publication is manual, at the end of the
0.4.x line). This section merges the never released v0.4.0 with everything built after it; there was
no v0.4.0 release.

### Added
- Console session (REPL): running `xrayvpn` with no arguments opens the same interactive wizard
  as a session — `deploy`/`help`/`version`/`lang ru|en`/`exit`, CLI syntax without the prefix;
  a selftest mode drives it in CI smokes.
- Standalone binaries in Releases (Windows x64, Linux x64/arm64, macOS arm64): Nuitka onefile
  with the embedded payload (roles/playbooks/config template), unpacked into a stable cache
  folder — the client works without Python, uv or a repository clone; Windows file-version
  metadata is stamped into the exe.
- The Python wheel now ships the payload inside (`xrayvpn/payload/…`): a fresh-environment
  install gives a working `deploy --dry-run` outside any repository.
- New-release checks in binary builds (at most once a day, silent on failures and silent until a
  stable release exists); disable with `XRAYVPN_UPDATE_CHECK=0`.
- Binary/dist workflow: a four-platform build matrix with smokes from a neutral directory,
  release artifacts, `SHA256SUMS.txt` and `latest.json` (a manifest for a future self-update
  command), and a draft release on tag push.
- Anti-hairpin: generated Clash/Mihomo profiles pin the server IP with a DIRECT rule so the
  tunnel never intercepts the client's own connection to the VPS.
- Crash net for packaged builds: a fatal double-click error stays on screen until Enter.

### Changed
- **Breaking**: `xrayvpn deploy` now defaults to `--execution remote` (was `local`): a no-argument
  run provisions a remote VPS (asks for the IP and the password); local mode requires the explicit
  `--execution local`.
- Remote deploy: low-memory guard — with < 1024 MB RAM and no active swap the client offers to
  create a 1 GB `/swapfile` (explicit opt-in prompt; an existing swap/fstab configuration is never
  touched).
- The role no longer installs `ufw`: the allow rule for `xray_port`/tcp is added only when `ufw`
  already exists on the server. The `xray_manage_firewall` variable and CLI flag renamed to
  `xray_manage_ufw` / `--manage-ufw/--no-ufw`.
- `--ru` (global and on `deploy`) and the `XRAYVPN_LANG` environment variable: a fully Russian
  CLI interface — prompts, messages, errors and `--help`; the flag works in any argument position.
  Windows double-click launchers in English and Russian (`xrayvpn-deploy.pyw` /
  `xrayvpn-deploy-ru.pyw`) keep the console open until Enter; they start the interpreter directly
  without a `pwsh -c` wrapper, so the exit code is not swallowed.
- Installing the command onto PATH: `uv tool install --editable python-client` — plain `xrayvpn`
  without the `uv run` prefix; the distribution is renamed to `xrayvpn` (install/uninstall by
  this name).
- Rotation and key parameters are forwarded into the shell wrappers: `--rotate`/`--no-rotate`,
  `--runtime`, `-Warp/-NoWarp`, `-Rotate/-NoRotate`, port and client-count flags.
- `deploy --help` now shows the effective defaults from `config/settings.yml` plus examples;
  switching languages replies with one line in the new language; interrupting a command (Ctrl-C)
  no longer closes the session.
- Author contact links moved to the korelov.dev domain (the GitHub repository path is unchanged).
- Client tests run on Windows and macOS in CI too; uv is version-pinned.

### Fixed
- Double-clicking `xrayvpn-deploy.pyw` on Windows failed (cmd quote escaping inside the
  launcher): direct interpreter launch without cmd, an honest exit code, explicit diagnostics
  when `.venv`/`uv` are missing; the launcher contract in the tests now verifies a real launch,
  not just static flags.
- `set -e` no longer kills dry-runs and interactive prompts in the shell wrappers; the
  dry-run preview works with no inventory at all and never touches the personal `inventory.yml`.

### Removed
- The `podman` runtime (experimental stub, never left experimental; not covered by molecule
  tests). Supported runtimes: `native` (default) and `docker`.

## v0.3 — 2026-09-05

Status: experimental (promotion criteria — `docs/dev/RELEASE.en.md`).

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
