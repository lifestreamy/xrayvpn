"""Tests for core/inventory.py: local and server inventory rendering."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from xrayvpn.core.inventory import (
    build_inventory,
    parse_user_inventory,
    validate_connection,
    write_inventory,
)


def test_local_inventory_connection(tmp_path) -> None:
    content = build_inventory({"xray_runtime": "native"}, connection="local")
    data = yaml.safe_load(content)
    host = data["all"]["hosts"]["vpn"]
    assert host["ansible_connection"] == "local"
    assert "ansible_python_interpreter" not in host
    assert data["all"]["vars"] == {"xray_runtime": "native"}


def test_ssh_inventory_host_params() -> None:
    content = build_inventory(
        {},
        connection="ssh",
        host_params={
            "ansible_host": "203.0.113.7",
            "ansible_user": "root",
            "ansible_port": "22",
            "ansible_ssh_private_key_file": "/home/tim/.ssh/id",
        },
    )
    host = yaml.safe_load(content)["all"]["hosts"]["vpn"]
    assert host["ansible_connection"] == "ssh"
    assert host["ansible_host"] == "203.0.113.7"
    assert host["ansible_ssh_private_key_file"] == "/home/tim/.ssh/id"


def test_server_inventory_interpreter() -> None:
    content = build_inventory(
        {"warp_enabled": False},
        python_interpreter="/opt/xrayvpn-venv/bin/python",
    )
    data = yaml.safe_load(content)
    host = data["all"]["hosts"]["vpn"]
    assert host["ansible_python_interpreter"] == "/opt/xrayvpn-venv/bin/python"


def test_write_inventory_file(tmp_path) -> None:
    path = write_inventory(tmp_path, build_inventory({}, connection="local"))
    assert path.name == ".xrayvpn-inventory.yml"
    assert "hosts" in path.read_text(encoding="utf-8")


def test_parse_user_inventory_split(tmp_path: Path) -> None:
    (tmp_path / "inventory.yml").write_text(
        "all:\n"
        "  hosts:\n"
        "    my_vps:\n"
        "      ansible_host: 1.2.3.4\n"
        "      ansible_user: root\n"
        "      ansible_ssh_private_key_file: ~/.ssh/id_rsa\n"
        "      xray_port: 8443\n"
        "  vars:\n"
        "    num_clients: 2\n",
        encoding="utf-8",
    )
    connection, extra_vars = parse_user_inventory(tmp_path)
    assert connection == {
        "ansible_host": "1.2.3.4",
        "ansible_user": "root",
        "ansible_ssh_private_key_file": "~/.ssh/id_rsa",
    }
    assert extra_vars == {"xray_port": 8443, "num_clients": 2}


def test_parse_user_inventory_missing(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="not found"):
        parse_user_inventory(tmp_path)


def test_parse_user_inventory_missing_hint(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="inventory.yml.example"):
        parse_user_inventory(tmp_path)


def test_parse_user_inventory_template_shaped_empties(tmp_path: Path) -> None:
    # copied from inventory.yml.example: only ansible_host filled, other
    # scalars left empty; empty values must stay unset (never str(None)="None")
    (tmp_path / "inventory.yml").write_text(
        "all:\n"
        "  hosts:\n"
        "    your_host:\n"
        "      ansible_host: 1.2.3.4\n"
        "      ansible_user:\n"
        "      ansible_port:\n"
        "      ansible_ssh_private_key_file: ~/.ssh/id_rsa\n"
        "      ansible_ssh_pass:\n",
        encoding="utf-8",
    )
    connection, _extra_vars = parse_user_inventory(tmp_path)
    assert "None" not in connection.values()
    problems = validate_connection(connection)
    assert any("ansible_user" in p for p in problems)
    assert any("ansible_port" in p for p in problems)
    # key filled + empty pass line must NOT trigger the both-set error
    assert not any("leave only one" in p for p in problems)


def test_validate_connection_ok() -> None:
    connection = {
        "ansible_host": "1.2.3.4",
        "ansible_user": "root",
        "ansible_port": "22",
        "ansible_ssh_private_key_file": "~/.ssh/id_rsa",
    }
    assert validate_connection(connection) == []


def test_validate_connection_missing_fields() -> None:
    problems = validate_connection({"ansible_user": "root"})
    assert any("ansible_host" in p for p in problems)
    assert any("ansible_port" in p for p in problems)
    # missing auth is intentionally OK: the CLI prompts for the password
    assert not any("auth" in p for p in problems)


def test_validate_connection_auth_mutex() -> None:
    connection = {
        "ansible_host": "1.2.3.4",
        "ansible_user": "root",
        "ansible_port": "22",
        "ansible_ssh_private_key_file": "~/.ssh/id_rsa",
        "ansible_ssh_pass": "secret",
    }
    assert any("leave only one" in p for p in validate_connection(connection))


def test_validate_connection_non_numeric_port() -> None:
    connection = {
        "ansible_host": "1.2.3.4",
        "ansible_user": "root",
        "ansible_port": "ssh",
        "ansible_ssh_pass": "secret",
    }
    assert any("must be numeric" in p for p in validate_connection(connection))