"""Windows console-host gate (MYXRAY-92).

When "Windows Terminal" is the system default terminal (microsoft/terminal#492),
a double-clicked packaged exe gets a WT tab, and the app icon never reaches the
window/taskbar. The documented per-launch escape is `conhost.exe app.exe`
(conhost inherits the icon of the exe it launches), so right at process start —
before any heavy imports — a packaged exe launched through that delegation
relaunches itself under conhost. Everything else (live consoles, WT tabs,
source runs, other OSes, valves `--wt`/`XRAYVPN_IN_WT`) stays untouched.
WT_SESSION is NOT usable for detection: Microsoft never injects terminal env vars
into default-terminal-delegated processes (microsoft/terminal#13006), so the host
is identified by the console window itself — classic conhost owns a
ConsoleWindowClass window via conhost.exe, while WT/OpenConsole is a pseudoconsole
whose window handle is null or owned by OpenConsole.exe.
Env lookups are case-insensitive on purpose: delegated launch chains may hand
over keys in a non-canonical case, and the conhost lookup has a
GetSystemDirectoryW fallback independent of the environment.
"""

from __future__ import annotations

import ctypes
import os
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from ctypes import wintypes
from pathlib import Path

from xrayvpn.core import runtime_paths

WT_FLAG = "--wt"
WT_ENV_PREFIX = "WT_"
WT_HOST_PROCESSES = frozenset(
    {"openconsole.exe", "windowsterminal.exe", "windowsterminal.preview.exe"}
)
IN_WT_ENV = "XRAYVPN_IN_WT"
RELAUNCHED_ENV = "XRAYVPN_WT_RELAUNCHED"
DEBUG_ENV = "XRAYVPN_TERMINAL_DEBUG"
SELFTEST_ENVS = ("XRAYVPN_REPL_SELFTEST", "XRAYVPN_PYW_SELFTEST")
PYTEST_ENV = "PYTEST_CURRENT_TEST"
_PROCESS_QUERY_LIMITED = 0x1000
_MAX_PIDS = 256
_SYS_DIR_BUF = 1024
_NEW_CONSOLE = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)


def _env_get(environ: Mapping[str, str], name: str) -> str | None:
    value = environ.get(name)
    if value is not None:
        return value
    folded = name.casefold()
    for key, candidate in environ.items():
        if key.casefold() == folded:
            return candidate
    return None


def strip_wt_flag(argv: Sequence[str]) -> list[str]:
    return [arg for arg in argv if arg != WT_FLAG]


def mangle_child_env(environ: Mapping[str, str]) -> dict[str, str]:
    prefix = WT_ENV_PREFIX.casefold()
    child = {
        key: value for key, value in environ.items() if not key.casefold().startswith(prefix)
    }
    child[RELAUNCHED_ENV] = "1"
    return child


def own_console(
    pids: Sequence[int],
    *,
    self_pid: int,
    parent_pid: int,
    is_packaged: bool,
) -> bool:
    if not pids:
        return False
    others = {int(pid) for pid in pids} - {self_pid}
    if not others:
        return True
    return is_packaged and others == {parent_pid}


def pseudo_host(hwnd: int, host_name: str | None, console_attached: bool) -> bool:
    if not console_attached:
        return False
    if not hwnd:
        return True
    return host_name is not None and host_name.casefold() in WT_HOST_PROCESSES


def should_relaunch(
    argv: Sequence[str],
    environ: Mapping[str, str],
    *,
    is_windows: bool,
    is_packaged: bool,
    stdout_is_tty: bool,
    own_console: bool,
    pseudo_host: bool,
) -> bool:
    if not is_windows or not is_packaged:
        return False
    if WT_FLAG in argv:
        return False
    if _env_get(environ, IN_WT_ENV) == "1":
        return False
    if _env_get(environ, RELAUNCHED_ENV) == "1":
        return False
    if any(_env_get(environ, name) == "1" for name in SELFTEST_ENVS):
        return False
    if _env_get(environ, PYTEST_ENV):
        return False
    if not pseudo_host:
        return False
    if not stdout_is_tty:
        return False
    return own_console


def _kernel32() -> ctypes.WinDLL:
    return ctypes.windll.kernel32  # type: ignore[attr-defined]


def process_list() -> list[int]:
    """PIDs attached to this process's console; empty when the API is
    unavailable or failed — the conservative no-relaunch answer."""
    if os.name != "nt":
        return []
    try:
        buf = (ctypes.c_uint32 * _MAX_PIDS)()
        count = int(_kernel32().GetConsoleProcessList(buf, _MAX_PIDS))
    except Exception:  # noqa: BLE001 - detection must never break startup
        return []
    if count <= 0 or count > _MAX_PIDS:
        return []
    return [int(buf[i]) for i in range(count)]


def _process_image_name(pid: int) -> str | None:
    """Full image path of a process via PROCESS_QUERY_LIMITED_INFORMATION."""
    try:
        kernel32 = _kernel32()
        kernel32.OpenProcess.restype = ctypes.c_void_p
        kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
        kernel32.CloseHandle.restype = wintypes.BOOL
        handle = kernel32.OpenProcess(_PROCESS_QUERY_LIMITED, False, pid)
        if not handle:
            return None
        try:
            buf = ctypes.create_unicode_buffer(32768)
            size = wintypes.DWORD(len(buf))
            if not kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
                return None
            return buf.value or None
        finally:
            kernel32.CloseHandle(handle)
    except Exception:  # noqa: BLE001 - detection must never break startup
        return None


