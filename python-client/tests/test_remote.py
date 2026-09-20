"""Tests for core/execution/remote.py: bootstrap/cleanup commands, orchestration."""

from __future__ import annotations

import re
import sys
import time
from pathlib import Path

import pytest

from xrayvpn import i18n
from xrayvpn.core.execution import remote as remote_mod
from xrayvpn.core.execution.base import DeployRequest
from xrayvpn.core.execution.remote import (
    ANSIBLE_CORE_PIN,
    SERVER_COLLECTIONS,
    SERVER_VENV,
    SWAPFILE,
    RemoteExecutor,
    bootstrap_commands,
    cleanup_commands,
    fetch_dir,
    fetch_targets,
    playbook_command,
    staging_dir,
    swap_guard_commands,
    swap_guard_needed,
    swap_status_commands,
)
from xrayvpn.core.transport.remote import CommandResult

_LOCK_PREFIX = "exec 200>/run/lock/xrayvpn-deploy.lock; flock -n 200 || exit 75;"


def test_bootstrap_commands_content() -> None:
    staging = staging_dir("testrun")
    commands = bootstrap_commands(staging)
    assert commands[0].startswith("command -v flock")
    assert all(c.startswith(_LOCK_PREFIX) for c in commands[1:])
    assert any("python3 -V" in c for c in commands)
    assert any("python3 -m venv" in c and SERVER_VENV in c for c in commands)
    # bare Debian/Ubuntu lack python3-venv → the venv line must carry the apt fallback
    assert any("apt-get install -y python3-venv" in c for c in commands)
    assert any(f"ansible-core=={ANSIBLE_CORE_PIN}" in c for c in commands)
    assert any("community.general" in c and SERVER_COLLECTIONS in c for c in commands)
    assert any(c.endswith(f"mkdir -p {staging} {fetch_dir(staging)}") for c in commands)
    assert any("xrayvpn-*" in c and "-mmin +1440" in c for c in commands)


def test_playbook_command_build() -> None:
    staging = staging_dir("testrun")
    request = DeployRequest(repo_root=Path("."), overrides={}, verbosity=3, dry_run=True)
    command = playbook_command(request, {"warp_enabled": False, "xray_runtime": "native"}, staging)
    assert command.startswith(f"{_LOCK_PREFIX} cd {staging}")
    assert f"ANSIBLE_COLLECTIONS_PATH={SERVER_COLLECTIONS}" in command
    assert f"{SERVER_VENV}/bin/ansible-playbook" in command
    assert "-i inventory.yml" in command
    assert "deploy.yml" in command
    assert "-vvv" in command
    assert "'{\"warp_enabled\": false, \"xray_runtime\": \"native\"}'" in command
    assert "--check" in command


def test_cleanup_commands_modes() -> None:
    staging = staging_dir("testrun")
    assert cleanup_commands("cleanup", staging) == [f"rm -rf {staging}"]
    assert cleanup_commands("full-cleanup", staging) == [f"rm -rf {staging} {SERVER_VENV}"]
    assert cleanup_commands("no-cleanup", staging) == []


def test_fetch_targets_filters() -> None:
    listing = "clash.yaml\namnezia.json\nnotes.txt\nsubdir\n"
    assert fetch_targets(listing) == ["clash.yaml", "amnezia.json"]


def test_swap_guard_needed_thresholds() -> None:
    assert swap_guard_needed(512 * 1024, 0)
    assert swap_guard_needed(1024 * 1024 - 1, 0)
    assert not swap_guard_needed(1024 * 1024, 0)
    assert not swap_guard_needed(512 * 1024, 1)
    assert not swap_guard_needed(2048 * 1024, 0)


def test_swap_status_commands_read_proc() -> None:
    commands = swap_status_commands()
    assert any("/proc/meminfo" in c for c in commands)
    assert any("/proc/swaps" in c for c in commands)


def test_swap_guard_commands_content() -> None:
    commands = swap_guard_commands()
    joined = "\n".join(commands)
    assert SWAPFILE in joined
    assert "fallocate -l 1G" in joined
    assert "dd if=/dev/zero" in joined
    assert "chmod 600" in joined
    assert "mkswap" in joined and "swapon" in joined
    assert "/etc/fstab" in joined
    assert all(c.startswith("sudo -n") for c in commands)


