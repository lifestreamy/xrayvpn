# Сборка standalone-приложения xrayvpn

Суть: `xrayvpn` упаковывается Nuitka (`--mode=onefile`) в один исполняемый
файл `xrayvpn-<os>-<arch>[.exe]` с bundled payload (`roles/`, `config/`, `deploy.yml`,
`inventory.yml.example` → `xrayvpn/payload/…`; тот же allowlist, что у загрузки на сервер).
PyInstaller-спека `xrayvpn.spec` — фолбэк с тем же контрактом payload
(общий staging из `build_support.py`).

## Требования

- `uv` (тот же пин, что в CI) — окружение и группу `build` ставит сам через wrapper.
- C-компилятор: Windows — Visual Studio 2022 (или авто-догруз MinGW Nuitka),
  Linux — gcc, macOS — clang (Xcode CLT).
- Python 3.12+ (_requires-python_ из `pyproject.toml`).

## Команды

```
# Windows
.\build-binary.ps1                       # onefile, канон
.\build-binary.ps1 -Mode standalone      # отладочный режим (папка onedir)
.\build-binary.ps1 -Engine pyinstaller   # фолбэк-спека
.\build-binary.ps1 -Version 0.4.1        # версия в метаданные/--version (дефолт: __version__)

# Linux/macOS
./build-binary.sh
./build-binary.sh --mode standalone
./build-binary.sh --engine pyinstaller --version 0.4.1
```

Артефакты — `dist-binary/`. Контракт: одинаковые payload-пути у обоих движков,
`--version` = переданная версия, имя файла = `xrayvpn-<os>-<arch>[.exe]`.

## Цикл отладки

1. `--mode standalone` → проверить `dist-binary/xrayvpn-*.dist/` вручную.
2. Претензий нет → `--mode onefile` (дефолт) → смоук ниже.
3. Nuitka-сюрпризы (bcrypt/cffi/плагин-зависимости) — чинить флагами/`--include-package`,
   не кодом клиента; в крайнем случае — PyInstaller-спека (контракт payload не меняется).

## Onefile-кэш

Распаковка идёт в `{CACHE_DIR}/xrayvpn/{VERSION}` (стабильный путь — Windows Firewall
не считает каждый запуск новой программой; повторные запуски без переупаковки).
Смена версии = новая папка кэша.

## Smoke-набор (ОБЯЗАТЕЛЬНО из НЕЙТРАЛЬНОГО cwd)

Каталог вне checkout репо (`--dry-run` сам нашёл бы бандл по композит-маркеру
`roles/xray_vpn`, если запускать внутри репо — проверка бандла не считается):

```
cd $TMPDIR/some-empty-dir
XRAYVPN_UPDATE_CHECK=0 ./xrayvpn-… --version          # первая строка: xrayvpn <версия>
XRAYVPN_UPDATE_CHECK=0 ./xrayvpn-… deploy --dry-run --no-interactive --host 127.0.0.1
XRAYVPN_LANG=ru XRAYVPN_UPDATE_CHECK=0 ./xrayvpn-… --ru --help   # RU-вывод (страж l10n-патчей в freeze)
XRAYVPN_REPL_SELFTEST=1 ./xrayvpn-… repl               # feeding stdin: help\nexit\n → rc 0
# Windows: двойной клик по .exe = тот же entry с консолью (--windows-console-mode=force);
# при фатальной ошибке окно остаётся с текстом до нажатия Enter.
```

## Known environment notes

- Не-подписанный Windows-exe → SmartScreen «показать подробности», macOS → `chmod +x`,
  Gatekeeper → ПКМ→Открыть/`xattr -d com.apple.quarantine`.
- Сброс кэша onefile: удалить папку `{CACHE_DIR}/xrayvpn/<версия>`.
- `--low-memory` / `--jobs=1` добавить в `build_binary.py` на малоразмерных хостах.
