# Тулинг для разработки

> English version: [README.en.md](README.en.md).

Отдельные скрипты контрибьюторов и CI. Это не продукт: приложение — в `python-client/`,
пользовательские shell-клиенты — в `shell-clients/`.

| Каталог | Назначение |
|---|---|
| `dev/` | подготовка локальной среды разработки (`setup_test_env.py`) |
| `test/` | проверочные прогоны на локальной машине (`local_test.py`) |

Оба скрипта — чистый Python 3, только stdlib, идемпотентны. Работают против тестового
venv в WSL (`~/xray-venv`, см. [`docs/dev/TEST-LOCAL.md`](../docs/dev/TEST-LOCAL.md)).
