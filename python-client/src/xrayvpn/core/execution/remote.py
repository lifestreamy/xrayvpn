"""RemoteExecutor — provision a VPS over SSH (ADR-001 semantics).

Flow: idempotent bootstrap (venv + pinned ansible-core + collection cache) →
tarball upload from the allowlist manifest → server-side inventory (0600) →
ansible-playbook on the server → SFTP fetch of generated client configs →
cleanup per mode. No dependency on GitHub or on the shell clients.
"""

from __future__ import annotations

import secrets
import shlex
import tempfile
import time
from pathlib import Path

from xrayvpn import i18n
from xrayvpn.core import manifest
from xrayvpn.core.config import (
    ANSIBLE_CORE_PIN,
    ANSIBLE_VENV_APT_PKG,
    CONFIG_SOURCE,
    GALAXY_COLLECTION,
    GALAXY_COLLECTION_DIR,
    SERVER_COLLECTIONS,
    SERVER_STAGING,
    SERVER_VENV,
    SWAP_GUARD_MIN_RAM_KB,
    SWAPFILE,
)
from xrayvpn.core.execution.base import DeployRequest, extra_var_args
from xrayvpn.core.inventory import build_inventory
from xrayvpn.core.transport.remote import Remote

DEPLOY_LOCK = "/run/lock/xrayvpn-deploy.lock"
LOCK_MISSING_RC = 76
LOCK_HELD_RC = 75


def new_run_id() -> str:
    return f"{int(time.time())}-{secrets.token_hex(3)}"


def staging_dir(run_id: str) -> str:
    return f"{SERVER_STAGING}-{run_id}"


def fetch_dir(staging: str) -> str:
    return f"{staging}/fetch"


def _locked(command: str) -> str:
    """Serialize mutating server commands; fd-based flock dies with the process."""
    return f"exec 200>{DEPLOY_LOCK}; flock -n 200 || exit {LOCK_HELD_RC}; {command}"


def bootstrap_commands(staging: str) -> list[str]:
    """Idempotent server preparation (venv cached between runs).

    Privileged steps run through `sudo -n` (no-op when the SSH user is root;
    passwordless sudo is required otherwise). The venv line carries an
    apt fallback: Debian/Ubuntu minimal images lack `python3-venv`, so a bare
    `python3 -m venv` fails on ensurepip — retry after installing the package
    (inside `bash -c` we are already root, no extra sudo).
    """
    return [
        f"command -v flock >/dev/null 2>&1 || exit {LOCK_MISSING_RC}",
        _locked("python3 -V"),
        _locked(
            f"sudo -n [ -x {SERVER_VENV}/bin/python ] || "
            f"sudo -n bash -c 'python3 -m venv {SERVER_VENV} || "
            f"{{ apt-get update -y && apt-get install -y {ANSIBLE_VENV_APT_PKG} && "
            f"python3 -m venv {SERVER_VENV}; }}'"
        ),
        _locked(f"sudo -n {SERVER_VENV}/bin/pip install -q ansible-core=={ANSIBLE_CORE_PIN}"),
        _locked(
            f"sudo -n [ -d {SERVER_COLLECTIONS}/{GALAXY_COLLECTION_DIR} ] || "
            f"sudo -n {SERVER_VENV}/bin/ansible-galaxy collection install {GALAXY_COLLECTION} "
            f"-p {SERVER_COLLECTIONS}"
        ),
        _locked(f"mkdir -p {staging} {fetch_dir(staging)}"),
        _locked("find /tmp -maxdepth 1 -name 'xrayvpn-*' -mmin +1440 -exec rm -rf {} + || true"),
    ]


def playbook_command(
    request: DeployRequest, extra_vars: dict[str, object], staging: str
) -> str:
    """The ansible-playbook invocation on the server (collections from the venv)."""
    parts = [
        "cd",
        staging,
        "&&",
        f"ANSIBLE_COLLECTIONS_PATH={SERVER_COLLECTIONS}",
        f"{SERVER_VENV}/bin/ansible-playbook",
        "-i",
        "inventory.yml",
        "deploy.yml",
    ]
    if request.verbosity >= 4:
        parts.append("-vvvv")
    elif request.verbosity == 3:
        parts.append("-vvv")
    if request.debug:
        parts += ["-e", "xray_debug=true"]
    # JSON extra-var: one -e with a shell-quoted JSON object (types preserved).
    flag, payload = extra_var_args(extra_vars)
    parts += [flag, shlex.quote(payload)]
    if request.dry_run:
        parts.append("--check")
    return _locked(" ".join(parts))


def cleanup_commands(mode: str, staging: str) -> list[str]:
    """Cleanup semantics: cleanup keeps the venv cache; full-cleanup removes it."""
    if mode == "full-cleanup":
        return [f"rm -rf {staging} {SERVER_VENV}"]
    if mode == "no-cleanup":
        return []
    return [f"rm -rf {staging}"]


