# Glossary

Project terms. If you meet an unfamiliar word in the documentation, look it up here.

## Runtime selector (`xray_runtime`)

A parameter in `config/settings.yml` (`xray_runtime: native | docker`) that picks how the Xray server is launched. Default `native` — smallest footprint. `docker` — legacy escape hatch via Docker Engine.

## `xray_cli_command`

A runtime-aware command used to invoke the Xray CLI / keygen. Set as a fact in `roles/xray_vpn/tasks/runtime_setup.yml`: for `native` it is `/usr/local/bin/xray`, for `docker` it is `docker run --rm <image>`. The role uses it everywhere instead of a hard-coded `docker run`.

## `xray_container_image`

The container image for `docker`. The role computes it itself (pin or assembly from repository and version); how to set it and the current pin — the variables table in `config/README.en.md`.

## Rotation

Replacing credentials with new ones. After rotation, old client configs stop connecting — you need to distribute new ones. Details — in `docs/user/ROTATION.en.md`.

## The `xray_reality_rotate` switch

A parameter in `config/settings.yml` or the `-e xray_reality_rotate=true` command-line flag. Makes the Ansible role regenerate keys, short IDs and client UUIDs.

## REALITY

A stealth VPN technology in Xray — modified TLS 1.3. Masks itself as a legitimate third-party site via `reality_camouflage_domain` — for example, `dl.google.com`. Needs no domain of your own or a TLS certificate.

## VLESS

A tunnelling protocol in Xray with no built-in encryption. The security layer handles encryption and authentication — in this setup, REALITY (modified TLS 1.3 with X25519 key exchange).

## Private key / Public key

An X25519 key pair. REALITY uses it to authenticate the server: the private key stays on the server in `/root/xray-config/reality-state.json`, the public key goes into client configs. Session encryption is provided by TLS 1.3, not by this pair.

## Short ID

A short identifier of the "right client" during the handshake. Changes after rotation. Consists of 8 hex characters.

## Client UUID

A unique identifier the VPN client sends in every packet. Changes after rotation. Stored on the server in `reality-state.json` as an array.

## `num_clients`

How many client configs to generate. Increasing adds new UUIDs to `reality-state.json`. Decreasing doesn't remove existing UUIDs, it only reduces the number of exported configs.

## WARP

An extra outgoing tunnel through Cloudflare. Hides your VPS IP from visited sites — instead of your VPS IP they see the Cloudflare WARP IP. Optional. Enabled in `config/settings.yml` via `warp_enabled: true`.

WARP credentials are `wgcf-account.toml` and `wgcf-profile.conf` in `/root/xray-config/`. They rotate separately from REALITY (by deleting the files and re-running the playbook).

## `reality_camouflage_domain`

The SNI of a legitimate site REALITY masks itself as. Default `dl.google.com`. A public parameter, no rotation needed.

## `reality-state.json`

The file `/root/xray-config/reality-state.json` (mode `0600`). Stores `private_key`, `public_key`, `short_id` and `client_uuids`. The state between playbook runs. Before rotation a backup is created: `reality-state.json.bak-YYYY-MM-DD-HH:MM:SS`.

## `<VPS_IP>`

A placeholder. Your VPS IP address. Replace it before running commands from this guide.

## Interactive mode

`xrayvpn` with no arguments (or `xrayvpn repl`): the same commands as the CLI without the prefix;
`exit` returns to the shell. The earlier name was "REPL".

## Portable build (standalone)

A single executable from GitHub Releases with the roles and playbooks embedded; no Python and no
repository clone needed.

## Deployment staging directory

`/tmp/xrayvpn-<run-id>` on the VPS: the unpacked repository, the temporary inventory, fetched
configs. Leftovers are pruned by the next run; `--no-cleanup` keeps staging, `--full-cleanup` removes it together with the venv.

## Ansible / inventory

Ansible is a configuration management tool. The project role (`roles/xray_vpn/`) is applied to the VPS via `deploy.yml`. The inventory file (`inventory.yml`) describes the host connection. Syntax — standard Ansible inventory.

## `xray_manage_ufw`

Parameter in `config/settings.yml` (default `true`). The role does not install `ufw`; if `ufw` already exists on the server, it adds an allow rule for the `xray_port`/tcp port (never runs `ufw enable`, never touches other rules).

---

All `config/settings.yml` parameters are described in `config/README.en.md`.
