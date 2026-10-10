"""`FabricRemote` must never let fabric load `~/.ssh/config` itself.

Fabric's own loader reads the file with the locale codec (cp1252 on Windows)
and dies on non-ASCII bytes; alias resolution is `core/conn.py`'s job already.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from xrayvpn.core.transport.remote import FabricRemote


def test_constructor_ignores_hostile_ssh_config(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # \x81\x8d\x90\x9d is undecodable in both utf-8 (any CI) and cp1252
    # (Windows default), so the guard trips on every platform.
    home = tmp_path / "home"
    config = home / ".ssh" / "config"
    config.parent.mkdir(parents=True)
    config.write_bytes(b"Host vps\n  HostName 203.0.113.7\n  \x81\x8d\x90\x9d\n")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))

    FabricRemote("vps")
