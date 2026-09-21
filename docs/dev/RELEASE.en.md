# RELEASE — release policy

How the project ships releases: versioning, statuses and the check sequence before a release. The policy applies starting with v0.3.

## Purpose and scope

Contributions to the project are welcome (issues and pull requests on GitHub). The quality signals for releases are automated CI runs (GitHub Actions), operation on a production VPS, and user reports on releases (GitHub issues). There is no "alpha → beta → stable" ladder; a status is defined by the concrete criteria below.

## Versioning

- Versions are three-component `vX.Y.Z` (starting with v0.4.0; the old two-component tags are history and are not renamed).
- SemVer in the 0.x phase: a minor bump (`v0.3 → v0.4.0`) is a substantial change, breaking included (e.g. changing a CLI flag default); a patch (`v0.4.0 → v0.4.1`) is fixes, removals of experimental features and small renames (recorded in the CHANGELOG).
- The `v` prefix is required in all tags.

## Statuses and tags

Every release is pinned by an annotated git tag on a commit of the `staging` development line. No release branches are created.

Statuses — an explicit list:

- Code in `staging` without a tag is **not a release and has no status**; it may never become one.
- **release** — a plain `vX.Y.Z` tag: a confident ship, published as a regular GitHub Release and taking the "Latest" channel. It is created only after the exit criteria below are met.
- **experimental** — an optional marker of an unverified build: tag `vX.Y.Z_experimental` + a GitHub Release with the pre-release flag. Used when code must be handed to field operation without occupying the "Latest" channel.

- The `_stable` suffix is abolished (policy of 2026-09-14): there is no promotion anymore — a release ships as a plain tag right away, and a regression is fixed by the next patch `vX.Y.Z+1` (fix-forward).
- The `v0.2_release` and `v0.3_experimental` tags were shipped under the previous policy — history, not renamed.

### Release exit criteria (all four)

1. A green full CI run on the release commit: distro matrix ubuntu 22.04 / 24.04 + debian 12, the firewall job, CLI tests and lint.
2. CI covers the client scenarios as fully as possible: the python client + the bash and PowerShell wrappers × ubuntu / windows / macos runners; missing coverage is built before the release.
3. The maintainer has manually clicked through every usage scenario on a real VPS following the testing cheatsheets (`docs/dev/TEST-LOCAL.en.md`, `docs/user/TEST-VPS.en.md`): deploy in two ways, rotation, client usability (responsiveness, translations, text clarity), real VPN traffic.
4. No known open regressions or hotfixes at the moment of the release.

A calendar soak period is not a criterion (decision 2026-09-09): a deploy either fails immediately or works; the main risk lives in the deployment process and config generation, which the checks above cover.

## Release sequence

One release per version — after the whole planned version scope is done; no intermediate pre-releases for partially finished work (decision 2026-09-09).

1. The version scope (work waves) is complete in `staging`; each wave is pushed and verified by a green CI run before the next one starts.
2. `staging` is pushed manually; a green full GitHub Actions run is awaited on the head commit: workflow `molecule` (syntax, distro matrix, firewall job), workflow `python-client` (CLI tests and lint) and — on the PR into main — the smoke binary build of workflow `release-binaries` (path-filtered). On failures — fix in separate commits and re-run until green.
3. One `docs: finalize vX.Y.Z` commit: `docs/dev/PLANNED.*`, both CHANGELOG halves, `Version` / `Last updated` stamps of the public docs, the README summary, the statuses table row below and the python-client package version bump (`pyproject.toml`, `src/xrayvpn/__init__.py`, `uv.lock`) to the release version.
4. The maintainer performs a successful manual deployment of the release content on a real VPS — the release is published only after that.
5. The PR from `staging` into `main` is merged with **Create a merge commit** (web rebase is prohibited — it recreates commits and strips signatures and dates).
6. The signed annotated tag `vX.Y.Z` is created on the merge node and pushed (by hand). Pushing the tag launches the build workflow: it builds the four platform binaries and dists, computes `SHA256SUMS.txt` and — for plain tags only — `latest.json`, and creates the GitHub release as a draft — the assets never block the tag: if the build leg fails, the release can still be published without them and the assets rebuilt later by rerunning the workflow on the tag.
7. The draft is published as a regular release (the "Latest" channel): title — the tag name; body — the matching CHANGELOG section (extended by hand if needed). For a `vX.Y.Z_experimental` tag the release is marked pre-release and does not take the "Latest" channel. Release assets are public files only; configs with keys never go into a release.

Tagging an unverified (not CI-green) commit is prohibited by the policy.

## Release statuses

The short sha is the verified code; its runs are visible in the repository's Actions history. A table row is updated by the finalize commit of its release.

| Release | Verified code | Checked by CI | Status |
|---|---|---|---|
| v0.3 | `cf98f0b` | distro matrix (ubuntu 22.04 / 24.04, debian 12), firewall job, CLI tests and lint — 2026-09-05 | `v0.3_experimental` |
| v0.4.1 | staging finalize commit (`d2604f5c`) | distro matrix (ubuntu 22.04 / 24.04, debian 12), firewall job, mihomo e2e; CLI tests and lint on ubuntu / windows / macos; four-platform binary build in the release workflow | **in preparation** — tag/release published manually at the end of the 0.4.x line |

Note (2026-09-12): v0.4.0 was never released — its scope and the work after it were merged into v0.4.1; the v0.4.0 row above was replaced by the v0.4.1 row. Note (2026-09-09): the promotion criteria changed — the calendar check "not before 2026-09-20" for v0.3 is void; v0.3 stays experimental; the format moved to three components.

## CHANGELOG

- A pair of root files: `CHANGELOG.md` (RU) and `CHANGELOG.en.md` (EN); one `## [vX.Y.Z] — YYYY-MM-DD` section per release (Added / Changed / Fixed / Removed) with a `Status:` line. No auto-bump.
- Filled from commit messages at shipping time; both halves updated by the same commit with mirrored structure.

## Release commit

Its rules reduce to step 3 of the release sequence: `docs/dev/PLANNED.*` (the "what is next" overview rewritten for the new version), public doc stamps, the README summary, both CHANGELOG halves. This document (`docs/dev/RELEASE.en.md`), until a release ships, is edited by regular commits.

The python-client package version always equals the release version: the finalize commit bumps `pyproject.toml` and `src/xrayvpn/__init__.py` (and refreshes `uv.lock`) to `vX.Y.Z`; `xrayvpn --version` must match the tag. The `tests/test_smoke.py` suite catches a desync.
