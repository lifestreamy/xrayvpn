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
- apt repository — `apt install xrayvpn` (Ubuntu / Debian).
- Homebrew — a formula in a tap.
- AUR — `xrayvpn-bin`.
- winget — a manifest.

## CHANGELOG
- Kept per shipped version; entries are added by the release commit; format — Added / Changed /
  Fixed / Removed.