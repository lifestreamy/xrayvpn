"""Tests for cli/repl.py + the no-args/session triggers (card B2)."""

from __future__ import annotations

import builtins
import io
from contextlib import redirect_stdout
from typing import Self
from unittest import mock

import pytest
from typer.testing import CliRunner

import xrayvpn.cli.main as main_mod
import xrayvpn.cli.repl as repl_mod
from xrayvpn import i18n
from xrayvpn.cli import l10n_typer, prompts
from xrayvpn.cli.repl import (
    REPL_SELFTEST_ENV,
    help_text,
    locale_suggests_ru,
    set_session_lang,
    start,
    tokenize,
    welcome_screen,
)

runner = CliRunner()


class Restore:
    """Undo language/session side effects regardless of test result."""

    def __enter__(self) -> Self:
        self.ru = i18n.is_ru()
        return self

    def __exit__(self, *exc: object) -> None:
        i18n.set_ru(self.ru)
        l10n_typer.revert_ru()


def _feed(lines: list):
    iterator = iter(lines)

    def fake_input(prompt: str = "") -> str:
        try:
            value = next(iterator)
        except StopIteration as exc:
            raise EOFError from exc
        if isinstance(value, BaseException):
            raise value
        return value

    return fake_input


def _run(
    lines: list,
    dispatch=None,
    *,
    locale_ru: bool = False,
    update_hint=None,
) -> tuple[int, list[list[str]], str]:
    calls: list[list[str]] = []

    def record(tokens: list[str]) -> int:
        calls.append(list(tokens))
        if tokens == ["deploy", "--interrupts"]:
            raise KeyboardInterrupt
        return 7 if (tokens and tokens[-1] == "--boom") else 0

    buffer = io.StringIO()
    with (
        mock.patch.object(builtins, "input", _feed(lines)),
        mock.patch.object(repl_mod, "locale_suggests_ru", lambda: locale_ru),
        redirect_stdout(buffer),
    ):
        rc = start(dispatch or record, version="9.9.9", update_hint=update_hint)
    return rc, calls, buffer.getvalue()


# --- tokenizer: Windows paths with spaces/backslashes survive -------------


def test_tokenize_plain_flags() -> None:
    assert tokenize("deploy --dry-run --no-interactive") == [
        "deploy",
        "--dry-run",
        "--no-interactive",
    ]


def test_tokenize_windows_path_with_spaces() -> None:
    tokens = tokenize(r'deploy --inventory "C:\Program Files\inv.yml"')
    assert tokens == ["deploy", "--inventory", r"C:\Program Files\inv.yml"]


def test_tokenize_windows_backslashes_intact_unquoted() -> None:
    tokens = tokenize(r"deploy --pkey C:\Users\Tim\.ssh\id_ed25519")
    assert tokens == ["deploy", "--pkey", r"C:\Users\Tim\.ssh\id_ed25519"]


def test_tokenize_inline_equals_quotes() -> None:
    assert tokenize('--host="203.0.113.7"') == ["--host=203.0.113.7"]


# --- locale detection -------------------------------------------------------


def test_locale_posix_prefix_order() -> None:
    env = {"LC_ALL": "ru_RU.UTF-8", "LANG": "en_US.UTF-8"}
    assert locale_suggests_ru(env=env, platform="linux")
    assert locale_suggests_ru(env={"LC_MESSAGES": "ru_RU"}, platform="linux")
    assert not locale_suggests_ru(env={"LANG": "en_US.UTF-8"}, platform="linux")
    assert not locale_suggests_ru(env={}, platform="linux")


def test_locale_win32_primary_language() -> None:
    assert locale_suggests_ru(platform="win32", win_ui_lang=lambda: 0x419)
    assert not locale_suggests_ru(platform="win32", win_ui_lang=lambda: 0x409)


def test_locale_errors_degrade_to_en() -> None:
    def boom() -> int:
        raise OSError("no kernel32")

    assert not locale_suggests_ru(platform="win32", win_ui_lang=boom)


# --- session loop -----------------------------------------------------------


