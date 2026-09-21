# `config/`

Параметры Ansible-роли `xray_vpn`.

- `settings.yml` — все переменные. Читается `deploy.yml` через `vars_files`.
- Личные значения (`num_clients`, `reality_camouflage_domain`) — через `inventory.yml` (`--use-inventory`) или CLI-флаги клиента; подробности — в `docs/user/SETUP.md`.
- В тестах molecule — параметрами роли в `molecule/default/converge.yml` и `molecule/distro/converge.yml`.