def swap_status_commands() -> list[str]:
    """Detection: total RAM in kB, then the number of active swap entries."""
    return [
        "awk '/MemTotal/{print $2}' /proc/meminfo",
        "tail -n +2 /proc/swaps | wc -l",
    ]


def swap_guard_needed(mem_kb: int, swap_entries: int) -> bool:
    """True only when RAM is below the threshold AND no swap is active."""
    return mem_kb < SWAP_GUARD_MIN_RAM_KB and swap_entries == 0


def swap_guard_commands() -> list[str]:
    """Opt-in 1 GB swapfile; runs only when no active swap exists (never touches
    an existing swap/fstab/sysctl configuration of the user)."""
    return [
        (
            f"sudo -n bash -c 'fallocate -l 1G {SWAPFILE} || "
            f"dd if=/dev/zero of={SWAPFILE} bs=1M count=1024 status=none'"
        ),
        f"sudo -n bash -c 'chmod 600 {SWAPFILE} && mkswap {SWAPFILE} && swapon {SWAPFILE}'",
        (
            f"sudo -n bash -c 'grep -qs \"^{SWAPFILE} \" /etc/fstab || "
            f"echo \"{SWAPFILE} none swap sw 0 0\" >> /etc/fstab'"
        ),
    ]


def fetch_targets(listing: str) -> list[str]:
    """Filter an `ls` listing down to client config files (.json/.yaml)."""
    targets: list[str] = []
    for line in listing.splitlines():
        name = line.strip()
        if name.endswith((".json", ".yaml")):
            targets.append(name)
    return targets


class RemoteExecutor:
    """Orchestrates bootstrap → upload → run → fetch → cleanup over a Remote."""

    def __init__(self, remote: Remote, *, cleanup: str = "cleanup") -> None:
        self._remote = remote
        self.cleanup = cleanup

    def deploy(self, request: DeployRequest, extra_vars: dict[str, object]) -> int:
        staging = staging_dir(new_run_id())
        for command in bootstrap_commands(staging):
            result = self._remote.run(command, warn=True)
            if result.failed:
                print(
                    i18n.t("EXEC_BOOTSTRAP_FAIL", command=command, err=result.stderr)
                )
                return result.return_code

        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)

            bundle = temp / "bundle.tar.gz"
            manifest.build_tarball(request.repo_root, bundle)
            self._remote.put(bundle, f"{staging}/bundle.tar.gz")
            extract = (
                f"tar -xzf {staging}/bundle.tar.gz -C {staging} "
                f"&& rm -f {staging}/bundle.tar.gz"
            )
            result = self._remote.run(extract, warn=True)
            if result.failed:
                print(i18n.t("EXEC_EXTRACT_FAIL", err=result.stderr))
                return result.return_code

            inv = temp / "inventory.yml"
            inv.write_text(
                build_inventory(
                    {},
                    connection="local",
                    python_interpreter=f"{SERVER_VENV}/bin/python",
                ),
                encoding="utf-8",
            )
            self._remote.put(inv, f"{staging}/inventory.yml")
            self._remote.run(f"chmod 0600 {staging}/inventory.yml")

            result = self._remote.run(
                playbook_command(request, extra_vars, staging), warn=True
            )
            if result.failed:
                print(i18n.t("EXEC_PLAYBOOK_FAIL", rc=result.return_code))
                return result.return_code

        if not request.dry_run:
            self.fetch_configs(request.resolved_clients_dir(), fetch_dir(staging))

        for command in cleanup_commands(self.cleanup, staging):
            self._remote.run(command, warn=True)
        return 0

    def fetch_configs(self, clients_dir: Path, staging_fetch_dir: str) -> None:
        """Stage the generated configs via sudo, then download them by SFTP."""
        clients_dir.mkdir(parents=True, exist_ok=True)
        # Glob must expand INSIDE sudo (the SSH user cannot read /root/vpn-configs);
        # root's umask may deny reads, so grant explicit world-read access.
        prepare = (
            f"sudo -n bash -c 'mkdir -p {staging_fetch_dir} && "
            f"cp {CONFIG_SOURCE}/*.json {CONFIG_SOURCE}/*.yaml {staging_fetch_dir}/ "
            f"2>/dev/null && chmod -R a+rX {staging_fetch_dir} || true'"
        )
        self._remote.run(prepare, warn=True)
        listing = self._remote.run(f"ls {staging_fetch_dir}", warn=True)
        for name in fetch_targets(listing.stdout):
            remote_path = f"{staging_fetch_dir}/{name}"
            local_path = clients_dir / name
            self._remote.get(remote_path, local_path)
            print(i18n.t("EXEC_FETCHED", name=name))