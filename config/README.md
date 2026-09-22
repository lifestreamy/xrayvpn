# `config/`

Параметры Ansible-роли `xray_vpn`.

- `settings.yml` — все переменные. Читается `deploy.yml` через `vars_files`.
- Личные значения (`num_clients`, `reality_camouflage_domain`) задаются в `inventory.yml` (`--use-inventory`) или CLI-флагами клиента.
- В тестах molecule — параметрами роли в `molecule/default/converge.yml` и `molecule/distro/converge.yml`.

## Выбор runtime

`xray_runtime` выбирает вариант развёртывания:

| `xray_runtime` | Что устанавливается | Когда выбирать |
|---|---|---|
| `native` (по умолчанию) | исполняемый файл Xray `/usr/local/xray/xray` под управлением systemd | Наименьший footprint (~10 МБ RAM); рекомендуемый вариант. |
| `docker` | Docker Engine + образ Xray через `xray.service.docker.j2` | Легаси-путь для старых развёртываний; не покрыт molecule-тестами. |

Сменить: `xray_runtime` в `settings.yml` → перезапустить playbook. Версия Xray — единый источник
`xray_version`; `:latest` не используйте (26.7.11 ломал VLESS+REALITY+vision).

## Переменные `settings.yml`

<details>
  <summary>Все переменные (для технарей)</summary>

| Переменная | Что делает |
|---|---|
| `xray_runtime` | Runtime: `native` (по умолчанию) или `docker`; см. «Выбор runtime» выше. |
| `xray_version` | Единая версия Xray-core (по умолчанию `"26.6.27"`). |
| `xray_container_repo` | Репозиторий для `docker` (по умолчанию `ghcr.io/xtls/xray-core`). |
| `num_clients` | Сколько клиентских конфигов сгенерировать (каждый со своим UUID). |
| `reality_camouflage_domain` | SNI легитимного сайта для маскировки REALITY (по умолчанию `dl.google.com`). Публичный параметр. |
| `xray_docker_image` | Явный пин образа контейнера (docker). Если не задан, образ собирается из `xray_container_repo:xray_version`. Сейчас задан `teddysun/xray:26.6.27`. |
| `xray_config_dir` | Каталог состояния на VPS (`/root/xray-config`). |
| `xray_client_configs_dir` | Каталог сгенерированных конфигов на VPS (`/root/vpn-configs`). |
| `xray_port` | Порт inbound (по умолчанию `443`). |
| `warp_enabled` | Включить WARP outbound (`true` / `false`). |
| `warp_ipv6` | IPv6 в WireGuard (`false` — IPv4-only по умолчанию). |
| `warp_endpoint` | Cloudflare WARP endpoint (`162.159.192.1:2408`). |
| `warp_mtu` | MTU WireGuard (`1420`). |
| `warp_wgcf_version` | Версия wgcf (`2.2.22`). |
| `warp_wgcf_url` | URL для скачивания wgcf. |
| `xray_backup_enabled` | Резервные копии с меткой времени перед перезаписью (`true`). |
| `xray_reality_rotate` | Полная ротация REALITY. По умолчанию `false`. Подробности — в [`docs/user/ROTATION.md`](../docs/user/ROTATION.md). |
| `xray_log_level` | Уровень подробных логов Xray внутри journald (`warning`). |
| `xray_log_access` | Access-лог Xray (пер-подключение). По умолчанию `false`. |
| `xray_journal_max_use` | Диск-потолок всего journal хоста (`120M`), не только Xray. |
| `xray_journal_retention_days` | Глубина истории journal в днях (`3`). |
| `xray_obs_timer` | «Чёрный ящик» — снапшот состояния сервера в journal каждый ~10 мин (`true`). |
| `xray_watchdog_enabled` | Watchdog: детект деградации WARP-egress / потока ошибок и точечный рестарт Xray (`true`). |
| `xray_watchdog_storm_count` | Сколько ошибок исходящего за 5 мин = «шторм» (`20`). |
| `xray_watchdog_min_fail_cycles` | Сколько циклов подряд без egress-ответа перед рестартом (`2`). |
| `xray_watchdog_max_restarts_per_hour` | Потолок авто-рестартов в час; дальше только `[ALERT]` (`3`). |
| `xray_watchdog_probe_port` | Порт loopback-зонда на `127.0.0.1` (`10820`). |

</details>