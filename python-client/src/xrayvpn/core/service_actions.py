"""Whitelisted remote commands for `xrayvpn service` (exact strings, no interpolation
of operator input beyond integer ports and the payload-settings config dir).
This module never talks to the network."""

from __future__ import annotations

import re
import time

XRAY_UNITS = ("xray", "xray-obs-snapshot", "xray-watchdog")
STORM_REGEX = "proxy/wireguard.*(failed|timeout)"
ERRORS_REGEX = f"{STORM_REGEX}|level=(error|warning)"
DEFAULT_CONFIG_DIR = "/root/xray-config"
EGRESS_PRIMARY = "https://api.ipify.org"
EGRESS_FALLBACK = "https://checkip.amazonaws.com"
_CONFIG_DIR_RE = re.compile(r"^[A-Za-z0-9_./-]+$")


def journal_filter() -> str:
    # repeated -u is journald OR of a single field; mixing -u and -t would AND.
    return " ".join(f"-u {unit}" for unit in XRAY_UNITS)


def status_commands(xray_port: int = 443, probe_port: int = 10820, minutes: int = 30) -> list[str]:
    port = int(xray_port)  # ports are ints from config, never free-form text
    probe = int(probe_port)
    mins = int(minutes)
    return [
        "systemctl is-active xray",
        "systemctl show xray -p NRestarts -p ActiveEnterTimestamp -p SubState",
        f"sudo -n journalctl -u xray --since '-{mins}m' -o cat | grep -Ec '{STORM_REGEX}' || true",
        (
            f"sudo -n journalctl {journal_filter()} --since '-{mins}m' -o short-iso --no-pager"
            f" | grep -E '{ERRORS_REGEX}' | tail -n 10 || true"
        ),
        f"sudo -n journalctl {journal_filter()} --since '-{mins}m' -o short-iso --no-pager | tail -n 5",
        f"sudo -n ss -tulpn '( sport = :{port} or sport = :{probe} or sport = :22 )'",
        "free -m",
    ]


def restart_commands() -> list[str]:
    return [
        "sudo -n systemctl reset-failed xray",
        "sudo -n systemctl restart xray",
        "systemctl is-active xray",
    ]


def logs_journal_command(since: str, lines: int | None = None) -> str:
    # `since` must match ^[0-9]+[mhd]$ (CLI normalizes before calling); never free text reaches the shell.
    # The journal is small by construction (capped in the role); stream it over SSH, no server-side file.
    limit = f" -n {int(lines)}" if lines is not None else ""
    return f"sudo -n journalctl {journal_filter()} --since \"-{since}\"{limit} -o short-iso --no-pager"


def reboot_command() -> str:
    return "sudo -n systemctl reboot"


def safe_config_dir(config_dir: str | None) -> str:
    candidate = str(config_dir or DEFAULT_CONFIG_DIR).strip()
    if not _CONFIG_DIR_RE.match(candidate):
        return DEFAULT_CONFIG_DIR
    return candidate


def reality_state_python() -> str:
    return (
        "import json,sys;"
        "d=json.load(open(sys.argv[1]));"
        "print('pub=%s'%str(d.get('public_key') or '')[:8]);"
        "print('shortid=%s'%(d.get('short_id') or ''));"
        "print('clients=%d'%len(d.get('client_uuids') or []))"
    )


def warp_state_python() -> str:
    return (
        "import json,sys;"
        "d=json.load(open(sys.argv[1]));"
        "print('warp=%s'%any(x.get('protocol')=='wireguard' for x in (d.get('outbounds') or [])));"
        "print('clients=%d'%sum(len((x.get('settings') or {}).get('clients') or [])"
        " for x in (d.get('inbounds') or [])))"
    )


