"""Process entry: the conhost gate runs before any heavy CLI import."""

from __future__ import annotations

import sys

from xrayvpn.cli import terminal_host


def main() -> None:
    terminal_host.relaunch_if_delegated()
    sys.argv[:] = [sys.argv[0], *terminal_host.strip_wt_flag(sys.argv[1:])]
    from xrayvpn.cli.main import run

    run()
