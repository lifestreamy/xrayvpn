"""Двойной клик: интерактивный `xrayvpn deploy` (русский интерфейс).

Открывает консоль и запускает мастер деплоя: CLI спросит узел исполнения,
хост VPS и SSH-аутентификацию, покажет план и перед любыми действиями
дождётся явного согласия. Английский вариант — рядом: `xrayvpn-deploy.pyw`.
Дефис в имени обязателен: обычный `xrayvpn.pyw` перехватывал бы
`import xrayvpn` на Windows. Синхронность COMMAND с `xrayvpn deploy --help`
контролирует tests/test_pyw_contract.py (статически и реальным запуском
обоих файлов).
"""

from __future__ import annotations

import sys

from _pywlaunch import run

COMMAND: list[str] = [
    "deploy",
    "--verbose",
    "--ru",
]

if __name__ == "__main__":
    sys.exit(run(COMMAND, ru=True))
