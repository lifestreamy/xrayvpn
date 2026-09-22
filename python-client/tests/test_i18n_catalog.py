"""Стражи каталога i18n: CLI-тексты живут только в xrayvpn.text.

`l10n_typer.py` исключён: он патчит внутренние строки typer/click (<0.28),
они обязаны совпадать с дефолтами библиотеки и не являются продуктовым текстом.
Динамические f-string-фрагменты (техническая диагностика, rc/repr) не
проверяются — проверяются литералы-аргументы вывода и форма вызова t().
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

import xrayvpn
from xrayvpn.text import MESSAGES

PACKAGE = Path(xrayvpn.__file__).resolve().parent
EXCLUDED_FILE = "l10n_typer.py"
OUTPUT_FUNCS = {"print", "echo", "secho", "getpass"}
_PREFIXES = ("COMMON", "EXEC", "REPL", "SVC", "MAIN", "I18N")
_WORD = re.compile(r"[A-Za-zА-Яа-яЁё]{2,}")
_CATALOG_TEXTS = {e.en for e in MESSAGES.values()} | {e.ru for e in MESSAGES.values()}


def _source_trees() -> list[tuple[str, ast.Module]]:
    result = []
    for path in sorted(PACKAGE.rglob("*.py")):
        if path.name == EXCLUDED_FILE or path.parent.name in ("payload", "build"):
            continue
        result.append((path.name, ast.parse(path.read_text(encoding="utf-8"))))
    return result


def _called_name(node: ast.Call) -> str:
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr
    return getattr(func, "id", "")


def test_every_t_call_is_single_catalog_key() -> None:
    for name, tree in _source_trees():
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or _called_name(node) != "t":
                continue
            assert len(node.args) == 1, f"{name}: t() takes exactly one positional key"
            first = node.args[0]
            assert isinstance(first, ast.Constant) and isinstance(first.value, str)
            assert first.value in MESSAGES, f"{name}: unknown i18n key {first.value!r}"


def test_no_plain_literal_user_output_calls() -> None:
    violations = []
    for name, tree in _source_trees():
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or _called_name(node) not in OUTPUT_FUNCS:
                continue
            if not node.args:
                continue
            first = node.args[0]
            if (
                isinstance(first, ast.Constant)
                and isinstance(first.value, str)
                and len(_WORD.findall(first.value)) > 2
                and first.value not in _CATALOG_TEXTS
            ):
                violations.append(f"{name}: {first.value!r}")
    assert not violations, "literal user text outside the catalog:\n" + "\n".join(violations)


@pytest.mark.parametrize("key", sorted(MESSAGES))
def test_catalog_entry_is_complete_pair(key: str) -> None:
    entry = MESSAGES[key]
    assert entry.en and entry.ru
    assert key.startswith(_PREFIXES), key
