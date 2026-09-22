"""i18n: `--ru` / XRAYVPN_LANG switch EVERYTHING to Russian, --help included.

Runtime messages are checked in-process (CliRunner); help and parser errors
are checked by real subprocess launches, because Typer bakes help texts at
import time and the RU built-ins are patched before the app is built
(see xrayvpn/cli/l10n_typer.py).
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from xrayvpn import i18n
from xrayvpn.cli.l10n_typer import translate_message
from xrayvpn.cli.main import app

runner = CliRunner()
CLIENT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _reset_i18n():
    yield
    i18n.set_ru(False)


def _output(result) -> str:
    text = result.output or ""
    stderr = getattr(result, "stderr", "") or ""
    return text + stderr


def _run_cli(args: list[str], env: dict[str, str] | None = None) -> str:
    # No PYTHONIOENCODING crutch: the CLI must survive redirected streams
    # (locale codec on Windows) on its own — see _harden_stdio in cli/main.py.
    full_env = {
        **os.environ,
        "COLUMNS": "200",
        **(env or {}),
        "NO_COLOR": "1",
    }
    full_env.pop("FORCE_COLOR", None)
    result = subprocess.run(
        [sys.executable, "-m", "xrayvpn", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=full_env,
        timeout=120,
        check=False,
        cwd=str(CLIENT_ROOT),
        input="",
    )
    return _strip_ansi((result.stdout or "") + (result.stderr or ""))


def _strip_ansi(text: str) -> str:
    """GitHub POSIX runners force color despite NO_COLOR, and rich splits an
    option like `--no-interactive` into separate SGR runs (``…\\x1b[36m-`` +
    ``-no`` + ``-interactive``), which breaks literal substring assertions.
    Stripping SGR re-joins the runs without merging table columns (those stay
    separated by plain spaces)."""
    return _ANSI_RE.sub("", text)


_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def test_t_switch() -> None:
    assert i18n.t("MAIN_CONFIRM_START") == "Start the deploy?"
    i18n.set_ru(True)
    assert i18n.t("MAIN_CONFIRM_START") == "Начать деплой?"
    assert i18n.is_ru()


def test_ru_flag_on_command_translates_guard_error() -> None:
    result = runner.invoke(app, ["deploy", "--ru", "--debug", "--verbose"])
    assert result.exit_code == 2
    assert "взаимоисключающие" in _output(result)


def test_ru_flag_before_command_translates_guard_error() -> None:
    result = runner.invoke(app, ["--ru", "deploy", "--debug", "--verbose"])
    assert result.exit_code == 2
    assert "взаимоисключающие" in _output(result)


def test_default_output_stays_english() -> None:
    result = runner.invoke(app, ["deploy", "--debug", "--verbose"])
    assert result.exit_code == 2
    assert "mutually exclusive" in _output(result)


def test_ru_inventory_guard_translation() -> None:
    result = runner.invoke(app, ["deploy", "--ru", "--inventory", "x.yml"])
    assert result.exit_code == 2
    assert "применим только к --execution local" in _output(result)


def test_confirmation_guard_error_is_russian() -> None:
    out = _run_cli(
        ["deploy", "--ru", "--execution", "local", "-H", "203.0.113.7",
         "--pkey", "pyproject.toml"]
    )
    assert "ошибка: подтверждение требует терминала" in out


def test_confirmation_guard_error_english_by_default() -> None:
    out = _run_cli(
        ["deploy", "--execution", "local", "-H", "203.0.113.7", "--pkey", "pyproject.toml"]
    )
    assert "confirmation needs a terminal" in out


def test_preinit_detects_ru_in_any_argv_position() -> None:
    i18n.preinit(["deploy", "--help", "--ru"])
    assert i18n.is_ru()
    i18n.set_ru(False)
    i18n.preinit(["--ru", "deploy"])
    assert i18n.is_ru()
    i18n.set_ru(False)
    i18n.preinit(["deploy", "--verbose"])
    assert not i18n.is_ru()


def test_preinit_reads_lang_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(i18n.LANG_ENV, "RU")
    i18n.preinit([])
    assert i18n.is_ru()
    monkeypatch.setenv(i18n.LANG_ENV, "en")
    i18n.preinit([])
    assert not i18n.is_ru()
    monkeypatch.setenv(i18n.LANG_ENV, "xx")
    i18n.preinit([])
    assert not i18n.is_ru()


def test_ru_flag_argv_wins_over_lang_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(i18n.LANG_ENV, "en")
    i18n.preinit(["deploy", "--ru"])
    assert i18n.is_ru()


def test_translate_message_maps_known_english_texts() -> None:
    assert translate_message("Got unexpected extra argument(s) (foo bar)") == (
        "Получены неожиданные лишние аргументы (foo bar)"
    )
    assert translate_message("Option '--host' requires an argument.") == (
        "Опция '--host' требует аргумент."
    )
    assert translate_message("Option '--host' requires 2 arguments.") == (
        "Опция '--host' требует аргументов: 2."
    )
    assert translate_message("Option '--warp' does not take a value.") == (
        "Опция '--warp' не принимает значение."
    )
    assert translate_message("'abc' is not a valid integer.") == (
        "'abc' не является допустимым целым числом."
    )
    assert translate_message("'x' is not a valid boolean. Recognized values: 1, 0") == (
        "'x' не является допустимым логическим значением. Допустимые значения: 1, 0"
    )
    assert translate_message("'x' is not a valid UUID.") == (
        "'x' не является допустимым UUID."
    )
    assert translate_message("something else") == "something else"


def test_help_is_russian_with_ru_flag_after_command() -> None:
    out = _run_cli(["deploy", "--ru", "--help"])
    assert "Использование:" in out
    assert "Опции" in out
    assert "Узел ansible" in out
    assert "Показать это сообщение и выйти." in out
    assert "--no-interactive" in out


def test_help_is_russian_with_ru_flag_before_command() -> None:
    out = _run_cli(["--ru", "deploy", "--help"])
    assert "Использование:" in out
    assert "Развёртывание VPN на VPS" in out


def test_help_is_russian_via_lang_env() -> None:
    out = _run_cli(["deploy", "--help"], env={i18n.LANG_ENV: "ru"})
    assert "Использование:" in out
    assert "Опции" in out


def test_top_level_help_commands_panel_is_russian() -> None:
    out = _run_cli(["--ru", "--help"])
    assert "Команды" in out


def test_default_values_are_russian_in_help() -> None:
    out = _run_cli(["deploy", "--ru", "--help"])
    assert "[по умолчанию:" in out


def test_apply_ru_patches_constants_and_plain_show_fallback() -> None:
    """Guard every rich_utils constant and the show() fallbacks (rich normally
    routes errors around show(); the plain path must stay Russian too)."""
    import io

    from typer import rich_utils
    from typer._click import decorators as click_decorators
    from typer._click import exceptions as click_exceptions
    from typer._click import formatting as click_formatting

    from xrayvpn.cli import l10n_typer

    constant_names = (
        "ARGUMENTS_PANEL_TITLE",
        "OPTIONS_PANEL_TITLE",
        "COMMANDS_PANEL_TITLE",
        "ERRORS_PANEL_TITLE",
        "ABORTED_TEXT",
        "DEFAULT_STRING",
        "REQUIRED_LONG_STRING",
        "RICH_HELP",
    )
    method_targets = (
        (click_formatting.HelpFormatter, "write_usage"),
        (click_decorators, "help_option"),
        (click_exceptions.ClickException, "show"),
        (click_exceptions.UsageError, "show"),
        (click_exceptions.UsageError, "format_message"),
        (click_exceptions.BadParameter, "format_message"),
        (click_exceptions.MissingParameter, "format_message"),
        (click_exceptions.NoSuchOption, "format_message"),
        (click_exceptions.FileError, "format_message"),
    )
    saved_constants = {name: getattr(rich_utils, name) for name in constant_names}
    saved_methods = [(obj, name, getattr(obj, name)) for obj, name in method_targets]
    try:
        l10n_typer._PATCHED = False
        l10n_typer.apply_ru()
        assert rich_utils.ABORTED_TEXT == "Прервано."
        assert rich_utils.COMMANDS_PANEL_TITLE == "Команды"
        assert rich_utils.DEFAULT_STRING == "[по умолчанию: {}]"
        assert rich_utils.OPTIONS_PANEL_TITLE == "Опции"
        assert rich_utils.ERRORS_PANEL_TITLE == "Ошибка"

        buf = io.StringIO()
        click_exceptions.ClickException("boom").show(file=buf)
        assert "Ошибка: boom" in buf.getvalue()
        buf = io.StringIO()
        click_exceptions.UsageError("bad usage").show(file=buf)
        assert "Ошибка: bad usage" in buf.getvalue()
    finally:
        for name, value in saved_constants.items():
            setattr(rich_utils, name, value)
        for obj, name, value in saved_methods:
            setattr(obj, name, value)
        l10n_typer._PATCHED = False


def test_help_stays_english_by_default() -> None:
    out = _run_cli(["deploy", "--help"])
    assert "Usage:" in out
    assert "Options" in out
    assert "Ansible control node:" in out


def test_completion_options_are_gone() -> None:
    out = _run_cli(["--help"])
    assert "--install-completion" not in out
    assert "--show-completion" not in out


def test_parse_errors_are_russian_with_ru_flag() -> None:
    out = _run_cli(["deploy", "--ru", "--nope"])
    assert "Нет такой опции: --nope" in out
    assert "Ошибка" in out
    assert "Попробуйте" in out


def test_parse_errors_stay_english_by_default() -> None:
    out = _run_cli(["deploy", "--nope"])
    assert "No such option: --nope" in out
    assert "Error" in out


def test_missing_option_value_error_is_russian() -> None:
    out = _run_cli(["deploy", "--ru", "--host"])
    assert "Опция '--host' требует аргумент." in out


def test_invalid_int_error_is_russian() -> None:
    out = _run_cli(["deploy", "--ru", "--xray-port", "abc"])
    assert "не является допустимым целым числом" in out


def test_extra_argument_error_is_russian() -> None:
    out = _run_cli(["deploy", "--ru", "surplus"])
    assert "Получены неожиданные лишние аргументы (surplus)" in out


def test_help_bool_defaults_are_worded_en() -> None:
    out = _run_cli(["deploy", "--help"])
    assert "default: true" not in out and "default: false" not in out
    assert "[default: True]" not in out and "[default: False]" not in out
    assert "default: enabled" in out or "default: disabled" in out
    assert "(default: keep existing state)" in out


def test_help_bool_defaults_are_worded_ru() -> None:
    out = _run_cli(["deploy", "--ru", "--help"])
    assert "по умолчанию: true" not in out and "по умолчанию: false" not in out
    assert "[по умолчанию: True]" not in out and "[по умолчанию: False]" not in out
    assert "по умолчанию: включено" in out or "по умолчанию: выключено" in out
    assert "по умолчанию: сохранить текущее состояние" in out
