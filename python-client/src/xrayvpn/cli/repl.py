"""Interactive REPL session: type once, run deploy several times.

Entered by running xrayvpn with no arguments on a TTY (or `xrayvpn repl`,
or the selftest env for CI smoke feeds). Built-in commands are handled
here; anything else is dispatched through the real Typer app in-process
(`app(args=...)`, not CliRunner — click's input isolation would kill the
InquirerPy prompts of a deploy). The built-in typer `--help` language is
fixed at process start; every runtime string and click error follows
`lang ru|en` in both directions.
"""

from __future__ import annotations

import ctypes
import os
import shlex
import sys
from collections.abc import Callable, Mapping, Sequence

import typer

from xrayvpn import __version__, i18n
from xrayvpn.cli import l10n_typer, prompts, theme
from xrayvpn.core.update_check import LATEST_RELEASE_PAGE, PROFILE_URL, REPO_URL

REPO_DOCS_URL = REPO_URL + "/tree/main/docs"

REPL_SELFTEST_ENV = "XRAYVPN_REPL_SELFTEST"
PROMPT = "> "
_PREFIX_ALIASES = {"xrayvpn", "xrayvpn.exe"}
_LANG_ALIASES = {
    "ru": "ru",
    "рус": "ru",
    "русский": "ru",
    "en": "en",
    "англ": "en",
    "english": "en",
}
_EXIT_WORDS = {"exit", "quit", "q"}


def session_requested() -> bool:
    """No-args start opens the session on a TTY; the selftest env removes the gate."""
    return prompts.is_interactive() or _selftest_enabled()


def _selftest_enabled() -> bool:
    return os.environ.get(REPL_SELFTEST_ENV) == "1"


def locale_suggests_ru(
    *,
    env: Mapping[str, str] | None = None,
    platform: str | None = None,
    win_ui_lang: Callable[[], int] | None = None,
) -> bool:
    """POSIX: first set of LC_ALL/LC_MESSAGES/LANG, `ru*` wins; win32: the primary
    UI language is 0x19. Everything else (and any error) is English."""
    environment = os.environ if env is None else env
    sys_platform = sys.platform if platform is None else platform
    if sys_platform == "win32":
        getter = win_ui_lang or _win_default_ui_language
        try:
            return (getter() & 0x3FF) == 0x19
        except Exception:  # noqa: BLE001 - detection must never break the start
            return False
    for key in ("LC_ALL", "LC_MESSAGES", "LANG"):
        value = (environment.get(key) or "").strip().lower()
        if value:
            return value.startswith("ru")
    return False


def _win_default_ui_language() -> int:
    return int(ctypes.windll.kernel32.GetUserDefaultUILanguage())  # type: ignore[attr-defined]


def set_session_lang(lang: str) -> None:
    """Runtime language switch: i18n strings + typer/Click patches both ways."""
    i18n.set_lang(lang)
    if lang == "ru":
        l10n_typer.apply_ru()
    else:
        l10n_typer.revert_ru()


def normalize_lang(value: str) -> str | None:
    return _LANG_ALIASES.get(value.strip().lower())


def tokenize(line: str) -> list[str]:
    """posix=False keeps Windows backslashes intact; quotes are unwrapped after."""
    return [_clean_token(token) for token in shlex.split(line, posix=False)]


def _clean_token(token: str) -> str:
    unwrapped = _unwrap(token)
    if unwrapped is not None:
        return unwrapped
    if "=" in token:
        name, _, value = token.partition("=")
        unwrapped = _unwrap(value)
        if unwrapped is not None:
            return f"{name}={unwrapped}"
    return token


def _unwrap(token: str) -> str | None:
    if len(token) >= 2 and token[0] == token[-1] and token[0] in ("\"", "'"):
        return token[1:-1]
    return None


def _box(
    lines: list[str],
    color: Callable[[str], str] | None = None,
    max_width: int | None = None,
    pad_width: int | None = None,
) -> str:
    paint = color if color is not None else (lambda text: text)
    limit = max_width - 4 if max_width is not None else None
    content: list[str] = []
    for line in lines:
        content.extend(theme.wrap_visible(line, limit) if limit else [line])
    width = max(theme.visible_len(line) for line in content) + 2
    if max_width is not None:
        width = min(width, max_width - 2)
    if pad_width is not None:
        width = min(pad_width, max_width - 2 if max_width is not None else pad_width)
    top = paint("+" + "-" * width + "+")
    body = "\n".join(
        paint("|")
        + " "
        + line
        + " " * max(0, width - 2 - theme.visible_len(line))
        + " "
        + paint("|")
        for line in content
    )
    return f"{top}\n{body}\n{top}"


