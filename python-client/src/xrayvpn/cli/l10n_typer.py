"""Russian translations and palette theming for Typer/Click built-ins (typer 0.27.x).

Typer builds `--help` at import time and hard-codes its built-ins in
English. `apply_ru()` patches the finite set of user-visible strings;
`revert_ru()` restores the saved originals (idempotent pair, runtime-
switchable for the REPL session — already-built help options keep the
language chosen at process start). `apply_palette()` re-styles the rich
help panels onto the project color tokens (cli/theme.py), normalizes the EN
help-suggestion string, and is applied unconditionally at startup before
`apply_ru()`; it is never reverted. The dependency is pinned
to typer <0.28: the patches touch private internals, and the pin plus
tests/test_i18n.py and tests/test_cli_palette.py bound the drift.

Reachability on the current CLI surface — live and test-guarded: panel
titles, RICH_HELP, DEFAULT_STRING, the Usage prefix, the help-option text,
NoSuchOption/BadParameter/UsageError messages, translate_message maps, and
the plain-text show() fallbacks (rich normally routes errors around them;
unit-tested by direct call). Defensive forward-compat, unreachable today:
ARGUMENTS_PANEL_TITLE and REQUIRED_LONG_STRING (no positional/required
params), MissingParameter and FileError messages (same reason), and
_TYPE_NAMES entries beyond int/integer/UUID.
"""

from __future__ import annotations

import re

from xrayvpn.cli import theme

_BACKUP: list[tuple[object, str, object]] = []


def _rich_style(token: str, *, bold: bool = False) -> str:
    hex_value = theme.TOKENS[token]
    return f"bold {hex_value}" if bold else hex_value


PALETTE_OVERRIDES: dict[str, str] = {
    "STYLE_USAGE": _rich_style("accent", bold=True),
    "STYLE_USAGE_COMMAND": _rich_style("accent", bold=True),
    "STYLE_OPTION": _rich_style("accent", bold=True),
    "STYLE_SWITCH": _rich_style("accent", bold=True),
    "STYLE_COMMANDS_TABLE_FIRST_COLUMN": _rich_style("accent", bold=True),
    "STYLE_NEGATIVE_OPTION": _rich_style("ok", bold=True),
    "STYLE_NEGATIVE_SWITCH": _rich_style("ok", bold=True),
    "STYLE_TYPES": _rich_style("muted"),
    "STYLE_OPTION_ENVVAR": _rich_style("muted"),
    "STYLE_OPTION_DEFAULT": _rich_style("muted"),
    "STYLE_OPTIONS_PANEL_BORDER": _rich_style("muted"),
    "STYLE_COMMANDS_PANEL_BORDER": _rich_style("muted"),
    "STYLE_TYPES_SEPARATOR": _rich_style("muted"),
    "STYLE_REQUIRED_SHORT": _rich_style("error"),
    "STYLE_REQUIRED_LONG": _rich_style("error"),
    "STYLE_ERRORS_PANEL_BORDER": _rich_style("error"),
    "STYLE_ERRORS_SUGGESTION": _rich_style("ok", bold=True),
    "STYLE_ABORTED": _rich_style("error"),
    "STYLE_DEPRECATED": _rich_style("error"),
}

_RICH_HELP_EN = "Try '{command_path} {help_option}' for help."
_RICH_HELP_RU = "Попробуйте '{command_path} {help_option}' для справки."


def apply_palette() -> None:
    from typer import rich_utils

    for name, value in PALETTE_OVERRIDES.items():
        setattr(rich_utils, name, value)
    rich_utils.RICH_HELP = _RICH_HELP_EN


def disable_click_colorama() -> None:
    # click.echo wraps console streams in colorama, which converts ANSI to
    # legacy Win32 16-color and mangles 38;2/OSC-8 (colorama#217); patched in
    # both namespaces because echo imported the name into typer._click.utils.
    from typer._click import _compat
    from typer._click import utils as click_utils

    def _passthrough(stream: object, color: bool | None = None) -> object:
        return stream

    _compat.auto_wrap_for_ansi = _passthrough
    click_utils.auto_wrap_for_ansi = _passthrough

