"""Package smoke test: importable, reports a version, version matches pyproject."""

from __future__ import annotations

import tomllib
from pathlib import Path

from xrayvpn import __version__

PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"


def test_version_string() -> None:
    assert isinstance(__version__, str)
    assert __version__.count(".") >= 2


def test_version_matches_pyproject() -> None:
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    assert data["project"]["version"] == __version__