def _cmd_line(command: str, description: str) -> str:
    return f"  {theme.ok(command)} — {description}"


def _join_boxes(
    left: str, right: str, gap: int = 2, max_width: int | None = None
) -> list[str]:
    la = left.splitlines()
    ra = right.splitlines()
    lw = max(theme.visible_len(line) for line in la)
    rw = max(theme.visible_len(line) for line in ra)
    if max_width is not None and lw + gap + rw > max_width:
        return la + [""] + ra
    rows = []
    for index in range(max(len(la), len(ra))):
        l = la[index] if index < len(la) else ""
        r = ra[index] if index < len(ra) else ""
        rows.append(l + " " * (lw - theme.visible_len(l) + gap) + r)
    return rows


def lang_notice() -> str:
    """One-line confirmation in the NEW language; the welcome box prints once."""
    return i18n.t("REPL_LANG_NOTICE")


_BANNER_DESIGN_WIDTH = 100
_BANNER_NARROW_WIDTH = 72


def _credits_lines() -> list[str]:
    return [
        (
            f"{i18n.t('REPL_WELCOME_AUTHOR')} "
            f"{theme.accent(theme.link(i18n.t('REPL_WELCOME_AUTHOR_NAME'), PROFILE_URL))}"
        ),
        (
            f"{i18n.t('REPL_WELCOME_REPO')} "
            f"{theme.link(i18n.t('REPL_WELCOME_REPO_NAME'), REPO_URL)}"
        ),
        (
            f"{i18n.t('REPL_WELCOME_RELEASES')} "
            f"{theme.link(i18n.t('REPL_WELCOME_RELEASES_NAME'), LATEST_RELEASE_PAGE)}"
        ),
    ]


def _command_lines() -> list[tuple[str, str]]:
    return [
        ("help", i18n.t("REPL_WELCOME_CMD_HELP")),
        ("version", i18n.t("REPL_WELCOME_CMD_VERSION")),
        ("banner", i18n.t("REPL_WELCOME_CMD_BANNER")),
        ("service", i18n.t("REPL_WELCOME_CMD_SERVICE")),
        ("exit|quit|q", i18n.t("REPL_WELCOME_CMD_EXIT")),
    ]


def _retry_line() -> str:
    return (
        f"{theme.warn(i18n.t('REPL_WELCOME_RETRY'))} "
        f"{theme.link(i18n.t('REPL_WELCOME_RETRY_DOCS'), REPO_DOCS_URL)}"
    )


def _wrap_lines(lines: list[str], width: int) -> list[str]:
    wrapped: list[str] = []
    for line in lines:
        wrapped.extend(theme.wrap_visible(line, width))
    return wrapped


def _narrow_screen(version: str, width: int) -> str:
    """No boxes when the terminal is too narrow for them."""
    lines = [
        theme.accent(i18n.t("REPL_WELCOME_TITLE")),
        f"v{version}",
        i18n.t("REPL_WELCOME_PURPOSE"),
        "",
        i18n.t("REPL_WELCOME_MAIN"),
        f"  {theme.ok_bold('deploy')}",
        _cmd_line("deploy --help", i18n.t("REPL_WELCOME_CMD_FLAGS")),
        "",
        i18n.t("REPL_WELCOME_OTHER"),
    ]
    lines += [_cmd_line(command, description) for command, description in _command_lines()]
    lines += [
        "",
        i18n.t("REPL_WELCOME_SWITCH"),
        "",
        _retry_line(),
        "",
    ]
    lines += _credits_lines()
    return "\n".join(_wrap_lines(lines, width))


def welcome_screen(version: str = __version__) -> str:
    """Screen 0: purpose, Main|Other side by side, language switch, credits."""
    terminal = theme.terminal_width()
    if terminal < _BANNER_NARROW_WIDTH:
        return _narrow_screen(version, terminal)
    outer = min(_BANNER_DESIGN_WIDTH, terminal - 1)
    inner = outer - 4
    main_block = _box(
        [
            i18n.t("REPL_WELCOME_MAIN"),
            f"  {theme.ok_bold('deploy')}",
            _cmd_line("deploy --help", i18n.t("REPL_WELCOME_CMD_FLAGS")),
        ],
        max_width=inner,
    )
    other_block = _box(
        [
            i18n.t("REPL_WELCOME_OTHER"),
            "",
            *[
                _cmd_line(command, description)
                for command, description in _command_lines()
            ],
        ],
        max_width=inner,
    )
    language = _box(
        [i18n.t("REPL_WELCOME_SWITCH")], color=theme.warn, max_width=inner
    )
    credits = _box(_credits_lines(), color=theme.muted, max_width=inner)
    lines = [
        theme.accent(i18n.t("REPL_WELCOME_TITLE")),
        f"v{version}",
        i18n.t("REPL_WELCOME_PURPOSE"),
        "",
    ]
    lines += _join_boxes(main_block, other_block, max_width=inner)
    lines += [""]
    lines += language.splitlines()
    lines += [""]
    lines += [_retry_line()]
    lines += [""]
    lines += credits.splitlines()
    return _box(lines, color=theme.accent, max_width=outer, pad_width=outer - 2)


