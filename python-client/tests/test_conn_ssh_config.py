"""`~/.ssh/config` alias resolution for service/deploy connections."""

from __future__ import annotations

from pathlib import Path

from xrayvpn.core.conn import apply_ssh_config, resolve_connection, ssh_config_entry


def _write_config(tmp_path: Path) -> tuple[Path, Path]:
    key = tmp_path / "id_alias"
    key.write_text("fake", encoding="utf-8")
    cfg = tmp_path / "ssh_config"
    cfg.write_text(
        "Host myvps\n"
        "  HostName 203.0.113.9\n"
        "  User admin\n"
        "  Port 2222\n"
        f"  IdentityFile {key.as_posix()}\n"
        "\n"
        "Host bare\n"
        "  HostName 203.0.113.10\n",
        encoding="utf-8",
    )
    return cfg, key


def test_alias_maps_all_fields(tmp_path: Path) -> None:
    cfg, key = _write_config(tmp_path)
    host, user, port, identity = apply_ssh_config("myvps", "root", 22, config_path=cfg)
    assert (host, user, port) == ("203.0.113.9", "admin", 2222)
    assert identity == str(key)


def test_alias_keeps_explicit_user_port(tmp_path: Path) -> None:
    cfg, _ = _write_config(tmp_path)
    host, user, port, _identity = apply_ssh_config("myvps", "deploy", 2200, config_path=cfg)
    assert (host, user, port) == ("203.0.113.9", "deploy", 2200)


def test_alias_without_identity(tmp_path: Path) -> None:
    cfg, _ = _write_config(tmp_path)
    host, user, port, identity = apply_ssh_config("bare", "root", 22, config_path=cfg)
    assert (host, user, port, identity) == ("203.0.113.10", "root", 22, None)


def test_unknown_host_and_missing_config_are_noop(tmp_path: Path) -> None:
    cfg, _ = _write_config(tmp_path)
    assert apply_ssh_config("plain.example", "root", 22, config_path=cfg) == (
        "plain.example",
        "root",
        22,
        None,
    )
    assert apply_ssh_config("h", "root", 22, config_path=tmp_path / "missing") == (
        "h",
        "root",
        22,
        None,
    )


def test_resolve_connection_uses_alias(tmp_path: Path) -> None:
    cfg, key = _write_config(tmp_path)
    conn = resolve_connection(
        workspace=tmp_path,
        example_dir=tmp_path,
        host="myvps",
        no_interactive=True,
        ssh_config_path=cfg,
    )
    assert conn.host == "203.0.113.9"
    assert conn.user == "admin" and conn.port == 2222
    assert conn.pkey == str(key) and conn.password is None


def test_resolve_connection_alias_yields_to_password(tmp_path: Path) -> None:
    cfg, _ = _write_config(tmp_path)
    conn = resolve_connection(
        workspace=tmp_path,
        example_dir=tmp_path,
        host="myvps",
        password="pw",
        no_interactive=True,
        ssh_config_path=cfg,
    )
    assert conn.pkey is None and conn.password == "pw"
    assert conn.host == "203.0.113.9" and conn.user == "admin"


def test_ssh_config_entry_exposes_raw_lookup(tmp_path: Path) -> None:
    cfg, _ = _write_config(tmp_path)
    entry = ssh_config_entry("myvps", config_path=cfg)
    assert entry is not None
    assert entry["hostname"] == "203.0.113.9"
    assert entry["user"] == "admin"
    assert str(entry["port"]) == "2222"
    assert entry["identityfile"]
    bare = ssh_config_entry("bare", config_path=cfg)
    assert bare and bare["hostname"] == "203.0.113.10"
    assert ssh_config_entry("plain.example", config_path=cfg) is None
    assert ssh_config_entry("h", config_path=tmp_path / "missing") is None
