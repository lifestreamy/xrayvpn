"""Card 76: --no-config-download skips client config fetch in both modes."""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

import pytest
from typer.testing import CliRunner

import xrayvpn.cli.main as main_mod
from xrayvpn.cli.main import app
from xrayvpn.core.execution.base import DeployRequest
from xrayvpn.core.execution.remote import RemoteExecutor
from xrayvpn.core.transport.remote import CommandResult

runner = CliRunner()

SKIP_EN = "client config download skipped (--no-config-download)"


class LocalRecording:
    instances: ClassVar[list[LocalRecording]] = []

    def __init__(self, *, wsl_venv: str, wsl_distro: str | None = None) -> None:
        self.fetched = False
        self.deployed_request: DeployRequest | None = None
        LocalRecording.instances.append(self)

    def venv_binary(self) -> str:
        return "ansible-playbook"

    def preflight(self, *, password_auth: bool) -> None:
        pass

    def deploy(self, request: object, inventory: Path) -> int:
        self.deployed_request = request  # type: ignore[assignment]
        return 0

    def fetch_configs(self, request: object, inventory: Path) -> int:
        self.fetched = True
        return 0


def _stub_local(monkeypatch, tmp_path: Path) -> tuple[dict[str, object], Path]:
    LocalRecording.instances = []
    written: dict[str, object] = {}
    inv = tmp_path / "inv.yml"
    key = tmp_path / "id_ed25519"
    key.write_text("k", encoding="utf-8")

    def fake_write_inventory(repo_root: Path, content: str) -> Path:
        inv.write_text(content, encoding="utf-8")
        written["content"] = content
        return inv

    monkeypatch.setattr(main_mod, "find_repo_root", lambda: tmp_path)
    monkeypatch.setattr(main_mod, "load_settings", lambda root: {})
    monkeypatch.setattr(main_mod, "write_inventory", fake_write_inventory)
    monkeypatch.setattr(main_mod, "LocalExecutor", LocalRecording)
    monkeypatch.setattr(
        main_mod, "apply_ssh_config", lambda host, user, port, **kw: (host, user, port, None)
    )
    monkeypatch.setattr(main_mod, "ssh_config_entry", lambda host, **kw: None)
    return written, key


def _local_args(key: Path, extra: list[str]) -> list[str]:
    return [
        "deploy",
        "--execution",
        "local",
        "-H",
        "203.0.113.7",
        "--pkey",
        str(key),
        "--no-interactive",
        *extra,
    ]


def test_local_flag_skips_fetch_and_done_line(monkeypatch, tmp_path: Path) -> None:
    _written, key = _stub_local(monkeypatch, tmp_path)
    result = runner.invoke(app, _local_args(key, ["--no-config-download"]))
    assert result.exit_code == 0, result.output
    recorder = LocalRecording.instances[0]
    assert recorder.fetched is False
    assert recorder.deployed_request is not None
    assert recorder.deployed_request.download_configs is False
    out = result.output
    assert SKIP_EN in out
    assert "[done] configs written" not in out


def test_local_default_still_fetches(monkeypatch, tmp_path: Path) -> None:
    _written, key = _stub_local(monkeypatch, tmp_path)
    result = runner.invoke(app, _local_args(key, []))
    assert result.exit_code == 0, result.output
    assert LocalRecording.instances[0].fetched is True
    assert SKIP_EN not in result.output


def _remote_request(tmp_path: Path, *, download: bool) -> DeployRequest:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    (repo / "deploy.yml").write_text("---\n", encoding="utf-8")
    (repo / "config").mkdir()
    (repo / "config" / "settings.yml").write_text("a: 1\n", encoding="utf-8")
    return DeployRequest(
        repo_root=repo, clients_dir=tmp_path / "clients", overrides={}, download_configs=download
    )


class _QuietRemote:
    def run(self, command: str, **kwargs: object) -> CommandResult:
        return CommandResult(return_code=0)

    def put(self, local: object, remote: str) -> None:
        pass

    def get(self, remote: str, local: object) -> None:
        pass


def _spy_executor(calls: list[str]):
    class SpyExecutor(RemoteExecutor):
        def fetch_configs(self, clients_dir: Path, staging_fetch_dir: str) -> None:
            calls.append("fetch")

    return SpyExecutor(_QuietRemote(), cleanup="cleanup")  # type: ignore[arg-type]


@pytest.mark.parametrize("download", (True, False))
def test_remote_executor_honors_download_flag(
    tmp_path: Path, download: bool, capsys: pytest.CaptureFixture[str]
) -> None:
    calls: list[str] = []
    executor = _spy_executor(calls)
    request = _remote_request(tmp_path / f"run-{download}", download=download)
    rc = executor.deploy(request, extra_vars={})
    assert rc == 0
    assert calls == (["fetch"] if download else [])
    out = capsys.readouterr().out
    assert (SKIP_EN in out) is (not download)


def test_deploy_help_lists_new_flag() -> None:
    result = runner.invoke(app, ["deploy", "--help"])
    assert result.exit_code == 0
    assert "--no-config-download" in result.output
