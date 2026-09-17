> **Document:** `docs/SETUP.en.md` · **Location:** `docs/` · **Version:** v0.4.2 · **Last updated:** 2026-09-13
>
> [Main README](../README.en.md) — project overview and quick start

# SETUP — configuration and operation

Below are the variables and steps that actually affect server behavior. I've deployed it more than once, everything is verified.

How to prepare a VPS and a local machine; what variables exist and how they affect behavior; how to check that everything works after deployment.

The full glossary is in [`docs/GLOSSARY.en.md`](GLOSSARY.en.md).

## Configuration files

| File | What it configures | How it affects |
|---|---|---|
| `inventory.yml` (created from `inventory.yml.example`: `cp` / `Copy-Item`) | VPS connection: host, user, port, key or password | Only for inventory mode (`--use-inventory` or `--inventory PATH`); CLI mode builds its own inventory and does not need `inventory.yml` |
| `config/settings.yml` | All server parameters: `num_clients`, `reality_camouflage_domain`, `warp_enabled`, `xray_port`, `xray_docker_image` and others | Read on every Ansible playbook run via `vars_files` |
| `deploy.yml` | The playbook entry point | Not a configuration surface — usually left alone |

Which parameters can be passed as CLI flags — connection (`--host`, `-u`, `-p`, `--pkey`, `--pass`, `--use-inventory`/`--inventory`, cleanup, verbosity) and common overrides (runtime, port, number of clients, WARP, rotation, ufw) — through the main `xrayvpn` client (see the "`xrayvpn deploy` CLI flags" section below; all run options — in the README Quick start). The rest of the configuration goes through `config/settings.yml`.

## `config/settings.yml` variables

<details>
  <summary>All variables (for techies)</summary>

| Variable | What it does |
|---|---|
| `xray_runtime` | Runtime selector: `native` (default), `docker`. See the "Runtime selector" section below. |
| `xray_version` | Single Xray-core version (default `"26.6.27"`). |
| `xray_container_repo` | Container repository for `docker` (default `ghcr.io/xtls/xray-core`). |
| `num_clients` | How many client configs to generate (each with its own UUID). |
| `reality_camouflage_domain` | SNI of a legitimate site for REALITY masking (default `dl.google.com`). Public parameter. |
| `xray_docker_image` | Explicit container image pin (docker). If unset, the image is assembled from `xray_container_repo:xray_version`. Currently set to `teddysun/xray:26.6.27`. |
| `xray_config_dir` | The state directory on the VPS (`/root/xray-config`). |
| `xray_client_configs_dir` | The generated configs directory on the VPS (`/root/vpn-configs`). |
| `xray_port` | The inbound port (default `443`). |
| `warp_enabled` | Enable the WARP outbound (`true` / `false`). |
| `warp_ipv6` | IPv6 in WireGuard (`false` — IPv4-only by default). |
| `warp_endpoint` | Cloudflare WARP endpoint (`162.159.192.1:2408`). |
| `warp_mtu` | WireGuard MTU (`1420`). |
| `warp_wgcf_version` | wgcf version (`2.2.22`). |
| `warp_wgcf_url` | URL for downloading wgcf. |
| `xray_backup_enabled` | Timestamped backups before overwriting (`true`). |
| `xray_reality_rotate` | Full REALITY rotation. Default `false`. Details — in [`docs/ROTATION.en.md`](ROTATION.en.md). |
| `xray_log_level` | Xray verbosity inside journald (`warning`). |
| `xray_log_access` | Xray per-connection access log. Default `false`. |
| `xray_journal_max_use` | Disk cap for the whole host journal, not only Xray (`120M`). |
| `xray_journal_retention_days` | How many days of journal history to keep (`3`). |
| `xray_obs_timer` | Black box: a read-only server-state snapshot into journald every ~10 min (`true`). |
| `xray_watchdog_enabled` | Watchdog: detect WARP-egress / error-stream failure and point-restart Xray (`true`). |
| `xray_watchdog_storm_count` | How many outbound errors in 5 min count as a storm (`20`). |
| `xray_watchdog_min_fail_cycles` | Consecutive dead egress-probe cycles before a restart (`2`). |
| `xray_watchdog_max_restarts_per_hour` | Auto-restart budget per hour; beyond it, only `[ALERT]` (`3`). |
| `xray_watchdog_probe_port` | Loopback-only probe port on `127.0.0.1` (`10820`). |

</details>

## Runtime selector

`config/settings.yml` supports two deployment variants through `xray_runtime`:

