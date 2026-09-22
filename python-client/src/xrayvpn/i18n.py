"""RU/EN switch for user-facing CLI strings (`--ru`, `XRAYVPN_LANG`).

`preinit()` runs before the Typer app is built, so `--ru` in any argv
position or `XRAYVPN_LANG=ru` also translates `--help`: Typer bakes help
texts at import time. Two-letter language codes keep the door open for
more languages; the internal state is currently a RU boolean. `t(KEY, **fmt)`
resolves the pair stored in `xrayvpn.text.MESSAGES`.
"""

from __future__ import annotations

import os
import sys

from xrayvpn.text import MESSAGES

LANG_ENV = "XRAYVPN_LANG"

_STATE = {"ru": False}


def set_ru(enabled: bool) -> None:
    _STATE["ru"] = bool(enabled)


def is_ru() -> bool:
    return _STATE["ru"]


def t(key: str, **fmt: object) -> str:
    """Resolve a catalog key (xrayvpn.text.MESSAGES) in the active language."""
    entry = MESSAGES[key]
    text = entry.ru if _STATE["ru"] else entry.en
    return text.format(**fmt) if fmt else text


def set_lang(lang: str) -> None:
    normalized = lang.strip().lower()
    if normalized == "ru":
        set_ru(True)
    elif normalized == "en":
        set_ru(False)
    else:
        set_ru(False)
        print(t("I18N_LANG_WARNING", env=LANG_ENV, value=lang), file=sys.stderr)


def preinit(argv: list[str] | None = None) -> None:
    """Detect the language before the Typer app is built: env first, `--ru` wins."""
    args = sys.argv[1:] if argv is None else argv
    env_lang = os.environ.get(LANG_ENV, "").strip()
    if env_lang:
        set_lang(env_lang)
    if "--ru" in args:
        set_ru(True)
