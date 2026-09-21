"""terminal_host: WT-delegation detection, valves, env mangle, relaunch wiring (MYXRAY-92)."""

from __future__ import annotations

import ctypes
import os
import re
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from xrayvpn.cli import terminal_host

_PYW_LAUNCHER = Path(__file__).resolve().parents[1] / "_pywlaunch.py"
_PYW_SELFTEST_RE = re.compile(r'SELFTEST_ENV = "([^"]+)"')

_SELF = 1000
_PARENT = 2000
_SHELL = 3000

_ALL_ON = {
    "is_windows": True,
    "is_packaged": True,
    "stdout_is_tty": True,
    "own_console": True,
    "pseudo_host": True,
}
_SESSION = {"WT_SESSION": "deadbeef"}
_WT_HOST = "OpenConsole.exe"
_PROBE_WT = (0x10, _WT_HOST)


def _call(argv: list[str], env: dict[str, str], **kw: bool) -> bool:
    flags = {**_ALL_ON, **kw}
    return terminal_host.should_relaunch(argv, env, **flags)


@pytest.mark.parametrize(
    ("argv", "env", "kw", "expected"),
    [
        (["xrayvpn.exe"], _SESSION, {}, True),
        (["xrayvpn.exe", "deploy", "--ru"], _SESSION, {}, True),
        (["xrayvpn.exe"], {}, {}, True),
        (["xrayvpn.exe"], _SESSION, {"is_windows": False}, False),
        (["xrayvpn.exe"], _SESSION, {"is_packaged": False}, False),
        (["xrayvpn.exe"], _SESSION, {"pseudo_host": False}, False),
        (["xrayvpn.exe", "--wt"], _SESSION, {}, False),
        (["xrayvpn.exe", "deploy", "--wt"], _SESSION, {}, False),
        (["xrayvpn.exe"], {**_SESSION, "XRAYVPN_IN_WT": "1"}, {}, False),
        (["xrayvpn.exe"], {**_SESSION, "XRAYVPN_IN_WT": "0"}, {}, True),
        (["xrayvpn.exe"], {**_SESSION, "XRAYVPN_WT_RELAUNCHED": "1"}, {}, False),
        (["xrayvpn.exe"], {**_SESSION, "XRAYVPN_REPL_SELFTEST": "1"}, {}, False),
        (["xrayvpn.exe"], {**_SESSION, "XRAYVPN_PYW_SELFTEST": "1"}, {}, False),
        (["xrayvpn.exe"], {**_SESSION, "PYTEST_CURRENT_TEST": "t (call)"}, {}, False),
        (["xrayvpn.exe"], {"xrayvpn_in_wt": "1"}, {}, False),
        (["xrayvpn.exe"], {"xrayvpn_wt_relaunched": "1"}, {}, False),
        (["xrayvpn.exe"], _SESSION, {"stdout_is_tty": False}, False),
        (["xrayvpn.exe"], _SESSION, {"own_console": False}, False),
    ],
)
def test_should_relaunch_matrix(argv: list[str], env: dict[str, str], kw: dict, expected: bool) -> None:
    assert _call(argv, env, **kw) is expected


@pytest.mark.parametrize(
    ("hwnd", "host_name", "attached", "expected"),
    [
        (0, None, True, True),
        (0, None, False, False),
        (0x10, "OpenConsole.exe", True, True),
        (0x10, "openconsole.EXE", True, True),
        (0x10, "WindowsTerminal.exe", True, True),
        (0x10, "WindowsTerminal.Preview.exe", True, True),
        (0x10, "conhost.exe", True, False),
        (0x10, None, True, False),
        (0x10, "powershell.exe", True, False),
    ],
)
def test_pseudo_host_matrix(
    hwnd: int, host_name: str | None, attached: bool, expected: bool
) -> None:
    assert terminal_host.pseudo_host(hwnd, host_name, attached) is expected


@pytest.mark.parametrize(
    ("pids", "is_packaged", "expected"),
    [
        ([], True, False),
        ([], False, False),
        ([_SELF], True, True),
        ([_SELF], False, True),
        ([_SELF, _PARENT], True, True),
        ([_SELF, _PARENT], False, False),
        ([_SELF, _PARENT, _SHELL], True, False),
        ([_SELF, _SHELL], True, False),
    ],
)
def test_own_console_matrix(pids: list[int], is_packaged: bool, expected: bool) -> None:
    got = terminal_host.own_console(
        pids, self_pid=_SELF, parent_pid=_PARENT, is_packaged=is_packaged
    )
    assert got is expected


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        ([], []),
        (["xrayvpn", "deploy"], ["xrayvpn", "deploy"]),
        (["xrayvpn", "--wt"], ["xrayvpn"]),
        (["xrayvpn", "--wt", "deploy", "--wt"], ["xrayvpn", "deploy"]),
        (["xrayvpn", "--wt=x"], ["xrayvpn", "--wt=x"]),
    ],
)
def test_strip_wt_flag(argv: list[str], expected: list[str]) -> None:
    assert terminal_host.strip_wt_flag(argv) == expected


