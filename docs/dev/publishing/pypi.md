# PyPI

The `xrayvpn` package on pypi.org: `pip install xrayvpn`.

## Artifact

Wheel and sdist built from the tag by `publish-pypi.yml`.

## Pipeline

`publish-pypi.yml` runs on `ubuntu-24.04` in the `pypi` environment:

1. checks out the released tag;
2. builds the wheel and sdist with uv;
3. on a release, checks that the project version matches the tag (`vX.Y.Z` and
   `vX.Y.Z_experimental` both map to `X.Y.Z`) and uploads to pypi.org; on a manual run the guard
   allows TestPyPI only, which makes the manual path a rehearsal by design;
4. uploads through OIDC trusted publishing — there is no token secret; `skip-existing` keeps
   re-runs of an already published version harmless.

## Repair

Re-run the pipeline with the released tag and approve it.

## Verify

```
pip install xrayvpn
xrayvpn --version
```

The weekly `verify-channels` run installs the package into a clean virtual environment on
`ubuntu-24.04`.
