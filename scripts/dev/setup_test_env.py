#!/usr/bin/env python3
"""scripts/dev/setup_test_env.py — bootstrap local test environment (WSL Ubuntu).

Idempotent. Bootstraps a WSL Ubuntu (or any Debian-family Linux) for running
ansible-playbook + molecule locally. Intended for developers on a fresh box
and as a reference for CI (the same commands run in GitHub Actions runners).

Usage:
    python3 scripts/dev/setup_test_env.py

After it finishes:
    source ~/xray-venv/bin/activate
    cd <repo-root>
    python3 scripts/test/local_test.py
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

VENV_DIR = Path.home() / "xray-venv"
REQUIRED_APT = ("python3-venv", "python3-pip", "docker.io")
REQUIRED_PIP = (
    "ansible-core",
    "molecule",
    "molecule-plugins[docker]",
    "docker",
)
GALAXY_COLLECTION = ("community.general",)


def run(cmd: list[str], **kwargs) -> None:
    print(f"[setup] $ {' '.join(cmd)}")
    subprocess.run(cmd, check=True, **kwargs)


def main() -> int:
    print("[setup] Updating apt cache...")
    run(["sudo", "apt-get", "update", "-qq"])

    print(f"[setup] Installing system packages: {' '.join(REQUIRED_APT)}")
    run(["sudo", "apt-get", "install", "-y", "-qq", *REQUIRED_APT])

    # Docker group — required so `docker ps` works without sudo.
    groups = subprocess.run(["id", "-nG"], capture_output=True, text=True, check=True).stdout
    if "docker" not in groups.split():
        print(f"[setup] Adding {os.environ['USER']} to the docker group...")
        run(["sudo", "usermod", "-aG", "docker", os.environ["USER"]])
        print("[setup] NOTE: log out of WSL and back in (or run 'newgrp docker') for the group to take effect.")

    if not VENV_DIR.exists():
        print(f"[setup] Creating venv at {VENV_DIR}...")
        run(["python3", "-m", "venv", str(VENV_DIR)])

    venv_bin = VENV_DIR / "bin"
    pip = venv_bin / "pip"

    print("[setup] Upgrading pip...")
    run([str(pip), "install", "--upgrade", "pip", "--quiet"])

    print(f"[setup] Installing Python packages: {' '.join(REQUIRED_PIP)}")
    run([str(pip), "install", "--quiet", *REQUIRED_PIP])

    print(f"[setup] Installing Ansible collections: {' '.join(GALAXY_COLLECTION)}")
    run([str(venv_bin / "ansible-galaxy"), "collection", "install", *GALAXY_COLLECTION, "--quiet"])

    print()
    print("[setup] Done.")
    print("[setup] Next steps:")
    print(f"[setup]   source {VENV_DIR}/bin/activate")
    print("[setup]   cd <repo-root>")
    print("[setup]   python3 scripts/local_test.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())