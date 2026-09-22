"""Local deploy resolves ~/.ssh/config aliases (parity with remote mode)."""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from typer.testing import CliRunner

import xrayvpn.cli.main as main_mod
import xrayvpn.core.conn as conn_mod
from xrayvpn.cli.main import app

runner = CliRunner()


def _output(result) -> str:
    text = result.output or ""
    stderr = getattr(result, "stderr", "") or ""
    return text + stderr


class RecordingExecutor:
    instances: ClassVar[list[RecordingExecutor]] = []

    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs
        self.deployed_with: tuple | None = None
        self.fetched = False
        RecordingExecutor.instances.append(self)

    def venv_binary(self) -> str:
        return "ansible-playbook"

    def preflight(self, *, password_auth: bool) -> None:
        self.password_auth = password_auth

    def deploy(self, request: object, inventory: Path) -> int:
        self.deployed_with = (request, inventory)
        return 0

    def fetch_configs(self, request: object, inventory: Path) -> None:
        self.fetched = True


def _stub_local_mode(monkeypatch, tmp_path: Path) -> dict[str, object]:
    RecordingExecutor.instances = []
    written: dict[str, object] = {}
    fake_inv = tmp_path / "inv.yml"

    def fake_write_inventory(repo_root: Path, content: str) -> Path:
        fake_inv.write_text(content, encoding="utf-8")
        written["content"] = content
        return fake_inv

    monkeypatch.setattr(main_mod, "find_repo_root", lambda: tmp_path)
    monkeypatch.setattr(main_mod, "load_settings", lambda root: {})
    monkeypatch.setattr(main_mod, "write_inventory", fake_write_inventory)
    monkeypatch.setattr(main_mod, "LocalExecutor", RecordingExecutor)
    monkeypatch.setattr(main_mod, "ssh_config_entry", lambda host, **kwargs: None)
    return written


def _no_getpass(monkeypatch) -> None:
    def explode(*args: object, **kwargs: object) -> str:
        raise AssertionError("password must not be requested")

    monkeypatch.setattr(main_mod.getpass, "getpass", explode)


def test_alias_with_identityfile_skips_password_and_resolves_inventory(
    monkeypatch, tmp_path
) -> None:
    written = _stub_local_mode(monkeypatch, tmp_path)
    alias_key = tmp_path / "alias_id"
    alias_key.write_text("k", encoding="utf-8")
    calls: list[tuple] = []

    def fake_apply(host: str, user: str, port: int, **kwargs: object):
        calls.append((host, user, port))
        return "203.0.113.9", "deploy", 2222, str(alias_key)

    monkeypatch.setattr(main_mod, "apply_ssh_config", fake_apply)
    _no_getpass(monkeypatch)
    result = runner.invoke(
        app, ["deploy", "--execution", "local", "-H", "myvps", "--no-interactive"]
    )
    assert result.exit_code == 0, _output(result)
    assert calls == [("myvps", "root", 22)]
    content = str(written["content"])
    assert "ansible_host: 203.0.113.9" in content
    assert "ansible_user: deploy" in content
    assert "ansible_port: '2222'" in content or "ansible_port: 2222" in content
    assert "alias_id" in content
    assert "ansible_ssh_private_key_file" in content


def test_bare_ip_without_auth_prompts_password(monkeypatch, tmp_path) -> None:
    _stub_local_mode(monkeypatch, tmp_path)
    monkeypatch.setattr(
        main_mod, "apply_ssh_config", lambda host, user, port, **k: (host, user, port, None)
    )
    monkeypatch.setattr(main_mod.prompts, "is_interactive", lambda: True)
    monkeypatch.setattr(main_mod.prompts, "confirm", lambda *a, **k: False)
    prompted: list[str] = []

    def fake_getpass(prompt: str = "") -> str:
        prompted.append(prompt)
        return "secret"

    monkeypatch.setattr(main_mod.getpass, "getpass", fake_getpass)
    result = runner.invoke(app, ["deploy", "--execution", "local", "-H", "203.0.113.7"])
    assert result.exit_code == 0, _output(result)
    assert prompted
    assert "secret" not in _output(result)


def test_use_inventory_does_not_apply_ssh_config(monkeypatch, tmp_path) -> None:
    _stub_local_mode(monkeypatch, tmp_path)
    (tmp_path / "inventory.yml").write_text(
        "all:\n"
        "  hosts:\n"
        "    vps:\n"
        "      ansible_host: 203.0.113.7\n"
        "      ansible_user: root\n"
        "      ansible_port: 22\n"
        "      ansible_ssh_pass: hostpw\n",
        encoding="utf-8",
    )

    def explode(*args: object, **kwargs: object):
        raise AssertionError("apply_ssh_config must not run with --use-inventory")

    monkeypatch.setattr(main_mod, "apply_ssh_config", explode)
    result = runner.invoke(
        app, ["deploy", "--execution", "local", "--use-inventory", "--no-interactive"]
    )
    assert result.exit_code == 0, _output(result)


