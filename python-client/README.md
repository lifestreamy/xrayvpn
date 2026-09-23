# `python-client/`

> English version: [README.en.md](README.en.md).

Основной клиент `xrayvpn` (Python) — развертывание, обновление и ротация Xray-сервера.
Одинаково на Windows, Linux и macOS; удалённый и локальный режимы в одном CLI.

## Установка и запуск

Самый простой вариант — готовая standalone-сборка без Python: скачайте файл своей платформы
из [Releases](https://github.com/lifestreamy/xrayvpn/releases/latest).
Первый запуск — в [../docs/user/SETUP.md](../docs/user/SETUP.md), раздел «Первый запуск».
Как собрать самому (Nuitka onefile, режим отладки, smoke) — [BUILD.md](BUILD.md).

Ещё варианты установки: `pip install xrayvpn` (Python 3.12+; на Debian/Ubuntu — `pipx install
xrayvpn`) и apt-репозиторий — `apt install xrayvpn` (Ubuntu 24.04 / Debian 12; команды
подключения — в [корневом README](../README.md#быстрый-старт)).

Для работы с исходниками в репозитории нужен [uv](https://docs.astral.sh/uv/) (или Python 3.12+):

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"   # Windows
```

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh                                       # Linux/macOS
```

Из корня репозитория:

```bash
uv run --project python-client xrayvpn --help
```

Внутри `python-client/` (после `uv sync`) работают и `uv run xrayvpn ...`, и `python -m xrayvpn`.

На Windows можно вообще без флагов. Двойной клик по `xrayvpn-deploy.pyw` (английский интерфейс)
или `xrayvpn-deploy-ru.pyw` (русский) открывает консоль и запускает интерактивный мастер деплоя.
CLI спросит узел исполнения, хост VPS и SSH-аутентификацию, покажет план и запросит
подтверждение: без него ничего не выполняется. Окно остаётся открытым — ошибки и код возврата
видны до нажатия Enter.

Дефис в имени лаунчера обязателен: `xrayvpn.pyw` рядом с пакетом перехватывал бы
`import xrayvpn` на Windows.

### Команда `xrayvpn` в PATH

Чтобы вводить `xrayvpn` в любом терминале без префикса `uv run`, из корня репозитория:

```bash
uv tool install --editable python-client
```

Установка editable — изменения кода в репозитории применяются сразу. Запускать из папки
репозитория: клиент ищет `deploy.yml` и `config/settings.yml` вверх от текущей директории.
Удаление — `uv tool uninstall xrayvpn`.

## Интерактивный режим

`xrayvpn` без аргументов (или `xrayvpn repl`) открывает интерактивный режим: команды внутри —
с тем же синтаксисом, что CLI, без префикса. `deploy` спросит недостающее и покажет план как
обычно; `help` перечисляет встроенное (`version`, `lang ru|en`, `exit`); `deploy --help` —
полный список флагов развёртывания. Приветственная плашка перерисовывается при смене языка
(`lang ru|en` или просто `ru`/`en`) и сразу показывает `service` — аварийные команды по SSH.
Под ссылками — строка «прервалось — повтори деплой» со ссылкой на docs; во время прогона видно
прогресс этапов `[1/7]…[7/7]`, в долгих фазах — счётчик секунд.
Двойной клик по standalone-приложению и `.pyw`-обёртки —
это тот же режим. На Windows с Windows Terminal как терминалом по умолчанию двойной клик по `.exe`
открывает классическое окно conhost с иконкой приложения (перезапуск через `conhost.exe`); остаться
во вкладке Windows Terminal — флаг `--wt` или `XRAYVPN_IN_WT=1`.

## Куда ставится и где выполняется ansible

Цель деплоя — **всегда удалённый VPS**. `--execution` выбирает лишь узел, где
выполняется сам ansible:

- **remote** (по умолчанию) — окружение поднимается на VPS по SSH: bootstrap,
  загрузка репозитория tarball'ом (GitHub серверу не нужен), playbook на сервере,
  забор готовых клиентских конфигов. На слабом VPS bootstrap и apt могут упираться
  в память (для этого встроен swap-guard).
- **local** — ansible-контроллер на вашей машине: на Linux/macOS напрямую
  (venv/PATH, по умолчанию `~/xray-venv`), на Windows — через WSL. Цель та же —
  VPS по SSH (creds: флаги `--host/--user/--port/--pkey/--pass` или личный
  `inventory.yml` через `--use-inventory`), конфиги после прогона подтягиваются тем
  же ansible-fetch по SSH. Полезно на очень слабых VPS, где Ansible на самом
  сервере работать не может. Парольная аутентификация требует `sshpass`.
- Без `--execution` — вопрос в терминале (по умолчанию remote).

Перед любым реальным прогоном клиент показывает **план деплоя** (узел, цель,
аутентификация — пароль только `******`, изменения, предупреждение при `--rotate`,
куда лягут конфиги) и спрашивает согласие; `--no-interactive` отключает вопросы
для скриптов/CI (недостающие обязательные значения тогда — ошибка). `--dry-run`
план не подтверждает (он ничего не меняет).

## Примеры

```bash
# VPS по IP: пароль спросит скрыто (или заранее --pkey ~/.ssh/id_ed25519)
uv run --project python-client xrayvpn deploy --host 1.2.3.4

# параметры подключения из личного inventory.yml
uv run --project python-client xrayvpn deploy --use-inventory

# ansible с вашей машины против того же VPS, без WARP и без ротации
uv run --project python-client xrayvpn deploy --execution local --host 1.2.3.4 --no-warp --no-rotate

# план remote-развертывания без какого-либо подключения
uv run --project python-client xrayvpn deploy --host 1.2.3.4 --dry-run
```

## Флаги `deploy`

- Узел выполнения: `--execution remote|local` (цель всегда VPS; без флага — вопрос, дефолт remote).
- Неинтерактивно: `--no-interactive` — без вопросов и подтверждения плана (для CI/скриптов).
- Язык: `--ru` — полностью русский интерфейс (промпты, сообщения, ошибки, `--help`);
  работает в любой позиции аргументов, альтернатива — переменная окружения `XRAYVPN_LANG=ru`.
- Переопределения сервера (иначе берётся из `config/settings.yml`): `--runtime native|docker`,
  `--xray-port`, `--num-clients`, `--camouflage-domain`, `--warp/--no-warp`,
  `--rotate/--no-rotate` (перегенерация ключа REALITY и UUID / оставить как есть),
  `--manage-ufw/--no-ufw`.
- Инвентарь: `--inventory PATH` — только local, ssh-inventory для прогона (по умолчанию
  генерируется `.xrayvpn-inventory.yml` с параметрами VPS из флагов/inventory, 0600,
  после прогона удаляется);
  `--use-inventory` — читает подключение и переменные из личного `inventory.yml`
  (перекрывает host/key-флаги с предупреждением).
- Подключение (цель-VPS, оба узла): `--host`/`-H`, `--user`/`-u` (default `root`), `--port`/`-p` (default 22),
  `--pkey FILE` (предпочтительно), `--pass TEXT` (пароль в открытом виде, хуже ключа; без него —
  скрытый запрос). `--user`/`--port` без явного значения не пинуются: для хоста из
  `~/.ssh/config` работают user/port из конфига, для голого IP — `root:22`.
- Результат: `--clients-dir PATH` — куда сохранить конфиги клиентов
  (default `<repo>/downloaded-clients/`, забираются с сервера из `/root/vpn-configs`);
  `--no-config-download` — вообще не скачивать, оставить их на сервере.
- Уборка на сервере (remote): по умолчанию staging-каталог удаляется, venv остаётся;
  `--full-cleanup` — снести и venv, `--no-cleanup` — оставить всё.
- Windows и `--execution local`: `--wsl-distro` (дистрибутив WSL) и `--wsl-venv` (venv с
  `ansible-playbook`, по умолчанию `~/xray-venv`).
- Диагностика: `--dry-run` (узел local: ansible `--check`; узел remote: напечатанный план без подключения),
  `--debug` / `--verbose` (Ansible -vvv/-vvvv; вместе нельзя, как и `--pkey` с `--pass`).

Полная афиша: `xrayvpn deploy --help`.

## Сервисные действия (`xrayvpn service`)

Когда VPN уже развёрнут и что-то деградировало — точечные действия по SSH теми же флагами
подключения (`-H/--pkey/--pass/--use-inventory`): `service status` (состояние, журнал, слушатели),
`service restart` (перезапуск xray — WARP живёт внутри него),
`service logs [--since 30m] [--lines N] [--out DIR]` (дамп журнала на свою машину: конечный снимок
окна, по умолчанию 30 минут; Ctrl+C прерывает загрузку и сохраняет частичный файл),
`service reboot --yes` (крайний случай, только с явным `--yes`).
Порядок действий при сбое — [`docs/user/RUNBOOK.md`](../docs/user/RUNBOOK.md).

## Где что лежит

- `src/xrayvpn/` — пакет (`cli/`, `core/`, `core/execution/`, `core/transport/`);
- `tests/` — pytest-набор (в CI нога `python-client` гоняет его и ruff; контракт лаунчеров
  `.pyw` ↔ CLI проверяется статически и реальным запуском);
- смежные зоны репо: `shell-clients/` (Bash/PowerShell, поддержка без развития), `scripts/`
  (инструменты разработки).

Настройка сервера — [../docs/user/SETUP.md](../docs/user/SETUP.md), ротация ключей —
[../docs/user/ROTATION.md](../docs/user/ROTATION.md).
