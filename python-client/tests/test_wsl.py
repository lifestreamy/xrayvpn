"""Tests for core/wsl.py: path translation, script assembly and probes."""

from __future__ import annotations

import sys

import pytest

from xrayvpn.core import wsl as wsl_mod
from xrayvpn.core.wsl import command_exists, quote, to_wsl_path

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