def probe_console_host() -> tuple[int, str | None]:
    """(console HWND, basename of its owning process); (0, None) on any failure.
    HWND is 0 for windowless pseudoconsoles, per GetConsoleWindow semantics."""
    if os.name != "nt":
        return 0, None
    try:
        kernel32 = _kernel32()
        kernel32.GetConsoleWindow.restype = ctypes.c_void_p
        hwnd = int(kernel32.GetConsoleWindow() or 0)
        if not hwnd:
            return 0, None
        pid = wintypes.DWORD()
        kernel32.GetWindowThreadProcessId.restype = wintypes.DWORD
        kernel32.GetWindowThreadProcessId.argtypes = (ctypes.c_void_p, ctypes.POINTER(wintypes.DWORD))
        if not kernel32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid)):
            return hwnd, None
        image = _process_image_name(int(pid.value))
        return hwnd, Path(image).name if image else None
    except Exception:  # noqa: BLE001 - detection must never break startup
        return 0, None


def _system_dir_conhost() -> str | None:
    """conhost.exe resolved via GetSystemDirectoryW — independent of the
    environment block, which a delegated launch chain may alter."""
    if os.name != "nt":
        return None
    try:
        buf = ctypes.create_unicode_buffer(_SYS_DIR_BUF)
        length = int(_kernel32().GetSystemDirectoryW(buf, _SYS_DIR_BUF))
        candidate = Path(buf.value) / "conhost.exe" if length > 0 else None
    except Exception:  # noqa: BLE001 - lookup must never break startup
        return None
    if candidate is None or not candidate.is_file():
        return None
    return str(candidate)


def conhost_path(environ: Mapping[str, str]) -> str | None:
    root = _env_get(environ, "SystemRoot") or _env_get(environ, "windir")
    if root:
        candidate = Path(root) / "System32" / "conhost.exe"
        if candidate.is_file():
            return str(candidate)
    return _system_dir_conhost()


def _exe_path() -> str | None:
    argv0 = sys.argv[0] if sys.argv else ""
    if argv0 and Path(argv0).is_file():
        return str(Path(argv0).resolve())
    return sys.executable or None


def relaunch_if_delegated(
    *,
    argv: Sequence[str] | None = None,
    environ: Mapping[str, str] | None = None,
    pids: Sequence[int] | None = None,
    is_windows: bool | None = None,
    is_packaged: bool | None = None,
    stdout_is_tty: bool | None = None,
    console: tuple[int, str | None] | None = None,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
    detacher: Callable[..., subprocess.Popen] = subprocess.Popen,
) -> None:
    args = list(sys.argv if argv is None else argv)
    env = dict(os.environ if environ is None else environ)
    windows = sys.platform == "win32" if is_windows is None else is_windows
    packaged = runtime_paths.is_frozen() if is_packaged is None else is_packaged
    tty = (sys.stdout is not None and sys.stdout.isatty()) if stdout_is_tty is None else stdout_is_tty
    attached = process_list() if pids is None else [int(pid) for pid in pids]
    hwnd, host_name = probe_console_host() if console is None else console
    pseudo = pseudo_host(hwnd, host_name, bool(attached))
    decision = should_relaunch(
        args,
        env,
        is_windows=windows,
        is_packaged=packaged,
        stdout_is_tty=tty,
        own_console=own_console(
            attached,
            self_pid=os.getpid(),
            parent_pid=os.getppid(),
            is_packaged=packaged,
        ),
        pseudo_host=pseudo,
    )
    if _env_get(env, DEBUG_ENV) == "1":
        root = _env_get(env, "SystemRoot") or _env_get(env, "windir") or ""
        print(
            f"terminal-host: windows={int(windows)} packaged={int(packaged)} tty={int(tty)} "
            f"hwnd=0x{hwnd:x} host={host_name!r} pseudo={int(pseudo)} root={root!r} "
            f"pids={','.join(map(str, attached))} decision={int(decision)}",
            file=sys.stderr,
            flush=True,
        )
    if not decision:
        return
    conhost = conhost_path(env)
    exe = _exe_path()
    if conhost is None or exe is None:
        print(f"terminal-host: cannot relaunch, conhost={conhost!r}, exe={exe!r}",
              file=sys.stderr, flush=True)
        return
    command = [conhost, "--", exe, *args[1:]]
    child_env = mangle_child_env(env)
    try:
        if len(args) <= 1:
            detacher(command, env=child_env, creationflags=_NEW_CONSOLE)
            raise SystemExit(0)
        completed = runner(command, env=child_env, creationflags=_NEW_CONSOLE)
    except OSError as exc:
        print(f"terminal-host: relaunch failed ({exc}), staying in the current host",
              file=sys.stderr, flush=True)
        return
    raise SystemExit(int(completed.returncode or 0))
