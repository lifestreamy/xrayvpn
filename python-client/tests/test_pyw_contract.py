"""Launcher contract: static argv checks plus a real end-to-end launch.

Static: the COMMAND baked into each `.pyw` must exist in the Typer surface
(a renamed command or a dropped flag fails here). Runtime: with
XRAYVPN_PYW_SELFTEST=1 the launcher swaps COMMAND for `--version` and runs
the same interpreter-resolution and subprocess path — a launcher that cannot
start fails here, not on double-click.
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

import pytest
import typer.main

from xrayvpn import __version__
from xrayvpn.cli.main import app

CLIENT_ROOT = Path(__file__).resolve().parents[1]
LAUNCHERS: dict[Path, bool] = {
    CLIENT_ROOT / "xrayvpn-deploy.pyw": False,
    CLIENT_ROOT / "xrayvpn-deploy-ru.pyw": True,
}


def _pyw_command(path: Path) -> list[str]:
    """Extract the literal COMMAND list from a .pyw without executing it."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            targets: list[ast.expr] = list(node.targets)
            value = node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets = [node.target]
            value = node.value
        else:
            continue
        for target in targets:
            if isinstance(target, ast.Name) and target.id == "COMMAND":
                if not isinstance(value, ast.List):
                    raise AssertionError("COMMAND must be a list literal")
                elements = value.elts
                words = [
                    el.value
                    for el in elements
                    if isinstance(el, ast.Constant) and isinstance(el.value, str)
                ]
                assert len(words) == len(elements), "COMMAND must hold only string literals"
                return words
    raise AssertionError(f"COMMAND literal list not found in {path.name}")


def _cli_registry() -> dict[str, set[str]]:
    """command name -> every flag spelling the CLI accepts for it."""
    group = typer.main.get_command(app)
    registry: dict[str, set[str]] = {}
    for name, command in group.commands.items():
        flags: set[str] = set()
        for param in command.params:
            flags.update(param.opts)
            flags.update(getattr(param, "secondary_opts", []))
        registry[name] = flags
    return registry


@pytest.mark.parametrize("path", sorted(LAUNCHERS), ids=lambda p: p.name)
def test_launcher_exists_and_parses(path: Path) -> None:
    assert path.is_file(), f"{path.name} launcher is missing"
    assert _pyw_command(path)


@pytest.mark.parametrize("path", sorted(LAUNCHERS), ids=lambda p: p.name)
def test_launcher_invokes_a_real_command(path: Path) -> None:
    command = _pyw_command(path)
    registry = _cli_registry()
    assert command[0] in registry, (
        f"{path.name} calls unknown command {command[0]!r}; CLI defines {sorted(registry)}"
    )


@pytest.mark.parametrize("path", sorted(LAUNCHERS), ids=lambda p: p.name)
def test_launcher_flags_exist_in_cli(path: Path) -> None:
    command = _pyw_command(path)
    flags = _cli_registry()[command[0]]
    used = [word for word in command if word.startswith("-")]
    assert used, "the launcher must pin its mode/flags explicitly"
    unknown = [word for word in used if word not in flags]
    assert not unknown, f"{path.name} uses flags absent from the CLI: {unknown}"


@pytest.mark.parametrize("path", sorted(LAUNCHERS), ids=lambda p: p.name)
def test_launchers_stay_interactive_and_safe(path: Path) -> None:
    command = _pyw_command(path)
    assert command[0] == "deploy"
    assert "--no-interactive" not in command, "double-click must never skip the plan confirmation"
    assert "--execution" not in command, "the wizard asks; nothing may default silently"
    assert "--rotate" not in command, "double-click may never rotate REALITY keys"


@pytest.mark.parametrize("path", sorted(LAUNCHERS), ids=lambda p: p.name)
def test_launcher_language_matches_file_name(path: Path) -> None:
    command = _pyw_command(path)
    assert ("--ru" in command) is LAUNCHERS[path]


@pytest.mark.parametrize("path", sorted(LAUNCHERS), ids=lambda p: p.name)
def test_launcher_runs_end_to_end(path: Path) -> None:
    env = {**os.environ, "XRAYVPN_PYW_SELFTEST": "1"}
    result = subprocess.run(
        [sys.executable, str(path)],
        capture_output=True,
        text=True,
        env=env,
        timeout=180,
        cwd=str(CLIENT_ROOT),
        check=False,
    )
    assert result.returncode == 0, f"{path.name} launch failed:\n{result.stdout}\n{result.stderr}"
    assert f"xrayvpn {__version__}" in result.stdout


def test_shared_launcher_module_exists() -> None:
    assert (CLIENT_ROOT / "_pywlaunch.py").is_file()
