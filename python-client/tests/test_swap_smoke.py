"""Swap smoke: replace a RUNNING binary copy on the real OS (tmp_path only).

A helper process is started from the target path and holds it open; the
update module must still rename-and-replace that path (the mechanism the
updater relies on for Windows and POSIX alike). The child is always
terminated; nothing outside tmp_path is touched.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

from xrayvpn.core import update


class _Http:
    def __init__(self, responses: dict[str, bytes]) -> None:
        self.responses = responses

    def __call__(self, url: str) -> bytes:
        for fragment, payload in self.responses.items():
            if fragment in url:
                return payload
        raise AssertionError(f"unexpected URL {url}")


def _holding_binary(tmp_path: Path) -> tuple[Path, list[str]]:
    if sys.platform == "win32":
        source = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "ping.exe"
        target = tmp_path / "xrayvpn.exe"
        args = ["-n", "120", "127.0.0.1"]
    else:
        source = Path(shutil.which("sleep") or "/bin/sleep")
        target = tmp_path / "xrayvpn"
        args = ["120"]
    shutil.copy2(source, target)
    return target, args


def _start_holding(target: Path, args: list[str]) -> subprocess.Popen[bytes]:
    return subprocess.Popen([str(target), *args])


def _stop(process: subprocess.Popen[bytes]) -> None:
    process.terminate()
    try:
        process.wait(timeout=30)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=30)


def test_swap_in_place_of_running_binary(tmp_path: Path) -> None:
    target, args = _holding_binary(tmp_path)
    staged = tmp_path / "staged.bin"
    staged.write_bytes(b"new-binary-payload")
    process = _start_holding(target, args)
    try:
        time.sleep(1.5)
        assert process.poll() is None
        backup = update.swap_in_place(staged, target)
        assert target.read_bytes() == b"new-binary-payload"
        assert backup.read_bytes() != b"new-binary-payload"
    finally:
        _stop(process)


def test_perform_update_replaces_running_binary(tmp_path: Path) -> None:
    token = update.platform_token(sys.platform, platform.machine())
    if token is None:
        pytest.skip(f"no update asset token for {sys.platform}/{platform.machine()}")
    extension = ".exe" if sys.platform == "win32" else ""
    name = f"xrayvpn-9.9.9-{token}-portable{extension}"
    data = b"fresh-updated-binary"
    sha = hashlib.sha256(data).hexdigest()
    responses = {
        "releases/latest": json.dumps(
            {
                "tag_name": "v9.9.9",
                "prerelease": False,
                "draft": False,
                "published_at": "2026-01-01T00:00:00Z",
                "html_url": "https://example.invalid/releases/tag/v9.9.9",
            }
        ).encode(),
        "latest.json": json.dumps(
            {"assets": {token: {"name": name, "url": f"https://dl/{name}", "sha256": sha}}}
        ).encode(),
        "SHA256SUMS.txt": f"{sha}  {name}\n".encode(),
    }
    target, args = _holding_binary(tmp_path)
    process = _start_holding(target, args)
    try:
        time.sleep(1.5)
        assert process.poll() is None
        outcome = update.perform_standalone_update(
            target,
            current="0.4.2",
            platform=sys.platform,
            machine=platform.machine(),
            http=_Http(responses),
            opener=lambda url: io.BytesIO(data),
        )
        assert outcome.status == update.STATUS_UPDATED
        assert target.read_bytes() == data
        assert outcome.backup is not None
    finally:
        _stop(process)
