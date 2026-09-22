#!/usr/bin/env python3
"""scripts/test/local_test.py — runs the project's local verification.

Looks up an existing venv (does NOT create one) at the path given by
--venv (default: $HOME/xray-venv), then runs:
    ansible-playbook --syntax-check -i inventory.yml.example deploy.yml
    molecule test

Exits non-zero on the first failure. Exit code 2 means the venv was not
found — bootstrap it with `python3 scripts/dev/setup_test_env.py` first.

Usage:
    python3 scripts/test/local_test.py
    python3 scripts/test/local_test.py --skip-molecule   # syntax-check only
    python3 scripts/test/local_test.py --venv /path/to/venv
    python3 scripts/test/local_test.py --runtime native  # molecule with xray_runtime override
    python3 scripts/test/local_test.py --runtime docker  # legacy escape hatch
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

SUPPORTED_RUNTIMES = ("native", "docker")


def run_in_venv(venv_dir: Path, cmd: list[str]) -> int:
    venv_bin = venv_dir / "bin"
    env = os.environ.copy()
    env["PATH"] = f"{venv_bin}{os.pathsep}{env.get('PATH', '')}"
    env["VIRTUAL_ENV"] = str(venv_dir)
    # Visible per-task progress so a long converge does not look hung; ephemeral test keys may echo — fine.
    env.setdefault("ANSIBLE_VERBOSITY", "3")
    env.setdefault("ANSIBLE_FORCE_COLOR", "1")
    env.setdefault("ANSIBLE_STDOUT_CALLBACK", "default")
    print(f"[local-test] {' '.join(cmd)}")
    return subprocess.call(cmd, env=env)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--venv",
        default=str(Path.home() / "xray-venv"),
        help="Path to an existing Python venv that has ansible-playbook and molecule "
             "(default: $HOME/xray-venv). The venv is NOT created by this script.",
    )
    parser.add_argument(
        "--skip-molecule",
        action="store_true",
        help="Run only ansible-playbook --syntax-check, skip molecule test",
    )
    parser.add_argument(
        "--runtime",
        choices=SUPPORTED_RUNTIMES,
        default=None,
        help="xray_runtime passed to molecule as --extra-vars (native|docker). "
             "When omitted, the value from config/settings.yml is used.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Pass --debug to molecule (verbose ansible output; persisted logs "
             "under ~/.cache/molecule/.../logs for post-mortem).",
    )
    args = parser.parse_args()

    venv_dir = Path(args.venv).expanduser()
    if not venv_dir.exists():
        print(
            f"[local-test] {venv_dir} missing — run 'python3 scripts/setup_test_env.py' first.",
            file=sys.stderr,
        )
        return 2

    repo_root = Path(__file__).resolve().parents[2]
    os.chdir(repo_root)

    venv_bin = venv_dir / "bin"

    rc = run_in_venv(venv_dir, [
        str(venv_bin / "ansible-playbook"),
        "--syntax-check",
        "-i", "inventory.yml.example",
        "deploy.yml",
    ])
    if rc != 0:
        print(f"[local-test] ansible-playbook --syntax-check exited with rc={rc}", file=sys.stderr)
        return rc

    if not args.skip_molecule:
        mol_cmd = [str(venv_bin / "molecule")]
        if args.debug:
            mol_cmd.append("--debug")
        mol_cmd.append("test")
        if args.runtime is not None:
            mol_cmd += ["--", "-e", f"xray_runtime={args.runtime}"]
        rc = run_in_venv(venv_dir, mol_cmd)
        if rc != 0:
            print(f"[local-test] molecule test exited with rc={rc}", file=sys.stderr)
            return rc

    print("[local-test] OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
