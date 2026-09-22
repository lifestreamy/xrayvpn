"""`xrayvpn service` — whitelisted commands, conn resolution and CLI guards."""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar, Self

import pytest
from typer.testing import CliRunner

import xrayvpn.cli.service as service_mod
from xrayvpn import i18n
from xrayvpn.cli.main import app
from xrayvpn.cli.repl import help_text
from xrayvpn.core.conn import ConnResolveError, resolve_connection
from xrayvpn.core.inventory import parse_user_inventory
from xrayvpn.core.runtime_paths import RunRoots
from xrayvpn.core.service_actions import (
    logs_journal_command,
    reboot_command,
    restart_commands,
    status_commands,
)
from xrayvpn.core.transport.remote import CommandResult

runner = CliRunner()


@pytest.fixture(autouse=True)
def _reset_i18n():
    i18n.set_ru(False)
    yield
    i18n.set_ru(False)


def _output(result) -> str:
    text = result.output or ""
    stderr = getattr(result, "stderr", "") or ""
    return text + stderr


class FakeRemote:
    """Scripted Remote: returns a canned CommandResult per executed prefix."""

    calls: ClassVar[list[str]] = []
    run_kwargs: ClassVar[list[dict]] = []
    responses: ClassVar[dict[str, str]] = {}
    ki_on_prefix: ClassVar[str | None] = None
    ki_partial: ClassVar[str] = ""

    def __init__(self, *args, **kwargs) -> None:
        pass

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc) -> None:
        return None

    def run(
        self, command, *, sudo=False, warn=True, env=None, hide=False, out_stream=None
    ) -> CommandResult:
        FakeRemote.calls.append(command)
        FakeRemote.run_kwargs.append({"hide": hide, "out_stream": out_stream})
        if FakeRemote.ki_on_prefix and command.startswith(FakeRemote.ki_on_prefix):
            if out_stream is not None:
                out_stream.write(FakeRemote.ki_partial)
            raise KeyboardInterrupt
        for prefix, out in FakeRemote.responses.items():
            if command.startswith(prefix):
                if out_stream is not None:
                    out_stream.write(out)
                return CommandResult(return_code=0, stdout=out)
        return CommandResult(return_code=0, stdout="")


def _stub_transport(monkeypatch, tmp_path: Path) -> None:
    FakeRemote.calls = []
    FakeRemote.run_kwargs = []
    FakeRemote.ki_on_prefix = None
    FakeRemote.ki_partial = ""
    FakeRemote.responses = {
        "systemctl is-active xray": "active\n",
        "systemctl show xray -p NRestarts": "NRestarts=0\nActiveEnterTimestamp=Sat 2026-09-13 00:00:00 UTC\nSubState=running\n",
        "sudo -n journalctl -u xray --since '-30m' -o cat": "3\n",
        "sudo -n journalctl -u xray -u xray-obs-snapshot -u xray-watchdog --since '-30m' -o short-iso --no-pager | grep -E": "2026-09-13T00:00:00Z xray[1]: proxy/wireguard: connection failed\n",
        "sudo -n journalctl -u xray -u xray-obs-snapshot -u xray-watchdog --since '-30m' -o short-iso --no-pager | tail -n 5": "2026-09-13T00:00:00Z xray[1]: sample journal line\n",
        "sudo -n journalctl -u xray -u xray-obs-snapshot": "2026-09-13T00:00:00Z xray[1]: sample journal line\n",
        "systemctl cat xray": "[Service]\nExecStart=/usr/local/bin/xray run -c /usr/local/etc/xray/config.json\n",
        "/usr/local/bin/xray version": "Xray 26.6.27 (Xray, Penetrates Everything.) custom\n",
        "stat -c %Y": "1757700000\npub=AbCdEfGh\nshortid=1234abcd\nclients=3\n",
        "python3 -c": "warp=True\nclients=3\n",
        "timeout 8 curl": "1.2.3.4\n",
        "curl -sS": "5.6.7.8\n",
    }
    monkeypatch.setattr(service_mod, "FabricRemote", FakeRemote)
    monkeypatch.setattr(
        service_mod,
        "_roots",
        lambda: RunRoots(repo=tmp_path, workspace=tmp_path, payload=tmp_path),
    )


def _key(tmp_path: Path) -> Path:
    key = tmp_path / "id_ed25519"
    key.write_text("fake", encoding="utf-8")
    return key


# --- builders: exact whitelist strings ---