def test_selftest_envs_pin_production_names() -> None:
    from xrayvpn.cli import repl

    assert repl.REPL_SELFTEST_ENV in terminal_host.SELFTEST_ENVS
    match = _PYW_SELFTEST_RE.search(_PYW_LAUNCHER.read_text(encoding="utf-8"))
    assert match is not None
    assert match.group(1) in terminal_host.SELFTEST_ENVS


def test_mangle_child_env_strips_wt_prefix_and_sets_marker() -> None:
    environ = {
        "WT_SESSION": "s",
        "WT_PROFILE_ID": "p",
        "WT_WINDOW_TITLE": "t",
        "wt_session": "lower",
        "Wt_Event": "mixed",
        "PATH": "/usr/bin",
        "XRAYVPN_LANG": "ru",
    }
    child = terminal_host.mangle_child_env(environ)
    assert [k for k in child if k.casefold().startswith("wt_")] == []
    assert child["XRAYVPN_WT_RELAUNCHED"] == "1"
    assert child["PATH"] == "/usr/bin"
    assert child["XRAYVPN_LANG"] == "ru"


def _fake_kernel32(result: int, fills: tuple[int, ...] = ()) -> SimpleNamespace:
    def get_console_process_list(buf, size):
        for i, pid in enumerate(fills):
            buf[i] = pid
        return result

    return SimpleNamespace(GetConsoleProcessList=get_console_process_list)


@pytest.mark.parametrize(
    ("os_name", "result", "fills", "expected"),
    [
        ("nt", 2, (_SELF, _PARENT), [_SELF, _PARENT]),
        ("nt", 1, (_SELF,), [_SELF]),
        ("nt", 0, (), []),
        ("nt", terminal_host._MAX_PIDS + 1, (), []),
        ("posix", 1, (_SELF,), []),
    ],
)
def test_process_list(
    monkeypatch: pytest.MonkeyPatch,
    os_name: str,
    result: int,
    fills: tuple[int, ...],
    expected: list[int],
) -> None:
    def guard() -> SimpleNamespace:
        raise AssertionError("API must not be touched off Windows")

    kernel32_factory = guard if os_name != "nt" else (lambda: _fake_kernel32(result, fills))
    monkeypatch.setattr(terminal_host, "_kernel32", kernel32_factory)
    monkeypatch.setattr("os.name", os_name)
    assert terminal_host.process_list() == expected


def test_process_list_swallows_api_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom() -> SimpleNamespace:
        raise OSError("no windll")

    monkeypatch.setattr(terminal_host, "_kernel32", boom)
    monkeypatch.setattr("os.name", "nt")
    assert terminal_host.process_list() == []


class _Runner:
    def __init__(self, rc: int | None, error: OSError | None = None) -> None:
        self.calls: list[tuple[list[str], dict]] = []
        self.rc = rc
        self.error = error

    def __call__(self, command: list[str], **kwargs) -> subprocess.CompletedProcess:
        self.calls.append((command, kwargs))
        if self.error is not None:
            raise self.error
        return subprocess.CompletedProcess(command, self.rc)


def _wiring_setup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(terminal_host, "conhost_path", lambda environ: r"C:\fake\conhost.exe")
    monkeypatch.setattr(terminal_host, "_exe_path", lambda: r"Z:\dl\xrayvpn.exe")


def test_relaunch_wiring_spawns_conhost_list_and_propagates_rc(monkeypatch: pytest.MonkeyPatch) -> None:
    _wiring_setup(monkeypatch)
    runner = _Runner(7)
    with pytest.raises(SystemExit) as excinfo:
        terminal_host.relaunch_if_delegated(
            argv=["Z:\\dl\\xrayvpn.exe", "deploy", "--ru"],
            environ={**_SESSION, "PATH": "/usr/bin"},
            pids=[os.getpid(), os.getppid()],
            is_windows=True,
            is_packaged=True,
            stdout_is_tty=True,
            console=_PROBE_WT,
            runner=runner,
        )
    assert excinfo.value.code == 7
    (command, kwargs), = runner.calls
    assert command == [r"C:\fake\conhost.exe", "--", r"Z:\dl\xrayvpn.exe", "deploy", "--ru"]
    assert kwargs["creationflags"] == getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
    child_env = kwargs["env"]
    assert child_env["XRAYVPN_WT_RELAUNCHED"] == "1"
    assert child_env["PATH"] == "/usr/bin"
    assert "WT_SESSION" not in child_env


