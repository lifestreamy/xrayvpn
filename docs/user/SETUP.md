# SETUP — установка и настройка

Консольное приложение: всё для первого запуска и обычной работы. Технические детали — в соседних файлах.
Требования: VPS — свежий Ubuntu 20.04+ или Debian 11+, root или sudo, публичный IP; на Windows
для локального режима — WSL2 с Ubuntu/Debian.

## Содержание

- [Установка](#установка)
- [Первый запуск](#первый-запуск)
- [Подключение](#подключение)
- [После деплоя](#после-деплоя)
- [Параметры сервера](#параметры-сервера)
- [Помощь](#помощь)

## Установка

| Способ | Что делать | Комментарий |
|---|---|---|
| [Releases](https://github.com/lifestreamy/xrayvpn/releases/latest) | Скачать файл платформы и запустить | основной путь |
| [pip](https://pypi.org/project/xrayvpn/) | `pip install xrayvpn` | любые ОС с Python 3.12+ |
| apt | Репозиторий, `apt install xrayvpn` | Ubuntu 24.04 / Debian 12; подключение — в [README](../../README.md#быстрый-старт) |
| Из репозитория | `uv run --project python-client xrayvpn deploy` | запуск из исходников |

## Первый запуск

1. Скачайте файл для своей платформы из [Releases](https://github.com/lifestreamy/xrayvpn/releases/latest).
2. Windows — двойной клик; macOS и Linux — `chmod +x` и запуск из терминала.
3. В помощнике наберите `deploy`, укажите IP и пароль.
4. Конфиги клиентов появятся в `downloaded-clients`.

Windows при первом запуске покажет SmartScreen («Подробнее → Всё равно выполнить» — сборки без
подписи), macOS — попросит обойти Gatekeeper (правый клик → «Открыть»). Файл держите в обычной
папке, не в синхронизируемой; `config/settings.yml` и `inventory.yml` кладутся рядом с ним.

## Подключение

- Флаги: `--host`, `--user`, `--port`, `--pkey` или `--pass` (без них пароль спросится скрыто).
- Алиас хоста из `~/.ssh/config` подхватывается как в ssh.
- Режим: `--execution remote` (по умолчанию) или `local`; без флага — интерактивный выбор.
- Inventory: `--use-inventory` — личный `inventory.yml`; `--inventory <path>` — свой файл для `local`.

Полный список флагов и примеры — [`python-client/README.md`](../../python-client/README.md).

## После деплоя

- Состояние: `xrayvpn service status`; логи — `xrayvpn service logs`; перезапуск — `xrayvpn service restart`.
- Порт слушает: `nc -zv <VPS_IP> 443`. Затем подключитесь реальным клиентом — встроенные проверки
  роли этого не заменяют.
- В Mihomo-профилях (Clash Verge, FlClash) IP сервера закреплён правилом DIRECT — защита от петли:
  клиент не заворачивает своё соединение с VPS в туннель. Сменили IP — перегенерируйте конфиг.
- VPN не отвечает — [`RUNBOOK.md`](RUNBOOK.md), по шагам.

## Параметры сервера

Число клиентов, WARP, порт, домен маскировки — `config/settings.yml`; таблица переменных —
[`../../config/README.md`](../../config/README.md).

- Runtime: `xray_runtime: native` (по умолчанию) или `docker` — детали в `config/README.md`.
- WARP: `warp_enabled: true` — сайты увидят IP Cloudflare вместо IP вашего VPS; endpoint и IPv6 —
  в `config/settings.yml`, смена учётных данных — [`ROTATION.md`](ROTATION.md), §3.
- Больше клиентов без ротации: увеличьте `num_clients` и запустите playbook снова — новые конфиги
  добавятся, существующие продолжат работать.

## Помощь

`xrayvpn --help`, `xrayvpn deploy --help`; термины — [`GLOSSARY.md`](GLOSSARY.md).