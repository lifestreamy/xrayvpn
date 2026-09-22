"""LocalExecutor — ansible runs on this machine against a remote VPS over SSH.

Windows: the existing WSL bridge is the transport (same venv requirements as
`scripts/test/local_test.py`); Linux/macOS: the control node runs natively.
The ansible TARGET is always the VPS — the old local-target execution was a
test-bench trick and now lives only in `scripts/test` + molecule.

Command builders are pure functions; the class resolves the control-node
environment (preflight), writes a 0600 ssh-target inventory, runs the
playbook, then pulls generated client configs with an `ansible.builtin.fetch`
playbook over the same SSH credentials.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

from xrayvpn.core import runtime_paths, wsl
from xrayvpn.core.config import (
    COLLECTIONS_DIR,
    CONFIG_SOURCE,
    DEFAULT_WSL_VENV,
    GALAXY_COLLECTION,
    GALAXY_COLLECTION_DIR,
    SERVER_FETCH_PREFIX,
    SSH_ARGS,
)
from xrayvpn.core.execution.base import DeployRequest, extra_var_args

VENV_HINT = (
    "create it from the repository root: python3 scripts/dev/setup_test_env.py "
    "(makes ~/xray-venv with ansible-core; password auth additionally needs "
    "sshpass) — or use --execution remote instead"
)
VENV_HINT_BINARY = (
    "install ansible-core on this machine (pipx install ansible-core, "
    "pip install ansible-core, a distro package, or WSL; password auth "
    "additionally needs sshpass) — or use --execution remote instead"
)


def venv_hint(*, frozen: bool | None = None) -> str:
    """Venv-repair hint for the current install shape."""
    is_packaged = runtime_paths.is_frozen() if frozen is None else frozen
    return VENV_HINT_BINARY if is_packaged else VENV_HINT


SSHPASS_HINT = (
    "local execution with a password needs sshpass on the control node "
    "(`sudo apt-get install sshpass` in WSL / your package manager elsewhere) "
    "— or provide --pkey"
)

_WINDOWS_PATH = re.compile(r"^[A-Za-z]:[\\/]")

FETCH_PLAYBOOK = """- name: Fetch client configs
  hosts: vpn
  gather_facts: false
  tasks:
    - name: Create private staging dir for the generated configs
      ansible.builtin.tempfile:
        path: /tmp
        prefix: "{fetch_prefix}"
        state: directory
        mode: 0700
      register: stage
      become: true
    - name: Copy generated configs into staging
      ansible.builtin.shell: >
        cp {config_source}/*.json {config_source}/*.yaml "{{{{ stage.path }}}}" 2>/dev/null;
        true
      changed_when: false
      become: true
    - name: Find staged configs
      ansible.builtin.find:
        paths: "{{{{ stage.path }}}}"
        patterns: ["*.json", "*.yaml"]
      become: true
      register: staged
    - name: Fail when the server produced no client configs to fetch
      ansible.builtin.assert:
        that: staged.matched > 0
        fail_msg: "no client configs under {config_source}: check the deploy
          and whether --user ({config_source} is root-owned, become is required)"
      become: true
    - name: Copy configs to the control node
      ansible.builtin.fetch:
        src: "{{{{ item.path }}}}"
        dest: "{dest}/"
        flat: true
      loop: "{{{{ staged.files }}}}"
      loop_control:
        label: "{{{{ item.path }}}}"
      become: true
    - name: Remove the private staging dir
      ansible.builtin.file:
        path: "{{{{ stage.path }}}}"
        state: absent
      become: true
"""


def build_ssh_inventory_vars(target: dict[str, str]) -> dict[str, str]:
    """Host vars for an ssh-target inventory; the host name stays `vpn`.
    A user/port that the ssh config fully governs is omitted, not pinned."""
    params: dict[str, str] = {"ansible_host": target["host"]}
    if target.get("user"):
        params["ansible_user"] = target["user"]
    if target.get("port"):
        params["ansible_port"] = str(target["port"])
    if target.get("pkey"):
        params["ansible_ssh_private_key_file"] = target["pkey"]
    elif target.get("password"):
        params["ansible_ssh_pass"] = target["password"]
    return params


class LocalExecutor:
    def __init__(
        self,
        *,
        wsl_venv: str = DEFAULT_WSL_VENV,
        wsl_distro: str | None = None,
    ) -> None:
        self.wsl_venv = wsl_venv
        self.wsl_distro = wsl_distro
        self._wsl_home: str | None = None

    # --- control-node paths (pure) ---

    def venv_binary(self, wsl_home: str | None = None) -> str:
        """Path to the ansible-playbook binary the executor will invoke."""
        venv = self.wsl_venv
        if wsl_home and venv.startswith("~"):
            venv = wsl_home + venv[1:]
        return f"{venv}/bin/ansible-playbook"

    def galaxy_binary(self, wsl_home: str | None = None) -> str:
        return self.venv_binary(wsl_home=wsl_home).replace("ansible-playbook", "ansible-galaxy")

    def collections_path(self, wsl_home: str | None = None) -> str:
        base = wsl_home or str(Path.home())
        return f"{base}/{COLLECTIONS_DIR}"

    # --- command construction (pure, unit-testable) ---

    def deploy_argv(self, request: DeployRequest, inventory: Path) -> list[str]:
        parts = [self.venv_binary_for_run(), "deploy.yml", "-i", str(inventory)]
        if request.verbosity >= 4:
            parts.append("-vvvv")
        elif request.verbosity == 3:
            parts.append("-vvv")
        if request.debug:
            parts += ["-e", "xray_debug=true"]
        parts += extra_var_args(request.overrides)
        if request.dry_run:
            parts.append("--check")
        return parts

    def fetch_argv(self, inventory: Path, playbook: Path) -> list[str]:
        return [self.venv_binary_for_run(), "-i", str(inventory), str(playbook)]

    def _fetch_dest(self, clients_dir: Path) -> str:
        if wsl.is_windows():
            return wsl.to_wsl_path(str(clients_dir))
        return clients_dir.as_posix()

    def fetch_playbook_text(self, clients_dir: Path) -> str:
        return FETCH_PLAYBOOK.format(
            fetch_prefix=SERVER_FETCH_PREFIX,
            config_source=CONFIG_SOURCE,
            dest=self._fetch_dest(clients_dir),
        )

    def build_wsl_script(self, argv: list[str], repo_root: Path) -> str:
        home = self._wsl_home or "$HOME"
        translated = [
            wsl.to_wsl_path(part) if _WINDOWS_PATH.match(part) else part for part in argv
        ]
        quoted = " ".join(wsl.quote(part) for part in translated)
        colls = f"$HOME/{COLLECTIONS_DIR}"
        gal = self.galaxy_binary(wsl_home=home)
        return (
            f"cd {wsl.quote(wsl.to_wsl_path(repo_root))} && "
            f"[ -d {colls}/{GALAXY_COLLECTION_DIR} ] || "
            f"{wsl.quote(gal)} collection install {GALAXY_COLLECTION} -p {colls} || exit 22; "
            f"ANSIBLE_FORCE_COLOR=1 "
            f"ANSIBLE_COLLECTIONS_PATH={colls} "
            f"ANSIBLE_SSH_ARGS={wsl.quote(SSH_ARGS)} {quoted}"
        )

    # --- executor surface ---

    def _native_binary(self) -> str | None:
        configured = Path(self.wsl_venv).expanduser() / "bin" / "ansible-playbook"
        if configured.is_file():
            return str(configured)
        return shutil.which("ansible-playbook")

    def _native_galaxy(self) -> str | None:
        configured = Path(self.wsl_venv).expanduser() / "bin" / "ansible-galaxy"
        if configured.is_file():
            return str(configured)
        return shutil.which("ansible-galaxy")

    def preflight(self, *, password_auth: bool) -> None:
        """Check the control-node environment; raise RuntimeError with a hint."""
        if wsl.is_windows():
            if not wsl.wsl_available():
                raise RuntimeError(
                    "local execution on Windows requires WSL; install WSL "
                    "(wsl --install) or use --execution remote"
                )
            self._wsl_home = wsl.wsl_home(self.wsl_distro)
            binary = self.venv_binary(wsl_home=self._wsl_home)
            if not wsl.path_exists(binary, distro=self.wsl_distro):
                raise RuntimeError(
                    f"ansible-playbook not found in WSL at {binary}; {venv_hint()}"
                )
            if password_auth and not wsl.command_exists("sshpass", distro=self.wsl_distro):
                raise RuntimeError(SSHPASS_HINT)
            return
        if self._native_binary() is None:
            raise RuntimeError(
                f"ansible-playbook not found ({self.wsl_venv}/bin or PATH); {venv_hint()}"
            )
        if password_auth and shutil.which("sshpass") is None:
            raise RuntimeError(SSHPASS_HINT)

    def venv_binary_for_run(self) -> str:
        """Binary path in the coordinate space of the runner (preflight first)."""
        if wsl.is_windows():
            return self.venv_binary(wsl_home=self._wsl_home)
        return self._native_binary() or self.venv_binary()

    def run(self, argv: list[str], request: DeployRequest) -> int:
        if not wsl.is_windows():
            colls = Path(self.collections_path())
            if not (colls / Path(GALAXY_COLLECTION_DIR)).is_dir():
                galaxy = self._native_galaxy()
                if galaxy is None or subprocess.call(
                    [galaxy, "collection", "install", GALAXY_COLLECTION, "-p", str(colls)]
                ) != 0:
                    return 22
            env = dict(os.environ)
            env.setdefault("ANSIBLE_FORCE_COLOR", "1")
            env["ANSIBLE_COLLECTIONS_PATH"] = str(colls)
            env.setdefault("ANSIBLE_SSH_ARGS", SSH_ARGS)
            return subprocess.call(argv, cwd=str(request.repo_root), env=env)
        script = self.build_wsl_script(argv, request.repo_root)
        print(f"[local] wsl bash -lc {wsl.quote(script)}")
        return wsl.run_script(script, distro=self.wsl_distro)

    def deploy(self, request: DeployRequest, inventory: Path) -> int:
        return self.run(self.deploy_argv(request, inventory), request)

    def fetch_configs(self, request: DeployRequest, inventory: Path) -> int:
        clients = request.resolved_clients_dir()
        clients.mkdir(parents=True, exist_ok=True)
        playbook = request.resolved_workspace() / ".xrayvpn-fetch-playbook.yml"
        playbook.write_text(self.fetch_playbook_text(clients), encoding="utf-8")
        try:
            return self.run(self.fetch_argv(inventory, playbook), request)
        finally:
            playbook.unlink(missing_ok=True)

    def cleanup(self, request: DeployRequest) -> None:
        """Nothing to clean on the target for local execution; run() removes the
        ad-hoc fetch playbook itself."""