def test_status_commands_are_exact() -> None:
    cmds = status_commands(443, 10820, 30)
    assert cmds == [
        "systemctl is-active xray",
        "systemctl show xray -p NRestarts -p ActiveEnterTimestamp -p SubState",
        "sudo -n journalctl -u xray --since '-30m' -o cat | grep -Ec 'proxy/wireguard.*(failed|timeout)' || true",
        (
            "sudo -n journalctl -u xray -u xray-obs-snapshot -u xray-watchdog --since '-30m' -o short-iso --no-pager"
            " | grep -E 'proxy/wireguard.*(failed|timeout)|level=(error|warning)' | tail -n 10 || true"
        ),
        "sudo -n journalctl -u xray -u xray-obs-snapshot -u xray-watchdog --since '-30m' -o short-iso --no-pager | tail -n 5",
        "sudo -n ss -tulpn '( sport = :443 or sport = :10820 or sport = :22 )'",
        "free -m",
    ]


def test_restart_and_reboot_commands() -> None:
    assert restart_commands() == [
        "sudo -n systemctl reset-failed xray",
        "sudo -n systemctl restart xray",
        "systemctl is-active xray",
    ]
    assert reboot_command() == "sudo -n systemctl reboot"


def test_logs_command_streams_over_ssh() -> None:
    cmd = logs_journal_command("24h")
    assert cmd == (
        'sudo -n journalctl -u xray -u xray-obs-snapshot -u xray-watchdog '
        '--since "-24h" -o short-iso --no-pager'
    )
    assert ">" not in cmd and "; " not in cmd and "&&" not in cmd


def test_logs_command_line_limit() -> None:
    cmd = logs_journal_command("30m", 500)
    assert cmd == (
        'sudo -n journalctl -u xray -u xray-obs-snapshot -u xray-watchdog '
        '--since "-30m" -n 500 -o short-iso --no-pager'
    )


# --- conn.resolve_connection ---

def test_conn_explicit_pkey(tmp_path: Path) -> None:
    key = _key(tmp_path)
    conn = resolve_connection(
        workspace=tmp_path, example_dir=tmp_path, host=" 1.2.3.4 ", pkey=key, no_interactive=True
    )
    assert conn.host == "1.2.3.4" and conn.user == "root" and conn.port == 22
    assert conn.pkey == str(key) and conn.password is None


def test_conn_requires_host(tmp_path: Path) -> None:
    import pytest

    with pytest.raises(ConnResolveError, match="VPS host required"):
        resolve_connection(workspace=tmp_path, example_dir=tmp_path, no_interactive=True)


def test_conn_mutex_and_missing_key(tmp_path: Path) -> None:
    import pytest

    key = _key(tmp_path)
    with pytest.raises(ConnResolveError, match="private key and a password"):
        resolve_connection(
            workspace=tmp_path, example_dir=tmp_path, host="h", pkey=key, password="x",
            no_interactive=True,
        )
    with pytest.raises(ConnResolveError, match="private key not found"):
        resolve_connection(
            workspace=tmp_path, example_dir=tmp_path, host="h", pkey=tmp_path / "nope",
            no_interactive=True,
        )


def test_conn_password_prompt_or_error(tmp_path: Path) -> None:
    import pytest

    with pytest.raises(ConnResolveError, match="SSH auth required"):
        resolve_connection(workspace=tmp_path, example_dir=tmp_path, host="h", no_interactive=True)
    conn = resolve_connection(
        workspace=tmp_path, example_dir=tmp_path, host="h",
        ask_password=lambda _q: "s3cret",
    )
    assert conn.password == "s3cret"


