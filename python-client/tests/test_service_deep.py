"""Deep read-only probe: command builders, parsers, and the privacy guard."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from xrayvpn.core.service_actions import (
    deep_status_commands,
    parse_egress,
    parse_reality,
    parse_runtime,
    parse_version,
    parse_warp,
    reality_state_python,
    safe_config_dir,
    warp_state_python,
)

NATIVE_UNIT = (
    "# /etc/systemd/system/xray.service\n"
    "[Unit]\nDescription=Xray\n[Service]\n"
    "ExecStart=/usr/local/bin/xray run -c /usr/local/etc/xray/config.json\n"
)
DOCKER_UNIT = (
    "# /etc/systemd/system/xray.service\n"
    "[Service]\n"
    "ExecStart=/usr/bin/docker run \\\n"
    "  --rm \\\n"
    "  --name xray \\\n"
    "  --network host \\\n"
    "  ghcr.io/xtls/xray-core:26.6.27 \\\n"
    "  /usr/bin/xray -c /etc/xray/config.json\n"
)


def test_deep_commands_are_whitelisted() -> None:
    cmds = deep_status_commands(443, 10820, "/root/xray-config")
    assert len(cmds) == 6
    assert cmds[0] == "systemctl cat xray 2>/dev/null || true"
    assert cmds[1].startswith("/usr/local/bin/xray version")
    assert "docker exec xray /usr/bin/xray version" in cmds[1]
    assert "/root/xray-config/reality-state.json" in cmds[2]
    assert "/root/xray-config/config.json" in cmds[3]
    assert "--socks5-hostname 127.0.0.1:10820" in cmds[4]
    assert "https://api.ipify.org" in cmds[4] and "https://checkip.amazonaws.com" in cmds[4]
    assert cmds[5] == "curl -sS -m 5 https://api.ipify.org 2>/dev/null || true"


def test_unsafe_config_dir_falls_back_to_default() -> None:
    assert safe_config_dir(None) == "/root/xray-config"
    assert safe_config_dir("/root/xray-config") == "/root/xray-config"
    assert safe_config_dir("/root/x; rm -rf /") == "/root/xray-config"
    cmds = deep_status_commands(443, 10820, "/tmp/$(whoami)")
    assert "$(whoami)" not in cmds[2] and "$(whoami)" not in cmds[3]


def test_parse_runtime() -> None:
    assert parse_runtime(NATIVE_UNIT) == {"runtime": "native", "container": None}
    docker = parse_runtime(DOCKER_UNIT)
    assert docker == {"runtime": "docker", "container": "xray"}
    assert parse_runtime("") == {"runtime": "n/a", "container": None}


def test_parse_version() -> None:
    out = "Xray 26.6.27 (Xray, Penetrates Everything.) custom (go1.24.4 linux/amd64)\n"
    assert parse_version(out, "26.6.27") == {"version": "26.6.27", "match": True}
    assert parse_version(out, "26.7.1") == {"version": "26.6.27", "match": False}
    assert parse_version(out) == {"version": "26.6.27", "match": None}
    assert parse_version("") == {"version": None, "match": None}


def test_parse_reality() -> None:
    stdout = "1757700000\npub=AbCdEfGh\nshortid=1234abcd\nclients=3\n"
    info = parse_reality(stdout, now=1757700000 + 90061)
    assert info["mtime"] == 1757700000
    assert info["age_days"] == 1 and info["age_hours"] == 1
    assert info["public_prefix"] == "AbCdEfGh"
    assert info["short_id"] == "1234abcd"
    assert info["clients"] == 3
    empty = parse_reality("")
    assert empty["mtime"] is None and empty["age_days"] is None


def test_parse_warp() -> None:
    assert parse_warp("warp=True\nclients=3\n") == {"warp": True, "clients": 3}
    assert parse_warp("warp=False\nclients=0\n") == {"warp": False, "clients": 0}
    assert parse_warp("") == {"warp": None, "clients": None}


def test_parse_egress() -> None:
    assert parse_egress("1.2.3.4\n", "5.6.7.8\n") == {
        "egress_ip": "1.2.3.4",
        "server_ip": "5.6.7.8",
        "differs": True,
    }
    same = parse_egress("5.6.7.8", "5.6.7.8")
    assert same["differs"] is False
    dead = parse_egress("", "5.6.7.8")
    assert dead == {"egress_ip": None, "server_ip": "5.6.7.8", "differs": None}


def _run_python(code: str, arg: str) -> str:
    result = subprocess.run(
        [sys.executable, "-c", code, arg],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


def test_reality_probe_never_prints_private_key(tmp_path: Path) -> None:
    state = {
        "private_key": "SUPER-FAKE-PRIVATE-KEY-DO-NOT-LEAK",
        "public_key": "PUBKEY1234567890",
        "short_id": "abcd1234",
        "client_uuids": ["u1", "u2"],
    }
    path = tmp_path / "reality-state.json"
    path.write_text(json.dumps(state), encoding="utf-8")
    out = _run_python(reality_state_python(), str(path))
    assert "SUPER-FAKE-PRIVATE-KEY" not in out
    assert "pub=PUBKEY12" in out
    assert "shortid=abcd1234" in out
    assert "clients=2" in out


def test_warp_probe_reads_only_shape(tmp_path: Path) -> None:
    config = {
        "inbounds": [
            {"protocol": "vless", "settings": {"clients": [{"id": "uuid-1"}, {"id": "uuid-2"}]}},
            {"protocol": "socks", "settings": {}},
        ],
        "outbounds": [{"protocol": "freedom"}, {"protocol": "wireguard", "settings": {"key": "SECRET"}}],
    }
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    out = _run_python(warp_state_python(), str(path))
    assert out == "warp=True\nclients=2\n"
    assert "SECRET" not in out