_EXTRA_ARGS = re.compile(r"^Got unexpected extra argument\(s\) \((?P<args>.*)\)$")
_REQUIRES_ARG = re.compile(
    r"^Option (?P<opt>'[^']+') requires (?P<what>an argument\.|\d+ arguments\.)$"
)
_NO_VALUE = re.compile(r"^Option (?P<opt>'[^']+') does not take a value\.$")
_NOT_VALID_BOOL = re.compile(
    r"^(?P<value>.+) is not a valid boolean\. Recognized values: (?P<states>.*)$"
)
_NOT_VALID = re.compile(r"^(?P<value>.+) is not a valid (?P<type>[A-Za-z ]+)\.$")

_TYPE_NAMES = {
    "integer": "целым числом",
    "int": "целым числом",
    "float": "числом",
    "number": "числом",
    "boolean": "логическим значением",
    "bool": "логическим значением",
    "uuid": "UUID",
    "path": "путём",
    "file": "файлом",
    "directory": "каталогом",
    "text": "текстом",
    "string": "строкой",
}


def translate_message(message: str) -> str:
    """Map the hard-coded English parser/type messages onto Russian."""
    match = _EXTRA_ARGS.match(message)
    if match:
        return f"Получены неожиданные лишние аргументы ({match['args']})"
    match = _REQUIRES_ARG.match(message)
    if match:
        what = "аргумент" if match["what"] == "an argument." else "аргументов: " + match["what"].split()[0]
        return f"Опция {match['opt']} требует {what}."
    match = _NO_VALUE.match(message)
    if match:
        return f"Опция {match['opt']} не принимает значение."
    match = _NOT_VALID_BOOL.match(message)
    if match:
        return (
            f"{match['value']} не является допустимым логическим значением. "
            f"Допустимые значения: {match['states']}"
        )
    match = _NOT_VALID.match(message)
    if match:
        kind = _TYPE_NAMES.get(match["type"].lower())
        if kind:
            return f"{match['value']} не является допустимым {kind}."
        return f"{match['value']} — недопустимое значение ({match['type']})."
    return message


def _set(target: object, name: str, value: object) -> None:
    _BACKUP.append((target, name, getattr(target, name)))
    setattr(target, name, value)


