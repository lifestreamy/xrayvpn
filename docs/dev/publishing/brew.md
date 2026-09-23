# Homebrew

The `xrayvpn` formula in the tap `lifestreamy/homebrew-tap`, so users install with
`brew install lifestreamy/tap/xrayvpn`.

## Artifact

`packaging/brew/xrayvpn.rb`, rendered into `Formula/xrayvpn.rb` of the tap:

- `url` — the `macos-arm64` portable asset of the release; the version is scanned from the URL;
- `sha256` — from the release checksums;
- `depends_on arch: :arm64` — the asset exists for Apple Silicon only.

## Pipeline

`publish-brew.yml` runs on `ubuntu-24.04` in the `brew` environment:

1. checks that the tag is a plain `vX.Y.Z` and the latest published release, then downloads
   `SHA256SUMS.txt` from it;
2. renders the formula with `scripts/cd/render_channels.py`;
3. keeps the formula as the `brew-formula` build artifact;
4. clones the tap over SSH with a deploy key and pushes `Formula/xrayvpn.rb` to `main` with the
   commit message `xrayvpn <version>`; the host key comes from the pinned
   `.github/ssh/known_hosts`.

Secret: `BREW_DEPLOY_KEY` (write deploy key of the tap repository).

## Repair

Re-run the pipeline with the released tag and approve it. The formula can also be pushed by hand:
clone the tap, copy the rendered file, commit, push.

## Verify and remove

```
brew install lifestreamy/tap/xrayvpn
xrayvpn --version
```

The weekly `verify-channels` run audits and installs the formula on `macos-14` and asserts that the
installed version equals the latest release. Removal: delete `Formula/xrayvpn.rb` in the tap and
push the removal.
