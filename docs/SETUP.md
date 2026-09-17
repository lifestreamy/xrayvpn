> **Document:** `docs/SETUP.md` · **Location:** `docs/` · **Version:** v0.4.2 · **Last updated:** 2026-09-13
>
> [Главный README](../README.md) — обзор проекта и быстрый старт

# SETUP — настройка и эксплуатация

Ниже — переменные и шаги, которые реально влияют на поведение сервера. Разворачивал не раз, всё проверено.

Как подготовить VPS и локальную машину; какие переменные есть и как влияют на поведение; как проверить, что после развёртывания всё работает.

Полный глоссарий терминов — в [`docs/GLOSSARY.md`](GLOSSARY.md).

## Файлы конфигурации

| Файл | Что настраивает | Как влияет |
|---|---|---|
| `inventory.yml` (создаётся из `inventory.yml.example`: `cp` / `Copy-Item`) | Подключение к VPS: хост, пользователь, порт, ключ или пароль | Только для inventory-режима (`--use-inventory` или `--inventory PATH`); CLI-режим собирает свой inventory сам и `inventory.yml` не требует |
| `config/settings.yml` | Все параметры сервера: `num_clients`, `reality_camouflage_domain`, `warp_enabled`, `xray_port`, `xray_docker_image` и остальные | Читается при каждом запуске Ansible playbook через `vars_files` |
| `deploy.yml` | Точка входа playbook | Не конфигурационная поверхность — обычно не трогается |

Какие параметры можно передать как CLI-флаги — подключение (`--host`, `-u`, `-p`, `--pkey`, `--pass`, `--use-inventory`/`--inventory`, cleanup, verbosity) и частые override'ы (runtime, порт, число клиентов, WARP, ротация, ufw) — через основной клиент `xrayvpn` (см. раздел «CLI-флаги `xrayvpn deploy`» ниже; все способы запуска — в быстром старте README). Остальная конфигурация — через `config/settings.yml`.

## Переменные `config/settings.yml`

<details>
  <summary>Все переменные (для технарей)</summary>

| Переменная | Что делает |
|---|---|
| `xray_runtime` | Runtime selector: `native` (по умолчанию), `docker`. См. раздел «Runtime selector» ниже. |
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
| `xray_reality_rotate` | Полная ротация REALITY. По умолчанию `false`. Подробности — в [`docs/ROTATION.md`](ROTATION.md). |
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

## Runtime selector

`config/settings.yml` поддерживает два варианта развёртывания через переменную `xray_runtime`:

| `xray_runtime` | Что устанавливается | Когда выбирать |
|---|---|---|
| `native` (по умолчанию) | исполняемый файл Xray `/usr/local/xray/xray` под управлением systemd | Наименьший footprint (~10 МБ RAM); рекомендуемый вариант для новых развёртываний. |
| `docker` | Docker Engine + `teddysun/xray:26.6.27` через `xray.service.docker.j2` | Легаси-путь. Оставлен для совместимости со старыми развёртываниями; не покрыт molecule-тестами. |

Изменить runtime можно в `config/settings.yml` (`xray_runtime: native` → `docker`) и перезапустить playbook. Дополнительные переменные:

- `xray_version: "26.6.27"` — единственный источник версии Xray-core. Не используйте `:latest` (Инцидент 2026-07-28: 26.7.11 сломал VLESS+REALITY+vision).
- `xray_container_repo: "ghcr.io/xtls/xray-core"` — репозиторий для `docker`.
- `xray_docker_image` — явный пин образа контейнера; сейчас `teddysun/xray:26.6.27`. Механизм — таблица переменных ниже.

## CLI-флаги `xrayvpn deploy`

Основной клиент — `python-client/` (команда `xrayvpn deploy`). Принимает:

