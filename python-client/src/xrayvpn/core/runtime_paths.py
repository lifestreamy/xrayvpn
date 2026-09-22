"""Install-shape path contract: repo clone, standalone binary, plain wheel.

Three roots replace the single repo-root walk:

- payload — the source tree (`deploy.yml`, `roles/`, `config/`,
  `inventory.yml.example`): the live repo in a clone, otherwise the
  `xrayvpn/payload` bundle shipped inside the binary/wheel;
- workspace — the writable home for user files (`inventory.yml`,
  `.xrayvpn-inventory.yml`, the fetch playbook, `downloaded-clients/`):
  the repo in a clone, otherwise `$XRAYVPN_HOME` / the exe folder / cwd;
- repo (ansible root) — what the tarball is built from and local ansible
  runs in: the payload root in a clone, a fresh temp copy of the read-only
  bundle overlaid with the workspace `config/settings.yml` otherwise.

In a repo clone all three coincide, so dev behaviour is unchanged. Every
helper takes injectable flags/paths, so unit tests never emulate a frozen
interpreter globally.
"""

from __future__ import annotations

import atexit
import os
import shutil
import sys
import tempfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

PAYLOAD_DIRNAME = "payload"
PAYLOAD_MARKER = "deploy.yml"
PROJECT_ROLE_SUBPATH = Path("roles") / "xray_vpn"
SETTINGS_SUBPATH = Path("config") / "settings.yml"
WORKSPACE_HOME_ENV = "XRAYVPN_HOME"

PERSONAL_INVENTORY_NAME = "inventory.yml"
PERSONAL_INVENTORY_EXAMPLE_NAME = "inventory.yml.example"
NOT_WRITABLE_WORKSPACE_HINT = (
    "no writable workspace folder: place xrayvpn in a user-writable directory "
    "or set XRAYVPN_HOME to one"
)

PACKAGE_DIR = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class RunRoots:
    payload: Path
    workspace: Path
    repo: Path


def is_frozen(
    *,
    sys_ns: object | None = None,
    compiled_ns: Mapping[str, object] | None = None,
) -> bool:
    """Nuitka deliberately never sets sys.frozen; its marker is __compiled__.

    The check is on this module's globals — the whole xrayvpn package is
    compiled together, so any compiled module carries it.
    """
    mod = sys if sys_ns is None else sys_ns
    markers = globals() if compiled_ns is None else compiled_ns
    return bool(getattr(mod, "frozen", False)) or "__compiled__" in markers


def find_repo_dir(start: Path | None = None) -> Path | None:
    """Walk up from `start` to the xray-ansible clone.

    The match is composite (deploy.yml + roles/xray_vpn): a lone deploy.yml
    from some unrelated Ansible project must never hijack the packaged
    binary away from its bundled payload.
    """
    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if (candidate / PAYLOAD_MARKER).is_file() and (candidate / PROJECT_ROLE_SUBPATH).is_dir():
            return candidate
    return None


def bundled_payload_root(*, package_dir: Path | None = None) -> Path:
    """The packaged `xrayvpn/payload` tree (extracted onefile, PyInstaller
    _MEIPASS and wheel site-packages resolve identically), marker-checked."""
    bundle = (package_dir or PACKAGE_DIR) / PAYLOAD_DIRNAME
    if not (bundle / PAYLOAD_MARKER).is_file():
        raise RuntimeError(
            f"playbook payload not found at {bundle}; this xrayvpn install or "
            "binary is incomplete — use the standalone binary from the "
            "project releases, or run xrayvpn from inside a clone of the "
            "xray-ansible repository"
        )
    return bundle


def payload_root(
    *,
    cwd: Path | None = None,
    package_dir: Path | None = None,
) -> Path:
    """Repo walk first (a clone always wins), then the bundled payload."""
    repo = find_repo_dir(cwd)
    if repo is not None:
        return repo
    return bundled_payload_root(package_dir=package_dir)


def _writable(path: Path) -> bool:
    return os.access(path, os.W_OK)


def _state_workspace(env: Mapping[str, str], home: Path) -> Path:
    if sys.platform == "win32":
        base = env.get("LOCALAPPDATA") or str(home / "AppData" / "Local")
        return Path(base) / "xrayvpn"
    if sys.platform == "darwin":
        return home / "Library" / "Application Support" / "xrayvpn"
    base = env.get("XDG_DATA_HOME") or str(home / ".local" / "share")
    return Path(base) / "xrayvpn"


