# Developer tooling (contributor scripts)

> This is the English copy of [README.md](README.md); the Russian file is the base.

Loose scripts for repository contributors, CI and CD. Not the main xrayvpn app
(that lives in `python-client/`) and not the user-facing shell clients
(`shell-clients/`).

| Directory | Purpose |
|---|---|
| `dev/` | local development environment setup (`setup_test_env.py`) |
| `test/` | local verification runs (`local_test.py`) |
| `cd/` | channel artifact and update manifest rendering (`render_channels.py`, `make_release_manifest.py`) |

The `dev/` and `test/` scripts are plain Python 3 (stdlib only) and are idempotent. They run
against the test venv in WSL (`~/xray-venv`, see [`docs/dev/TEST-LOCAL.md`](../docs/dev/TEST-LOCAL.md)).
The `cd/` scripts are stdlib-only as well; release pipelines invoke them
(see [`docs/dev/publishing/`](../docs/dev/publishing/README.md)).
