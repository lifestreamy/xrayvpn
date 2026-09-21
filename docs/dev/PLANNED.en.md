# What's planned, in progress, and done

Deadlines are rough targets, not promises. The order can change.

## Done in v0.4.1 (2026-09-12)

- Standalone binaries in Releases (Windows x64, Linux x64/arm64, macOS arm64): the roles and
  playbooks are embedded, extraction goes to a stable cache, a Windows double-click opens the
  console assistant; the four-platform matrix and neutral-directory smokes run in CI.
- Python install with no clone: the wheel carries the payload inside; the distribution is named `xrayvpn`.
- Console session (REPL) when started with no arguments; `deploy --help` now shows the effective
  defaults from `config/settings.yml` plus examples; the language switch replies in a single line.
- Anti-hairpin: the server IP is pinned by a DIRECT rule in generated Clash/Mihomo profiles.
- New-version hint in binary builds (at most daily, silent on failures) plus `latest.json` and
  `SHA256SUMS.txt` release assets.
- Fully Russian interface (`--ru` / `XRAYVPN_LANG`), double-click `.pyw` launchers, the low-memory
  guard (an explicit opt-in 1 GB swapfile offer), `ufw` only adds an allow rule, the `podman`
  runtime removed, `--execution remote` by default, key flags forwarded into the bash/PowerShell
  wrappers, `uv tool install --editable python-client` for a plain `xrayvpn` on PATH.
- CI: client tests on Windows/macOS/Ubuntu plus the four-platform release binary matrix; uv pinned.
- Release policy: three-component versions, one release per version, exit criteria without
  a calendar soak (CI coverage of client scenarios + a manual click-through cheatsheet); a plain
  `vX.Y.Z` tag is the release (the "Latest" channel), `_experimental` is an optional pre-release
  marker, fix-forward.
- Author contact links moved to korelov.dev.

## Done in v0.3 (2026-09-05)

- All role configuration (the set of files that deploys Xray on the server) lives in one file: `config/settings.yml`.
- The primary CLI client `xrayvpn` (Python): remote mode over SSH and local mode; parameters go
  through CLI flags, no hand-editing of yaml files.
- GitHub Actions CI: molecule matrix on ubuntu 22.04 / 24.04 / debian 12 plus a full host run
  with the mihomo-client e2e (ufw is exercised there).
- Runtimes: `native` (default), `docker`. Container systemd units use `--network host`.
- `xray.service` is enabled on deploy; `python3-venv` and `ufw` were auto-installed where needed
  (the `ufw` behavior changed in v0.4.1).
- Readable `inventory.yml` errors with a hint on how to create the file from the template.
- Release policy (`docs/dev/RELEASE.en.md`), CHANGELOG (RU/EN), docs brought to one rhythm.

## High priority

- Ship v0.4.1 as a plain tag — per the exit criteria in `docs/dev/RELEASE.en.md`: CI coverage of the
  client scenarios (python + bash + PowerShell × Ubuntu/Windows/macOS) and a manual click-through
  of all scenarios on a real VPS following the testing cheatsheet; no calendar soak.
- **[Client]** — a visual console client (TUI): the deploy wizard and everyday commands in one
  menu, RU/EN. Target: v0.4.2.
- **[Server]** — observability and recovery: server-side logs with retention (days), a service
  status view and whitelisted recovery actions (restart from the binary without reaching for SSH
  by hand). Target: v0.4.2.

## Medium priority

- **[Distribution]** — publish the `xrayvpn` package on PyPI and install it from package managers
  (winget / choco / AUR); every release already carries `latest.json` — the base for a future
  `update` command (self-update of the binary). Target: after the publishing-identity decisions.
- **[WARP]** — think through scenarios: multiple outbounds, endpoint rotation. Target: none.

## Low priority

- (free for now — will appear along the way)