def test_explicit_pkey_wins_over_alias_key(monkeypatch, tmp_path) -> None:
    written = _stub_local_mode(monkeypatch, tmp_path)
    flag_key = tmp_path / "flag_id"
    flag_key.write_text("k", encoding="utf-8")
    alias_key = tmp_path / "alias_id"
    alias_key.write_text("k", encoding="utf-8")
    monkeypatch.setattr(
        main_mod,
        "apply_ssh_config",
        lambda host, user, port, **k: ("203.0.113.9", user, port, str(alias_key)),
    )
    _no_getpass(monkeypatch)
    result = runner.invoke(
        app,
        [
            "deploy",
            "--execution",
            "local",
            "-H",
            "myvps",
            "--pkey",
            str(flag_key),
            "--no-interactive",
        ],
    )
    assert result.exit_code == 0, _output(result)
    content = str(written["content"])
    assert "flag_id" in content
    assert "alias_id" not in content


def test_plan_shows_alias_resolution(monkeypatch, tmp_path) -> None:
    _stub_local_mode(monkeypatch, tmp_path)
    alias_key = tmp_path / "alias_id"
    alias_key.write_text("k", encoding="utf-8")
    monkeypatch.setattr(
        main_mod,
        "apply_ssh_config",
        lambda host, user, port, **k: ("203.0.113.9", user, 2222, str(alias_key)),
    )
    monkeypatch.setattr(main_mod.prompts, "is_interactive", lambda: True)
    monkeypatch.setattr(main_mod.prompts, "confirm", lambda *a, **k: False)
    _no_getpass(monkeypatch)
    result = runner.invoke(app, ["deploy", "--execution", "local", "-H", "myvps"])
    out = _output(result)
    assert result.exit_code == 0, out
    assert "ssh alias: myvps → 203.0.113.9:2222" in out
    assert "target: root@203.0.113.9:2222" in out
    assert "auth: SSH key" in out


def _use_real_ssh_config(monkeypatch, cfg: Path) -> None:
    monkeypatch.setattr(
        main_mod,
        "apply_ssh_config",
        lambda host, user, port, **kw: conn_mod.apply_ssh_config(
            host, user, port, config_path=cfg
        ),
    )
    monkeypatch.setattr(
        main_mod,
        "ssh_config_entry",
        lambda host, **kw: conn_mod.ssh_config_entry(host, config_path=cfg),
    )


def test_full_config_block_pins_nothing_without_flags(monkeypatch, tmp_path: Path) -> None:
    written = _stub_local_mode(monkeypatch, tmp_path)
    cfg = tmp_path / "ssh_config"
    cfg.write_text(
        "Host myvps\n  HostName 203.0.113.9\n  User deploy\n  Port 2222\n",
        encoding="utf-8",
    )
    _use_real_ssh_config(monkeypatch, cfg)
    _no_getpass(monkeypatch)
    result = runner.invoke(
        app, ["deploy", "--execution", "local", "-H", "myvps", "--no-interactive"]
    )
    assert result.exit_code == 0, _output(result)
    content = str(written["content"])
    assert "ansible_host: myvps" in content
    assert "ansible_user" not in content
    assert "ansible_port" not in content
    assert "ansible_ssh" not in content


def test_identityfile_only_alias_delegates_auth(monkeypatch, tmp_path: Path) -> None:
    written = _stub_local_mode(monkeypatch, tmp_path)
    alias_key = tmp_path / "alias_id"
    alias_key.write_text("k", encoding="utf-8")
    cfg = tmp_path / "ssh_config"
    cfg.write_text(f"Host myvps\n  IdentityFile {alias_key.as_posix()}\n", encoding="utf-8")
    _use_real_ssh_config(monkeypatch, cfg)
    _no_getpass(monkeypatch)
    result = runner.invoke(
        app, ["deploy", "--execution", "local", "-H", "myvps", "--no-interactive"]
    )
    assert result.exit_code == 0, _output(result)
    content = str(written["content"])
    assert "ansible_host: myvps" in content
    assert "ansible_user" not in content
    assert "ansible_ssh_private_key_file" not in content


def test_explicit_user_flag_pins_user_despite_config(monkeypatch, tmp_path: Path) -> None:
    written = _stub_local_mode(monkeypatch, tmp_path)
    flag_key = tmp_path / "flag_id"
    flag_key.write_text("k", encoding="utf-8")
    cfg = tmp_path / "ssh_config"
    cfg.write_text(
        "Host myvps\n  HostName 203.0.113.9\n  User deploy\n  Port 2222\n",
        encoding="utf-8",
    )
    _use_real_ssh_config(monkeypatch, cfg)
    _no_getpass(monkeypatch)
    result = runner.invoke(
        app,
        [
            "deploy",
            "--execution",
            "local",
            "-H",
            "myvps",
            "-u",
            "ops",
            "--pkey",
            str(flag_key),
            "--no-interactive",
        ],
    )
    assert result.exit_code == 0, _output(result)
    content = str(written["content"])
    assert "ansible_host: 203.0.113.9" in content
    assert "ansible_user: ops" in content
    assert "2222" in content
    assert "ansible_ssh_private_key_file" in content
