# Developer tooling (contributor scripts)

> This is the English copy of [README.md](README.md); the Russian file is the base.

Loose scripts for repository contributors and CI. Not the main xrayvpn app
(that lives in `python-client/`) and not the user-facing shell clients
(`shell-clients/`).

| Directory | Purpose |
|---|---|
| `dev/` | local development environment setup (`setup_test_env.py`) |
| `test/` | local verification runs (`local_test.py`) |

Both scripts are plain Python 3 (stdlib only) and are idempotent. They run
against the test venv in WSL (`~/xray-venv`, see [`docs/dev/TEST-LOCAL.md`](../docs/dev/TEST-LOCAL.md)).
