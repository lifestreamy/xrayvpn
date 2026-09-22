"""Double-click console launcher: interactive `xrayvpn deploy` (English UI).

Opens a console and runs the plain deploy wizard: the CLI asks for the
execution node, the VPS host and SSH auth, prints a deploy plan and waits
for an explicit yes before touching anything. The Russian variant lives
next to it: `xrayvpn-deploy-ru.pyw`. The file name keeps a hyphen on
purpose: a plain `xrayvpn.pyw` would shadow the `xrayvpn` package on the
Windows import path. Keep COMMAND in sync with `xrayvpn deploy --help`:
tests/test_pyw_contract.py enforces this statically and launches both files.
"""

from __future__ import annotations

import sys

from _pywlaunch import run

COMMAND: list[str] = [
    "deploy",
    "--verbose",
]

if __name__ == "__main__":
    sys.exit(run(COMMAND))
