"""Приёмочные фиксы SSH-UX: человекочитаемые ошибки, живая REPL-сессия,
пустой пароль и `$VAR`-пути к ключу."""

from __future__ import annotations

import socket
from pathlib import Path

import paramiko
import pytest
from typer.testing import CliRunner

import xrayvpn.cli.main as main_mod
import xrayvpn.cli.service as service_mod
from xrayvpn.cli.main import app
from xrayvpn.core.conn import ConnResolveError, resolve_connection
from xrayvpn.core.runtime_paths import RunRoots
from xrayvpn.core.transport.remote import FabricRemote, SshConnectError

runner = CliRunner()


class _StubConn:
    def __init__(self, exc: Exception) -> None:
        self.exc = exc
        self.client = self

    def set_missing_host_key_policy(self, policy: object) -> None:
        return None

    def open(self) -> None:
        raise self.exc


def _remote_raising(exc: Exception) -> FabricRemote:
    remote = FabricRemote("203.0.113.7")
    remote._conn = _StubConn(exc)
    return remote


def test_banner_error_is_human() -> None:
    remote = _remote_raising(paramiko.SSHException("Error reading SSH protocol banner"))
    with pytest.raises(SshConnectError) as info:
        remote._ensure_open()
    assert "banner" in str(info.value)
    assert "root@203.0.113.7:22" in str(info.value)


def test_auth_error_is_human() -> None:
    remote = _remote_raising(paramiko.AuthenticationException("Auth failed"))
    with pytest.raises(SshConnectError, match="authentication failed"):
        remote._ensure_open()


def test_socket_error_is_human() -> None:
    remote = _remote_raising(socket.gaierror("Name or service not known"))
    with pytest.raises(SshConnectError, match="failed"):
        remote._ensure_open()


class _BoomRemote:
    def __init__(self, *args, **kwargs) -> None:
        pass

    def __enter__(self):
        raise SshConnectError("SSH connection to root@h:22 failed: boom")

    def __exit__(self, *exc) -> None:
        return None


def _output(result) -> str:
    return (result.output or "") + (getattr(result, "stderr", "") or "")


def test_service_status_ssh_error_is_clean(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(service_mod, "FabricRemote", _BoomRemote)
    monkeypatch.setattr(
        service_mod,
        "_roots",
        lambda: RunRoots(repo=tmp_path, workspace=tmp_path, payload=tmp_path),
    )
    key = tmp_path / "id_test"
    key.write_text("fake", encoding="utf-8")
    result = runner.invoke(
        app, ["service", "status", "-H", "h", "--pkey", str(key), "--no-interactive"]
    )
    assert result.exit_code == 2
    out = _output(result)
    assert "SSH connection to root@h:22 failed" in out
    assert "Traceback" not in out


def test_repl_dispatch_survives_exception(monkeypatch) -> None:
    def boom(*args, **kwargs):
        raise RuntimeError("kaput")

    monkeypatch.setattr(main_mod, "app", boom)
    assert main_mod._repl_dispatch(["service", "status"]) == 1


def test_conn_empty_password_rejected(tmp_path: Path) -> None:
    with pytest.raises(ConnResolveError, match="empty SSH password"):
        resolve_connection(
            workspace=tmp_path,
            example_dir=tmp_path,
            host="h",
            ask_password=lambda _q: "",
        )


def test_pkey_env_var_expanded(tmp_path: Path, monkeypatch) -> None:
    key = tmp_path / "id_x"
    key.write_text("k", encoding="utf-8")
    monkeypatch.setenv("XRAYVPN_TEST_KEYS", str(tmp_path))
    conn = resolve_connection(
        workspace=tmp_path,
        example_dir=tmp_path,
        host="h",
        pkey="$XRAYVPN_TEST_KEYS/id_x",
        no_interactive=True,
    )
    assert conn.pkey == str(key)
