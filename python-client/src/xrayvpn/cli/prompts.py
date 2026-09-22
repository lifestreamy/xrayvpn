"""Interactive prompts (arrow-key selects). Degrade silently when stdin is not a TTY."""

from __future__ import annotations

import sys


def is_interactive() -> bool:
    try:
        return sys.stdin.isatty()
    except OSError:
        return False




def select(title: str, choices: list[str], default: str | None = None) -> str | None:
    """Arrow-key selection inside the terminal; returns `default` when not interactive."""
    if not is_interactive():
        return default
    try:
        from InquirerPy import inquirer

        return inquirer.select(
            message=title, choices=choices, default=default or choices[0]
        ).execute()
    except Exception as exc:  # noqa - intentional: prompts degrade to defaults
        return default


def confirm(title: str, default: bool = False) -> bool:
    """Yes/no prompt; returns `default` when not interactive."""
    if not is_interactive():
        return default
    try:
        from InquirerPy import inquirer

        return bool(inquirer.confirm(message=title, default=default).execute())
    except Exception as exc:  # noqa - intentional: prompts degrade to defaults
        return default


def text(title: str, default: str | None = None) -> str | None:
    """Prompt for a text value; returns `default` when not interactive."""
    if not is_interactive():
        return default
    try:
        from InquirerPy import inquirer

        result = inquirer.text(message=title, default=default or "").execute()
        return result or default
    except Exception as exc:  # noqa - intentional: prompts degrade to defaults
        return default