# `config/`

Variables for the Ansible role `xray_vpn`.

- `settings.yml` — all variables. Loaded from `deploy.yml` via `vars_files`.
- Personal values (`num_clients`, `reality_camouflage_domain`) — via `inventory.yml` (`--use-inventory`) or the client's CLI flags; details — in `docs/user/SETUP.en.md`.
- In molecule tests — as role parameters in `molecule/default/converge.yml` and `molecule/distro/converge.yml`.