class FakeRemote:
    """Recorded-run Remote stub: all commands succeed."""

    def __init__(self, listing: str = "clash.yaml\namnezia.json\n") -> None:
        self.commands: list[str] = []
        self.puts: list[tuple[str, str]] = []
        self.gets: list[tuple[str, str]] = []
        self.listing = listing

    def run(self, command, *, sudo=False, warn=True, env=None) -> CommandResult:
        self.commands.append(command)
        stdout = self.listing if "ls " in command else ""
        return CommandResult(return_code=0, stdout=stdout)

    def put(self, local, remote) -> None:
        self.puts.append((str(local), remote))

    def get(self, remote, local) -> None:
        self.gets.append((remote, str(local)))
        Path(local).write_text(f"# fake {Path(remote).name}\n", encoding="utf-8")

    def close(self) -> None:
        pass


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "deploy.yml").write_text("---\n", encoding="utf-8")
    (repo / "config").mkdir()
    (repo / "config" / "settings.yml").write_text("a: 1\n", encoding="utf-8")
    return repo


def test_deploy_orchestration(tmp_path: Path) -> None:
    remote = FakeRemote()
    executor = RemoteExecutor(remote, cleanup="cleanup")
    repo = _repo(tmp_path)
    request = DeployRequest(
        repo_root=repo,
        clients_dir=tmp_path / "clients",
        overrides={"warp_enabled": False},
    )
    rc = executor.deploy(request, extra_vars={"warp_enabled": False})

    assert rc == 0
    # bootstrap ran
    joined = "\n".join(remote.commands)
    assert f"ansible-core=={ANSIBLE_CORE_PIN}" in joined
    assert "pip install" in joined
    # extract + inventory + playbook + cleanup
    assert "tar -xzf" in joined
    assert "chmod 0600" in joined
    assert "ansible-playbook" in joined
    assert any(c.startswith("rm -rf /tmp/xrayvpn-") for c in remote.commands)
    assert not any("SERVER_VENV" in c and "rm -rf" in c for c in remote.commands)
    # uploads: bundle + server inventory
    assert len(remote.puts) == 2
    assert remote.puts[0][1].endswith("bundle.tar.gz")
    assert remote.puts[1][1].endswith("inventory.yml")
    # fetched client configs
    assert len(remote.gets) == 2
    assert (tmp_path / "clients" / "clash.yaml").exists()


def test_deploy_playbook_failure_stops_flow(tmp_path: Path) -> None:
    class FailingRemote(FakeRemote):
        def run(self, command, *, sudo=False, warn=True, env=None) -> CommandResult:
            self.commands.append(command)
            if "ansible-playbook" in command:
                return CommandResult(return_code=4, stderr="boom")
            return CommandResult(return_code=0)

    remote = FailingRemote()
    executor = RemoteExecutor(remote, cleanup="cleanup")
    request = DeployRequest(repo_root=_repo(tmp_path), overrides={})
    rc = executor.deploy(request, extra_vars={})
    assert rc == 4
    assert not any(c.startswith("rm -rf /tmp/xrayvpn-") for c in remote.commands)


# --- card 99: [n/7] bootstrap progress ------------------------------------------------


class _ProgressRemote(FakeRemote):
    def __init__(self, *, delay_fragment: str = "", fail: str = "") -> None:
        super().__init__()
        self.delay_fragment = delay_fragment
        self.fail = fail

    def run(self, command, *, sudo=False, warn=True, env=None) -> CommandResult:
        self.commands.append(command)
        if self.delay_fragment and self.delay_fragment in command:
            time.sleep(0.2)
        if self.fail and self.fail in command:
            return CommandResult(return_code=9, stderr="nope")
        return CommandResult(return_code=0)


def _stage_en_lines() -> list[tuple[int, str]]:
    return [
        (1, "python"),
        (2, "venv"),
        (3, "installing ansible-core"),
        (4, "galaxy collection"),
        (5, "staging dirs"),
        (6, "uploading repo"),
        (7, "playbook"),
    ]