- `--execution {remote|local}` — узел, где выполняется ansible (цель всегда VPS): по умолчанию `remote` (плейбук на сервере); `local` — прогон с вашей машины против VPS по SSH (Windows — через WSL; пригодится на совсем слабых VPS). Без флага — интерактивный выбор, дефолт `remote`.
- Подтверждение: перед реальным прогодом печатается план (узел, цель, аутентификация — пароль показывается как `******`, override'ы, предупреждение при `--rotate`, папка конфигов) и запрашивается согласие; `--no-interactive` — без вопросов и подтверждения (CI/скрипты).
- Малая память VPS: при RAM < 1024 МБ и отсутствии swap клиент перед деплоем предложит создать swap-файл 1 ГБ (явный opt-in-вопрос; существующие настройки swap не трогаются). Если и с swap тяжело — гоняйте ansible через `--execution local`.
- Параметры подключения (цель-VPS, оба узла): `--host/-H`, `--user/-u` (root), `--port/-p` (22), `--pkey` / `--pass` (взаимоисключающие; если ни один не задан — скрытый запрос пароля), `--use-inventory` (параметры и vars из личного `inventory.yml`).
- `--inventory <path>` — ssh-inventory для `--execution local` вместо генерируемого (в remote используйте `--use-inventory`).
- `--clients-dir <path>` — куда сохранять клиентские конфиги (по умолчанию `downloaded-clients/`).
- `--cleanup` (по умолчанию) / `--full-cleanup` / `--no-cleanup` — удаление временных данных на сервере после запуска. `--cleanup` оставляет venv-кэш для следующего запуска, `--full-cleanup` удаляет и его.
- Override'ы: `--runtime {native|docker}`, `--xray-port`, `--num-clients`, `--camouflage-domain`, `--warp/--no-warp`, `--rotate/--no-rotate`, `--manage-ufw/--no-ufw`, `--ru` (полностью русскоязычный интерфейс, включая `--help`; альтернатива — `XRAYVPN_LANG=ru`).
- `--dry-run` — local: `ansible-playbook --check`; remote: план команд без подключения.
- `--debug` / `--verbose` — Ansible `-vvv` / `-vvvv` + `xray_debug=true`.

Примеры:

```bash
uv run --project python-client xrayvpn deploy --execution local --host 1.2.3.4 --no-warp
uv run --project python-client xrayvpn deploy --execution remote --host 1.2.3.4 --pkey ~/.ssh/id_rsa --runtime native
uv run --project python-client xrayvpn deploy --use-inventory --no-warp
```

Хотите голый `xrayvpn` в PATH без префикса `uv run` — `uv tool install --editable python-client` из корня репозитория (подробности — [python-client/README.md](../python-client/README.md)).

В режиме local для прогона генерируется ssh-inventory `.xrayvpn-inventory.yml` (gitignored, права 0600, удаляется после прогона) с параметрами VPS из флагов/личного inventory и переданными override'ами; остальное по-прежнему берётся из `config/settings.yml`. В режиме remote inventory собирается на самом сервере, а личный `inventory.yml` на него не загружается никогда.

Альтернативные shell-клиенты (`shell-clients/`) принимают только параметры подключения плюс cleanup и verbosity — подробности в их `--help`.

## Standalone-приложение

Самый простой способ пользования — единый исполняемый файл из [Releases](https://github.com/lifestreamy/xrayvpn/releases): `xrayvpn-<версия>-windows-x64-portable.exe`, `xrayvpn-<версия>-linux-x64-portable`, `xrayvpn-<версия>-linux-arm64-portable`, `xrayvpn-<версия>-macos-arm64-portable`. Внутри — тот же клиент и встроенный набор ролей/плейбуков (`xrayvpn/payload/…`), поэтому клон репозитория и python не нужны.

- Первый запуск: Windows — SmartScreen «Подробнее → Всё равно выполнить» (сборки без подписи); macOS — `chmod +x`, при Gatekeeper — открыть через ПКМ → «Открыть».
- Двойной клик (или запуск без аргументов) открывает консольного ассистента: `deploy` спросит узел и пароль скрыто, `ru`/`en` переключают язык, `help` и `deploy --help` показывают остальное.
- Файлы конфигурации кладутся рядом с исполняемым файлом: `config/settings.yml` и `inventory.yml` (из `inventory.yml.example` рядом же) работают с той же семантикой, что в клоне.
- Каталог рабочей области (куда пишутся временный inventory, скачанные конфиги, staging) определяется по порядку: `XRAYVPN_HOME` → папка с исполняемым файлом (если запись разрешена) → пользовательский каталог состояния (Windows `%LOCALAPPDATA%\xrayvpn`, Linux `~/.local/share/xrayvpn`, macOS `~/Library/Application Support/xrayvpn`) → текущая папка. Не помещайте standalone-приложение в OneDrive/Google Drive и прочие синхронизируемые папки: рабочие файлы будут конфликтовать с синхронизацией.
- Если VPN перестал отвечать: `xrayvpn service status` / `restart` / `logs`, полный порядок действий — [`docs/RUNBOOK.md`](RUNBOOK.md).
- Переменные окружения:

| Переменная | Действие |
|---|---|
| `XRAYVPN_LANG` | `ru` / `en` — язык интерфейса и `--help` (флаг `--ru` то же); без неё берётся системная локаль. |
| `XRAYVPN_HOME` | явный каталог рабочей области — переопределяет порядок выше. |
| `XRAYVPN_UPDATE_CHECK` | в standalone-приложении проверка новых релизов включена по умолчанию (не чаще раза в сутки, failures silent); исходный python-режим — по запросу `1`. Pre-release-сборки в подсказке не участвуют, пока не появится stable-релиз. |

## Про проект

Это утилита, использующая Ansible для развёртывания Xray VLESS + REALITY VPN-сервера на удалённом VPS. Генерирует клиентские конфиги для Clash Verge / FlClash (Mihomo Meta YAML) и Amnezia VPN (JSON). Clash Verge и FlClash — основные рекомендуемые и протестированные клиенты. Amnezia — рабочий, но не рекомендуемый из-за нестабильности вариант. Для запуска на разных платформах есть обёртки: PowerShell и Bash. PowerShell-обёртка запускает bash-клиент через WSL.

## Что нужно знать перед началом

**VPS:** свежий Ubuntu 20.04+ или Debian 11+, root или sudo, публичный IP.

**Локальная машина:** на Windows — WSL2 с Ubuntu/Debian и PowerShell 5.1+. Перед оплатой VPS на длительный срок проверяйте его — [`docs/TEST-VPS.md`](TEST-VPS.md). Требования по платформам — в README, раздел «Требования».

## WARP подробно

`warp_enabled: true` добавляет исходящий туннель через Cloudflare WARP: сайты видят IP Cloudflare вместо IP вашего VPS.

- **IPv4-only по умолчанию** (`warp_ipv6: false`); при рабочем IPv6 — `true`.
- **Endpoint:** `162.159.192.1:2408` (стабильное имя — `engage.cloudflareclient.com:2408`); переопределяется в `config/settings.yml`.
- **Учётные данные:** `wgcf` 2.2.22, роль скачивает его сама; `wgcf-account.toml` и `wgcf-profile.conf` — в `/root/xray-config/`.

Проверка egress — снаружи VPS, через реальный VPN-клиент: `curl -4 https://ifconfig.io` должен вернуть IP Cloudflare. Ротация WARP — в [`docs/ROTATION.md`](ROTATION.md), §4.

## Проверка после развёртывания

```bash
systemctl is-active xray                      # должно вернуть 'active'
nc -zv <VPS_IP> 443                           # порт слушает; <VPS_IP> — на свой
```

Затем подключитесь хотя бы одним реальным клиентом (Clash Verge / FlClash / Amnezia) и проверьте, что трафик идёт через него. Встроенные проверки роли этого не заменяют.

В генерируемых Clash/Mihomo-профилях (Clash Verge, FlClash) IP сервера закреплён правилом DIRECT: трафик к самому VPS не должен идти через туннель (анти-hairpin). Сменили IP сервера — перегенерируйте конфиг, а не правьте правило вручную.

Если VPN перестал работать — диагностика и восстановление по шагам: [`docs/RUNBOOK.md`](RUNBOOK.md).

## Как добавить ещё клиентов без ротации

Если вы хотите добавить новый клиентский конфиг, не трогая существующие ключи — увеличьте `num_clients` в `config/settings.yml` и запустите playbook. Новые UUID добавятся в `reality-state.json`, новые конфиги появятся в `/root/vpn-configs/` на VPS и в `./downloaded-clients/` локально. Существующие клиенты продолжают работать.

## Лицензия

AGPL-3.0 с дополнительным ограничением коммерческого использования. Свободно для личного использования и некоммерческого распространения. Коммерческое использование — только с моего письменного разрешения: **tim.korelov@yandex.com**.

Полный текст — в [`LICENSE`](../LICENSE) (English). Краткое описание на русском — в [`LICENSE.ru.md`](../LICENSE.ru.md).