def deep_status_commands(
    xray_port: int = 443,
    probe_port: int = 10820,
    config_dir: str = DEFAULT_CONFIG_DIR,
) -> list[str]:
    cfg = safe_config_dir(config_dir)
    probe = int(probe_port)
    egress = (
        f"timeout 8 curl -s --socks5-hostname 127.0.0.1:{probe} --max-time 6 {EGRESS_PRIMARY}"
        f" 2>/dev/null || timeout 8 curl -s --socks5-hostname 127.0.0.1:{probe} --max-time 6"
        f" {EGRESS_FALLBACK} 2>/dev/null || true"
    )
    return [
        "systemctl cat xray 2>/dev/null || true",
        "/usr/local/bin/xray version 2>/dev/null || docker exec xray /usr/bin/xray version 2>/dev/null || true",
        (
            f"stat -c %Y {cfg}/reality-state.json 2>/dev/null; "
            f"python3 -c \"{reality_state_python()}\" {cfg}/reality-state.json 2>/dev/null || true"
        ),
        f"python3 -c \"{warp_state_python()}\" {cfg}/config.json 2>/dev/null || true",
        egress,
        f"curl -sS -m 5 {EGRESS_PRIMARY} 2>/dev/null || true",
    ]


def parse_runtime(stdout: str) -> dict[str, object]:
    text = (stdout or "").strip()
    if not text:
        return {"runtime": "n/a", "container": None}
    if "docker" in text:
        container: str | None = None
        for line in text.splitlines():
            parts = line.split()
            if "--name" in parts:
                index = parts.index("--name")
                if index + 1 < len(parts):
                    container = parts[index + 1].strip().rstrip("\\").strip() or None
        return {"runtime": "docker", "container": container}
    return {"runtime": "native", "container": None}


def parse_version(stdout: str, expected: str | None = None) -> dict[str, object]:
    version: str | None = None
    for line in (stdout or "").splitlines():
        for token in line.replace("(", " ").split():
            if token and token[0].isdigit() and "." in token:
                version = token.strip()
                break
        if version:
            break
    match: bool | None = None
    if version is not None and expected is not None:
        match = version == str(expected).strip()
    return {"version": version, "match": match}


def parse_reality(stdout: str, now: float | None = None) -> dict[str, object]:
    mtime: int | None = None
    public_prefix: str | None = None
    short_id: str | None = None
    clients: int | None = None
    for line in (stdout or "").splitlines():
        stripped = line.strip()
        if mtime is None and stripped.isdigit():
            mtime = int(stripped)
        elif stripped.startswith("pub="):
            public_prefix = stripped[4:] or None
        elif stripped.startswith("shortid="):
            short_id = stripped[8:] or None
        elif stripped.startswith("clients="):
            try:
                clients = int(stripped[8:])
            except ValueError:
                pass
    age_days: int | None = None
    age_hours: int | None = None
    if mtime is not None:
        current = time.time() if now is None else float(now)
        delta = max(0, int(current) - mtime)
        age_days, age_hours = delta // 86400, (delta % 86400) // 3600
    return {
        "mtime": mtime,
        "age_days": age_days,
        "age_hours": age_hours,
        "public_prefix": public_prefix,
        "short_id": short_id,
        "clients": clients,
    }


def parse_warp(stdout: str) -> dict[str, object]:
    warp: bool | None = None
    clients: int | None = None
    for line in (stdout or "").splitlines():
        stripped = line.strip()
        if stripped.startswith("warp="):
            warp = stripped[5:] == "True"
        elif stripped.startswith("clients="):
            try:
                clients = int(stripped[8:])
            except ValueError:
                pass
    return {"warp": warp, "clients": clients}


def _clean_ip(stdout: str) -> str | None:
    lines = [line.strip() for line in (stdout or "").splitlines() if line.strip()]
    if not lines:
        return None
    candidate = lines[-1]
    if " " in candidate or len(candidate) > 45:
        return None
    return candidate


def parse_egress(probe_stdout: str, direct_stdout: str) -> dict[str, object]:
    egress_ip = _clean_ip(probe_stdout)
    server_ip = _clean_ip(direct_stdout)
    differs: bool | None = None
    if egress_ip is not None and server_ip is not None:
        differs = egress_ip != server_ip
    return {"egress_ip": egress_ip, "server_ip": server_ip, "differs": differs}
