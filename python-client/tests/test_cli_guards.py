"""CLI guards: flag/mode validation and the deploy-plan confirmation policy."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import ClassVar

from typer.testing import CliRunner

import xrayvpn.cli.main as main_mod
from xrayvpn.cli.main import app

runner = CliRunner()


def _output(result) -> str:
    text = result.output or ""
    stderr = getattr(result, "stderr", "") or ""
    return text + stderr


class RecordingExecutor:
    """Stands in for LocalExecutor; records calls, returns a fixed rc."""

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


def _stub_local_mode(
    monkeypatch,
    tmp_path: Path,
) -> dict[str, object]:
    """Isolate _run_local: fake repo root, recording executor, fake inventory."""
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
    return written


def test_inventory_requires_local_mode() -> None:
    result = runner.invoke(app, ["deploy", "--inventory", "x.yml"])
    assert result.exit_code == 2
    assert "--execution local" in _output(result)


def test_unknown_execution_mode_rejected() -> None:
    result = runner.invoke(app, ["deploy", "--execution", "cloud"])
    assert result.exit_code == 2
    assert "unknown execution mode" in _output(result)


def test_default_execution_is_remote_noninteractive() -> None:
    """No flag + non-interactive stdin must resolve remote (never silent local);
    dry-run shows the remote preview and never connects."""
    result = runner.invoke(app, ["deploy", "--dry-run"])
    assert result.exit_code == 0
    assert "[preview] remote deploy" in _output(result)


def test_confirmation_blocks_run_without_terminal(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(main_mod.prompts, "is_interactive", lambda: False)
    _stub_local_mode(monkeypatch, tmp_path)
    key = tmp_path / "id_ed25519"
    key.write_text("x", encoding="utf-8")
    result = runner.invoke(
        app,
        ["deploy", "--execution", "local", "-H", "203.0.113.7", "--pkey", str(key)],
    )
    assert result.exit_code == 2
    assert "confirmation needs a terminal" in _output(result)
    assert RecordingExecutor.instances == []


def test_declined_plan_aborts_before_any_work(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(main_mod.prompts, "is_interactive", lambda: True)
    monkeypatch.setattr(main_mod.prompts, "confirm", lambda *a, **k: False)
    _stub_local_mode(monkeypatch, tmp_path)
    key = tmp_path / "id_ed25519"
    key.write_text("x", encoding="utf-8")
    result = runner.invoke(
        app,
        ["deploy", "--execution", "local", "-H", "203.0.113.7", "--pkey", str(key)],
    )
    assert result.exit_code == 0
    out = _output(result)
    assert "[abort]" in out
    assert "deploy plan:" in out
    assert "auth: SSH key" in out
    assert RecordingExecutor.instances == []


def test_no_interactive_runs_and_writes_ssh_inventory(monkeypatch, tmp_path) -> None:
    written = _stub_local_mode(monkeypatch, tmp_path)
    key = tmp_path / "id_ed25519"
    key.write_text("x", encoding="utf-8")
    result = runner.invoke(
        app,
        [
            "deploy",
            "--execution",
            "local",
            "-H",
            "203.0.113.7",
            "-u",
            "root",
            "--pkey",
            str(key),
            "--no-interactive",
        ],
    )
    assert result.exit_code == 0
    executor = RecordingExecutor.instances[-1]
    assert executor.deployed_with is not None
    content = str(written["content"])
    assert "ansible_connection: ssh" in content
    assert "ansible_host: 203.0.113.7" in content
    assert "ansible_ssh_private_key_file" in content
    assert executor.fetched
    assert "[done] configs written to" in _output(result)


def test_rotate_warning_in_plan(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(main_mod.prompts, "is_interactive", lambda: True)
    monkeypatch.setattr(main_mod.prompts, "confirm", lambda *a, **k: False)
    _stub_local_mode(monkeypatch, tmp_path)
    key = tmp_path / "id_ed25519"
    key.write_text("x", encoding="utf-8")
    result = runner.invoke(
        app,
        [
            "deploy",
            "--execution",
            "local",
            "-H",
            "203.0.113.7",
            "--pkey",
            str(key),
            "--rotate",
        ],
    )
    out = _output(result)
    assert "REALITY keys and client UUIDs will be regenerated" in out


def test_mutual_exclusions_keep_working() -> None:
    result = runner.invoke(app, ["deploy", "--full-cleanup", "--no-cleanup"])
    assert result.exit_code == 2
    assert "mutually exclusive" in _output(result)
    result = runner.invoke(app, ["deploy", "--pkey", "k", "--pass", "p"])
    assert result.exit_code == 2
    assert "--pkey and --pass" in _output(result)
    result = runner.invoke(app, ["deploy", "--runtime", "podman"])
    assert result.exit_code == 2
    assert "--runtime must be one of" in _output(result)


def test_plan_shows_merged_inventory_vars_and_redacts_secrets(monkeypatch, tmp_path) -> None:
    _stub_local_mode(monkeypatch, tmp_path)
    (tmp_path / "inventory.yml").write_text(
        "all:\n"
        "  hosts:\n"
        "    vps:\n"
        "      ansible_host: 203.0.113.7\n"
        "      ansible_user: root\n"
        "      ansible_port: 22\n"
        "      ansible_ssh_pass: hostpw\n"
        "  vars:\n"
        "    num_clients: 3\n"
        "    gateway_password: topsecret\n",
        encoding="utf-8",
    )
    result = runner.invoke(
        app,
        ["deploy", "--execution", "local", "--use-inventory", "--no-interactive"],
    )
    assert result.exit_code == 0
    out = _output(result)
    assert "num_clients" in out
    assert "topsecret" not in out
    assert "hostpw" not in out
    assert "******" in out


def test_local_dry_run_needs_no_input(monkeypatch, tmp_path) -> None:
    _stub_local_mode(monkeypatch, tmp_path)

    def explode(*args: object, **kwargs: object) -> None:
        raise AssertionError("dry-run must not prompt")

    monkeypatch.setattr(main_mod.prompts, "text", explode)
    monkeypatch.setattr(main_mod.prompts, "confirm", explode)
    result = runner.invoke(
        app, ["deploy", "--execution", "local", "--dry-run", "--no-interactive"]
    )
    assert result.exit_code == 0
    out = _output(result)
    assert "[preview] local ansible" in out
    assert "<host>" in out


def test_remote_no_interactive_requires_host_without_prompting(monkeypatch) -> None:
    monkeypatch.setattr(main_mod, "load_settings", lambda root: {})

    def explode(*args: object, **kwargs: object) -> None:
        raise AssertionError("--no-interactive must not prompt")

    monkeypatch.setattr(main_mod.prompts, "text", explode)
    result = runner.invoke(app, ["deploy", "--no-interactive"])
    assert result.exit_code == 2
    assert "--host is required in remote mode" in _output(result)


def test_swap_guard_no_interactive_is_explicit(monkeypatch, capsys) -> None:
    class StubRemote:
        def __init__(self) -> None:
            self.calls: list[str] = []

        def run(self, command: str, **kwargs: object) -> SimpleNamespace:
            self.calls.append(command)
            stdout = "512000" if len(self.calls) == 1 else "0"
            return SimpleNamespace(stdout=stdout, failed=False, return_code=0)

    def explode(*args: object, **kwargs: object) -> None:
        raise AssertionError("swap-guard must not ask when prompts are unavailable")

    monkeypatch.setattr(main_mod.prompts, "confirm", explode)
    monkeypatch.setattr(main_mod.prompts, "is_interactive", lambda: False)
    main_mod._swap_guard(StubRemote(), no_interactive=True)
    assert "WITHOUT swap" in capsys.readouterr().err
