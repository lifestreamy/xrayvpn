"""Tests for core/execution/local.py: ssh-target inventory vars, argv builders,
WSL script assembly, control-node preflight and the fetch playbook rendering."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from xrayvpn.core import wsl
from xrayvpn.core.execution import local as local_mod
from xrayvpn.core.execution.base import DeployRequest
from xrayvpn.core.execution.local import (
    LocalExecutor,
    build_ssh_inventory_vars,
)


def _request(tmp_path: Path, **kwargs: object) -> DeployRequest:
    defaults: dict[str, object] = {
        "repo_root": tmp_path,
        "overrides": {"xray_port": 443},
        "verbosity": 4,
        "debug": True,
        "dry_run": True,
    }
    defaults.update(kwargs)
    return DeployRequest(**defaults)


def test_ssh_vars_key_auth() -> None:
    params = build_ssh_inventory_vars(
        {"host": "203.0.113.7", "user": "root", "port": "2222", "pkey": "/home/tim/.ssh/id"}
    )
    assert params["ansible_host"] == "203.0.113.7"
    assert params["ansible_user"] == "root"
    assert params["ansible_port"] == "2222"
    assert params["ansible_ssh_private_key_file"] == "/home/tim/.ssh/id"
    assert "ansible_ssh_pass" not in params


def test_ssh_vars_password_and_no_auth() -> None:
    params = build_ssh_inventory_vars(
        {"host": "h", "user": "u", "port": "22", "password": "s3cret"}
    )
    assert params["ansible_ssh_pass"] == "s3cret"
    bare = build_ssh_inventory_vars({"host": "h", "user": "u", "port": "22"})
    assert not any(k.startswith("ansible_ssh_") for k in bare)


def test_ssh_vars_omit_unset_user_port() -> None:
    assert build_ssh_inventory_vars({"host": "myvps"}) == {"ansible_host": "myvps"}


def test_deploy_argv_native(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(wsl, "is_windows", lambda: False)
    monkeypatch.setattr(local_mod.shutil, "which", lambda name: None)
    executor = LocalExecutor(wsl_venv="/opt/venv")
    inventory = tmp_path / "inv.yml"
    argv = executor.deploy_argv(_request(tmp_path), inventory)
    assert argv[0].endswith("ansible-playbook")
    assert argv[1] == "deploy.yml"
    assert argv[2:4] == ["-i", str(inventory)]
    assert "-vvvv" in argv
    assert argv.count("-e") == 2
    assert "xray_debug=true" in argv
    assert "--check" in argv


def test_deploy_argv_quiet_no_check(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(wsl, "is_windows", lambda: False)
    monkeypatch.setattr(local_mod.shutil, "which", lambda name: None)
    executor = LocalExecutor()
    request = _request(tmp_path, verbosity=0, debug=False, dry_run=False)
    argv = executor.deploy_argv(request, tmp_path / "inv.yml")
    assert not any(a.startswith("-vv") for a in argv)
    assert "--check" not in argv
    assert argv.count("-e") == 1


def test_wsl_script_translates_and_wraps(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(wsl, "is_windows", lambda: True)
    monkeypatch.setattr(local_mod.wsl, "to_wsl_path", lambda p: f"/mnt/z/{p}")
    executor = LocalExecutor(wsl_venv="~/xray-venv")
    executor._wsl_home = "/home/tim"
    # a space forces shlex quoting identically on every OS (plain /tmp paths
    # come back unquoted on POSIX runners)
    script = executor.build_wsl_script(
        executor.deploy_argv(_request(tmp_path), Path("inv.yml")),
        tmp_path / "work dir",
    )
    assert script.startswith("cd '/mnt/z/")
    assert "[ -d $HOME/xrayvpn-collections/ansible_collections/community/general ]" in script
    assert "ANSIBLE_SSH_ARGS='-o StrictHostKeyChecking=accept-new'" in script
    assert "inv.yml" in script
    assert "--check" in script
    assert "/home/tim/xray-venv/bin/ansible-playbook" in script


def test_build_wsl_script_drive_translation() -> None:
    if sys.platform == "win32":
        assert wsl.to_wsl_path(r"C:\repo\inv.yml") == "/mnt/c/repo/inv.yml"
    else:
        assert wsl.to_wsl_path(Path("/tmp/repo/inv.yml")) == "/tmp/repo/inv.yml"


@pytest.mark.skipif(
    sys.platform != "win32",
    reason="WSL bridge exists only for Windows hosts (Linux runs natively)",
)
def test_wsl_script_real_windows_paths() -> None:
    executor = LocalExecutor(wsl_venv="~/xray-venv")
    executor._wsl_home = "/home/tim"
    script = executor.build_wsl_script(
        ["ansible-playbook", "-i", r"C:\repo\inv.yml"],
        Path(r"C:\repo"),
    )
    assert script.startswith("cd /mnt/c/repo")
    assert "/mnt/c/repo/inv.yml" in script


def test_preflight_native_missing_binary(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(wsl, "is_windows", lambda: False)
    monkeypatch.setattr(local_mod.shutil, "which", lambda name: None)
    executor = LocalExecutor(wsl_venv=str(tmp_path / "no-venv"))
    with pytest.raises(RuntimeError, match="ansible-playbook not found"):
        executor.preflight(password_auth=False)


def test_preflight_native_password_requires_sshpass(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(wsl, "is_windows", lambda: False)
    (tmp_path / "bin").mkdir()
    (tmp_path / "bin" / "ansible-playbook").write_text("#!", encoding="utf-8")
    monkeypatch.setattr(local_mod.shutil, "which", lambda name: None)
    executor = LocalExecutor(wsl_venv=str(tmp_path))
    with pytest.raises(RuntimeError, match="sshpass"):
        executor.preflight(password_auth=True)


def test_preflight_native_ok(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(wsl, "is_windows", lambda: False)
    (tmp_path / "bin").mkdir()
    (tmp_path / "bin" / "ansible-playbook").write_text("#!", encoding="utf-8")
    monkeypatch.setattr(local_mod.shutil, "which", lambda name: "/usr/bin/" + name)
    executor = LocalExecutor(wsl_venv=str(tmp_path))
    executor.preflight(password_auth=True)
    assert executor.venv_binary_for_run() == str(tmp_path / "bin" / "ansible-playbook")


def test_preflight_windows_requires_wsl(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(wsl, "is_windows", lambda: True)
    monkeypatch.setattr(wsl, "wsl_available", lambda: False)
    executor = LocalExecutor()
    with pytest.raises(RuntimeError, match="WSL"):
        executor.preflight(password_auth=False)


def test_fetch_playbook_targets_ssh_stage_dirs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(wsl, "is_windows", lambda: False)
    executor = LocalExecutor()
    clients = tmp_path / "clients"
    text = executor.fetch_playbook_text(clients)
    assert "hosts: vpn" in text
    assert "xrayvpn-fetch." in text
    assert "/root/vpn-configs" in text
    assert "fetch:" in text
    assert "flat: true" in text
    assert "{{ item.path }}" in text
    assert "staged.matched > 0" in text
    assert "state: directory" in text
    assert "mode: 0700" in text
    assert "state: absent" in text
    assert clients.as_posix() in text


def test_fetch_playbook_dest_uses_wsl_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(wsl, "is_windows", lambda: True)
    monkeypatch.setattr(wsl, "to_wsl_path", lambda value: "/mnt/z/clients")
    text = LocalExecutor().fetch_playbook_text(tmp_path / "clients")
    assert 'dest: "/mnt/z/clients/"' in text


def test_fetch_argv_uses_playbook(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(wsl, "is_windows", lambda: False)
    executor = LocalExecutor(wsl_venv="/opt/venv")
    argv = executor.fetch_argv(tmp_path / "inv.yml", tmp_path / "fetch.yml")
    assert argv[1:4] == ["-i", str(tmp_path / "inv.yml"), str(tmp_path / "fetch.yml")]
