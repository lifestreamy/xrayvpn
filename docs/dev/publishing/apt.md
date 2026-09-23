# apt

The signed apt repository on GitHub Pages: `apt install xrayvpn` on Ubuntu 24.04 (noble) and
Debian 12 (bookworm).

## Artifact

The `.deb` from the release assets, published as a signed repository:

- distribution: `noble`, `bookworm`; component `main`; architecture `amd64`;
- the repository root is served from `https://lifestreamy.github.io/xrayvpn/apt/`;
- the archive key is exported next to it as `xrayvpn-archive-keyring.gpg`.

## Pipeline

`publish-apt.yml` runs on `ubuntu-24.04` in the `apt` environment, then deploys through the
`github-pages` environment:

1. downloads the `.deb` from the release and checks its package name and architecture;
2. imports the archive signing key (`APT_GPG_PRIVATE_KEY`) and builds the signed archive with
   aptly;
3. uploads the site as the `apt-pages` build artifact and deploys it to Pages.

## Connection

The commands and the key fingerprint are in [`docs/dev/RELEASE.md`](../RELEASE.md) and
[`docs/dev/RELEASE.en.md`](../RELEASE.en.md).

## Repair

Re-run the pipeline with the released tag and approve it. The signing key is the only secret; if it
is rotated, publish the new keyring with the next run and update the fingerprint in the release
documents.

## Verify

```
sudo apt update && sudo apt install xrayvpn
xrayvpn --version
```

The weekly `verify-channels` run installs from the repository on `ubuntu-24.04` and in a
`debian:12` container.