| `xray_runtime` | What gets installed | When to pick it |
|---|---|---|
| `native` (default) | Xray binary at `/usr/local/xray/xray` under systemd | Smallest footprint (~10 MB RAM); recommended for new deployments. |
| `docker` | Docker Engine + `teddysun/xray:26.6.27` via `xray.service.docker.j2` | Legacy escape hatch. Kept for compatibility with old deploys; not covered by molecule. |

To switch runtime, change `xray_runtime` in `config/settings.yml` and rerun the playbook. Related variables:

- `xray_version: "26.6.27"` — single source of truth for the Xray-core version. Do not use `:latest` (Incident 2026-07-28: 26.7.11 broke VLESS+REALITY+vision).
- `xray_container_repo: "ghcr.io/xtls/xray-core"` — repository used for `docker`.
- `xray_docker_image` — an explicit container image pin; currently `teddysun/xray:26.6.27`. The mechanism — the variables table below.

## `xrayvpn deploy` CLI flags

The main client is `python-client/` (the `xrayvpn deploy` command). It accepts:

- `--execution {remote|local}` — the node where ansible runs (the target is always the VPS): default `remote` (playbook on the server); `local` — run it from your own machine against the VPS over SSH (through WSL on Windows; useful on very weak VPSes). Without the flag — interactive choice, default `remote`.
- Confirmation: before any real run the client prints a deploy plan (node, target, auth — a password shown only as `******`, overrides, a warning when `--rotate` is on, configs destination) and asks for consent; `--no-interactive` — no prompts and no confirmation (CI/scripts).
- Low-memory VPS: with < 1024 MB RAM and no swap, the client offers to create a 1 GB swapfile before the deploy (explicit opt-in prompt; an existing swap configuration is never touched). If it is still too heavy — run ansible via `--execution local`.
- Connection parameters (the VPS target, both nodes): `--host/-H`, `--user/-u` (root), `--port/-p` (22), `--pkey` / `--pass` (mutually exclusive; if neither is set — hidden password prompt), `--use-inventory` (connection params and vars from your personal `inventory.yml`).
- `--inventory <path>` — ssh-inventory to use with `--execution local` instead of the generated one (in remote mode use `--use-inventory`).
- `--clients-dir <path>` — where generated client configs are saved (default `downloaded-clients/`).
- `--cleanup` (default) / `--full-cleanup` / `--no-cleanup` — remove server-side temporary data after the run. `--cleanup` keeps the venv cache for the next run, `--full-cleanup` removes it too.
- Overrides: `--runtime {native|docker}`, `--xray-port`, `--num-clients`, `--camouflage-domain`, `--warp/--no-warp`, `--rotate/--no-rotate`, `--manage-ufw/--no-ufw`, `--ru` (fully Russian interface, `--help` included; alternative — `XRAYVPN_LANG=ru`).
- `--dry-run` — local: `ansible-playbook --check`; remote: plan of commands without connecting.
- `--debug` / `--verbose` — Ansible `-vvv` / `-vvvv` + `xray_debug=true`.

Examples:

```bash
uv run --project python-client xrayvpn deploy --execution local --host 1.2.3.4 --no-warp
uv run --project python-client xrayvpn deploy --execution remote --host 1.2.3.4 --pkey ~/.ssh/id_rsa --runtime native
uv run --project python-client xrayvpn deploy --use-inventory --no-warp
```

Want plain `xrayvpn` on PATH without the `uv run` prefix — `uv tool install --editable python-client` from the repository root (details in [python-client/README.en.md](../python-client/README.en.md)).

In local mode the run uses a generated ssh-inventory `.xrayvpn-inventory.yml` (gitignored, mode 0600, removed after the run) holding the VPS parameters from flags/personal inventory plus passed overrides; everything else still comes from `config/settings.yml`. In remote mode the inventory is assembled on the server itself, and your personal `inventory.yml` is never uploaded.

The alternative shell clients (`shell-clients/`) accept only connection parameters plus cleanup and verbosity — see their `--help` for details.

## Standalone binary

