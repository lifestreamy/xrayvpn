"""Theme: color-mode gate (COLORTERM/NO_COLOR/tty), 16-color fallback, OSC-8 links, literal guard."""

from __future__ import annotations

import re
from pathlib import Path

import typer
from typer.testing import CliRunner

import xrayvpn
from xrayvpn.cli import theme

PACKAGE = Path(xrayvpn.__file__).resolve().parent
HELPERS = (theme.ok, theme.ok_bold, theme.err, theme.warn, theme.muted, theme.accent)


def _clean_color_env(monkeypatch) -> None:
    for key in (
        "NO_COLOR",
        "COLORTERM",
        "XRAYVPN_FORCE_COLOR",
        "WT_SESSION",
        "TERM_PROGRAM",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(theme.sys, "platform", "linux")
    monkeypatch.setattr(theme, "_console_vt_enabled", lambda: False)


def _clean_link_env(monkeypatch) -> None:
    for key in ("XRAYVPN_HYPERLINK", "WT_SESSION", "TERM_PROGRAM"):
        monkeypatch.delenv(key, raising=False)


def test_tokens_are_hex_palette() -> None:
    assert theme.TOKENS == {
        "ok": "#1DB954",
        "error": "#F85149",
        "warn": "#D29922",
        "muted": "#C4CDD8",
        "accent": "#00D587",
    }


def test_tokens_match_assets_color_tokens_json() -> None:
    import json

    tokens_file = PACKAGE.parents[2] / "assets" / "color-tokens.json"
    mirror = json.loads(tokens_file.read_text(encoding="utf-8"))
    assert mirror == theme.TOKENS


def test_color_mode_table(monkeypatch) -> None:
    _clean_color_env(monkeypatch)
    monkeypatch.setattr(theme, "_is_tty", lambda: False)
    assert theme.color_mode() == "plain"
    monkeypatch.setattr(theme, "_is_tty", lambda: True)
    assert theme.color_mode() == "16"
    monkeypatch.setenv("COLORTERM", "truecolor")
    assert theme.color_mode() == "truecolor"
    monkeypatch.setenv("COLORTERM", "24bit")
    assert theme.color_mode() == "truecolor"
    monkeypatch.delenv("COLORTERM")
    monkeypatch.setenv("WT_SESSION", "any")
    assert theme.color_mode() == "truecolor"
    monkeypatch.delenv("WT_SESSION")
    monkeypatch.setenv("TERM_PROGRAM", "vscode")
    assert theme.color_mode() == "truecolor"
    monkeypatch.delenv("TERM_PROGRAM")
    assert theme.color_mode() == "16"
    monkeypatch.setattr(theme, "_console_vt_enabled", lambda: True)
    assert theme.color_mode() == "truecolor"
    monkeypatch.setattr(theme, "_console_vt_enabled", lambda: False)
    monkeypatch.setenv("XRAYVPN_FORCE_COLOR", "1")
    assert theme.color_mode() == "truecolor"
    monkeypatch.delenv("XRAYVPN_FORCE_COLOR")
    monkeypatch.setenv("NO_COLOR", "1")
    assert theme.color_mode() == "plain"


def test_windows_vt_matrix(monkeypatch) -> None:
    _clean_color_env(monkeypatch)
    monkeypatch.setattr(theme.sys, "platform", "win32")
    monkeypatch.setattr(theme, "_is_tty", lambda: True)
    monkeypatch.setattr(theme, "_console_vt_ready", lambda: False)
    assert theme.color_mode() == "plain"
    monkeypatch.setattr(theme, "_console_vt_ready", lambda: True)
    monkeypatch.setattr(theme, "_windows_truecolor_capable", lambda: False)
    assert theme.color_mode() == "16"
    monkeypatch.setattr(theme, "_windows_truecolor_capable", lambda: True)
    assert theme.color_mode() == "truecolor"
    monkeypatch.setattr(theme, "_console_vt_ready", lambda: False)
    monkeypatch.setenv("XRAYVPN_FORCE_COLOR", "1")
    assert theme.color_mode() == "truecolor"
    monkeypatch.delenv("XRAYVPN_FORCE_COLOR")
    monkeypatch.setenv("COLORTERM", "truecolor")
    assert theme.color_mode() == "truecolor"


def test_windows_vt_self_enable_wiring(monkeypatch) -> None:
    _clean_color_env(monkeypatch)
    monkeypatch.setattr(theme.sys, "platform", "win32")
    monkeypatch.setattr(theme, "_is_tty", lambda: True)
    monkeypatch.setattr(theme, "_VT_READY_CACHE", None)
    monkeypatch.setattr(theme, "_enable_console_vt", lambda: True)
    monkeypatch.setattr(theme, "_windows_truecolor_capable", lambda: True)
    assert theme.color_mode() == "truecolor"
    monkeypatch.setattr(theme, "_VT_READY_CACHE", None)
    monkeypatch.setattr(theme, "_enable_console_vt", lambda: False)
    assert theme.color_mode() == "plain"


def test_truecolor_and_16color_codes(monkeypatch) -> None:
    _clean_color_env(monkeypatch)
    monkeypatch.setattr(theme, "_is_tty", lambda: True)
    monkeypatch.setenv("COLORTERM", "truecolor")
    out = theme.ok("x")
    assert out == "\x1b[38;2;29;185;84mx\x1b[0m"
    assert theme.plain(out) == "x"
    assert theme.visible_len(out) == 1
    monkeypatch.delenv("COLORTERM")
    assert theme.ok("x") == "\x1b[32mx\x1b[0m"
    assert theme.accent("x") == "\x1b[92mx\x1b[0m"
    assert theme.ok_bold("x") == "\x1b[1;32mx\x1b[0m"


def test_plain_helpers_without_tty(monkeypatch) -> None:
    _clean_color_env(monkeypatch)
    monkeypatch.setattr(theme, "_is_tty", lambda: False)
    for helper in HELPERS:
        assert helper("x") == "x"


def test_no_color_disables_codes(monkeypatch) -> None:
    _clean_color_env(monkeypatch)
    monkeypatch.setattr(theme, "_is_tty", lambda: True)
    monkeypatch.setenv("COLORTERM", "truecolor")
    monkeypatch.setenv("NO_COLOR", "1")
    for helper in HELPERS:
        assert helper("x") == "x"


def test_debug_line_reports_mode(monkeypatch) -> None:
    _clean_color_env(monkeypatch)
    monkeypatch.setattr(theme, "_is_tty", lambda: True)
    monkeypatch.setattr(theme, "_console_vt_ready", lambda: False)
    line = theme.debug_line()
    assert "mode=16" in line and "COLORTERM=None" in line
    assert "vt=False" in line and "win=-" in line


def test_visible_len_ignores_ansi(monkeypatch) -> None:
    _clean_color_env(monkeypatch)
    monkeypatch.setattr(theme, "_is_tty", lambda: True)
    monkeypatch.setenv("COLORTERM", "truecolor")
    styled = theme.accent("abcd")
    assert styled != "abcd"
    assert theme.visible_len(styled) == 4
    assert theme.plain(styled) == "abcd"


def test_plain_strips_osc8() -> None:
    linked = theme.plain("\x1b]8;;https://e\x1b\\text\x1b]8;;\x1b\\")
    assert linked == "text"
    assert theme.visible_len("\x1b]8;;https://e\x1b\\text\x1b]8;;\x1b\\") == 4


def test_link_plain_fallback_without_tty(monkeypatch) -> None:
    _clean_link_env(monkeypatch)
    monkeypatch.setattr(theme, "_is_tty", lambda: False)
    assert theme.link("name", "https://example") == "name (https://example)"


def test_link_plain_fallback_without_terminal_support(monkeypatch) -> None:
    _clean_link_env(monkeypatch)
    monkeypatch.setattr(theme, "_is_tty", lambda: True)
    assert theme.link("name", "https://example") == "name (https://example)"


def test_link_emitted_on_windows_terminal(monkeypatch) -> None:
    _clean_link_env(monkeypatch)
    monkeypatch.setenv("WT_SESSION", "any")
    monkeypatch.setattr(theme, "_is_tty", lambda: True)
    assert theme.link("abcd", "u") == "\x1b]8;;u\x1b\\abcd\x1b]8;;\x1b\\"
    assert theme.visible_len(theme.link("abcd", "u")) == 4


def test_link_emitted_on_vscode_only_exact(monkeypatch) -> None:
    _clean_link_env(monkeypatch)
    monkeypatch.setattr(theme, "_is_tty", lambda: True)
    monkeypatch.setenv("TERM_PROGRAM", "vscode")
    assert "\x1b]8;;" in theme.link("t", "u")
    monkeypatch.setenv("TERM_PROGRAM", "vscode-ish")
    assert theme.link("t", "u") == "t (u)"


def test_link_kill_switch_and_force(monkeypatch) -> None:
    _clean_link_env(monkeypatch)
    monkeypatch.setattr(theme, "_is_tty", lambda: False)
    monkeypatch.setenv("XRAYVPN_HYPERLINK", "1")
    assert "\x1b]8;;" in theme.link("t", "u")
    monkeypatch.setenv("XRAYVPN_HYPERLINK", "0")
    monkeypatch.setenv("WT_SESSION", "any")
    monkeypatch.setattr(theme, "_is_tty", lambda: True)
    assert theme.link("t", "u") == "t (u)"


def test_output_plain_on_non_tty_end_to_end(monkeypatch) -> None:
    _clean_color_env(monkeypatch)
    probe_app = typer.Typer()

    @probe_app.command()
    def probe() -> None:
        typer.echo(theme.ok("green text"))
        typer.echo(theme.err("red text"), err=True)

    result = CliRunner().invoke(probe_app, [])
    assert "green text" in result.output
    assert "\x1b[" not in result.output


def test_color_literals_live_only_in_theme() -> None:
    pattern = re.compile(
        r"typer\.style|click\.style|\\x1b\[|\bfg="
        r"|#[0-9a-fA-F]{6}"
        r"|\[/?[a-z_]*(blue|cyan|magenta|yellow|red|green|white|bright)[a-z_ ]*\]"
    )
    offenders = []
    for path in sorted(PACKAGE.rglob("*.py")):
        if path.name == "theme.py" or path.parent.name in ("payload", "build"):
            continue
        if pattern.search(path.read_text(encoding="utf-8")):
            offenders.append(path.name)
    assert not offenders