def _packaged_workspace(
    resolved_cwd: Path,
    env: Mapping[str, str] | None,
    argv: Sequence[str] | None,
    home: Path | None = None,
) -> Path:
    """Files live next to the program: $XRAYVPN_HOME → exe folder (when
    writable) → per-user state folder → cwd; nothing writable raises early
    with advice instead of a PermissionError mid-wizard.

    sys.argv[0] is the original exe path in both packagers (Nuitka onefile
    docs, PyInstaller launcher), so the workspace survives the temp extract.
    """
    environment = os.environ if env is None else env
    home_dir = Path.home() if home is None else home
    exe_dir: Path | None = None
    home_override = (environment.get(WORKSPACE_HOME_ENV) or "").strip()
    if home_override:
        return Path(home_override).expanduser().resolve()
    args = sys.argv if argv is None else argv
    if args and args[0]:
        exe_dir = Path(args[0]).resolve().parent
    if exe_dir is not None and _writable(exe_dir):
        return exe_dir
    state = _state_workspace(environment, home_dir)
    if state.is_dir() and _writable(state):
        return state
    if _writable(resolved_cwd):
        return resolved_cwd
    try:
        state.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise RuntimeError(NOT_WRITABLE_WORKSPACE_HINT) from exc
    return state


def workspace_root(
    *,
    cwd: Path | None = None,
    frozen: bool | None = None,
    env: Mapping[str, str] | None = None,
    argv: Sequence[str] | None = None,
    home: Path | None = None,
) -> Path:
    """Writable home: repo in a clone, packaged workspace when frozen, else cwd."""
    resolved_cwd = (cwd or Path.cwd()).resolve()
    is_packaged = is_frozen() if frozen is None else frozen
    if is_packaged:
        return _packaged_workspace(resolved_cwd, env, argv, home)
    return find_repo_dir(resolved_cwd) or resolved_cwd


def stage_bundle(payload: Path, workspace: Path, dest: Path) -> Path:
    """Copy the read-only payload into `dest` and overlay the user settings.

    A workspace `config/settings.yml` wins over the bundled default; when
    the bundle carries no settings at all an empty one is created so
    load_settings keeps its contract.
    """
    shutil.copytree(payload, dest)
    user_settings = workspace / SETTINGS_SUBPATH
    if user_settings.is_file():
        target = dest / SETTINGS_SUBPATH
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(user_settings, target)
    elif not (payload / SETTINGS_SUBPATH).is_file():
        settings_dest = dest / SETTINGS_SUBPATH
        settings_dest.parent.mkdir(parents=True, exist_ok=True)
        settings_dest.write_text("", encoding="utf-8")
    return dest


_STAGED_TEMP_ROOTS: set[Path] = set()


def _drop_staged_temps() -> None:
    for root in tuple(_STAGED_TEMP_ROOTS):
        shutil.rmtree(root, ignore_errors=True)
    _STAGED_TEMP_ROOTS.clear()


atexit.register(_drop_staged_temps)


def _make_temp_root() -> Path:
    return Path(tempfile.mkdtemp(prefix="xrayvpn-payload-"))


def resolve_roots(
    *,
    cwd: Path | None = None,
    frozen: bool | None = None,
    package_dir: Path | None = None,
    env: Mapping[str, str] | None = None,
    argv: Sequence[str] | None = None,
    find_repo: Callable[[], Path] | None = None,
    new_temp_root: Callable[[], Path] | None = None,
) -> RunRoots:
    """Compose the three roots; stage the bundle when it is read-only.

    `find_repo` keeps the config-level repo walk (raises when absent)
    injectable: the repo walk wins over the bundle, everything else is
    identical to calling the primitives directly.
    """
    resolved_cwd = (cwd or Path.cwd()).resolve()
    is_packaged = is_frozen() if frozen is None else frozen
    lookup: Callable[[], Path] = find_repo or (lambda: require_repo_root(resolved_cwd))
    try:
        repo = lookup()
    except RuntimeError:
        repo = None
    if repo is not None:
        workspace = repo if not is_packaged else _packaged_workspace(resolved_cwd, env, argv)
        return RunRoots(payload=repo, workspace=workspace, repo=repo)
    payload = bundled_payload_root(package_dir=package_dir)
    workspace = (
        _packaged_workspace(resolved_cwd, env, argv)
        if is_packaged
        else resolved_cwd
    )
    temp_root = (new_temp_root or _make_temp_root)()
    staged = stage_bundle(payload, workspace, temp_root / "repo")
    _STAGED_TEMP_ROOTS.add(temp_root)
    return RunRoots(payload=payload, workspace=workspace, repo=staged)


def require_repo_root(start: Path | None = None) -> Path:
    """The config-level contract: repo walk that raises when no clone is found."""
    repo = find_repo_dir(start)
    if repo is None:
        current = (start or Path.cwd()).resolve()
        raise RuntimeError(
            f"repository root not found (no {PAYLOAD_MARKER}) from {current}"
        )
    return repo
