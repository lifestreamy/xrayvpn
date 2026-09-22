"""Banner layout must respect the terminal width in every language."""

from __future__ import annotations

import pytest

from xrayvpn import i18n
from xrayvpn.cli import repl, theme
from xrayvpn.cli.repl import welcome_screen


class Restore:
    def __enter__(self) -> None:
        self.lang = i18n.is_ru()

    def __exit__(self, *exc: object) -> None:
        i18n.set_ru(self.lang)


def _screen(monkeypatch, width: int, lang: str) -> str:
    monkeypatch.setenv("XRAYVPN_WIDTH", str(width))
    monkeypatch.delenv("XRAYVPN_HYPERLINK", raising=False)
    with Restore():
        i18n.set_ru(lang == "ru")
        return welcome_screen("1.2.3")


@pytest.mark.parametrize("width", [60, 72, 80, 100, 120, 200])
@pytest.mark.parametrize("lang", ["en", "ru"])
def test_every_line_fits_terminal_width(monkeypatch, width: int, lang: str) -> None:
    screen = _screen(monkeypatch, width, lang)
    for line in screen.splitlines():
        assert theme.visible_len(line) <= width


@pytest.mark.parametrize("width", [80, 100, 200])
def test_box_lines_align_and_match_across_languages(monkeypatch, width: int) -> None:
    en = _screen(monkeypatch, width, "en")
    ru = _screen(monkeypatch, width, "ru")
    en_widths = {theme.visible_len(line) for line in en.splitlines()}
    ru_widths = {theme.visible_len(line) for line in ru.splitlines()}
    assert len(en_widths) == 1
    assert len(ru_widths) == 1
    assert en_widths == ru_widths


def test_narrow_terminal_renders_without_boxes(monkeypatch) -> None:
    screen = _screen(monkeypatch, 50, "en")
    assert "+---" not in screen
    for line in screen.splitlines():
        assert theme.visible_len(line) <= 50


def test_banner_rerender_follows_current_width(monkeypatch) -> None:
    wide = _screen(monkeypatch, 120, "en")
    narrow = _screen(monkeypatch, 74, "en")
    assert max(theme.visible_len(line) for line in wide.splitlines()) > max(
        theme.visible_len(line) for line in narrow.splitlines()
    )


def test_docs_url_stays_intact_when_it_fits(monkeypatch) -> None:
    screen = _screen(monkeypatch, 120, "en")
    assert repl.REPO_DOCS_URL in screen
    split = _screen(monkeypatch, 60, "en")
    for line in split.splitlines():
        assert theme.visible_len(line) <= 60
