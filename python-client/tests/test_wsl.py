"""Tests for core/wsl.py: path translation, script assembly and probes."""

from __future__ import annotations

import sys

import pytest

from xrayvpn.core import wsl as wsl_mod
from xrayvpn.core.wsl import command_exists, quote, to_wsl_path, wsl_available, wsl_home

windows_only = pytest.mark.skipif(
    sys.platform != "win32",
    reason="drive-letter translation is Windows-host semantics",
)


@windows_only
def test_to_wsl_path_drive_letter() -> None:
    assert to_wsl_path(r"C:\Users\Tim\proj") == "/mnt/c/Users/Tim/proj"


@windows_only
def test_to_wsl_path_lowercase_drive() -> None:
    assert to_wsl_path(r"z:\My_Xray\setup\xray-ansible") == "/mnt/z/My_Xray/setup/xray-ansible"


def test_to_wsl_path_without_drive() -> None:
    assert to_wsl_path(r"relative\path") == "relative/path"


def test_quote_wraps_spaces() -> None:
    assert quote("/mnt/z/a b/") == "'/mnt/z/a b/'"


def test_quote_plain() -> None:
    assert quote("deploy.yml") == "deploy.yml"


def test_command_exists_builds_bash_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    class _Result:
        returncode = 0

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return _Result()

    monkeypatch.setattr(wsl_mod.subprocess, "run", fake_run)
    assert command_exists("sshpass", distro="Ubuntu-24.04")
    cmd = calls[-1]
    assert "-d" in cmd and "Ubuntu-24.04" in cmd
    assert cmd[-3:-1] == ["bash", "-lc"]
    assert cmd[-1] == "command -v sshpass"


def test_command_exists_quotes(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        result = _Zero()
        return result

    class _Zero:
        returncode = 0

    monkeypatch.setattr(wsl_mod.subprocess, "run", fake_run)
    command_exists("ssh; rm -rf /")
    assert calls[-1][-1] == "command -v 'ssh; rm -rf /'"


def test_wsl_available_does_not_decode_output(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict] = []

    class _Result:
        returncode = 0

    def fake_run(cmd, **kwargs):
        calls.append(kwargs)
        return _Result()

    monkeypatch.setattr(wsl_mod, "is_windows", lambda: True)
    monkeypatch.setattr(wsl_mod.subprocess, "run", fake_run)
    assert wsl_available()
    assert "text" not in calls[-1]
    assert "encoding" not in calls[-1]


def test_wsl_home_decodes_as_utf8(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict] = []

    class _Result:
        stdout = "/home/u\n"

    def fake_run(cmd, **kwargs):
        calls.append(kwargs)
        return _Result()

    monkeypatch.setattr(wsl_mod.subprocess, "run", fake_run)
    assert wsl_home() == "/home/u"
    assert calls[-1]["encoding"] == "utf-8"