def test_relaunch_wiring_null_rc_becomes_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    _wiring_setup(monkeypatch)
    runner = _Runner(None)
    with pytest.raises(SystemExit) as excinfo:
        terminal_host.relaunch_if_delegated(
            argv=[r"Z:\dl\xrayvpn.exe", "--version"],
            environ=_SESSION,
            pids=[os.getpid()],
            is_windows=True,
            is_packaged=True,
            stdout_is_tty=True,
            console=_PROBE_WT,
            runner=runner,
        )
    assert excinfo.value.code == 0


class _Detacher:
    def __init__(self, error: OSError | None = None) -> None:
        self.calls: list[tuple[list[str], dict]] = []
        self.error = error

    def __call__(self, command: list[str], **kwargs) -> object:
        self.calls.append((command, kwargs))
        if self.error is not None:
            raise self.error
        return object()


def test_relaunch_detaches_and_exits_zero_when_no_args(monkeypatch: pytest.MonkeyPatch) -> None:
    _wiring_setup(monkeypatch)
    detacher = _Detacher()
    runner = _Runner(5)
    with pytest.raises(SystemExit) as excinfo:
        terminal_host.relaunch_if_delegated(
            argv=[r"Z:\dl\xrayvpn.exe"],
            environ=_SESSION,
            pids=[os.getpid()],
            is_windows=True,
            is_packaged=True,
            stdout_is_tty=True,
            console=_PROBE_WT,
            runner=runner,
            detacher=detacher,
        )
    assert excinfo.value.code == 0
    assert runner.calls == []
    (command, kwargs), = detacher.calls
    assert command == [r"C:\fake\conhost.exe", "--", r"Z:\dl\xrayvpn.exe"]
    assert kwargs["creationflags"] == getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
    assert kwargs["env"]["XRAYVPN_WT_RELAUNCHED"] == "1"
    assert "WT_SESSION" not in kwargs["env"]


