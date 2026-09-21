# `python-client/`

> This is the English copy of [README.md](README.md); the Russian file is the base.

The primary `xrayvpn` client (Python) — deploy, update and rotate an Xray server.
Works the same on Windows, Linux and macOS; remote and local modes in one CLI.

## Install and run

The simplest option is the standalone binary with no Python: download the build for your
platform from [Releases](https://github.com/lifestreamy/xrayvpn/releases/latest). First run —
[../docs/user/SETUP.en.md](../docs/user/SETUP.en.md), "First run" section. To build the binary
yourself (Nuitka onefile, debug mode, smoke) — [BUILD.en.md](BUILD.en.md).

Working with the sources in the repository requires [uv](https://docs.astral.sh/uv/) (or Python 3.12+):

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"   # Windows
```

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh                                       # Linux/macOS
```

From the repository root:

```bash
uv run --project python-client xrayvpn --help
```

Inside `python-client/` (after `uv sync`) both `uv run xrayvpn ...` and `python -m xrayvpn` work.

On Windows you can skip flags entirely. Double-click `xrayvpn-deploy.pyw` (English UI) or
`xrayvpn-deploy-ru.pyw` (Russian UI): a console opens and the interactive deploy wizard starts.
The CLI asks for the execution node, the VPS host and SSH auth, prints a deploy plan and asks
for confirmation: nothing runs without it. The window stays open — failures and the exit code
are visible until you press Enter.

The hyphen in the launcher name is mandatory: `xrayvpn-deploy.pyw` cannot shadow
`import xrayvpn`, while a plain `xrayvpn.pyw` next to the package would.

### The `xrayvpn` command on PATH

To type `xrayvpn` in any terminal without the `uv run` prefix, from the repository root:

```bash
uv tool install --editable python-client
```

The install is editable — repository code changes apply immediately. Run it from the repository
folder: the client locates `deploy.yml` and `config/settings.yml` by walking up from the current
directory. Remove with `uv tool uninstall xrayvpn`.

## Interactive mode

`xrayvpn` with no arguments (or `xrayvpn repl`) opens the interactive mode: commands use the exact
CLI syntax without the prefix. `deploy` still asks for the missing pieces and confirms the plan;
`help` lists the built-ins (`version`, `lang ru|en`, `exit`); `deploy --help` shows every flag of
the deploy command. The welcome banner is reprinted whenever the language switches
(`lang ru|en` or just `ru`/`en`) and already shows `service` — the SSH recovery commands. The banner carries a "interrupted — rerun deploy" line with a docs link; a run shows stage progress `[1/7]…[7/7]`, counting seconds on the long stages.
Double-clicking the binary and the `.pyw` launchers are this very mode. On Windows with
Windows Terminal as the default terminal, double-clicking the `.exe` opens a classic conhost window
with the app icon (a `conhost.exe` relaunch); to stay in a Windows Terminal tab, use the `--wt`
flag or `XRAYVPN_IN_WT=1`.

## Where the deploy goes and where ansible runs

The target is **always a remote VPS**. `--execution` only picks the node where
ansible itself runs:

- **remote** (default) — the client bootstraps the VPS over SSH itself: environment
  setup, repo uploaded as a tarball (the server never needs GitHub), the playbook on the
  server, then it fetches the generated client configs. On a very small VPS the bootstrap
  and apt may hit the RAM limit (a built-in swap-guard covers this).
- **local** — the ansible control node is your own machine: directly on Linux/macOS
  (venv/PATH, default `~/xray-venv`), through WSL on Windows. The target stays the same
  VPS over SSH (creds: `--host/--user/--port/--pkey/--pass` flags or the personal
  `inventory.yml` via `--use-inventory`); generated configs are pulled back with the same
  ansible-fetch over SSH. Useful on weak VPSes where Ansible cannot run on the server
  itself. Password auth additionally requires `sshpass`.
- Without `--execution` the CLI asks in the terminal (default: remote).

Before any real run the client prints a **deploy plan** (node, target, auth — a password
is shown only as `******`, overrides, a warning when `--rotate` is set, where the configs
land) and asks for consent; `--no-interactive` skips all prompts for scripts/CI (missing
required values then fail). `--dry-run` needs no confirmation (it changes nothing).

## Examples

```bash
# VPS by IP: the password is prompted with hidden input (or pass --pkey ~/.ssh/id_ed25519)
uv run --project python-client xrayvpn deploy --host 1.2.3.4

# connection parameters from the personal inventory.yml
uv run --project python-client xrayvpn deploy --use-inventory

# ansible on your own machine against the same VPS, no WARP, no forced rotation
uv run --project python-client xrayvpn deploy --execution local --host 1.2.3.4 --no-warp --no-rotate

# the remote deploy plan without connecting anywhere
uv run --project python-client xrayvpn deploy --host 1.2.3.4 --dry-run
```

## `deploy` flags

- Execution node: `--execution remote|local` (the target is always the VPS; no flag asks, default remote).
- Non-interactive: `--no-interactive` — no prompts and no plan confirmation (for CI/scripts).
- Language: `--ru` — fully Russian interface (prompts, messages, errors, `--help`);
  works in any argument position, alternative — the `XRAYVPN_LANG=ru` environment variable.
- Server overrides (otherwise taken from `config/settings.yml`): `--runtime native|docker`,
  `--xray-port`, `--num-clients`, `--camouflage-domain`, `--warp/--no-warp`,
  `--rotate/--no-rotate` (regenerate the REALITY key and UUIDs / keep them),
  `--manage-ufw/--no-ufw`.
- Inventory: `--inventory PATH` — `--execution local` only: the ssh-inventory to run with
  (by default `.xrayvpn-inventory.yml` is generated from flags/inventory.yml, 0600, removed after the run);
  `--use-inventory` — reads connection vars from the personal `inventory.yml` in both nodes
  (overrides the host/key flags with a warning).
- Connection (the VPS target, both nodes): `--host`/`-H`, `--user`/`-u`, `--port`/`-p`,
  `--pkey FILE` (preferred), `--pass TEXT` (plain password, worse than a key; omit both and
  it prompts, hidden). Left alone, `--user`/`--port` are not pinned: a `~/.ssh/config` host
  keeps its user and port, a bare IP falls back to `root:22`.
- Output: `--clients-dir PATH` — where client configs are saved
  (default `<repo>/downloaded-clients/`, fetched from the server's `/root/vpn-configs`);
  `--no-config-download` skips fetching and leaves them on the server.
- Server-side cleanup (remote): by default the staging dir is removed, the venv stays;
  `--full-cleanup` removes the venv too, `--no-cleanup` leaves everything.
- Windows and `--execution local`: `--wsl-distro` (the WSL distro) and `--wsl-venv` (a venv holding
  `ansible-playbook`, default `~/xray-venv`).
- Diagnostics: `--dry-run` (local node: ansible `--check`; remote node: printed plan without connecting),
  `--debug` / `--verbose` (Ansible -vvv/-vvvv; mutually exclusive, as are `--pkey` with `--pass`).

Full list: `xrayvpn deploy --help`.

## Service actions (`xrayvpn service`)

Once the VPN is deployed and something degrades — point actions over SSH with the same
connection flags (`-H/--pkey/--pass/--use-inventory`): `service status` (state, journal,
listeners), `service restart` (restarts xray — WARP lives inside it), `service logs
[--since 30m] [--lines N] [--out DIR]` (dumps the journal to your machine: a finite snapshot
of the window, 30 minutes by default; Ctrl+C aborts the download and keeps the partial file),
`service reboot --yes` (last resort, requires the explicit `--yes`). The recovery sequence —
[`docs/user/RUNBOOK.en.md`](../docs/user/RUNBOOK.en.md).

## Layout

- `src/xrayvpn/` — the package (`cli/`, `core/`, `core/execution/`, `core/transport/`);
- `tests/` — pytest suite (the `python-client` CI leg runs it plus ruff; the `.pyw` launcher ↔ CLI
  contract is checked statically and by a real end-to-end launch);
- sibling repo zones: `shell-clients/` (Bash/PowerShell, maintained, not developed) and
  `scripts/` (contributor tooling).

Server configuration — [../docs/user/SETUP.en.md](../docs/user/SETUP.en.md), key rotation —
[../docs/user/ROTATION.en.md](../docs/user/ROTATION.en.md).
