# `config/`

Variables for the Ansible role `xray_vpn`.

- `settings.yml` — all variables. Loaded from `deploy.yml` via `vars_files`.
- Personal values (`num_clients`, `reality_camouflage_domain`) — via `inventory.yml` (`--use-inventory`) or the client's CLI flags.
- In molecule tests — as role parameters in `molecule/default/converge.yml` and `molecule/distro/converge.yml`.

## Runtime selector

`xray_runtime` picks the deployment variant:

| `xray_runtime` | What gets installed | When to pick it |
|---|---|---|
| `native` (default) | Xray binary at `/usr/local/xray/xray` under systemd | Smallest footprint (~10 MB RAM); recommended. |
| `docker` | Docker Engine + an Xray image via `xray.service.docker.j2` | Legacy path for old deployments; not covered by molecule. |

To switch: change `xray_runtime` in `settings.yml` and rerun the playbook. The Xray version has a
single source — `xray_version`; don't use `:latest` (26.7.11 broke VLESS+REALITY+vision).

## `settings.yml` variables

<details>
  <summary>All variables (for techies)</summary>

| Variable | What it does |
|---|---|
| `xray_runtime` | Runtime: `native` (default) or `docker`; see "Runtime selector" above. |
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
| `xray_reality_rotate` | Full REALITY rotation. Default `false`. Details — in [`docs/user/ROTATION.en.md`](../docs/user/ROTATION.en.md). |
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