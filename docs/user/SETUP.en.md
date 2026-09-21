# SETUP — install and configure

A console application: everything for the first run and everyday use. Technical details live in the neighbouring files.
Requirements: a VPS — fresh Ubuntu 20.04+ or Debian 11+, root or sudo, a public IP; on Windows for local mode — WSL2 with Ubuntu/Debian.

## Contents

- [Install](#install)
- [First run](#first-run)
- [Connection](#connection)
- [After the deploy](#after-the-deploy)
- [Server options](#server-options)
- [Help](#help)

## Install

| Way | What to do | Comment |
|---|---|---|
| [Releases](https://github.com/lifestreamy/xrayvpn/releases/latest) | Download the build for your platform and run it | the main path |
| [pip](https://pypi.org/project/xrayvpn/) | `pip install xrayvpn` | any OS with Python |
| apt | A repository, `apt install xrayvpn` | Ubuntu / Debian |
| Homebrew | `brew install lifestreamy/xrayvpn/xrayvpn` | macOS |
| winget | `winget install xrayvpn` | Windows |
| AUR | `xrayvpn-bin` | Arch Linux |
| From the repository | `uv run --project python-client xrayvpn deploy` | running from source |

## First run

1. Download the file for your platform from [Releases](https://github.com/lifestreamy/xrayvpn/releases/latest).
2. Windows — double-click; macOS and Linux — `chmod +x` and run it from a terminal.
3. In the helper, type `deploy`, give the IP and the password.
4. Client configs appear in `downloaded-clients`.

On the first run Windows shows SmartScreen ("More info → Run anyway" — the builds are unsigned),
macOS asks you to bypass Gatekeeper (right-click → Open). Keep the file in a regular folder, not in a
synced one; `config/settings.yml` and `inventory.yml` go next to it.

## Connection

- Flags: `--host`, `--user`, `--port`, `--pkey` or `--pass` (without them the password prompt is hidden).
- A host alias from `~/.ssh/config` works exactly as with ssh.
- Mode: `--execution remote` (default) or `local`; without the flag — an interactive choice.
- Inventory: `--use-inventory` — your `inventory.yml`; `--inventory <path>` — your own file for `local`.

The full flag list and examples — [`python-client/README.en.md`](../../python-client/README.en.md).

## After the deploy

- State: `xrayvpn service status`; logs — `xrayvpn service logs`; restart — `xrayvpn service restart`.
- The port is listening: `nc -zv <VPS_IP> 443`. Then connect with a real client — the role's built-in
  checks don't replace that.
- In Mihomo profiles (Clash Verge, FlClash) the server IP is pinned by a DIRECT rule — loop protection:
  the client never routes its own connection to the VPS through the tunnel. Changed the IP — regenerate
  the config.
- The VPN is down — [`RUNBOOK.en.md`](RUNBOOK.en.md), step by step.

## Server options

Client count, WARP, port, camouflage domain — `config/settings.yml`; the variables table —
[`../../config/README.en.md`](../../config/README.en.md).

- Runtime: `xray_runtime: native` (default) or `docker` — details in `config/README.en.md`.
- WARP: `warp_enabled: true` — sites see the Cloudflare IP instead of your VPS IP; endpoint and IPv6 —
  in `config/settings.yml`, credentials rotation — [`ROTATION.en.md`](ROTATION.en.md), §3.
- More clients without rotation: raise `num_clients` and run the playbook again — new configs are
  added, existing clients keep working.

## Help

`xrayvpn --help`, `xrayvpn deploy --help`; terms — [`GLOSSARY.en.md`](GLOSSARY.en.md).