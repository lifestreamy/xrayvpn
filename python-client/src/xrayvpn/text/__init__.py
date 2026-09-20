"""User-facing string catalog: key → (EN, RU).

Single source for client UI text (rule in `.kilo/rules` gate after v0.4.x): no
user-visible literals outside this module; call sites use `i18n.t(KEY, **fmt)`.
Templates interpolate via `{param}` markers; `{value!r}` conversions allowed.
`xrayvpn/i18n.py` is the mechanism (language state); this package is the data.
"""

from __future__ import annotations

from typing import Final, NamedTuple


class Entry(NamedTuple):
    en: str
    ru: str


MESSAGES: Final[dict[str, Entry]] = {
    # --- shared prompts and error envelope ---
    "COMMON_HOST_PROMPT": Entry(
        "VPS host (IP, hostname or ~/.ssh/config alias)",
        "Хост VPS (IP, hostname или алиас ~/.ssh/config)",
    ),
    "COMMON_SSH_PASS_PROMPT": Entry("SSH password: ", "SSH-пароль: "),
    "COMMON_DEFAULT_ON": Entry("enabled", "включено"),
    "COMMON_DEFAULT_OFF": Entry("disabled", "выключено"),
    "COMMON_ERR": Entry("error: {err}", "ошибка: {err}"),
    "COMMON_USER": Entry("SSH user", "SSH-пользователь"),
    "COMMON_PORT": Entry("SSH port", "SSH-порт"),
    "COMMON_PKEY": Entry(
        "Path to an SSH private key", "Путь к приватному SSH-ключу"
    ),
    "COMMON_PASS": Entry(
        "SSH password (avoid, prefer --pkey)",
        "SSH-пароль (не рекомендуется, лучше --pkey)",
    ),
    # --- core: executors and update check ---
    "EXEC_BOOTSTRAP_FAIL": Entry(
        "[remote] bootstrap failed: {command}\n{err}",
        "[remote] ошибка bootstrap: {command}\n{err}",
    ),
    "EXEC_EXTRACT_FAIL": Entry(
        "[remote] extract failed:\n{err}",
        "[remote] ошибка распаковки:\n{err}",
    ),
    "EXEC_PLAYBOOK_FAIL": Entry(
        "[remote] playbook failed (rc={rc})",
        "[remote] ошибка playbook (rc={rc})",
    ),
    "EXEC_FETCHED": Entry("[remote] fetched {name}", "[remote] получен {name}"),
    "EXEC_UPDATE_AVAILABLE": Entry(
        "update available: {tag} — {page}",
        "доступно обновление: {tag} — {page}",
    ),
    "I18N_LANG_WARNING": Entry(
        "warning: unknown {env} value {value!r}; falling back to English",
        "предупреждение: неизвестное значение {env} {value!r}; переключаюсь на английский",
    ),
    # --- interactive session (repl) ---
    "REPL_LANG_NOTICE": Entry(
        "interface language: English", "язык интерфейса: русский"
    ),
    "REPL_WELCOME_SWITCH": Entry(
        'Русский интерфейс — введите "ru" (можно "рус")',
        'English interface — type "en" (or "english")',
    ),
    "REPL_WELCOME_TITLE": Entry(
        "xrayvpn — VPN server provisioning assistant",
        "xrayvpn — помощник развёртывания VPN-сервера",
    ),
    "REPL_WELCOME_PURPOSE": Entry(
        "Deploys a self-hosted Xray VLESS + REALITY VPN server on a remote VPS.",
        "Разворачивает собственный VPN-сервер Xray VLESS + REALITY на удалённом VPS.",
    ),
    "REPL_WELCOME_MAIN": Entry("Main command:", "Основная команда:"),
    "REPL_WELCOME_OTHER": Entry("Other commands:", "Другие команды:"),
    "REPL_WELCOME_CMD_HELP": Entry("command list", "список команд"),
    "REPL_WELCOME_CMD_FLAGS": Entry("all flags", "все флаги"),
    "REPL_WELCOME_CMD_VERSION": Entry("show version", "показать версию"),
    "REPL_WELCOME_CMD_BANNER": Entry(
        "show this screen again", "показать этот экран снова"
    ),
    "REPL_WELCOME_CMD_SERVICE": Entry(
        "status/restart/logs/reboot over SSH",
        "состояние/рестарт/логи/перезагрузка по SSH",
    ),
    "REPL_WELCOME_CMD_EXIT": Entry("leave", "выход"),
    "REPL_WELCOME_AUTHOR": Entry("by:", "автор:"),
    "REPL_WELCOME_AUTHOR_NAME": Entry("Tim Korelov", "Tim Korelov"),
    "REPL_WELCOME_REPO": Entry("repository:", "репозиторий:"),
    "REPL_WELCOME_REPO_NAME": Entry("xrayvpn", "xrayvpn"),
    "REPL_WELCOME_RELEASES": Entry("releases:", "релизы:"),
    "REPL_WELCOME_RELEASES_NAME": Entry("releases/latest", "releases/latest"),
    "REPL_SHORT_HINT": Entry(
        'type "deploy" to start, "help" for the command list, "exit" to leave',
        'введите "deploy" чтобы начать, "help" — список команд, "exit" — выход',
    ),
    "REPL_HELP_HEADER": Entry("commands:", "команды:"),
    "REPL_HELP_DEPLOY": Entry(
        "  deploy [flags]   same syntax as: xrayvpn deploy --help",
        "  deploy [флаги]   тот же синтаксис, что у xrayvpn deploy --help",
    ),
    "REPL_HELP_SERVICE": Entry(
        "  service status|restart|logs|reboot --help — recovery actions",
        "  service status|restart|logs|reboot --help — диагностика и восстановление",
    ),
    "REPL_HELP_LANG": Entry(
        "  lang ru|en       switch interface language now (рус/англ ok)",
        "  lang ru|en       переключить язык интерфейса (рус/англ тоже)",
    ),
    "REPL_HELP_HELP": Entry("  help             this list", "  help             этот список"),
    "REPL_HELP_BANNER": Entry(
        "  banner           show the welcome screen again",
        "  banner           показать приветственный экран снова",
    ),
    "REPL_HELP_VERSION": Entry(
        "  version          show version", "  version          показать версию"
    ),
    "REPL_HELP_EXIT": Entry(
        "  exit|quit|q      leave (Ctrl+D works too)",
        "  exit|quit|q      выход (или Ctrl+D)",
    ),
    "REPL_HELP_NOTE": Entry(
        "note: the built-in --help language is fixed at process start (--ru / XRAYVPN_LANG).",
        "заметка: язык встроенного --help фиксируется при запуске процесса (--ru / XRAYVPN_LANG).",
    ),
    "REPL_KI_TIP": Entry(
        'type "exit" or press Ctrl+D to leave',
        'введите "exit" или нажмите Ctrl+D для выхода',
    ),
    "REPL_UNKNOWN_OPT": Entry(
        "unknown option: {opts} (help — command list)",
        "неизвестная опция: {opts} (help — список команд)",
    ),
    "REPL_ALREADY": Entry(
        "[session] you are already in a session", "[сессия] вы уже в сессии"
    ),
    "REPL_ABORTED": Entry(
        "[cancel] command aborted; the session continues",
        "[отмена] команда прервана; сессия продолжает работу",
    ),
    "REPL_INTERRUPTED": Entry(
        "[interrupted] command aborted; the session continues",
        "[прервано] команда остановлена; сессия продолжает работу",
    ),
    "REPL_LANG_USAGE": Entry("usage: lang ru|en", "использование: lang ru|en"),
    "REPL_DISPATCH_ERROR": Entry(
        "[error] command failed: {err}",
        "[ошибка] команда завершилась сбоем: {err}",
    ),
    # --- service command ---
    "SVC_HELP": Entry(
        "Service status and point recovery over SSH (target is always the VPS).",
        "Состояние сервиса и точечное восстановление по SSH (цель всегда VPS).",
    ),
    "SVC_HOST_OPT": Entry(
        "VPS host/IP or ~/.ssh/config alias", "Хост/IP VPS или алиас ~/.ssh/config"
    ),
    "SVC_INVENTORY_OPT": Entry(
        "Read connection params from the personal inventory.yml",
        "Читать параметры подключения из личного inventory.yml",
    ),
    "SVC_RU_OPT": Entry("Russian interface output", "Русский вывод интерфейса"),
    "SVC_NOINT_OPT": Entry(
        "Never prompt (CI/scripts)", "Никогда не спрашивать (CI/скрипты)"
    ),
    "SVC_SINCE_OPT": Entry(
        "journal window for the dump: 30m | 24h | 7d (default 30m)",
        "окно дампа журнала: 30m | 24h | 7d (по умолчанию 30m)",
    ),
    "SVC_LINES_OPT": Entry(
        "keep only the last N journal lines (default: the whole window)",
        "сохранить только последние N строк журнала (по умолчанию: всё окно)",
    ),
    "SVC_LINES_INVALID": Entry(
        "invalid --lines {value} (expected a positive number)",
        "неверный --lines {value} (ожидается положительное число)",
    ),
    "SVC_OUT_OPT": Entry(
        "where to save the dump (file or folder; default <workspace>/logs/)",
        "куда сохранить дамп (файл или папка; по умолчанию <workspace>/logs/)",
    ),
    "SVC_YES_OPT": Entry(
        "required confirmation: the host reboot really happens",
        "обязательное подтверждение: reboot хоста реально выполнится",
    ),
    "SVC_SINCE_INVALID": Entry(
        "invalid --since {value!r} (expected like 30m, 24h, 7d)",
        "неверный --since {value!r} (ожидаётся формат вроде 30m, 24h, 7d)",
    ),
    "SVC_STATUS_TITLE": Entry(
        "service xray@{host}:{port} — {active}",
        "сервис xray@{host}:{port} — {active}",
    ),
    "SVC_STATUS_FACTS": Entry(
        "restarts(NRestarts)={n} since={since} sub={sub}",
        "рестартов(NRestarts)={n} с={since} под={sub}",
    ),
    "SVC_STATUS_STORM": Entry(
        "outbound errors in the last 30 min: {count}",
        "ошибок исходящего за последние 30 мин: {count}",
    ),
    "SVC_STATUS_ERRORS": Entry(
        "errors in the last 30 min (wireguard/level):",
        "ошибки за последние 30 мин (wireguard/level):",
    ),
    "SVC_STATUS_NO_ERRORS": Entry(
        "  no errors in the window", "  в окне ошибок нет"
    ),
    "SVC_DEEP_RUNTIME": Entry("runtime: {runtime}", "рантайм: {runtime}"),
    "SVC_DEEP_VERSION": Entry("xray: {version}", "xray: {version}"),
    "SVC_DEEP_VERSION_OK": Entry(
        "xray: {version} (matches settings.yml)",
        "xray: {version} (совпадает с settings.yml)",
    ),
    "SVC_DEEP_VERSION_MISMATCH": Entry(
        "xray: {version} (settings.yml expects {expected})",
        "xray: {version} (settings.yml ожидает {expected})",
    ),
    "SVC_DEEP_VERSION_NA": Entry("xray: n/a", "xray: н/д"),
    "SVC_DEEP_AGE": Entry("{days}d {hours}h", "{days} д {hours} ч"),
    "SVC_DEEP_REALITY": Entry(
        "REALITY: {age} since rotation, public {prefix}…, shortId {sid}, clients {clients}",
        "REALITY: {age} с ротации, public {prefix}…, shortId {sid}, клиентов {clients}",
    ),
    "SVC_DEEP_REALITY_NA": Entry(
        "REALITY: n/a (no state file)", "REALITY: н/д (нет файла состояния)"
    ),
    "SVC_DEEP_WARP_ON": Entry(
        "WARP: on, egress {egress} vs server {server}",
        "WARP: вкл, egress {egress} vs сервер {server}",
    ),
    "SVC_DEEP_WARP_NO_PROBE": Entry(
        "WARP: on, probe n/a (egress IP unavailable)",
        "WARP: вкл, зонд н/д (egress IP недоступен)",
    ),
    "SVC_DEEP_WARP_OFF": Entry(
        "WARP: off, server egress {server}", "WARP: выкл, egress сервера {server}"
    ),
    "SVC_DEEP_WARP_NA": Entry(
        "WARP: n/a (config not readable)", "WARP: н/д (конфиг не читается)"
    ),
    "SVC_JOURNAL_TAIL": Entry("journal tail (last 5):", "хвост журнала (5):"),
    "SVC_LISTENERS": Entry("listeners:", "слушатели:"),
    "SVC_MEMORY": Entry("memory:", "память:"),
    "SVC_RESTARTED": Entry(
        "[done] xray restarted ({state}); clients reconnect in 10-15s",
        "[готово] xray перезапущен ({state}); клиенты переподключатся за 10-15 с",
    ),
    "SVC_LOGS_SAVED": Entry(
        "[done] journal ({since}, {lines} lines) saved to {path}",
        "[готово] журнал ({since}, строк: {lines}) сохранён в {path}",
    ),
    "SVC_LOGS_CANCELLED": Entry(
        "[cancel] interrupted; the partial dump ({lines} lines) is saved to {path}",
        "[отмена] прервано; частичный дамп (строк: {lines}) сохранён в {path}",
    ),
    "SVC_REBOOT_NEED_YES": Entry(
        "error: a full host reboot is a last resort (see docs/RUNBOOK first);"
        " rerun with --yes to confirm",
        "ошибка: полный reboot хоста — крайнее средство (сначала docs/RUNBOOK);"
        " повторите с --yes для подтверждения",
    ),
    "SVC_REBOOTING": Entry(
        "[ok] host {host} is rebooting; the VPN comes up with systemd (allow a minute)",
        "[ок] хост {host} перезагружается; VPN поднимется вместе с systemd (минута)",
    ),
    # --- deploy command (main) ---
    "MAIN_APP_HELP": Entry(
        "Provision an Xray VLESS + REALITY VPN server on a remote VPS.",
        "Развёртывание VPN-сервера Xray VLESS + REALITY на удалённом VPS.",
    ),
    "MAIN_VERSION_OPT": Entry(
        "Show the version and exit.", "Показать версию и выйти."
    ),
    "MAIN_RU_OPT": Entry(
        "Переключает вывод интерфейса на русский (Switches interface output to Russian); "
        "в REPL язык переключается командами ru/en (in REPL use `ru`/`en` to switch)",
        "Переключает вывод интерфейса на русский (Switches interface output to Russian); "
        "в REPL язык переключается командами ru/en (in REPL use `ru`/`en` to switch)",
    ),
    "MAIN_PAUSE": Entry(
        "Press Enter to close this window...",
        "Нажмите Enter, чтобы закрыть окно...",
    ),
    "MAIN_EXEC_PROMPT": Entry(
        "Execution node (where ansible runs; the target is always the VPS)",
        "Узел исполнения ansible (где запускается плейбук; цель — всегда VPS)",
    ),
    "MAIN_EXEC_UNKNOWN": Entry(
        "error: unknown execution mode: {mode}",
        "ошибка: неизвестный режим исполнения: {mode}",
    ),
    "MAIN_PLAN_HEADER": Entry("deploy plan:", "план деплоя:"),
    "MAIN_CONFIRM_TTY": Entry(
        "error: confirmation needs a terminal; add --no-interactive to run without it",
        "ошибка: подтверждение требует терминала; добавьте --no-interactive для запуска без него",
    ),
    "MAIN_CONFIRM_START": Entry("Start the deploy?", "Начать деплой?"),
    "MAIN_ABORT": Entry("[abort] deploy cancelled", "[отмена] деплой отменён"),
    "MAIN_INV_OVERRIDES": Entry(
        "warning: --use-inventory overrides connection/auth flags",
        "предупреждение: --use-inventory переопределяет флаги подключения/аутентификации",
    ),
    "MAIN_INV_NOT_READY": Entry(
        "error: {path} is not ready for deploy:",
        "ошибка: {path} не готов к деплою:",
    ),
    "MAIN_INV_FILL": Entry(
        "  fill the keys under all.hosts.<host> as in inventory.yml.example",
        "  заполните ключи в all.hosts.<host> как в inventory.yml.example",
    ),
    "MAIN_INV_NOAUTH": Entry(
        "note: no auth key in inventory.yml; the SSH password will be requested"
        " at run time (or set ansible_ssh_private_key_file)",
        "заметка: в inventory.yml нет ключа аутентификации; SSH-пароль будет"
        " запрошен во время запуска (или укажите ansible_ssh_private_key_file)",
    ),
    "MAIN_PLAN_RUNNER_REMOTE": Entry(
        "ansible runs ON THE VPS (SSH bootstrap, server-side playbook)",
        "ansible выполняется НА VPS (SSH-бутстрап, плейбук на сервере)",
    ),
    "MAIN_PLAN_RUNNER_LOCAL": Entry(
        "ansible runs ON THIS MACHINE (Windows: WSL) against the VPS over SSH",
        "ansible выполняется НА ЭТОЙ МАШИНЕ (Windows: WSL), цель — VPS по SSH",
    ),
    "MAIN_PLAN_ALIAS": Entry(
        "ssh alias: {alias} → {host}:{port}",
        "ssh-алиас: {alias} → {host}:{port}",
    ),
    "MAIN_PLAN_TARGET": Entry(
        "target: {user}@{host}:{port}", "цель: {user}@{host}:{port}"
    ),
    "MAIN_PLAN_AUTH": Entry("auth: {desc}", "аутентификация: {desc}"),
    "MAIN_PLAN_OVERRIDES": Entry(
        "overrides: {display}", "переопределения: {display}"
    ),
    "MAIN_PLAN_ROTATE_WARN": Entry(
        "WARNING: REALITY keys and client UUIDs will be regenerated — "
        "existing client configs stop working",
        "ВНИМАНИЕ: ключи REALITY и UUID клиентов будут пересозданы — "
        "старые клиентские конфиги перестанут работать",
    ),
    "MAIN_PLAN_CLEANUP_FULL": Entry(
        "cleanup on the server: staging + venv removed",
        "уборка на сервере: удалить staging и venv",
    ),
    "MAIN_PLAN_CLEANUP_SKIP": Entry(
        "cleanup on the server: skipped (staging kept)",
        "уборка на сервере: пропущена (staging остаётся)",
    ),
    "MAIN_PLAN_CLEANUP_DEFAULT": Entry(
        "cleanup on the server: staging removed",
        "уборка на сервере: удалить staging",
    ),
    "MAIN_PLAN_DEST": Entry(
        "client configs will be written to: {path}",
        "клиентские конфиги будут сохранены в: {path}",
    ),
    "MAIN_AUTH_PKEY": Entry("SSH key: {pkey}", "SSH-ключ: {pkey}"),
    "MAIN_AUTH_PASSWORD": Entry("password ******", "пароль ******"),
    "MAIN_AUTH_AGENT": Entry("none (ssh agent)", "нет (ssh-агент)"),
    "MAIN_DEPLOY_HELP": Entry(
        "Deploy the VPN to a VPS (target is always remote). By default ansible "
        "runs on the VPS; --execution local runs the playbook from this machine.\n\n"
        "examples:\n"
        "  xrayvpn deploy -H 203.0.113.7\n"
        "  xrayvpn deploy -H 203.0.113.7 --runtime docker --no-warp\n"
        "  xrayvpn deploy --dry-run --no-interactive -H 203.0.113.7\n\n"
        "every override flag is optional; unset flags keep the config/settings.yml defaults.",
        "Развёртывание VPN на VPS (цель всегда удалённая). По умолчанию ansible "
        "выполняется на VPS; --execution local запускает плейбук с этой машины.\n\n"
        "примеры:\n"
        "  xrayvpn deploy -H 203.0.113.7\n"
        "  xrayvpn deploy -H 203.0.113.7 --runtime docker --no-warp\n"
        "  xrayvpn deploy --dry-run --no-interactive -H 203.0.113.7\n\n"
        "каждый переопределяющий флаг необязателен: без него действует значение "
        "из config/settings.yml.",
    ),
    "MAIN_EXEC_OPT": Entry(
        "Ansible control node: {modes} (remote default: playbook runs on the VPS)",
        "Узел ansible: {modes} (remote по умолчанию: плейбук выполняется на VPS)",
    ),
    "MAIN_RUNTIME_OPT": Entry(
        "xray_runtime override ({runtimes}; default: {d})",
        "Переопределение xray_runtime ({runtimes}; по умолчанию: {d})",
    ),
    "MAIN_PORT_OPT": Entry(
        "VLESS inbound TCP port override (default: {d})",
        "Переопределение TCP-порта входящего VLESS (по умолчанию: {d})",
    ),
    "MAIN_NUMCLIENTS_OPT": Entry(
        "Number of client configs to generate (default: {d})",
        "Сколько клиентских конфигов генерировать (по умолчанию: {d})",
    ),
    "MAIN_CAMO_OPT": Entry(
        "REALITY camouflage/SNI domain (default: {d})",
        "Переопределение домена маскировки REALITY (SNI) (по умолчанию: {d})",
    ),
    "MAIN_WARP_OPT": Entry(
        "Enable/disable Cloudflare WARP outbound (default: {d})",
        "Включить/выключить исходящий туннель Cloudflare WARP (по умолчанию: {d})",
    ),
    "MAIN_ROTATE_OPT": Entry(
        "Force REALITY key + UUID regeneration (default: keep existing state)",
        "Принудительно перегенерировать ключ REALITY и UUID "
        "(по умолчанию: сохранить текущее состояние)",
    ),
    "MAIN_UFW_OPT": Entry(
        "Enable/disable ufw allow-rule management (default: {d}; disable on WSL test hosts)",
        "Включить/выключить управление правилами ufw "
        "(по умолчанию: {d}; отключайте на тестовых хостах WSL)",
    ),
    "MAIN_INV_OPT": Entry(
        "--execution local only: inventory file to deploy from "
        "(default: generated .xrayvpn-inventory.yml)",
        "только для --execution local: inventory-файл для деплоя "
        "(по умолчанию генерируемый .xrayvpn-inventory.yml)",
    ),
    "MAIN_DRYRUN_OPT": Entry(
        "Pass --check to ansible-playbook; no changes",
        "Передать --check в ansible-playbook; без изменений",
    ),
    "MAIN_WSLOPTS_DISTRO": Entry(
        "--execution local on Windows: WSL distro (default distro)",
        "--execution local на Windows: дистрибутив WSL (по умолчанию)",
    ),
    "MAIN_WSLOPTS_VENV": Entry(
        "--execution local: control-node venv holding ansible-playbook",
        "--execution local: venv узла с ansible-playbook",
    ),
    "MAIN_HOST_OPT": Entry(
        "VPS host/IP or ~/.ssh/config alias (required unless provided by the inventory)",
        "Хост/IP VPS или алиас ~/.ssh/config (обязателен, если не взят из inventory)",
    ),
    "MAIN_USEINV_OPT": Entry(
        "Read connection params and vars from the personal inventory.yml",
        "Читать параметры подключения и переменные из личного inventory.yml",
    ),
    "MAIN_CLIENTSDIR_OPT": Entry(
        "Where generated client configs are saved",
        "Куда сохранять сгенерированные клиентские конфиги",
    ),
    "MAIN_FULLCLEANUP_OPT": Entry(
        "Remote cleanup: also remove the server-side venv",
        "Уборка на сервере: удалить и серверный venv",
    ),
    "MAIN_NOCLEANUP_OPT": Entry(
        "Remote cleanup: keep the staging dir",
        "Уборка на сервере: сохранить staging-каталог",
    ),
    "MAIN_NOINT_OPT": Entry(
        "Skip all prompts including the deploy-plan confirmation (CI)",
        "Пропустить все вопросы, включая подтверждение плана деплоя (CI)",
    ),
    "MAIN_ERR_DEBUG_VERBOSE": Entry(
        "error: --debug and --verbose are mutually exclusive",
        "ошибка: --debug и --verbose взаимоисключающие",
    ),
    "MAIN_ERR_CLEANUP_FLAGS": Entry(
        "error: --full-cleanup and --no-cleanup are mutually exclusive",
        "ошибка: --full-cleanup и --no-cleanup взаимоисключающие",
    ),
    "MAIN_ERR_RUNTIME": Entry(
        "error: --runtime must be one of {runtimes}",
        "ошибка: --runtime должен быть одним из {runtimes}",
    ),
    "MAIN_ERR_PKEY_PASS": Entry(
        "error: --pkey and --pass are mutually exclusive",
        "ошибка: --pkey и --pass взаимоисключающие",
    ),
    "MAIN_ERR_INV_LOCAL": Entry(
        "error: --inventory applies to --execution local only",
        "ошибка: --inventory применим только к --execution local",
    ),
    "MAIN_SWAP_LOW": Entry(
        "[remote] low memory: {mb} MB RAM and no active swap — the deploy may be OOM-killed",
        "[remote] мало памяти: {mb} МБ RAM и нет активного swap — деплой может быть убит OOM-killer",
    ),
    "MAIN_SWAP_NO_TTY": Entry(
        "[remote] swap-guard: cannot ask without a terminal — proceeding "
        "WITHOUT swap; add a swapfile or free RAM if the deploy dies",
        "[remote] swap-guard: вопрос невозможен без терминала — продолжаю "
        "БЕЗ swap; добавьте swap-файл или освободите RAM, если деплой упадёт",
    ),
    "MAIN_SWAP_PROMPT": Entry(
        "Create a 1 GB swapfile /swapfile on the server?",
        "Создать swap-файл 1 ГБ /swapfile на сервере?",
    ),
    "MAIN_SWAP_DECLINED": Entry(
        "[remote] swap-guard declined; continuing without swap",
        "[remote] swap-guard отклонён; продолжаю без swap",
    ),
    "MAIN_SWAP_FAIL": Entry(
        "[remote] swap-guard failed: {command}\n{err}",
        "[remote] swap-guard ошибка: {command}\n{err}",
    ),
    "MAIN_SWAP_DONE": Entry(
        "[remote] swapfile created and enabled (fstab entry added)",
        "[remote] swap-файл создан и включён (запись в fstab добавлена)",
    ),
    "MAIN_ERR_HOST_REMOTE": Entry(
        "error: --host is required in remote mode",
        "ошибка: --host обязателен в remote-режиме",
    ),
    "MAIN_ERR_KEY_AND_PASS": Entry(
        "error: both a private key and a password are configured; use one",
        "ошибка: указаны и приватный ключ, и пароль; используйте что-то одно",
    ),
    "MAIN_ERR_KEY_NOT_FOUND": Entry(
        "error: private key not found: {path}",
        "ошибка: приватный ключ не найден: {path}",
    ),
    "MAIN_ERR_NOAUTH_NOINTERACTIVE": Entry(
        "error: --no-interactive requires --pkey, --pass or inventory auth",
        "ошибка: с --no-interactive нужны --pkey, --pass или аутентификация в inventory",
    ),
    "MAIN_SWAP_KEPT_NOTE": Entry(
        "[remote] note: full-cleanup keeps the swapfile (if the swap-guard created "
        "one); remove /swapfile and its fstab line manually if not needed",
        "[remote] заметка: full-cleanup сохраняет swap-файл (если swap-guard его "
        "создал); удалите /swapfile и строку в fstab вручную, если он не нужен",
    ),
    "MAIN_PREVIEW_REMOTE": Entry(
        "[preview] remote deploy to {host}",
        "[превью] remote-деплой на {host}",
    ),
    "MAIN_PREVIEW_SWAP_GUARD": Entry(
        "[preview] swap-guard: detect RAM/swap; if RAM < 1024 MB and no swap — "
        "offer an opt-in 1G /swapfile",
        "[превью] swap-guard: детект RAM/swap; при RAM < 1024 МБ без swap — "
        "opt-in вопрос про 1G /swapfile",
    ),
    "MAIN_PREVIEW_UPLOAD": Entry(
        "[preview] upload tarball with (allowlist):",
        "[превью] загрузка tarball (allowlist):",
    ),
    "MAIN_PREVIEW_LOCAL": Entry(
        "[preview] local ansible on this machine → target {user}@{host}:{port} over SSH",
        "[превью] локальный ansible на этой машине → цель {user}@{host}:{port} по SSH",
    ),
    "MAIN_PREVIEW_WSL": Entry(
        "[preview] transport: WSL control node (venv --wsl-venv, distro --wsl-distro)",
        "[превью] транспорт: узел WSL (venv --wsl-venv, дистрибутив --wsl-distro)",
    ),
    "MAIN_ERR_HOST_LOCAL": Entry(
        "error: --host is required unless provided by the inventory",
        "ошибка: --host обязателен, если не задан в inventory",
    ),
    "MAIN_ERR_EMPTY_PASSWORD": Entry(
        "error: empty SSH password; re-run and type it (or use --pkey)",
        "ошибка: пустой SSH-пароль; повторите и введите его (или укажите --pkey)",
    ),
    "MAIN_ERR_FETCH_CONFIGS": Entry(
        "error: fetching client configs failed (rc={rc}); the server-side deploy itself finished",
        "ошибка: загрузка клиентских конфигов не удалась (rc={rc}); "
        "развёртывание на сервере при этом завершено",
    ),
    "MAIN_DONE_LOCAL": Entry(
        "[done] configs written to {path}",
        "[готово] конфиги записаны в {path}",
    ),
    "MAIN_DEPLOY_OK_TITLE": Entry(
        "DEPLOY SUCCESSFUL — VPN server is up and configs are ready",
        "ДЕПЛОЙ ЗАВЕРШЁН УСПЕШНО — VPN-сервер поднят, конфиги готовы",
    ),
    "MAIN_DEPLOY_OK_CONFIGS": Entry(
        "Client configs saved:",
        "Клиентские конфиги сохранены:",
    ),
    "MAIN_DEPLOY_OK_HINT": Entry(
        "Import a config into Amnezia, Clash Verge or FlClash to connect ({path})",
        "Импортируйте конфиг в Amnezia, Clash Verge или FlClash для подключения ({path})",
    ),
}