def test_session_requested_tty_or_selftest(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(prompts, "is_interactive", lambda: False)
    monkeypatch.delenv(REPL_SELFTEST_ENV, raising=False)
    assert repl_mod.session_requested() is False
    monkeypatch.setenv(REPL_SELFTEST_ENV, "1")
    assert repl_mod.session_requested() is True
    monkeypatch.delenv(REPL_SELFTEST_ENV, raising=False)
    monkeypatch.setattr(prompts, "is_interactive", lambda: True)
    assert repl_mod.session_requested() is True


def test_session_exit_after_deploy_keeps_rc() -> None:
    rc, calls, out = _run(["deploy --dry-run", "exit"])
    assert rc == 0
    assert calls == [["deploy", "--dry-run"]]
    assert "Main command:" in out


def test_session_clean_exit_is_zero() -> None:
    rc, calls, _ = _run(["exit"])
    assert rc == 0
    assert calls == []


def test_session_last_rc_surfaces_on_exit() -> None:
    rc, _, _ = _run(["deploy --boom", "exit"])
    assert rc == 7


def test_empty_line_hints_and_never_deploys() -> None:
    rc, calls, out = _run(["", "", "exit"])
    assert rc == 0
    assert calls == []
    assert "help" in out


def test_xrayvpn_prefix_is_stripped() -> None:
    _, calls, _ = _run(["xrayvpn deploy --dry-run", "exit"])
    assert calls == [["deploy", "--dry-run"]]


def test_eof_exits_with_last_rc() -> None:
    rc, _, _ = _run(["deploy --dry-run"])
    assert rc == 0


def test_ctrl_c_at_prompt_hints_and_keeps_loop_alive() -> None:
    rc, calls, out = _run([KeyboardInterrupt(), "deploy --dry-run", "exit"])
    assert rc == 0
    assert calls == [["deploy", "--dry-run"]]
    assert "Ctrl+D" in out


def test_ctrl_c_during_command_marks_interrupted() -> None:
    rc, calls, out = _run(["deploy --interrupts", "exit"])
    assert rc == 0
    assert calls == [["deploy", "--interrupts"]]
    assert "[interrupted]" in out


def test_help_version_and_repl_words() -> None:
    rc, calls, out = _run(["help", "version", "repl", "exit"])
    assert rc == 0
    assert calls == []
    assert "commands:" in out
    assert "xrayvpn 9.9.9" in out
    assert "already in a session" in out


def test_lang_command_ru_en_round_trip_is_clean() -> None:
    with Restore():
        _, _, out = _run(["lang ru", "help", "lang en", "help", "exit"])
        assert i18n.is_ru() is False
        assert not l10n_typer._BACKUP
        assert "команды:" in out
        assert "commands:" in out


def test_bare_word_language_switch_confirms_in_one_line() -> None:
    with Restore():
        _, _, out = _run(["рус", "en", "exit"])
        assert "язык интерфейса: русский" in out
        assert "interface language: English" in out
        assert out.count("Main command:") == 2
        assert out.count("Основная команда:") == 1
        assert i18n.is_ru() is False
        assert not l10n_typer._BACKUP


def test_language_switch_reprints_banner_in_new_language() -> None:
    with Restore():
        _, _, out = _run(["рус", "exit"])
        assert "Main command:" in out
        assert "Основная команда:" in out
        assert "English interface" in out


def test_unknown_lang_prints_usage() -> None:
    with Restore():
        _, _, out = _run(["lang klingon", "exit"])
        assert "lang ru|en" in out


def test_update_hint_printed_under_banner() -> None:
    _, _, out = _run(["exit"], update_hint=lambda: "UPDATE-HINT")
    assert "UPDATE-HINT" in out
    assert out.index("Main command:") < out.index("UPDATE-HINT")


def test_no_hint_without_provider() -> None:
    _, _, out = _run(["exit"])
    assert "UPDATE-HINT" not in out


def test_start_applies_ru_when_locale_suggests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with Restore():
        monkeypatch.delenv(i18n.LANG_ENV, raising=False)
        _, _, out = _run(["exit"], locale_ru=True)
        assert "Основная команда:" in out
        assert i18n.is_ru()


def test_explicit_lang_env_beats_locale_detect(monkeypatch: pytest.MonkeyPatch) -> None:
    with Restore():
        monkeypatch.setenv(i18n.LANG_ENV, "en")
        _, _, out = _run(["exit"], locale_ru=True)
        assert "Main command:" in out
        assert i18n.is_ru() is False


def test_global_flags_in_session_do_not_nest(monkeypatch: pytest.MonkeyPatch) -> None:
    with Restore():
        monkeypatch.delenv(i18n.LANG_ENV, raising=False)
        rc, calls, out = _run(["--ru", "--version", "--bogus-flag", "exit"])
        assert rc == 0
        assert calls == []
        assert "язык интерфейса: русский" in out
        assert "рус/англ" in help_text()
        assert "xrayvpn 9.9.9" in out
        assert "--bogus-flag" in out


def test_dispatched_ru_flag_switches_full_session(capsys: pytest.CaptureFixture) -> None:
    with Restore():
        rc = main_mod._repl_dispatch(
            ["deploy", "--dry-run", "--no-interactive", "--host", "127.0.0.1", "--ru"]
        )
        assert rc == 0
        assert i18n.is_ru()
        assert l10n_typer._BACKUP
        assert "[превью] remote-деплой" in capsys.readouterr().out


# --- screen/guard strings ----------------------------------------------------


def test_welcome_and_help_strings_guards_en_ru(monkeypatch) -> None:
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.setenv("XRAYVPN_HYPERLINK", "0")
    with Restore():
        i18n.set_ru(False)
        en_screen = welcome_screen("1.2.3")
        assert "Main command:" in en_screen and "Other commands:" in en_screen
        assert "Just start:" not in en_screen
        assert "REALITY" in en_screen and 'введите "ru"' in en_screen
        assert "Tim Korelov (https://github.com/lifestreamy)" in en_screen
        assert "repository:" in en_screen and "xrayvpn" in en_screen
        assert "releases/latest" in en_screen
        assert "v1.2.3" in en_screen
        assert "command list" in en_screen and "deploy --help" in en_screen
        assert "all flags" in en_screen
        assert "banner" in en_screen and "show this screen again" in en_screen
        assert "service" in en_screen
        assert "status/restart/logs/reboot over SSH" in en_screen
        assert "exit|quit|q" in en_screen
        assert "this list" in help_text()
        set_session_lang("ru")
        ru_screen = welcome_screen("1.2.3")
        assert "Разворачивает собственный VPN-сервер Xray VLESS + REALITY" in ru_screen
        assert "Основная команда:" in ru_screen
        assert 'type "en"' in ru_screen and 'English interface — type "en"' in ru_screen
        assert "автор:" in ru_screen and "репозиторий:" in ru_screen
        assert "deploy --help — все флаги" in ru_screen
        assert "состояние/рестарт/логи/перезагрузка по SSH" in ru_screen
        ru_help = help_text()
        assert "тот же синтаксис" in ru_help
        assert "фиксируется при запуске процесса" in ru_help
        set_session_lang("en")
        assert not l10n_typer._BACKUP


def test_welcome_switch_inverts_per_reader_language() -> None:
    """The RU invite is written fully in Russian (EN banner), the EN invite fully
    in English (RU banner): each line is read by whoever needs it."""
    from xrayvpn.text import MESSAGES

    switch = MESSAGES["REPL_WELCOME_SWITCH"]
    assert "type" not in switch.en
    assert "введите" not in switch.ru
    with Restore():
        i18n.set_ru(False)
        en_screen = welcome_screen("1.2.3")
        set_session_lang("ru")
        ru_screen = welcome_screen("1.2.3")
    assert switch.en in en_screen
    assert switch.ru in ru_screen


def test_banner_command_reprints_welcome() -> None:
    rc, _, out = _run(["banner", "exit"])
    assert rc == 0
    assert out.count("VPN server provisioning assistant") == 2


def test_welcome_box_borders_align_with_colors(monkeypatch) -> None:
    monkeypatch.delenv("NO_COLOR", raising=False)
    from xrayvpn.cli import theme

    monkeypatch.setattr(theme, "_is_tty", lambda: True)
    monkeypatch.setattr(theme, "_console_vt_ready", lambda: True)
    with Restore():
        i18n.set_ru(False)
        monkeypatch.delenv("XRAYVPN_HYPERLINK", raising=False)
        screen = welcome_screen("1.2.3")
        assert "\x1b[" in screen
        widths = {theme.visible_len(line) for line in screen.splitlines()}
        assert len(widths) == 1

        monkeypatch.setenv("XRAYVPN_HYPERLINK", "1")
        linked = welcome_screen("1.2.3")
        assert "\x1b]8;;" in linked
        widths = {theme.visible_len(line) for line in linked.splitlines()}
        assert len(widths) == 1


def test_run_capture_is_plain_without_tty(monkeypatch) -> None:
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.delenv("XRAYVPN_HYPERLINK", raising=False)
    _, _, out = _run(["exit"])
    assert "\x1b[" not in out
    assert "\x1b]8;" not in out
    assert (
        "Tim Korelov (https://github.com/lifestreamy)" in out
    )


def test_lang_notice_renders_in_new_language_each_way() -> None:
    with Restore():
        i18n.set_ru(False)
        assert repl_mod.lang_notice() == "interface language: English"
        set_session_lang("ru")
        assert repl_mod.lang_notice() == "язык интерфейса: русский"
        set_session_lang("en")


def test_cancel_rc_130_keeps_session_with_note() -> None:
    def dispatch(tokens: list[str]) -> int:
        return 130 if "--abort" in tokens else 0

    rc, _, out = _run(["deploy --abort", "exit"], dispatch=dispatch)
    assert rc == 0
    assert "[cancel] command aborted" in out


def test_deploy_help_carries_settings_defaults_and_examples() -> None:
    result = runner.invoke(main_mod.app, ["deploy", "--help"])
    assert result.exit_code == 0
    dense = "".join(ch for ch in result.output.split() if not set(ch) & set("│─┌┐└┘"))
    assert "examples:" in result.output
    assert "default:native" in dense
    assert "default:443" in dense
    assert "default:3" in dense
    assert "default:dl.google.com" in dense
    assert "default:enabled" in dense
    assert "default:keepexistingstate" in dense
    assert "default:true" not in dense
    assert "default:false" not in dense


# --- l10n_typer symmetry ------------------------------------------------------


def test_apply_ru_revert_ru_round_trip_is_symmetric() -> None:
    from typer._click import exceptions as click_exceptions

    original = click_exceptions.NoSuchOption("--zz").format_message()
    assert original.startswith("No such option")
    try:
        l10n_typer.apply_ru()
        l10n_typer.apply_ru()  # idempotent
        assert "Нет такой опции" in click_exceptions.NoSuchOption("--zz").format_message()
    finally:
        l10n_typer.revert_ru()
        l10n_typer.revert_ru()  # idempotent
    assert click_exceptions.NoSuchOption("--zz").format_message() == original
    assert not l10n_typer._BACKUP


# --- wiring into typer ---------------------------------------------------------


def test_bare_invocation_non_tty_help_exit2_pinned(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(prompts, "is_interactive", lambda: False)
    monkeypatch.delenv(REPL_SELFTEST_ENV, raising=False)
    result = runner.invoke(main_mod.app, [])
    assert result.exit_code == 2
    assert "Usage" in result.output


def test_bare_invocation_tty_opens_session(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(prompts, "is_interactive", lambda: True)
    monkeypatch.setattr(repl_mod, "start", lambda dispatch, **kw: 5)
    result = runner.invoke(main_mod.app, [])
    assert result.exit_code == 5


def test_repl_command_opens_without_tty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(prompts, "is_interactive", lambda: False)
    monkeypatch.setattr(repl_mod, "start", lambda dispatch, **kw: 9)
    result = runner.invoke(main_mod.app, ["repl"])
    assert result.exit_code == 9


def test_repl_command_is_hidden_from_help() -> None:
    result = runner.invoke(main_mod.app, ["--help"])
    assert result.exit_code == 0
    assert "repl" not in result.output


def test_repl_dispatch_runs_the_real_command_in_process(capsys: pytest.CaptureFixture) -> None:
    rc = main_mod._repl_dispatch(
        ["deploy", "--dry-run", "--no-interactive", "--host", "127.0.0.1"]
    )
    assert rc == 0
    assert "[preview] remote deploy" in capsys.readouterr().out


def test_repl_dispatch_click_usage_error_is_code_two() -> None:
    assert main_mod._repl_dispatch(["deploy", "--definitely-not-a-flag"]) == 2


def test_flag_invocations_do_not_open_session(monkeypatch: pytest.MonkeyPatch) -> None:
    def explode(*args: object, **kwargs: object) -> None:
        raise AssertionError("REPL must not intercept non-command runs")

    monkeypatch.setattr(prompts, "is_interactive", lambda: True)
    monkeypatch.setattr(repl_mod, "start", lambda dispatch, **kw: explode())
    assert runner.invoke(main_mod.app, ["--version"]).exit_code == 0
    assert runner.invoke(main_mod.app, ["--ru", "--version"]).exit_code == 0
