# Release policy

General shipping rules. The process is short.

## Versions
- Format `vX.Y.Z`; the `v` prefix is required.
- In the 0.x phase: minor — substantial changes (possibly breaking), patch — fixes and small edits.
- A tag is the only fact of a shipped release.

## Statuses
- A plain `vX.Y.Z` tag is a release.
- `vX.Y.Z_experimental` is a preliminary build for field testing: a GitHub pre-release, it does not
  take the Latest channel.
- New releases ship as a plain tag; a regression is fixed by the next patch.

## Shipping
- A release ships after checks: automated tests, builds for every platform and a manual run on a
  live server.
- Code without a release never lands in the CHANGELOG.

## Where releases ship
- GitHub Releases — builds for every platform, wheel/sdist and checksums.
- PyPI — `pip install xrayvpn`.
- apt repository — `apt install xrayvpn`; codenames noble (Ubuntu 24.04), bookworm (Debian 12).
- Homebrew — a formula in a tap.
- AUR — `xrayvpn-bin`.
- winget — a manifest.

How publishing per channel works and how to repair a channel — [`docs/dev/publishing/`](publishing/README.md).

Connecting the apt repository (key fingerprint — `60DA D207 F0BE 147C 5830 D3D8 1BD4 9EC3 0480 57D3`):

```bash
sudo curl -fsSL -o /usr/share/keyrings/xrayvpn-archive-keyring.gpg \
  https://lifestreamy.github.io/xrayvpn/apt/xrayvpn-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/xrayvpn-archive-keyring.gpg] https://lifestreamy.github.io/xrayvpn/apt/ $(. /etc/os-release; echo $VERSION_CODENAME) main" \
  | sudo tee /etc/apt/sources.list.d/xrayvpn.list
sudo apt update && sudo apt install xrayvpn
```

Homebrew (macOS, Apple Silicon):

```bash
brew install lifestreamy/tap/xrayvpn
```

## Badges
- README badges update on events (pipeline `badges.yml`): a release publish and successful
  channel publishes (pypi, brew, apt). The versions come from the channels themselves (they may
  differ), `?v=` moves on the badge that changed, and the bot commit lands on main.
- The winget badge shows the version only when `CHANNEL_WINGET_LIVE=true` (a repository variable),
  otherwise — «скоро»/«soon»; run the pipeline manually after the flip.
- Repair — a manual run without inputs (Actions tab).

## CHANGELOG
- Kept per shipped version; entries are added by the release commit; format — Added / Changed /
  Fixed / Removed.

## Release notes (GitHub Release)
The release body is one RU/EN text pair:
- a centred icon; when screenshots exist — a table with `align="center"`; then `---` and the
  `## vX.Y.Z — YYYY-MM-DD` heading;
- per language: a visible bold lead (one line) and a collapsible block
  `<details><summary>:us: English summary</summary>` / `<summary>:ru: Описание на русском</summary>`;
  order EN → RU, with `---` between the blocks;
- inside — short Added / Changed / Fixed / Removed bullets without implementation details; the full
  wording lives in `CHANGELOG.md`;
- service notes (e.g. about an unshipped release) — `<sub>…</sub>` at the end of their block;
- at the bottom — `<sub> Pre-built by the release-binaries workflow from tag vX.Y.Z. See
  SHA256SUMS.txt and latest.json. </sub>`.