def short_hint() -> str:
    return i18n.t("REPL_SHORT_HINT")


def help_text() -> str:
    """Dynamic command reference (t() at call time, unlike baked typer help)."""
    return "\n".join(
        [
            i18n.t("REPL_HELP_HEADER"),
            i18n.t("REPL_HELP_DEPLOY"),
            i18n.t("REPL_HELP_SERVICE"),
            i18n.t("REPL_HELP_LANG"),
            i18n.t("REPL_HELP_HELP"),
            i18n.t("REPL_HELP_BANNER"),
            i18n.t("REPL_HELP_VERSION"),
            i18n.t("REPL_HELP_EXIT"),
            "",
            i18n.t("REPL_HELP_NOTE"),
        ]
    )


def start(
    dispatch: Callable[[list[str]], int],
    *,
    version: str = __version__,
    update_hint: Callable[[], str | None] | None = None,
) -> int:
    """Session loop; the process exit code is the last dispatched command's rc.

    A KeyboardInterrupt that escapes the inner handlers (a second Ctrl+C during
    output, one inside paramiko on Windows) still exits cleanly with rc 130.
    """
    try:
        return _session(dispatch, version=version, update_hint=update_hint)
    except KeyboardInterrupt:
        print()
        print(i18n.t("REPL_INTERRUPTED"))
        return 130


def _session(
    dispatch: Callable[[list[str]], int],
    *,
    version: str,
    update_hint: Callable[[], str | None] | None,
) -> int:
    explicit_lang = (os.environ.get(i18n.LANG_ENV) or "").strip()
    if not explicit_lang and not i18n.is_ru() and locale_suggests_ru():
        set_session_lang("ru")
    typer.echo(welcome_screen(version))
    if update_hint is not None:
        hint = update_hint()
        if hint:
            for hint_line in theme.wrap_visible(hint, theme.terminal_width()):
                typer.echo(theme.muted(hint_line))
    last_rc = 0
    while True:
        try:
            line = input(PROMPT)
        except EOFError:
            print()
            return last_rc
        except KeyboardInterrupt:
            print()
            typer.echo(theme.muted(i18n.t("REPL_KI_TIP")))
            continue
        tokens = tokenize(line)
        if tokens and tokens[0].lower() in _PREFIX_ALIASES:
            tokens = tokens[1:]
        if not tokens:
            typer.echo(theme.muted(short_hint()))
            continue
        if len(tokens) == 1:
            lang = normalize_lang(tokens[0])
            if lang is not None:
                set_session_lang(lang)
                print(lang_notice())
                typer.echo(welcome_screen(version))
                continue
        command = tokens[0].lower()
        if command in _EXIT_WORDS:
            return last_rc
        options = {token.lower() for token in tokens}
        if all(token.startswith("-") for token in options):
            if "--ru" in options:
                set_session_lang("ru")
                print(lang_notice())
                typer.echo(welcome_screen(version))
            if "--version" in options:
                print(f"xrayvpn {version}")
            unknown = options - {"--ru", "--version"}
            if unknown:
                joined = ", ".join(sorted(unknown))
                print(i18n.t("REPL_UNKNOWN_OPT", opts=joined))
            continue
        try:
            if command == "help":
                print(help_text())
            elif command == "version":
                print(f"xrayvpn {version}")
            elif command == "lang":
                _switch_lang(tokens[1:], version)
            elif command == "banner":
                typer.echo(welcome_screen(version))
            elif command == "repl":
                print(i18n.t("REPL_ALREADY"))
            else:
                last_rc = dispatch(tokens)
                if last_rc == 130:
                    print(i18n.t("REPL_ABORTED"))
                    last_rc = 0
        except KeyboardInterrupt:
            print(i18n.t("REPL_INTERRUPTED"))


def _switch_lang(args: Sequence[str], version: str) -> None:
    lang = normalize_lang(args[0]) if args else None
    if lang is None:
        print(i18n.t("REPL_LANG_USAGE"))
        return
    set_session_lang(lang)
    print(lang_notice())
    typer.echo(welcome_screen(version))