def apply_ru() -> None:
    if _BACKUP:
        return

    from typer import rich_utils
    from typer._click import decorators as click_decorators
    from typer._click import exceptions as click_exceptions
    from typer._click import formatting as click_formatting

    _set(rich_utils, "ARGUMENTS_PANEL_TITLE", "Аргументы")
    _set(rich_utils, "OPTIONS_PANEL_TITLE", "Опции")
    _set(rich_utils, "COMMANDS_PANEL_TITLE", "Команды")
    _set(rich_utils, "ERRORS_PANEL_TITLE", "Ошибка")
    _set(rich_utils, "ABORTED_TEXT", "Прервано.")
    _set(rich_utils, "DEFAULT_STRING", "[по умолчанию: {}]")
    _set(rich_utils, "REQUIRED_LONG_STRING", "[обязательно]")
    _set(rich_utils, "RICH_HELP", _RICH_HELP_RU)

    original_write_usage = click_formatting.HelpFormatter.write_usage

    def write_usage(self, prog, args="", prefix=None):  # type: ignore[no-untyped-def]
        if prefix is None:
            prefix = "Использование: "
        original_write_usage(self, prog, args, prefix)

    _set(click_formatting.HelpFormatter, "write_usage", write_usage)

    original_help_option = click_decorators.help_option

    def help_option(param_decls):  # type: ignore[no-untyped-def]
        decorate = original_help_option(param_decls)

        def apply(command):  # type: ignore[no-untyped-def]
            decorate(command)
            command.params[-1].help = "Показать это сообщение и выйти."
            return command

        return apply

    _set(click_decorators, "help_option", help_option)

    def click_exception_show(self, file=None):  # type: ignore[no-untyped-def]
        if file is None:
            file = click_exceptions.get_text_stderr()
        click_exceptions.echo(
            f"Ошибка: {self.format_message()}", file=file, color=self.show_color
        )

    _set(click_exceptions.ClickException, "show", click_exception_show)

    def usage_error_show(self, file=None):  # type: ignore[no-untyped-def]
        if file is None:
            file = click_exceptions.get_text_stderr()
        color = None
        hint = ""
        if self.ctx is not None and self.ctx.command.get_help_option(self.ctx) is not None:
            command = self.ctx.command_path
            option = self.ctx.help_option_names[0]
            hint = f"Попробуйте '{command} {option}' для справки.\n"
        if self.ctx is not None:
            color = self.ctx.color
            click_exceptions.echo(
                f"{self.ctx.get_usage()}\n{hint}", file=file, color=color
            )
        click_exceptions.echo(
            f"Ошибка: {self.format_message()}", file=file, color=color
        )

    _set(click_exceptions.UsageError, "show", usage_error_show)

    def usage_error_format_message(self):  # type: ignore[no-untyped-def]
        return translate_message(self.message)

    _set(click_exceptions.UsageError, "format_message", usage_error_format_message)

    def bad_parameter_format_message(self):  # type: ignore[no-untyped-def]
        if self.param_hint is not None:
            param_hint = self.param_hint
        elif self.param is not None:
            param_hint = self.param.get_error_hint(self.ctx)
        else:
            return f"Неверное значение: {translate_message(self.message)}"
        hint = click_exceptions._join_param_hints(param_hint)
        return f"Неверное значение для {hint}: {translate_message(self.message)}"

    _set(click_exceptions.BadParameter, "format_message", bad_parameter_format_message)

    def missing_parameter_format_message(self):  # type: ignore[no-untyped-def]
        if self.param_hint is not None:
            param_hint = self.param_hint
        elif self.param is not None:
            param_hint = self.param.get_error_hint(self.ctx)
        else:
            param_hint = None
        param_hint = click_exceptions._join_param_hints(param_hint)
        param_hint = f" {param_hint}" if param_hint else ""

        param_type = self.param_type
        if param_type is None and self.param is not None:
            param_type = self.param.param_type_name

        msg = self.message
        if self.param is not None:
            msg_extra = self.param.type.get_missing_message(param=self.param, ctx=self.ctx)
            if msg_extra:
                msg = f"{msg}. {msg_extra}" if msg else msg_extra
        msg = f" {msg}" if msg else ""

        missing = {
            "argument": "Отсутствует аргумент",
            "option": "Отсутствует опция",
            "parameter": "Отсутствует параметр",
        }.get(param_type, f"Отсутствует {param_type}")
        return f"{missing}{param_hint}.{msg}"

    _set(
        click_exceptions.MissingParameter, "format_message", missing_parameter_format_message
    )

    def no_such_option_format_message(self):  # type: ignore[no-untyped-def]
        base = f"Нет такой опции: {self.option_name}"
        if not self.possibilities:
            return base
        possibility_str = ", ".join(sorted(self.possibilities))
        return f"{base} (Возможные варианты: {possibility_str})"

    _set(click_exceptions.NoSuchOption, "format_message", no_such_option_format_message)

    def file_error_format_message(self):  # type: ignore[no-untyped-def]
        return f"Не удалось открыть файл {self.ui_filename!r}: {self.message}"

    _set(click_exceptions.FileError, "format_message", file_error_format_message)


def revert_ru() -> None:
    """Undo every patch made by the last apply_ru(); no-op when unpatched."""
    while _BACKUP:
        target, name, original = _BACKUP.pop()
        setattr(target, name, original)
