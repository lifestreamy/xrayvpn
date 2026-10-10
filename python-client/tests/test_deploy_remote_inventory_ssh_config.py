"""Remote deploy resolves ~/.ssh/config aliases for --use-inventory hosts."""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar, Self

from typer.testing import CliRunner

import xrayvpn.cli.main as main_mod
import xrayvpn.core.conn as conn_mod
from xrayvpn.cli.main import app

runner = CliRunner()


def _output(result) -> str:
    return (result.output or "") + (getattr(result, "stderr", "") or "")


class RecordingRemote:
    instances: ClassVar[list[RecordingRemote]] = []

    def __init__(self, host: str, **kwargs: object) -> None:
        self.host = host
        self.kwargs = kwargs
        RecordingRemote.instances.append(self)

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> bool:
        return False


class _NoopExecutor:
    def __init__(self, remote: object, *, cleanup: str) -> None:
        pass

    def deploy(self, request: object, *, extra_vars: dict) -> int:
        return 0


def _stub(monkeypatch, tmp_path: Path, cfg: Path) -> None:
    RecordingRemote.instances = []
    monkeypatch.setattr(main_mod, "find_repo_root", lambda: tmp_path)
    monkeypatch.setattr(main_mod, "load_settings", lambda root: {})
    monkeypatch.setattr(main_mod, "_swap_guard", lambda remote, *, no_interactive: None)
    monkeypatch.setattr(main_mod, "FabricRemote", RecordingRemote)
    monkeypatch.setattr(main_mod, "RemoteExecutor", _NoopExecutor)
    monkeypatch.setattr(
        main_mod,
        "apply_ssh_config",
        lambda host, user, port, **kw: conn_mod.apply_ssh_config(
            host, user, port, config_path=cfg
        ),
    )


def _write_inventory(tmp_path: Path, auth_line: str | None = None) -> None:
    lines = [
        "all:",
        "  hosts:",
        "    vps:",
        "      ansible_host: myvps",
        "      ansible_user: root",
        "      ansible_port: 22",
    ]
    if auth_line is not None:
        lines.append(f"      {auth_line}")
    (tmp_path / "inventory.yml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_remote_use_inventory_resolves_alias(monkeypatch, tmp_path: Path) -> None:
    cfg = tmp_path / "ssh_config"
    cfg.write_text(
        "Host myvps\n  HostName 203.0.113.9\n  User deploy\n  Port 2222\n",
        encoding="utf-8",
    )
    _stub(monkeypatch, tmp_path, cfg)
    _write_inventory(tmp_path, "ansible_ssh_pass: hostpw")
    result = runner.invoke(
        app, ["deploy", "--execution", "remote", "--use-inventory", "--no-interactive"]
    )
    assert result.exit_code == 0, _output(result)
    remote = RecordingRemote.instances[-1]
    assert remote.host == "203.0.113.9"
    assert remote.kwargs["user"] == "deploy"
    assert remote.kwargs["port"] == 2222


def test_remote_use_inventory_alias_identity_used(monkeypatch, tmp_path: Path) -> None:
    alias_key = tmp_path / "alias_id"
    alias_key.write_text("k", encoding="utf-8")
    cfg = tmp_path / "ssh_config"
    cfg.write_text(f"Host myvps\n  IdentityFile {alias_key.as_posix()}\n", encoding="utf-8")
    _stub(monkeypatch, tmp_path, cfg)
    _write_inventory(tmp_path)
    result = runner.invoke(
        app, ["deploy", "--execution", "remote", "--use-inventory", "--no-interactive"]
    )
    assert result.exit_code == 0, _output(result)
    remote = RecordingRemote.instances[-1]
    assert remote.host == "myvps"
    assert remote.kwargs["key_filename"] == str(alias_key)