The simplest way to use the tool is a single executable from [Releases](https://github.com/lifestreamy/xrayvpn/releases): `xrayvpn-<version>-windows-x64-portable.exe`, `xrayvpn-<version>-linux-x64-portable`, `xrayvpn-<version>-linux-arm64-portable`, `xrayvpn-<version>-macos-arm64-portable`. It embeds the same client and the bundled roles/playbooks (`xrayvpn/payload/…`), so no repository clone and no Python are needed.

- First run: Windows — SmartScreen "More info → Run anyway" (builds are unsigned); macOS — `chmod +x`, and with Gatekeeper open once via right-click → Open.
- Double-click (or running with no arguments) opens the console assistant: `deploy` asks for the host and password (hidden), `ru`/`en` switch the language, `help` and `deploy --help` show the rest.
- Configuration files live next to the binary: `config/settings.yml` and `inventory.yml` (from the same-folder `inventory.yml.example`) behave exactly as in a clone.
- Workspace resolution order (where the generated inventory, downloaded configs and staging are written): `XRAYVPN_HOME` → the binary's folder (if writable) → per-user state folder (Windows `%LOCALAPPDATA%\xrayvpn`, Linux `~/.local/share/xrayvpn`, macOS `~/Library/Application Support/xrayvpn`) → current folder. Do not put the binary into OneDrive/Google Drive or other synced folders — working files will fight the sync client.
- When the VPN stops answering: `xrayvpn service status` / `restart` / `logs`; the full sequence — [`docs/RUNBOOK.en.md`](RUNBOOK.en.md).
- Environment variables:

| Variable | Meaning |
|---|---|
| `XRAYVPN_LANG` | `ru` / `en` for interface and `--help` (flag `--ru` does the same); falls back to the system locale. |
| `XRAYVPN_HOME` | explicit workspace folder — overrides the order above. |
| `XRAYVPN_UPDATE_CHECK` | update check is on by default in binary builds (at most once per day, silent on failures); in source runs it is opt-in via `1`. Pre-releases never appear in the hint until a stable release exists. |

## About the project

This is a utility that uses Ansible to deploy an Xray VLESS + REALITY VPN server on a remote VPS. It generates client configs for Clash Verge / FlClash (Mihomo Meta YAML) and Amnezia VPN (JSON). Clash Verge and FlClash are the main recommended and tested clients. Amnezia works but isn't recommended because of instability. Platform wrappers: PowerShell and Bash. The PowerShell wrapper runs the Bash client through WSL.

## What you need before you start

**VPS:** fresh Ubuntu 20.04+ or Debian 11+, root or sudo, public IP.

**Local machine:** on Windows — WSL2 with Ubuntu/Debian and PowerShell 5.1+. Before paying for a VPS long-term, check it — [`docs/TEST-VPS.en.md`](TEST-VPS.en.md). Platform requirements — in the README, the "Requirements" section.

## WARP in detail

`warp_enabled: true` adds an outgoing tunnel through Cloudflare WARP: sites see the Cloudflare IP instead of your VPS IP.

- **IPv4-only by default** (`warp_ipv6: false`); if you have working IPv6 — `true`.
- **Endpoint:** `162.159.192.1:2408` (stable name — `engage.cloudflareclient.com:2408`); override in `config/settings.yml`.
- **Credentials:** `wgcf` 2.2.22, the role downloads it itself; `wgcf-account.toml` and `wgcf-profile.conf` — in `/root/xray-config/`.

Egress check — from outside the VPS, through a real VPN client: `curl -4 https://ifconfig.io` should return the Cloudflare IP. WARP rotation — in [`docs/ROTATION.en.md`](ROTATION.en.md), §4.

## Post-deployment checks

```bash
systemctl is-active xray                      # should return 'active'
nc -zv <VPS_IP> 443                           # port listening; replace <VPS_IP> with yours
```

Then connect with at least one real client (Clash Verge / FlClash / Amnezia) and verify traffic goes through it. The role's built-in checks don't replace this.

In the generated Clash/Mihomo profiles (Clash Verge, FlClash) the server IP is pinned by a DIRECT rule — traffic to the VPS itself must not go through the tunnel (anti-hairpin). If the server IP changes, regenerate the config instead of editing the rule by hand.

If the VPN stops working — step-by-step diagnosis and recovery: [`docs/RUNBOOK.en.md`](RUNBOOK.en.md).

## Adding more clients without rotation

To add a new client config without touching existing keys — increase `num_clients` in `config/settings.yml` and run the playbook. New UUIDs will be added to `reality-state.json`, new configs will appear in `/root/vpn-configs/` on the VPS and in `./downloaded-clients/` locally. Existing clients keep working.

## License

AGPL-3.0 with an additional commercial-use restriction. Free for personal use and non-commercial distribution. Commercial use — only with the author's written permission: **tim.korelov@yandex.com**.

Full text — in [`LICENSE`](../LICENSE) (English). A short summary in Russian — in [`LICENSE.ru.md`](../LICENSE.ru.md).