@pytest.fixture(autouse=True)
def _reset_i18n():
    yield
    i18n.set_ru(False)


def test_deploy_prints_all_seven_stage_labels_once(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    executor = RemoteExecutor(_ProgressRemote(), cleanup="cleanup")
    request = DeployRequest(repo_root=_repo(tmp_path), clients_dir=tmp_path / "c", overrides={})
    rc = executor.deploy(request, extra_vars={})
    assert rc == 0
    out = capsys.readouterr().out
    labels = [line for line in out.splitlines() if re.match(r"^\[\d/7\]", line)]
    expected = [f"[{n}/7] {stage}" for n, stage in _stage_en_lines()]
    assert labels == expected


def test_progress_ru_and_en_switch(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    i18n.set_ru(True)
    executor = RemoteExecutor(_ProgressRemote(), cleanup="cleanup")
    request = DeployRequest(repo_root=_repo(tmp_path), overrides={}, dry_run=True)
    rc = executor.deploy(request, extra_vars={})
    assert rc == 0
    out = capsys.readouterr().out
    assert "[7/7] плейбук" in out
    assert "[3/7] установка ansible-core" in out


def _force_tty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)


def test_heartbeat_ticks_only_during_long_stage(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(remote_mod, "HEARTBEAT_INTERVAL_SECONDS", 0.02)
    _force_tty(monkeypatch)
    remote = _ProgressRemote(delay_fragment="python3 -m venv")
    executor = RemoteExecutor(remote, cleanup="cleanup")
    request = DeployRequest(repo_root=_repo(tmp_path), overrides={}, dry_run=True)
    rc = executor.deploy(request, extra_vars={})
    assert rc == 0
    out = capsys.readouterr().out
    assert re.search(r"\r\[2/7\] venv, \d+ s", out)
    assert "[1/7] python, " not in out


def test_heartbeat_absent_without_tty(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    executor = RemoteExecutor(_ProgressRemote(delay_fragment="ansible-core=="), cleanup="cleanup")
    request = DeployRequest(repo_root=_repo(tmp_path), overrides={}, dry_run=True)
    rc = executor.deploy(request, extra_vars={})
    assert rc == 0
    out = capsys.readouterr().out
    assert "\r" not in out
    assert "[3/7] installing ansible-core" in out


def test_heartbeat_tick_language(tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(remote_mod, "HEARTBEAT_INTERVAL_SECONDS", 0.02)
    _force_tty(monkeypatch)
    i18n.set_ru(True)
    executor = RemoteExecutor(_ProgressRemote(delay_fragment="ansible-galaxy"), cleanup="cleanup")
    request = DeployRequest(repo_root=_repo(tmp_path), overrides={}, dry_run=True)
    assert executor.deploy(request, extra_vars={}) == 0
    assert re.search(r"\r\[4/7\] коллекция galaxy, \d+ с", capsys.readouterr().out)


def test_stage_line_terminated_before_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    remote = _ProgressRemote(fail="python3 -m venv")
    executor = RemoteExecutor(remote, cleanup="cleanup")
    request = DeployRequest(repo_root=_repo(tmp_path), overrides={}, dry_run=True)
    rc = executor.deploy(request, extra_vars={})
    assert rc == 9
    out = capsys.readouterr().out
    assert "[2/7] venv\n[remote] bootstrap failed:" in out


def test_heartbeat_joined_after_playbook_failure(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(remote_mod, "HEARTBEAT_INTERVAL_SECONDS", 0.02)
    _force_tty(monkeypatch)
    remote = _ProgressRemote(delay_fragment="ansible-playbook", fail="ansible-playbook")
    executor = RemoteExecutor(remote, cleanup="cleanup")
    request = DeployRequest(repo_root=_repo(tmp_path), overrides={}, dry_run=True)
    rc = executor.deploy(request, extra_vars={})
    assert rc == 9
    out = capsys.readouterr().out
    assert re.search(r"\r\[7/7\] playbook, \d+ s", out)
    assert i18n.t("EXEC_PLAYBOOK_FAIL", rc=9) in out