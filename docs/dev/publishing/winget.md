# winget

Manifests for the Windows package manager, published as a pull request to
[`microsoft/winget-pkgs`](https://github.com/microsoft/winget-pkgs).

## Artifact

Four YAML manifests for one version, rendered from `packaging/winget/`:

- `Lifestreamy.XrayVpn.yaml` — version manifest;
- `Lifestreamy.XrayVpn.installer.yaml` — portable x64 installer (release asset URL and sha256 from
  the release);
- `Lifestreamy.XrayVpn.locale.en-US.yaml` — default locale (the manifest type is `defaultLocale`);
- `Lifestreamy.XrayVpn.locale.ru-RU.yaml` — Russian locale.

The command alias `xrayvpn` comes from `Commands` in the installer manifest; `PortableCommandAlias`
applies only to nested portable installers inside archives.

## Pipeline

`publish-winget.yml` runs on `windows-latest` in the `winget` environment:

1. checks that the tag is a plain `vX.Y.Z` and the latest published release, then downloads
   `SHA256SUMS.txt` from it;
2. renders the manifests with `scripts/cd/render_channels.py`; the manifest directory comes from
   `--print-winget-dir`, so the path layout lives only in the renderer;
3. runs `winget validate` on the rendered set;
4. keeps the set as the `winget-manifests` build artifact;
5. downloads the pinned `wingetcreate.exe`, verifies its pinned sha256, and submits a pull request;
   the token is passed through the `WINGET_CREATE_GITHUB_TOKEN` environment variable, not on the
   command line.

Secret: `WINGET_TOKEN`. The submission is three authenticated writes under your account — forking
`microsoft/winget-pkgs`, pushing a branch to the fork, and opening the pull request — and a headless
job has no interactive login, so a token is required. It must be a **classic** token with the
`public_repo` scope (add `delete_repo` if wingetcreate should remove its fork after a failed
submission): fine-grained tokens cannot drive this flow, because the cross-fork pull request needs
`pull_requests=write` on `microsoft/winget-pkgs`, a permission only the base repository owner can
grant (microsoft/winget-create#595).

## After the pull request

The winget-pkgs automation runs ten validation steps as GitHub checks (PR structure, manifest
schema, manifest policy, installer scan) and reports their state as labels; `Validation-Completed`
means every step passed. A community moderator then reviews the manifest and the installed package,
and the approval (`Moderator-Approved`) triggers the automatic merge; after the publish pipeline the
package appears in the source within about an hour.

Two things to expect on the first submission: the Microsoft CLA must be signed once (the PR gets a
`Needs-CLA` label with the link), and an unsigned portable binary can draw an installer-scan or
SmartScreen note. A moderator re-runs a flaky step with `@wingetbot run`; if a fix is requested
(`Needs-Author-Feedback`), answer within ten days — after that the bot closes the pull request.
Expect hours for the automated part and hours to a few days for the first human review.

Field fixes belong in the templates in `packaging/winget/`; after a template change, re-run the
pipeline and close the duplicate pull request if one appears.

If `wingetcreate submit` fails in the pipeline, the same command can be run locally:

```
wingetcreate.exe submit <manifest directory>
```

## URL validation

The validation pipeline checks the URLs in the manifest set — metadata URLs (`PublisherUrl`,
`PublisherSupportUrl`, `PackageUrl`, `LicenseUrl`, `ReleaseNotesUrl`) and the installer URL — and
fails the URL step with a `URL-Validation-Error` when one of them answers with an HTTP error; the
comment names the URL and the status code, and the domain step that follows is skipped. A publisher
site that is down or answers through a broken origin fails this way. The check runs from Azure IP
ranges, so a server that blocks them fails it too.

Fix the URL and re-run the validation; no manifest change is needed when the fix is on the site
side. `@wingetbot run` is a moderator command — it re-runs the validation and strips the transient
labels — so the re-run is requested from a moderator. The validation service also retries failed
steps on its own schedule: a failed run is picked up again within a few hours, the transient labels
are dropped, and the retry re-checks every URL.

## Verify and remove

```
winget install Lifestreamy.XrayVpn
xrayvpn --version
winget uninstall Lifestreamy.XrayVpn
```

Removal: close the pull request before it is merged; after it is merged, submit a removal pull
request to winget-pkgs.
