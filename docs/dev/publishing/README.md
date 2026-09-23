# Publishing channels

How release artifacts reach the user-facing channels, who runs what, and how to repair a channel.

## Channels

| Channel | Artifact | Destination | Pipeline | Environment | User command |
|---|---|---|---|---|---|
| GitHub Releases | platform binaries, wheel/sdist, checksums | this repository | `release-binaries.yml` | — | download from Releases |
| PyPI | wheel + sdist | pypi.org | `publish-pypi.yml` | `pypi` | `pip install xrayvpn` |
| apt | signed repository on GitHub Pages | `lifestreamy.github.io/xrayvpn/apt` | `publish-apt.yml` | `apt`, `github-pages` | `apt install xrayvpn` |
| winget | YAML manifests | pull request to `microsoft/winget-pkgs` | `publish-winget.yml` | `winget` | `winget install Lifestreamy.XrayVpn` |
| AUR | `PKGBUILD`, `.SRCINFO`, desktop entry, icon | `aur.archlinux.org/xrayvpn-bin` | `publish-aur.yml` | `aur` | `yay -S xrayvpn-bin` |
| Homebrew | formula | tap `lifestreamy/homebrew-tap` | `publish-brew.yml` | `brew` | `brew install lifestreamy/tap/xrayvpn` |

A publish pipeline runs on `release: published` for a plain `vX.Y.Z` tag. To repair a channel, or to
publish a release that shipped before the pipeline existed, run the pipeline from the Actions tab
(manual run with the `tag` input). Publishing starts only after the environment approval: without
it nothing leaves the repository. Each run keeps its rendered set as a build artifact, so it is
always clear what was sent to a channel.

Every run accepts only the latest non-prerelease release: the tag must be a plain `vX.Y.Z` and must
match the newest published release, so a repair run cannot downgrade a live channel with stale
content.

ARM64 Linux ships through Releases and pip/uv only; packages for ARM are not published to the
channels. apt-arm64 and AUR aarch64 are candidates if there is demand.

## Renderer

`scripts/cd/render_channels.py` renders the complete publishable set for every channel from one
release:

- input: the tag and `SHA256SUMS.txt` of the release; for AUR also the `LICENSE` file of the tag;
- templates: `packaging/winget/` (metadata plus locales), `packaging/aur/`, `packaging/brew/`;
- output: `build/channels/` (gitignored);
- guard: the release must carry the `windows-x64`, `linux-x64` and `macos-arm64` assets whose names
  match the tag; a missing asset stops the render.

`--print-winget-dir` prints the rendered manifest directory for a tag, so the pipelines never
duplicate the winget path layout. `scripts/cd/arch_container.sh` is the single Arch recipe used by
the AUR pipelines and checks: `srcinfo` writes `.SRCINFO` next to the rendered PKGBUILD, `build`
compiles and lints the package, `install` also installs it and asserts the installed version when
`EXPECTED_VERSION` is set.

The `verify-channels` pipeline renders from the latest published release on pull requests that
touch `packaging/**` or `scripts/cd/**`, and checks the live channels weekly; a channel is checked
once its `CHANNEL_*_LIVE` variable is set, and a manual run checks exactly the same set. Every
weekly check asserts that the installed version equals the latest release, so a stale channel fails
instead of passing silently; the run summary lists which gated channels were enabled or skipped.

Authenticode signing of the Windows asset is not part of the release flow. If it is added later, it
slots into `release-binaries.yml` between the build and the checksums: sign and timestamp the exe,
verify it, then compute `SHA256SUMS.txt` over the signed bytes. Every channel artifact is rendered
from those checksums, so the winget, AUR and brew sets pick up the signed hashes without further
changes, and the signing decision does not hold up the current publication.

## Owner runbook

One-time setup (GitHub → Settings):

1. Environments `winget`, `aur`, `brew`: add a required reviewer. Approval is the only manual step
   per release.
2. winget: create a classic token with the `public_repo` scope (fine-grained tokens cannot open the
   cross-fork pull request — see [`winget.md`](winget.md)), store it as the environment secret
   `WINGET_TOKEN`.
3. AUR: create an account on `aur.archlinux.org` (registration can be paused by the Arch team — see
   [`aur.md`](aur.md)), add an SSH public key to the profile, store the private key as the
   environment secret `AUR_SSH_PRIVATE_KEY`.
4. Tap: create the public repository `lifestreamy/homebrew-tap` (branch `main`), add a write deploy
   key, store its private key as the environment secret `BREW_DEPLOY_KEY`.
5. Repository variables `CHANNEL_WINGET_LIVE`, `CHANNEL_AUR_LIVE`, `CHANNEL_BREW_LIVE`: set each to
   `true` once the channel is live, so the weekly checks start covering it. Until then the gate
   summary in each weekly run lists the channel as skipped.

Secret values live only in the environment secrets; the repository and these documents contain
names, never values.

## Pinned trust material

- `.github/ssh/known_hosts` holds the host keys of `aur.archlinux.org` and `github.com`, so the
  pipelines never trust a key discovered at push time. The AUR keys match the fingerprints
  published on the AUR home page (Ed25519 `SHA256:RFzBCUItH9LZS0cKB5UE6ceAYhBD5C8GeOBip8Z11+4`,
  ECDSA `SHA256:uTa/0PndEgPZTf76e1DFqXKJEXKsn7m9ivhLQtzGOCI`,
  RSA `SHA256:5s5cIyReIfNNVGRFdDbe3hdYiI5OelHGpw2rOUud3Q8`); the GitHub keys match
  `https://api.github.com/meta`. To refresh after a rotation, scan the hosts with a current
  OpenSSH (`ssh-keyscan -t ed25519,ecdsa,rsa <host>`), compare the fingerprints against those
  sources, and replace the file.
- `publish-winget.yml` pins both the `wingetcreate` version and the sha256 of its executable and
  verifies the hash before running it.

## When a channel fails

- Republish: run the channel pipeline again with the released tag and approve it.
- The weekly check going red means a live channel is broken: repair the channel instead of ignoring
  the run.
- Channel-specific repair paths are in the per-channel guides.
