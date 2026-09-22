"""Shared bootstrap for the double-click `.pyw` launchers.

Resolves the interpreter (python-client/.venv first, `uv run` as fallback),
runs the command as a direct subprocess (no cmd.exe string building — its
quote escaping broke the previous launcher), prints what it is about to run,
keeps the window open until Enter and returns the real child exit code.

`XRAYVPN_PYW_SELFTEST=1` replaces the command with `--version` and skips the
console allocation and the pause; tests/test_pyw_contract.py uses it to
launch both `.pyw` files end to end.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SELFTEST_ENV = "XRAYVPN_PYW_SELFTEST"


def _text(ru: bool, en: str, ru_text: str) -> str:
    return ru_text if ru else en


def _venv_python() -> Path:
    if sys.platform == "win32":
        return HERE / ".venv" / "Scripts" / "python.exe"
    return HERE / ".venv" / "bin" / "python"


def resolve_launcher() -> tuple[list[str] | None, str]:
    """Interpreter argv prefix for `xrayvpn`, plus a description for diagnostics."""
    venv_python = _venv_python()
    if venv_python.is_file():
        return [str(venv_python), "-m", "xrayvpn"], str(venv_python)
    uv = shutil.which("uv")
    if uv:
        return [uv, "run", "--directory", str(HERE), "xrayvpn"], uv
    return None, ""


def _selftest() -> bool:
    return os.environ.get(SELFTEST_ENV) == "1"


def _ensure_console() -> None:
    """Give a windowless pythonw process a console the child can inherit."""
    if sys.platform != "win32" or _selftest() or sys.stdout is not None:
        return
    import ctypes

    kernel32 = ctypes.windll.kernel32
    if not kernel32.AllocConsole():
        return
    kernel32.SetConsoleOutputCP(65001)
    kernel32.SetConsoleCP(65001)
    sys.stdout = open("CONOUT$", "w", encoding="utf-8", errors="replace")  # noqa: SIM115
    sys.stderr = sys.stdout
    sys.stdin = open("CONIN$", "r", encoding="utf-8", errors="replace")  # noqa: SIM115


def _pause(ru: bool) -> None:
    if _selftest():
        return
    print(_text(ru, "Press Enter to close this window...", "Нажмите Enter, чтобы закрыть окно..."))
    try:
        input()
    except (EOFError, OSError):
        pass


def _harden_streams() -> None:
    """Diagnostics must not crash on a non-UTF-8 console/pipe (cp1252/cp866)."""
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")


def run(command: list[str], *, ru: bool = False) -> int:
    if _selftest():
        command = ["--version"]
    _ensure_console()
    _harden_streams()
    launcher, description = resolve_launcher()
    if launcher is None:
        print(
            _text(
                ru,
                "error: neither python-client/.venv nor uv was found.\n"
                "Run 'uv sync' inside python-client/ or install uv: "
                "https://docs.astral.sh/uv/",
                "ошибка: не найдены ни python-client/.venv, ни uv.\n"
                "Выполните 'uv sync' в python-client/ или установите uv: "
                "https://docs.astral.sh/uv/",
            )
        )
        _pause(ru)
        return 1
    argv = launcher + command
    print(_text(ru, f"interpreter: {description}", f"интерпретатор: {description}"))
    print(f"$ {subprocess.list2cmdline(argv)}")
    try:
        rc = subprocess.call(argv, cwd=str(HERE.parent))
    except OSError as exc:
        print(_text(ru, f"error: failed to start: {exc}", f"ошибка: не удалось запустить: {exc}"))
        _pause(ru)
        return 1
    if rc != 0:
        print(_text(ru, f"exit code: {rc}", f"код выхода: {rc}"))
    _pause(ru)
    return rc
