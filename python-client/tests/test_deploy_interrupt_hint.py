"""Card 98: every unfinished deploy exit prints the repeat-deploy hint."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Self

import pytest
from typer.testing import CliRunner

import xrayvpn.cli.main as main_mod
from xrayvpn import i18n
from xrayvpn.cli.main import app
from xrayvpn.core.execution.remote import LOCK_HELD_RC, LOCK_MISSING_RC
from xrayvpn.core.transport.remote import SshConnectError

runner = CliRunner()
CLIENT_ROOT = Path(__file__).resolve().parents[1]


def _output(result) -> str:
    text = result.output or ""
    stderr = getattr(result, "stderr", "") or ""
    return text + stderr


def _flat(text: str) -> str:
    return " ".join(text.split())


HINT_EN = (
    "deploy did not finish — no repair needed, just run deploy again, every step is repeatable"
)
HINT_RU = "деплой не завершён — сервер можно не чинить"


@pytest.fixture(autouse=True)
def _reset_i18n():
    yield
    i18n.set_ru(False)


def _stub_common(monkeypatch, tmp_path: Path) -> Path:
    key = tmp_path / "id_ed25519"
    key.write_text("k", encoding="utf-8")
    monkeypatch.setattr(main_mod, "find_repo_root", lambda: tmp_path)
    monkeypatch.setattr(main_mod, "load_settings", lambda root: {})
    monkeypatch.setattr(
        main_mod, "apply_ssh_config", lambda host, user, port, **kw: (host, user, port, None)
    )
    return key


def _stub_remote(monkeypatch, tmp_path: Path, deploy_result: object, connect_exc: Exception | None = None):
    monkeypatch.setattr(main_mod, "_swap_guard", lambda remote, *, no_interactive: None)

    class FakeRemote:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def __enter__(self) -> Self:
            if connect_exc is not None:
                raise connect_exc
            return self

        def __exit__(self, *exc: object) -> bool:
            return False

    class FakeExecutor:
        def __init__(self, remote: object, *, cleanup: str) -> None:
            pass

        def deploy(self, request: object, *, extra_vars: dict) -> int:
            if isinstance(deploy_result, BaseException):
                raise deploy_result
            return int(deploy_result)

    monkeypatch.setattr(main_mod, "FabricRemote", FakeRemote)
    monkeypatch.setattr(main_mod, "RemoteExecutor", FakeExecutor)
    return _stub_common(monkeypatch, tmp_path)


def _remote_args(key: Path) -> list[str]:
    return ["deploy", "-H", "203.0.113.7", "--pkey", str(key), "--no-interactive"]


def test_remote_keyboardinterrupt_prints_hint_and_130(monkeypatch, tmp_path: Path) -> None:
    key = _stub_remote(monkeypatch, tmp_path, KeyboardInterrupt())
    result = runner.invoke(app, _remote_args(key))
    assert result.exit_code == 130, _output(result)
    assert HINT_EN in _flat(_output(result))


def test_remote_plain_failure_rc_prints_hint(monkeypatch, tmp_path: Path) -> None:
    key = _stub_remote(monkeypatch, tmp_path, 5)
    result = runner.invoke(app, _remote_args(key))
    assert result.exit_code == 5, _output(result)
    assert HINT_EN in _flat(_output(result))


def test_remote_lock_rcs_do_not_print_hint(monkeypatch, tmp_path: Path) -> None:
    key = _stub_remote(monkeypatch, tmp_path, LOCK_HELD_RC)
    result = runner.invoke(app, _remote_args(key))
    assert result.exit_code == LOCK_HELD_RC, _output(result)
    flat = _flat(_output(result))
    assert "another deploy is already running" in flat
    assert HINT_EN not in flat and HINT_RU not in flat

    key = _stub_remote(monkeypatch, tmp_path, LOCK_MISSING_RC)
    result = runner.invoke(app, _remote_args(key))
    assert result.exit_code == LOCK_MISSING_RC, _output(result)
    assert i18n.t("EXEC_DEPLOY_NOFLOCK") in _flat(_output(result))
    assert HINT_EN not in _flat(_output(result))


def test_remote_success_does_not_print_hint(monkeypatch, tmp_path: Path) -> None:
    key = _stub_remote(monkeypatch, tmp_path, 0)
    result = runner.invoke(app, _remote_args(key))
    assert result.exit_code == 0, _output(result)
    out = _flat(_output(result))
    assert HINT_EN not in out
    assert i18n.t("MAIN_DEPLOY_OK_TITLE") in out


def test_remote_connect_error_error_then_hint(monkeypatch, tmp_path: Path) -> None:
    key = _stub_remote(monkeypatch, tmp_path, 0, SshConnectError("SSH refused"))
    result = runner.invoke(app, _remote_args(key))
    assert result.exit_code == 2, _output(result)
    out = _flat(_output(result))
    assert "SSH refused" in out
    assert HINT_EN in out


class _LocalStub:
    def __init__(self, deploy_rc: int = 0, fetch_rc: int = 0, *, interrupt: bool = False) -> None:
        self.deploy_rc = deploy_rc
        self.fetch_rc = fetch_rc
        self.interrupt = interrupt


def _stub_local(monkeypatch, tmp_path: Path, impl: _LocalStub) -> Path:
    inv = tmp_path / "inv.yml"

    def fake_write_inventory(repo_root: Path, content: str) -> Path:
        inv.write_text(content, encoding="utf-8")
        return inv

    class FakeLocalExecutor:
        def __init__(self, *, wsl_venv: str, wsl_distro: str | None = None) -> None:
            pass

        def venv_binary(self) -> str:
            return "ansible-playbook"

        def preflight(self, *, password_auth: bool) -> None:
            pass

        def deploy(self, request: object, inventory: Path) -> int:
            if impl.interrupt:
                raise KeyboardInterrupt
            return impl.deploy_rc

        def fetch_configs(self, request: object, inventory: Path) -> object:
            return impl.fetch_rc

    monkeypatch.setattr(main_mod, "write_inventory", fake_write_inventory)
    monkeypatch.setattr(main_mod, "LocalExecutor", FakeLocalExecutor)
    return _stub_common(monkeypatch, tmp_path)


def _local_args(key: Path) -> list[str]:
    return [
        "deploy",
        "--execution",
        "local",
        "-H",
        "203.0.113.7",
        "--pkey",
        str(key),
        "--no-interactive",
    ]


def test_local_keyboardinterrupt_hint_and_temp_inventory_cleaned(
    monkeypatch, tmp_path: Path
) -> None:
    key = _stub_local(monkeypatch, tmp_path, _LocalStub(interrupt=True))
    result = runner.invoke(app, _local_args(key))
    assert result.exit_code == 130, _output(result)
    assert HINT_EN in _flat(_output(result))
    assert not (tmp_path / "inv.yml").exists()


def test_local_deploy_rc_hint(monkeypatch, tmp_path: Path) -> None:
    key = _stub_local(monkeypatch, tmp_path, _LocalStub(deploy_rc=7))
    result = runner.invoke(app, _local_args(key))
    assert result.exit_code == 7, _output(result)
    assert HINT_EN in _flat(_output(result))


def test_local_fetch_rc_hint_after_error_line(monkeypatch, tmp_path: Path) -> None:
    key = _stub_local(monkeypatch, tmp_path, _LocalStub(fetch_rc=3))
    result = runner.invoke(app, _local_args(key))
    assert result.exit_code == 3, _output(result)
    assert "rc=3" in _output(result)
    assert HINT_EN in _flat(_output(result))


def test_local_success_no_hint(monkeypatch, tmp_path: Path) -> None:
    key = _stub_local(monkeypatch, tmp_path, _LocalStub())
    result = runner.invoke(app, _local_args(key))
    assert result.exit_code == 0, _output(result)
    assert HINT_EN not in _flat(_output(result))


def test_local_hint_follows_output_language(monkeypatch, tmp_path: Path) -> None:
    i18n.set_ru(True)
    key = _stub_local(monkeypatch, tmp_path, _LocalStub(deploy_rc=1))
    result = runner.invoke(app, _local_args(key))
    assert HINT_RU in _flat(_output(result))


def test_welcome_retry_line_both_languages(monkeypatch) -> None:
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.setenv("XRAYVPN_HYPERLINK", "0")
    from xrayvpn.cli.repl import REPO_DOCS_URL, welcome_screen

    i18n.set_ru(False)
    en_screen = welcome_screen("1.2.3")
    assert "If something got interrupted — just run deploy again" in en_screen
    assert REPO_DOCS_URL in en_screen
    i18n.set_ru(True)
    ru_screen = welcome_screen("1.2.3")
    assert "Если что-то прервалось — просто повторите деплой" in ru_screen
    assert REPO_DOCS_URL in ru_screen


def _run_cli(args: list[str], env: dict[str, str]) -> str:
    result = subprocess.run(
        [sys.executable, "-m", "xrayvpn", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "COLUMNS": "200", "NO_COLOR": "1", **env},
        timeout=120,
        check=False,
        cwd=str(CLIENT_ROOT),
        input="",
    )
    return " ".join(((result.stdout or "") + (result.stderr or "")).split())


def test_deploy_help_epilogue_en_and_ru() -> None:
    en_help = _run_cli(["deploy", "--help"], {"XRAYVPN_LANG": "en"})
    assert "if a deploy gets interrupted, just run deploy again" in en_help
    assert "every step is repeatable" in en_help
    ru_help = _run_cli(["deploy", "--help"], {"XRAYVPN_LANG": "ru"})
    assert "если деплой прервался — просто запусти его заново" in ru_help
    assert "все шаги повторяемы" in ru_help
