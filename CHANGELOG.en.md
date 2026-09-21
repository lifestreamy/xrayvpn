# Changelog

Version history by shipped release. Русская версия: [CHANGELOG.md](CHANGELOG.md).
Release policy — [docs/dev/RELEASE.en.md](docs/dev/RELEASE.en.md).

Format:

- Newest versions first; one section per release: `## vX.Y.Z — YYYY-MM-DD`.
- Inside a section — categories: **Added**, **Changed**, **Fixed**, **Removed**.
- A `Status:` line appears only on released versions, when the status is not the regular one.
- Entries are built from commits and land in the release commit; no auto-bump.
- The RU/EN pair is updated in the same commit; section structure is mirrored.

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