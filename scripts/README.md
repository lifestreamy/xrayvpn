# Тулинг для разработки

> English version: [README.en.md](README.en.md).

Отдельные скрипты контрибьюторов, CI и CD. Не основное приложение xrayvpn — оно в `python-client/`,
пользовательские shell-клиенты — в `shell-clients/`.

| Каталог | Назначение |
|---|---|
| `dev/` | подготовка локальной среды разработки (`setup_test_env.py`) |
| `test/` | проверочные прогоны на локальной машине (`local_test.py`) |
| `cd/` | рендер артефактов каналов и манифеста обновлений (`render_channels.py`, `make_release_manifest.py`) |

Скрипты `dev/` и `test/` — чистый Python 3, только stdlib, идемпотентны. Работают против тестового
venv в WSL (`~/xray-venv`, см. [`docs/dev/TEST-LOCAL.md`](../docs/dev/TEST-LOCAL.md)).
Скрипты `cd/` — тоже stdlib-only; вызываются из релизных пайплайнов
(см. [`docs/dev/publishing/`](../docs/dev/publishing/README.md)).
