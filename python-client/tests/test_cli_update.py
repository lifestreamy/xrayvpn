"""CLI tests for `xrayvpn update` (CliRunner, everything injected)."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

import xrayvpn.cli.main as main_mod
from xrayvpn.core import install_source, update, update_state

runner = CliRunner()


def _info(kind: str) -> install_source.InstallInfo:
    return install_source.InstallInfo(kind=kind, confidence="high", detail="test")


def _release(tag: str) -> update.Release:
    return update.Release(
        tag=tag,
        version=tag.lstrip("vV"),
        prerelease=False,
        published_at="2026-01-01T00:00:00Z",
        html_url=f"https://github.com/lifestreamy/xrayvpn/releases/tag/{tag}",
    )


@pytest.fixture()
def state_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "state" / "update-state.json"
    monkeypatch.setattr(update_state, "default_state_path", lambda **kwargs: path)
    return path


def test_update_check_exit_codes(
    monkeypatch: pytest.MonkeyPatch, state_file: Path
) -> None:
    monkeypatch.setattr(install_source, "detect", lambda: _info(install_source.STANDALONE))
    monkeypatch.setattr(
        update, "resolve_release", lambda requested_version, http=None: _release("v9.9.9")
    )
    result = runner.invoke(main_mod.app, ["update", "--check"])
    assert result.exit_code == 10
    assert "v9.9.9" in result.output

    monkeypatch.setattr(
        update, "resolve_release", lambda requested_version, http=None: _release("v0.4.2")
    )
    current = runner.invoke(main_mod.app, ["update", "--check"])
    assert current.exit_code == 0


def test_update_standalone_yes_runs_swap(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, state_file: Path
) -> None:
    monkeypatch.setattr(install_source, "detect", lambda: _info(install_source.STANDALONE))
    calls: dict[str, object] = {}

    def fake_perform(
        target: Path,
        *,
        current: str,
        platform: str,
        machine: str,
        requested_version: str | None = None,
        http: object = None,
        opener: object = None,
    ) -> update.UpdateOutcome:
        calls.update(target=target, requested=requested_version)
        return update.UpdateOutcome(
            update.STATUS_UPDATED, "9.9.9", Path(target), Path(str(target) + ".old")
        )

    monkeypatch.setattr(update, "perform_standalone_update", fake_perform)
    fake_exe = tmp_path / "xrayvpn.exe"
    fake_exe.write_bytes(b"x")
    monkeypatch.setattr(main_mod.sys, "argv", [str(fake_exe)])
    result = runner.invoke(main_mod.app, ["update", "--yes"])
    assert result.exit_code == 0
    assert "9.9.9" in result.output
    assert calls["target"] == fake_exe


def test_update_pin_old_version_warns(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, state_file: Path
) -> None:
    monkeypatch.setattr(install_source, "detect", lambda: _info(install_source.STANDALONE))

    def fake_perform(
        target: Path,
        *,
        current: str,
        platform: str,
        machine: str,
        requested_version: str | None = None,
        http: object = None,
        opener: object = None,
    ) -> update.UpdateOutcome:
        return update.UpdateOutcome(
            update.STATUS_UPDATED, "0.4.2", Path(target), Path(str(target) + ".old")
        )

    monkeypatch.setattr(update, "perform_standalone_update", fake_perform)
    fake_exe = tmp_path / "xrayvpn.exe"
    fake_exe.write_bytes(b"x")
    monkeypatch.setattr(main_mod.sys, "argv", [str(fake_exe)])
    result = runner.invoke(main_mod.app, ["update", "--version", "0.4.2", "--yes"])
    assert result.exit_code == 0
    assert "has no `xrayvpn update`" in result.output


def test_update_pin_current_version_no_warn(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, state_file: Path
) -> None:
    monkeypatch.setattr(install_source, "detect", lambda: _info(install_source.STANDALONE))

    def fake_perform(
        target: Path,
        *,
        current: str,
        platform: str,
        machine: str,
        requested_version: str | None = None,
        http: object = None,
        opener: object = None,
    ) -> update.UpdateOutcome:
        return update.UpdateOutcome(
            update.STATUS_UPDATED, "0.4.3", Path(target), Path(str(target) + ".old")
        )

    monkeypatch.setattr(update, "perform_standalone_update", fake_perform)
    fake_exe = tmp_path / "xrayvpn.exe"
    fake_exe.write_bytes(b"x")
    monkeypatch.setattr(main_mod.sys, "argv", [str(fake_exe)])
    result = runner.invoke(main_mod.app, ["update", "--version", "0.4.3", "--yes"])
    assert result.exit_code == 0
    assert "has no `xrayvpn update`" not in result.output


def test_update_standalone_non_tty_requires_yes(
    monkeypatch: pytest.MonkeyPatch, state_file: Path
) -> None:
    monkeypatch.setattr(install_source, "detect", lambda: _info(install_source.STANDALONE))
    result = runner.invoke(main_mod.app, ["update"])
    assert result.exit_code == 2
    assert "--yes" in result.output


def test_update_dry_run_never_installs(
    monkeypatch: pytest.MonkeyPatch, state_file: Path
) -> None:
    monkeypatch.setattr(install_source, "detect", lambda: _info(install_source.STANDALONE))
    monkeypatch.setattr(
        update, "resolve_release", lambda requested_version, http=None: _release("v9.9.9")
    )

    def boom(*args: object, **kwargs: object) -> None:
        raise AssertionError("dry-run must not install")

    monkeypatch.setattr(update, "perform_standalone_update", boom)
    result = runner.invoke(main_mod.app, ["update", "--dry-run"])
    assert result.exit_code == 0
    assert "dry-run" in result.output


def test_update_manager_brew_shows_command(
    monkeypatch: pytest.MonkeyPatch, state_file: Path
) -> None:
    monkeypatch.setattr(install_source, "detect", lambda: _info(install_source.BREW))
    result = runner.invoke(main_mod.app, ["update"])
    assert result.exit_code == 2
    assert "brew upgrade xrayvpn" in result.output


def test_update_manager_pip_never_executes(
    monkeypatch: pytest.MonkeyPatch, state_file: Path
) -> None:
    monkeypatch.setattr(install_source, "detect", lambda: _info(install_source.PIP))

    def boom(kind: str, command: object, **kwargs: object) -> int:
        raise AssertionError("pip must not be executed")

    monkeypatch.setattr(update, "run_manager_command", boom)
    result = runner.invoke(main_mod.app, ["update", "--yes"])
    assert result.exit_code == 2
    assert "pip install" in result.output


def test_update_uv_tool_executes_with_yes(
    monkeypatch: pytest.MonkeyPatch, state_file: Path
) -> None:
    monkeypatch.setattr(install_source, "detect", lambda: _info(install_source.UV_TOOL))
    calls: list[tuple[str, list[str]]] = []

    def fake_run(kind: str, command: object, **kwargs: object) -> int:
        calls.append((kind, list(command)))
        return 0

    monkeypatch.setattr(update, "run_manager_command", fake_run)
    result = runner.invoke(main_mod.app, ["update", "--yes"])
    assert result.exit_code == 0
    assert calls == [(install_source.UV_TOOL, ["uv", "tool", "upgrade", "xrayvpn"])]


def test_update_uv_tool_failure_is_rc1(
    monkeypatch: pytest.MonkeyPatch, state_file: Path
) -> None:
    monkeypatch.setattr(install_source, "detect", lambda: _info(install_source.UV_TOOL))
    monkeypatch.setattr(update, "run_manager_command", lambda kind, command, **kw: 3)
    result = runner.invoke(main_mod.app, ["update", "--yes"])
    assert result.exit_code == 1
    assert "rc=3" in result.output


def test_update_manager_pin_hint(
    monkeypatch: pytest.MonkeyPatch, state_file: Path
) -> None:
    monkeypatch.setattr(install_source, "detect", lambda: _info(install_source.BREW))
    result = runner.invoke(main_mod.app, ["update", "--version", "0.4.2"])
    assert result.exit_code == 2
    assert "brew pin xrayvpn" in result.output


def test_update_dev_and_unknown_are_manual(
    monkeypatch: pytest.MonkeyPatch, state_file: Path
) -> None:
    monkeypatch.setattr(install_source, "detect", lambda: _info(install_source.DEV))
    dev = runner.invoke(main_mod.app, ["update"])
    assert dev.exit_code == 2
    assert "git pull" in dev.output

    monkeypatch.setattr(install_source, "detect", lambda: _info(install_source.UNKNOWN))
    unknown = runner.invoke(main_mod.app, ["update"])
    assert unknown.exit_code == 2


def test_update_error_envelope_is_rc1(
    monkeypatch: pytest.MonkeyPatch, state_file: Path
) -> None:
    monkeypatch.setattr(install_source, "detect", lambda: _info(install_source.STANDALONE))

    def boom(requested_version: str | None, http: object = None) -> update.Release:
        raise update.UpdateError("offline")

    monkeypatch.setattr(update, "resolve_release", boom)
    result = runner.invoke(main_mod.app, ["update", "--check"])
    assert result.exit_code == 1
    assert "offline" in result.output


def test_update_skip_and_unskip(
    monkeypatch: pytest.MonkeyPatch, state_file: Path
) -> None:
    monkeypatch.setattr(
        update, "resolve_release", lambda requested_version, http=None: _release("v9.9.9")
    )
    result = runner.invoke(main_mod.app, ["update", "--skip"])
    assert result.exit_code == 0
    assert update_state.skipped_version(state_file) == "9.9.9"

    unskip = runner.invoke(main_mod.app, ["update", "--unskip"])
    assert unskip.exit_code == 0
    assert update_state.skipped_version(state_file) is None


def test_update_skip_conflict_is_rc2(state_file: Path) -> None:
    result = runner.invoke(main_mod.app, ["update", "--skip", "--unskip"])
    assert result.exit_code == 2


def test_update_list_prints_releases(
    monkeypatch: pytest.MonkeyPatch, state_file: Path
) -> None:
    monkeypatch.setattr(
        update,
        "list_versions",
        lambda *, limit=10, include_prerelease=False, http=None: [_release("v0.4.2")],
    )
    result = runner.invoke(main_mod.app, ["update", "list"])
    assert result.exit_code == 0
    assert "v0.4.2" in result.output


def test_update_list_marks_not_recommended(
    monkeypatch: pytest.MonkeyPatch, state_file: Path
) -> None:
    monkeypatch.setattr(
        update,
        "list_versions",
        lambda *, limit=10, include_prerelease=False, http=None: [
            _release("v0.4.4"),
            _release("v0.4.3"),
        ],
    )
    result = runner.invoke(main_mod.app, ["update", "list"])
    assert result.exit_code == 0
    lines = result.output.splitlines()
    assert any(line.startswith("! v0.4.3") for line in lines)
    assert any(line.startswith("  v0.4.4") for line in lines)
    assert ("not recommended" in result.output) or ("не рекомендуется" in result.output)


def test_update_version_warns_when_not_recommended(
    monkeypatch: pytest.MonkeyPatch, state_file: Path
) -> None:
    monkeypatch.setattr(install_source, "detect", lambda: _info(install_source.STANDALONE))
    monkeypatch.setattr(
        update, "resolve_release", lambda requested_version, http=None: _release("v0.4.3")
    )
    result = runner.invoke(main_mod.app, ["update", "--version", "0.4.3", "--dry-run"])
    assert result.exit_code == 0
    assert ("not recommended" in result.output) or ("не рекомендуется" in result.output)

    monkeypatch.setattr(
        update, "resolve_release", lambda requested_version, http=None: _release("v0.4.4")
    )
    clean = runner.invoke(main_mod.app, ["update", "--version", "0.4.4", "--dry-run"])
    assert clean.exit_code == 0
    assert "not recommended" not in clean.output
    assert "не рекомендуется" not in clean.output


def test_update_list_error_is_rc1(
    monkeypatch: pytest.MonkeyPatch, state_file: Path
) -> None:
    def boom(**kwargs: object) -> list[update.Release]:
        raise update.UpdateError("offline")

    monkeypatch.setattr(update, "list_versions", boom)
    result = runner.invoke(main_mod.app, ["update", "list"])
    assert result.exit_code == 1