def test_relaunch_detach_failure_continues_startup(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _wiring_setup(monkeypatch)
    detacher = _Detacher(error=OSError(2, "no conhost"))
    runner = _Runner(0)
    terminal_host.relaunch_if_delegated(
        argv=[r"Z:\dl\xrayvpn.exe"],
        environ=_SESSION,
        pids=[os.getpid()],
        is_windows=True,
        is_packaged=True,
        stdout_is_tty=True,
        console=_PROBE_WT,
        runner=runner,
        detacher=detacher,
    )
    assert runner.calls == []
    assert len(detacher.calls) == 1
    assert "relaunch failed" in capsys.readouterr().err


def test_relaunch_wiring_skips_for_tab_console(monkeypatch: pytest.MonkeyPatch) -> None:
    _wiring_setup(monkeypatch)
    runner = _Runner(0)
    terminal_host.relaunch_if_delegated(
        argv=[r"Z:\dl\xrayvpn.exe"],
        environ=_SESSION,
        pids=[os.getpid(), os.getppid(), _SHELL],
        is_windows=True,
        is_packaged=True,
        stdout_is_tty=True,
        runner=runner,
    )
    assert runner.calls == []


def test_relaunch_wiring_skips_classic_host(monkeypatch: pytest.MonkeyPatch) -> None:
    _wiring_setup(monkeypatch)
    runner = _Runner(0)
    terminal_host.relaunch_if_delegated(
        argv=[r"Z:\dl\xrayvpn.exe"],
        environ={},
        pids=[os.getpid()],
        is_windows=True,
        is_packaged=True,
        stdout_is_tty=True,
        console=(0x10, "conhost.exe"),
        runner=runner,
    )
    assert runner.calls == []


def test_relaunch_wiring_valve_skips(monkeypatch: pytest.MonkeyPatch) -> None:
    _wiring_setup(monkeypatch)
    runner = _Runner(0)
    terminal_host.relaunch_if_delegated(
        argv=[r"Z:\dl\xrayvpn.exe", "--wt"],
        environ=_SESSION,
        pids=[os.getpid()],
        is_windows=True,
        is_packaged=True,
        stdout_is_tty=True,
        runner=runner,
    )
    assert runner.calls == []


def test_relaunch_wiring_lowercase_env_keys_spawn(monkeypatch: pytest.MonkeyPatch) -> None:
    _wiring_setup(monkeypatch)
    runner = _Runner(0)
    with pytest.raises(SystemExit):
        terminal_host.relaunch_if_delegated(
            argv=[r"Z:\dl\xrayvpn.exe", "--version"],
            environ={"wt_session": "s", "systemroot": "C:\\Windows"},
            pids=[os.getpid()],
            is_windows=True,
            is_packaged=True,
            stdout_is_tty=True,
            console=_PROBE_WT,
            runner=runner,
        )
    (command, kwargs) = runner.calls[0]
    assert command[0] == r"C:\fake\conhost.exe"
    child_env = kwargs["env"]
    assert child_env["XRAYVPN_WT_RELAUNCHED"] == "1"
    assert [k for k in child_env if k.casefold().startswith("wt_")] == []
    assert child_env["systemroot"] == "C:\\Windows"


def test_relaunch_wiring_debug_line(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    runner = _Runner(0)
    terminal_host.relaunch_if_delegated(
        argv=[r"Z:\dl\xrayvpn.exe", "--wt"],
        environ={**_SESSION, "XRAYVPN_TERMINAL_DEBUG": "1"},
        pids=[os.getpid()],
        is_windows=True,
        is_packaged=True,
        stdout_is_tty=True,
        console=_PROBE_WT,
        runner=runner,
    )
    err = capsys.readouterr().err
    assert "terminal-host:" in err
    assert "decision=0" in err
    assert "root=" in err
    assert "hwnd=0x10" in err
    assert "pseudo=1" in err
    assert "host='OpenConsole.exe'" in err


def test_relaunch_spawn_failure_continues_startup(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _wiring_setup(monkeypatch)
    runner = _Runner(None, error=OSError(2, "conhost not found"))
    terminal_host.relaunch_if_delegated(
        argv=[r"Z:\dl\xrayvpn.exe", "--version"],
        environ=_SESSION,
        pids=[os.getpid()],
        is_windows=True,
        is_packaged=True,
        stdout_is_tty=True,
        console=_PROBE_WT,
        runner=runner,
    )
    assert len(runner.calls) == 1
    assert "relaunch failed" in capsys.readouterr().err


def test_relaunch_without_conhost_path_skips(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(terminal_host, "conhost_path", lambda environ: None)
    monkeypatch.setattr(terminal_host, "_exe_path", lambda: r"Z:\dl\xrayvpn.exe")
    runner = _Runner(0)
    terminal_host.relaunch_if_delegated(
        argv=[r"Z:\dl\xrayvpn.exe"],
        environ=_SESSION,
        pids=[os.getpid()],
        is_windows=True,
        is_packaged=True,
        stdout_is_tty=True,
        runner=runner,
    )
    assert runner.calls == []


def test_conhost_path_resolves_systemroot(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setattr(terminal_host, "_system_dir_conhost", lambda: None)
    exe = tmp_path / "System32" / "conhost.exe"
    exe.parent.mkdir()
    exe.write_bytes(b"")
    assert terminal_host.conhost_path({"SystemRoot": str(tmp_path)}) == str(exe)
    assert terminal_host.conhost_path({"SYSTEMROOT": str(tmp_path)}) == str(exe)
    assert terminal_host.conhost_path({"windir": str(tmp_path)}) == str(exe)
    assert terminal_host.conhost_path({"WINDIR": str(tmp_path)}) == str(exe)
    assert terminal_host.conhost_path({}) is None
    assert terminal_host.conhost_path({"SystemRoot": str(tmp_path / "nope")}) is None


@pytest.mark.skipif(os.name != "nt", reason="GetSystemDirectoryW fallback is Windows-only")
def test_conhost_path_falls_back_to_system_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    sysdir = tmp_path / "System32"
    sysdir.mkdir()
    exe = sysdir / "conhost.exe"
    exe.write_bytes(b"")

    def get_system_directory(buf, size):
        buf.value = str(sysdir)
        return len(str(sysdir))

    monkeypatch.setattr(
        terminal_host, "_kernel32", lambda: SimpleNamespace(GetSystemDirectoryW=get_system_directory)
    )
    monkeypatch.setattr("os.name", "nt")
    assert terminal_host.conhost_path({}) == str(exe)


def test_console_probe_failure_is_conservative(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom() -> ctypes.WinDLL:
        raise OSError("no windll")

    monkeypatch.setattr(terminal_host, "_kernel32", boom)
    monkeypatch.setattr("os.name", "nt")
    assert terminal_host.probe_console_host() == (0, None)


def test_system_dir_conhost_failure_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom():
        raise OSError("no windll")

    monkeypatch.setattr(terminal_host, "_kernel32", boom)
    monkeypatch.setattr("os.name", "nt")
    assert terminal_host._system_dir_conhost() is None


def test_main_gate_strips_and_delegates(monkeypatch: pytest.MonkeyPatch) -> None:
    from xrayvpn.cli import entry

    order: list[str] = []
    monkeypatch.setattr(
        terminal_host,
        "relaunch_if_delegated",
        lambda **_: order.append("gate"),
    )
    monkeypatch.setattr("xrayvpn.cli.main.run", lambda: order.append("run"))
    monkeypatch.setattr("sys.argv", ["xrayvpn.exe", "deploy", "--wt", "--ru"])
    entry.main()
    assert order == ["gate", "run"]
    assert list(sys.argv) == ["xrayvpn.exe", "deploy", "--ru"]
