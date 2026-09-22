"""apply_palette(): rich help panels re-style onto theme.TOKENS (typer-pin guard)."""

from __future__ import annotations

import json
import re
from pathlib import Path

from typer import rich_utils

from xrayvpn.cli import l10n_typer, theme

_ROOT = Path(__file__).resolve().parents[2]
_COLOR_WORD = re.compile(r"\b(blue|cyan|magenta|yellow|red|green|white|bright)\b")
_HEX = re.compile(r"#[0-9a-fA-F]{6}")
_RICH_COLOR_TAG = re.compile(
    r"\[/?[a-z_]*(blue|cyan|magenta|yellow|red|green|white|bright)[a-z_ ]*\]"
)


def test_apply_palette_sets_all_overrides() -> None:
    l10n_typer.apply_palette()
    for name, value in l10n_typer.PALETTE_OVERRIDES.items():
        assert getattr(rich_utils, name) == value


def test_overrides_derive_from_theme_tokens_single_source() -> None:
    assert l10n_typer.PALETTE_OVERRIDES["STYLE_OPTION"] == (
        f"bold {theme.TOKENS['accent']}"
    )
    assert l10n_typer.PALETTE_OVERRIDES["STYLE_NEGATIVE_SWITCH"] == (
        f"bold {theme.TOKENS['ok']}"
    )
    assert l10n_typer.PALETTE_OVERRIDES["STYLE_TYPES"] == theme.TOKENS["muted"]
    assert l10n_typer.PALETTE_OVERRIDES["STYLE_ERRORS_PANEL_BORDER"] == (
        theme.TOKENS["error"]
    )


def test_palette_is_idempotent_and_survives_ru_revert() -> None:
    l10n_typer.revert_ru()
    l10n_typer.apply_palette()
    snapshot = {n: getattr(rich_utils, n) for n in l10n_typer.PALETTE_OVERRIDES}
    snapshot["RICH_HELP"] = rich_utils.RICH_HELP
    l10n_typer.apply_ru()
    l10n_typer.revert_ru()
    l10n_typer.apply_palette()
    current = {n: getattr(rich_utils, n) for n in snapshot}
    assert current == snapshot


def test_errors_suggestion_derives_from_ok() -> None:
    assert l10n_typer.PALETTE_OVERRIDES["STYLE_ERRORS_SUGGESTION"] == (
        f"bold {theme.TOKENS['ok']}"
    )


def test_rich_help_has_no_color_markup() -> None:
    l10n_typer.revert_ru()
    l10n_typer.apply_palette()
    en_help = rich_utils.RICH_HELP
    assert _RICH_COLOR_TAG.search(en_help) is None
    assert "{command_path}" in en_help and "{help_option}" in en_help
    l10n_typer.apply_ru()
    ru_help = rich_utils.RICH_HELP
    assert _RICH_COLOR_TAG.search(ru_help) is None
    assert "{command_path}" in ru_help and "{help_option}" in ru_help
    assert "Попробуйте" in ru_help
    l10n_typer.revert_ru()
    assert rich_utils.RICH_HELP == en_help


def test_all_color_styles_use_tokens() -> None:
    l10n_typer.apply_palette()
    token_hexes = {h.lower() for h in theme.TOKENS.values()}
    for name, value in vars(rich_utils).items():
        if not name.startswith("STYLE_"):
            continue
        text = str(value)
        assert not _COLOR_WORD.search(text), f"{name}={text!r}"
        for found in _HEX.findall(text):
            assert found.lower() in token_hexes, f"{name}={text!r}"


def test_color_tokens_mirror() -> None:
    mirror = json.loads((_ROOT / "assets" / "color-tokens.json").read_text(encoding="utf-8"))
    assert mirror == theme.TOKENS


def test_disable_click_colorama_is_passthrough() -> None:
    from typer._click import _compat
    from typer._click import utils as click_utils

    l10n_typer.disable_click_colorama()
    assert click_utils.auto_wrap_for_ansi("stream") == "stream"
    assert click_utils.auto_wrap_for_ansi("stream", color=True) == "stream"
    assert _compat.auto_wrap_for_ansi("stream") == "stream"


def test_echo_keeps_truecolor_on_windows_console(monkeypatch) -> None:
    import io

    from typer._click import utils as click_utils

    l10n_typer.disable_click_colorama()
    monkeypatch.setattr(click_utils, "WIN", True)

    class TtyStringIO(io.StringIO):
        def isatty(self) -> bool:
            return True

    buf = TtyStringIO()
    click_utils.echo("\x1b[38;2;0;213;135mx\x1b[0m", file=buf)
    assert "\x1b[38;2;0;213;135m" in buf.getvalue()