def _write_inventory(workspace: Path, hosts: list[tuple[str, str]]) -> None:
    lines = ["all:", "  hosts:"]
    for name, host in hosts:
        lines += [
            f"    {name}:",
            f"      ansible_host: {host}",
            "      ansible_user: root",
            "      ansible_port: 22",
            "      ansible_ssh_private_key_file: ''",
        ]
    (workspace / "inventory.yml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_conn_single_host_inventory(tmp_path: Path) -> None:

    _write_inventory(tmp_path, [("vpn", "5.6.7.8")])
    conn = resolve_connection(
        workspace=tmp_path, example_dir=tmp_path, use_inventory=True,
        ask_password=lambda _q: "pw",
    )
    assert conn.host == "5.6.7.8" and conn.password == "pw"


def test_conn_multi_host_inventory_rejected(tmp_path: Path) -> None:
    import pytest

    _write_inventory(tmp_path, [("vpn", "5.6.7.8"), ("second", "9.9.9.9")])
    with pytest.raises(ConnResolveError, match="multiple hosts"):
        resolve_connection(workspace=tmp_path, example_dir=tmp_path, use_inventory=True)


def test_conn_missing_inventory_is_clean_error(tmp_path: Path) -> None:
    import pytest

    with pytest.raises(ConnResolveError, match="inventory file not found"):
        resolve_connection(workspace=tmp_path, example_dir=tmp_path, use_inventory=True)


def test_conn_empty_string_pkey_parity(tmp_path: Path) -> None:
    lines = [
        "all:",
        "  hosts:",
        "    vpn:",
        "      ansible_host: 5.6.7.8",
        "      ansible_user: root",
        "      ansible_port: 22",
        '      ansible_ssh_private_key_file: ""',
        "      ansible_ssh_pass: secret",
    ]
    (tmp_path / "inventory.yml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    connection, _extra = parse_user_inventory(tmp_path, example_dir=tmp_path)
    assert "ansible_ssh_private_key_file" not in connection
    conn = resolve_connection(
        workspace=tmp_path, example_dir=tmp_path, use_inventory=True, no_interactive=True
    )
    assert conn.pkey is None and conn.password == "secret"


# --- CLI wiring ---

def test_service_status_end_to_end(monkeypatch, tmp_path) -> None:
    _stub_transport(monkeypatch, tmp_path)
    key = _key(tmp_path)
    result = runner.invoke(
        app, ["service", "status", "-H", "1.2.3.4", "--pkey", str(key), "--no-interactive"]
    )
    assert result.exit_code == 0, _output(result)
    out = _output(result)
    assert "service xray@1.2.3.4" in out and "ошибок" not in out
    assert "outbound errors in the last 30 min: 3" in out
    assert "errors in the last 30 min (wireguard/level):" in out
    assert "proxy/wireguard: connection failed" in out
    assert "journal tail (last 5):" in out
    assert any(c.startswith("sudo -n ss -tulpn") for c in FakeRemote.calls)
    assert FakeRemote.run_kwargs and all(kw["hide"] is True for kw in FakeRemote.run_kwargs)


def test_service_status_no_errors_block(monkeypatch, tmp_path) -> None:
    _stub_transport(monkeypatch, tmp_path)
    FakeRemote.responses = dict(FakeRemote.responses)
    FakeRemote.responses[
        "sudo -n journalctl -u xray -u xray-obs-snapshot -u xray-watchdog --since '-30m' -o short-iso --no-pager | grep -E"
    ] = "\n"
    key = _key(tmp_path)
    result = runner.invoke(
        app, ["service", "status", "-H", "1.2.3.4", "--pkey", str(key), "--no-interactive"]
    )
    assert result.exit_code == 0, _output(result)
    assert "no errors in the window" in _output(result)


def test_service_status_ru(monkeypatch, tmp_path) -> None:
    _stub_transport(monkeypatch, tmp_path)
    key = _key(tmp_path)
    result = runner.invoke(
        app,
        ["service", "status", "--ru", "-H", "1.2.3.4", "--pkey", str(key), "--no-interactive"],
    )
    out = _output(result)
    assert "сервис xray@1.2.3.4" in out and "ошибок исходящего" in out


def _write_settings(tmp_path: Path, version: str) -> None:
    (tmp_path / "config").mkdir(exist_ok=True)
    (tmp_path / "config" / "settings.yml").write_text(
        f"xray_version: '{version}'\nxray_config_dir: /root/xray-config\n",
        encoding="utf-8",
    )


def test_service_status_deep_sections(monkeypatch, tmp_path) -> None:
    _stub_transport(monkeypatch, tmp_path)
    _write_settings(tmp_path, "26.6.27")
    key = _key(tmp_path)
    result = runner.invoke(
        app, ["service", "status", "-H", "1.2.3.4", "--pkey", str(key), "--no-interactive"]
    )
    assert result.exit_code == 0, _output(result)
    out = _output(result)
    assert "runtime: native" in out
    assert "xray: 26.6.27 (matches settings.yml)" in out
    assert "REALITY:" in out and "public AbCdEfGh…" in out
    assert "shortId 1234abcd" in out and "clients 3" in out
    assert "WARP: on, egress 1.2.3.4 vs server 5.6.7.8" in out


def test_service_status_deep_version_mismatch(monkeypatch, tmp_path) -> None:
    _stub_transport(monkeypatch, tmp_path)
    _write_settings(tmp_path, "26.7.1")
    key = _key(tmp_path)
    result = runner.invoke(
        app, ["service", "status", "-H", "1.2.3.4", "--pkey", str(key), "--no-interactive"]
    )
    assert result.exit_code == 0, _output(result)
    assert "xray: 26.6.27 (settings.yml expects 26.7.1)" in _output(result)


def test_service_status_deep_warp_off(monkeypatch, tmp_path) -> None:
    _stub_transport(monkeypatch, tmp_path)
    FakeRemote.responses = dict(FakeRemote.responses)
    FakeRemote.responses["python3 -c"] = "warp=False\nclients=3\n"
    key = _key(tmp_path)
    result = runner.invoke(
        app, ["service", "status", "-H", "1.2.3.4", "--pkey", str(key), "--no-interactive"]
    )
    assert result.exit_code == 0, _output(result)
    assert "WARP: off, server egress 5.6.7.8" in _output(result)


def test_service_status_deep_na_is_graceful(monkeypatch, tmp_path) -> None:
    _stub_transport(monkeypatch, tmp_path)
    FakeRemote.responses = {
        key: value
        for key, value in FakeRemote.responses.items()
        if key.startswith(("systemctl is-active", "systemctl show", "sudo -n journalctl"))
    }
    key = _key(tmp_path)
    result = runner.invoke(
        app, ["service", "status", "-H", "1.2.3.4", "--pkey", str(key), "--no-interactive"]
    )
    assert result.exit_code == 0, _output(result)
    out = _output(result)
    assert "runtime: n/a" in out
    assert "xray: n/a" in out
    assert "REALITY: n/a" in out
    assert "WARP: n/a" in out


def test_reboot_requires_yes(monkeypatch, tmp_path) -> None:
    _stub_transport(monkeypatch, tmp_path)
    key = _key(tmp_path)
    result = runner.invoke(
        app, ["service", "reboot", "-H", "1.2.3.4", "--pkey", str(key), "--no-interactive"]
    )
    assert result.exit_code == 2
    assert "--yes" in _output(result)
    assert not any(c.startswith("sudo -n systemctl reboot") for c in FakeRemote.calls)

    result = runner.invoke(
        app,
        ["service", "reboot", "--yes", "-H", "1.2.3.4", "--pkey", str(key), "--no-interactive"],
    )
    assert result.exit_code == 0, _output(result)
    assert "sudo -n systemctl reboot" in FakeRemote.calls
    assert "[ok] host 1.2.3.4 is rebooting" in _output(result)


def test_reboot_error_ru(tmp_path) -> None:
    key = _key(tmp_path)
    result = runner.invoke(
        app, ["service", "reboot", "--ru", "-H", "1.2.3.4", "--pkey", str(key), "--no-interactive"]
    )
    out = _output(result)
    assert "ошибка:" in out and "--yes" in out


def test_service_logs_writes_local_file(monkeypatch, tmp_path) -> None:
    _stub_transport(monkeypatch, tmp_path)
    key = _key(tmp_path)
    out_dir = tmp_path / "dumpdir"
    result = runner.invoke(
        app,
        ["service", "logs", "--since", "6h", "--out", str(out_dir),
         "-H", "1.2.3.4", "--pkey", str(key), "--no-interactive"],
    )
    assert result.exit_code == 0, _output(result)
    files = list(out_dir.glob("logs-1.2.3.4-*.txt"))
    assert len(files) == 1
    assert "sample journal line" in files[0].read_text(encoding="utf-8")
    assert any(c.startswith("sudo -n journalctl -u xray -u xray-obs-snapshot") for c in FakeRemote.calls)
    assert not any("/tmp/xray-vpn-logs" in c for c in FakeRemote.calls)


def test_service_logs_rejects_bad_since(monkeypatch, tmp_path) -> None:
    _stub_transport(monkeypatch, tmp_path)
    key = _key(tmp_path)
    result = runner.invoke(
        app,
        ["service", "logs", "--since", "yesterday; rm -rf /",
         "-H", "1.2.3.4", "--pkey", str(key), "--no-interactive"],
    )
    assert result.exit_code == 2
    assert "invalid --since" in _output(result)
    assert not any("rm -rf" in c for c in FakeRemote.calls)


def test_service_help_lists_subcommands() -> None:
    result = runner.invoke(app, ["service", "--help"])
    out = _output(result)
    assert "status" in out and "restart" in out and "logs" in out and "reboot" in out
    root = runner.invoke(app, ["--help"])
    assert "service" in _output(root)


def test_repl_help_mentions_service() -> None:
    assert "service status|restart|logs|reboot" in help_text()


def test_service_restart_output(monkeypatch, tmp_path) -> None:
    _stub_transport(monkeypatch, tmp_path)
    key = _key(tmp_path)
    result = runner.invoke(
        app, ["service", "restart", "-H", "1.2.3.4", "--pkey", str(key), "--no-interactive"]
    )
    assert result.exit_code == 0, _output(result)
    assert "[done] xray restarted (active)" in _output(result)
    assert "sudo -n systemctl restart xray" in FakeRemote.calls
    assert FakeRemote.run_kwargs and all(kw["hide"] is True for kw in FakeRemote.run_kwargs)


def test_service_reboot_runs_quiet(monkeypatch, tmp_path) -> None:
    _stub_transport(monkeypatch, tmp_path)
    key = _key(tmp_path)
    result = runner.invoke(
        app,
        ["service", "reboot", "--yes", "-H", "1.2.3.4", "--pkey", str(key), "--no-interactive"],
    )
    assert result.exit_code == 0, _output(result)
    assert FakeRemote.run_kwargs and all(kw["hide"] is True for kw in FakeRemote.run_kwargs)


def test_logs_streams_line_by_line_via_tee(monkeypatch, tmp_path) -> None:
    _stub_transport(monkeypatch, tmp_path)
    key = _key(tmp_path)
    out_file = tmp_path / "dump.txt"
    result = runner.invoke(
        app,
        ["service", "logs", "--since", "6h", "--out", str(out_file),
         "-H", "1.2.3.4", "--pkey", str(key), "--no-interactive"],
    )
    assert result.exit_code == 0, _output(result)
    assert "sample journal line" in out_file.read_text(encoding="utf-8")
    assert "1 lines" in _output(result)
    journal_kwargs = [
        kw for c, kw in zip(FakeRemote.calls, FakeRemote.run_kwargs) if "journalctl" in c
    ]
    assert journal_kwargs and journal_kwargs[-1]["out_stream"] is not None


def test_logs_lines_option_reaches_command(monkeypatch, tmp_path) -> None:
    _stub_transport(monkeypatch, tmp_path)
    key = _key(tmp_path)
    result = runner.invoke(
        app,
        ["service", "logs", "--since", "6h", "--lines", "120", "--out", str(tmp_path / "d.txt"),
         "-H", "1.2.3.4", "--pkey", str(key), "--no-interactive"],
    )
    assert result.exit_code == 0, _output(result)
    assert any("-n 120" in c for c in FakeRemote.calls)


def test_logs_rejects_non_positive_lines(monkeypatch, tmp_path) -> None:
    _stub_transport(monkeypatch, tmp_path)
    key = _key(tmp_path)
    result = runner.invoke(
        app,
        ["service", "logs", "--lines", "0",
         "-H", "1.2.3.4", "--pkey", str(key), "--no-interactive"],
    )
    assert result.exit_code == 2
    assert "invalid --lines" in _output(result)


def test_logs_ctrl_c_saves_partial_and_exits_130(monkeypatch, tmp_path) -> None:
    _stub_transport(monkeypatch, tmp_path)
    FakeRemote.ki_on_prefix = "sudo -n journalctl -u xray -u xray-obs-snapshot"
    FakeRemote.ki_partial = "2026-09-13T00:00:00Z xray[1]: partial line\n"
    key = _key(tmp_path)
    out_file = tmp_path / "partial.txt"
    result = runner.invoke(
        app,
        ["service", "logs", "--since", "6h", "--out", str(out_file),
         "-H", "1.2.3.4", "--pkey", str(key), "--no-interactive"],
    )
    assert result.exit_code == 130
    assert out_file.exists()
    assert "partial line" in out_file.read_text(encoding="utf-8")
    out = _output(result)
    assert "[cancel] interrupted" in out and "1 lines" in out


def test_tee_counts_lines_and_dots(tmp_path: Path) -> None:
    target = tmp_path / "tee.txt"
    tee = service_mod._Tee(target)
    tee.write("a\nb\n")
    assert tee.lines == 2
    tee.write("c\n" + "x\n" * 400)
    tee.flush()
    tee.close()
    assert tee.lines == 403
    content = target.read_text(encoding="utf-8")
    assert content.startswith("a\nb\nc\n")
