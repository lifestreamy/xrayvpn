"""Install-source classification for `xrayvpn update`.

Only loose standalone binaries may be replaced by the updater; every
package-managed copy belongs to its manager. Classification uses positive
signals only (path ownership, tool receipts, metadata): a missing or
conflicting signal yields UNKNOWN and the caller falls back to instructions
instead of touching files. Every probe is injectable, so tests never touch
real package databases or the network.
"""

from __future__ import annotations

import importlib.metadata
import json
import os
import shutil
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from xrayvpn.core import runtime_paths

STANDALONE = "standalone"
DEV = "dev"
UV_TOOL = "uv-tool"
PIPX = "pipx"
PIP = "pip"
PIP_DIRECT = "pip-direct"
BREW = "brew"
APT = "apt"
PACMAN = "pacman"
WINGET = "winget"
UNKNOWN = "unknown"

CONFIDENCE_HIGH = "high"
CONFIDENCE_MEDIUM = "medium"
CONFIDENCE_LOW = "low"

DIST_NAME = "xrayvpn"
UV_RECEIPT_NAME = "uv-receipt.toml"
PIPX_METADATA_NAME = "pipx_metadata.json"
WINGET_PACKAGES_SUBPATH = Path("Microsoft") / "WinGet" / "Packages"
PROBE_TIMEOUT_SECONDS = 5.0

_OWNER_DETAILS = {
    WINGET: "winget-managed install",
    BREW: "Homebrew keg",
    APT: "dpkg-owned install",
    PACMAN: "pacman-owned install",
}


@dataclass(frozen=True)
class InstallInfo:
    kind: str
    confidence: str
    detail: str = ""


@dataclass(frozen=True)
class Signals:
    frozen: bool = False
    platform: str = "linux"
    entry: Path | None = None
    target: Path | None = None
    prefix: Path | None = None
    package_dir: Path | None = None
    repo_dir: Path | None = None
    home: Path | None = None
    env: Mapping[str, str] = field(default_factory=dict)
    dpkg_owner: bool = False
    pacman_owner: bool = False
    winget_owner: bool = False
    brew_owner: bool = False
    uv_receipt: bool = False
    pipx_metadata: bool = False
    direct_url: Mapping[str, Any] | None = None
    dist_found: bool = False


def classify(signals: Signals) -> InstallInfo:
    casefold = signals.platform == "win32"
    owners = [
        kind
        for kind, owned in (
            (WINGET, signals.winget_owner),
            (BREW, signals.brew_owner),
            (APT, signals.dpkg_owner),
            (PACMAN, signals.pacman_owner),
        )
        if owned
    ]
    if len(owners) > 1:
        return InstallInfo(UNKNOWN, CONFIDENCE_LOW, "conflicting package ownership")
    if owners:
        return InstallInfo(owners[0], CONFIDENCE_HIGH, _OWNER_DETAILS[owners[0]])
    if signals.uv_receipt and signals.pipx_metadata:
        return InstallInfo(UNKNOWN, CONFIDENCE_LOW, "conflicting tool managers")
    if signals.frozen:
        return InstallInfo(STANDALONE, CONFIDENCE_HIGH, "standalone binary")
    if signals.uv_receipt:
        return InstallInfo(UV_TOOL, CONFIDENCE_HIGH, "uv tool install")
    if signals.pipx_metadata:
        return InstallInfo(PIPX, CONFIDENCE_HIGH, "pipx install")
    if _under(signals.package_dir, signals.repo_dir, casefold=casefold):
        return InstallInfo(DEV, CONFIDENCE_HIGH, "repository checkout")
    if signals.direct_url is not None:
        if _editable(signals.direct_url):
            return InstallInfo(DEV, CONFIDENCE_HIGH, "editable install")
        return InstallInfo(PIP_DIRECT, CONFIDENCE_MEDIUM, _direct_detail(signals.direct_url))
    if signals.dist_found:
        return InstallInfo(PIP, CONFIDENCE_LOW, "python package install")
    return InstallInfo(UNKNOWN, CONFIDENCE_LOW, "no positive install-source signal")


def detect(
    *,
    frozen: bool | None = None,
    platform: str | None = None,
    argv: Sequence[str] | None = None,
    prefix: Path | None = None,
    package_dir: Path | None = None,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
    home: Path | None = None,
    which: Callable[[str], str | None] | None = None,
    run: Callable[[Sequence[str]], Any] | None = None,
    find_repo: Callable[[Path], Path | None] | None = None,
    dist_lookup: Callable[[str], Any] | None = None,
) -> InstallInfo:
    environment = os.environ if env is None else env
    plat = sys.platform if platform is None else platform
    is_frozen = runtime_paths.is_frozen() if frozen is None else frozen
    args = sys.argv if argv is None else argv
    resolved_cwd = (cwd or Path.cwd()).resolve()
    home_dir = Path.home() if home is None else home
    venv_prefix = Path(prefix) if prefix is not None else Path(sys.prefix)
    package = Path(package_dir) if package_dir is not None else runtime_paths.PACKAGE_DIR
    casefold = plat == "win32"
    entry, target = _entry_targets(args)
    paths = _unique_paths(entry, target)

    repo = None
    if not is_frozen:
        lookup_repo = find_repo or runtime_paths.find_repo_dir
        repo = lookup_repo(resolved_cwd)

    finder = which or shutil.which
    runner = run or _default_run

    dpkg_owner = False
    if plat == "linux" and finder("dpkg-query"):
        dpkg_owner = any(
            _dpkg_owner(_stdout(runner(["dpkg-query", "-S", str(path)]))) for path in paths
        )
    pacman_owner = False
    if plat == "linux" and finder("pacman"):
        pacman_owner = any(
            _pacman_owner(_stdout(runner(["pacman", "-Qo", str(path)]))) for path in paths
        )

    winget_owner = False
    local_appdata = environment.get("LOCALAPPDATA")
    if casefold and local_appdata:
        winget_root = Path(local_appdata) / WINGET_PACKAGES_SUBPATH
        winget_owner = any(_under(path, winget_root, casefold=True) for path in paths)
    brew_owner = any(_brew_keg(path) for path in paths)

    uv_root = _uv_tools_root(environment, home_dir, plat)
    uv_receipt = (venv_prefix / UV_RECEIPT_NAME).is_file() or _under(
        venv_prefix, uv_root, casefold=casefold
    )
    pipx_root = _pipx_venvs_root(environment, home_dir, plat)
    pipx_metadata = _pipx_marker(venv_prefix) or _under(
        venv_prefix, pipx_root, casefold=casefold
    )

    dist: Any = None
    direct_url: Mapping[str, Any] | None = None
    if not is_frozen:
        lookup_dist = dist_lookup or importlib.metadata.distribution
        try:
            dist = lookup_dist(DIST_NAME)
        except Exception:  # noqa: BLE001 - metadata trouble must fall back to UNKNOWN
            dist = None
        if dist is not None:
            direct_url = _direct_url(dist)

    return classify(
        Signals(
            frozen=is_frozen,
            platform=plat,
            entry=entry,
            target=target,
            prefix=venv_prefix,
            package_dir=package,
            repo_dir=repo,
            home=home_dir,
            env=environment,
            dpkg_owner=dpkg_owner,
            pacman_owner=pacman_owner,
            winget_owner=winget_owner,
            brew_owner=brew_owner,
            uv_receipt=uv_receipt,
            pipx_metadata=pipx_metadata,
            direct_url=direct_url,
            dist_found=dist is not None,
        )
    )


def _entry_targets(args: Sequence[str]) -> tuple[Path | None, Path | None]:
    if not args or not args[0]:
        return None, None
    entry = Path(os.path.abspath(args[0]))
    return entry, Path(os.path.realpath(entry))


def _unique_paths(*paths: Path | None) -> list[Path]:
    unique: list[Path] = []
    for path in paths:
        if path is not None and path not in unique:
            unique.append(path)
    return unique


def _under(path: Path | None, root: Path | None, *, casefold: bool = False) -> bool:
    if path is None or root is None:
        return False
    try:
        left = path.resolve()
        right = root.resolve()
    except OSError:
        return False
    if casefold:
        left_text = str(left).casefold()
        right_text = str(right).casefold()
        return left_text == right_text or left_text.startswith(right_text + os.sep)
    try:
        left.relative_to(right)
    except ValueError:
        return False
    return True


def _default_run(command: Sequence[str]) -> Any:
    try:
        return subprocess.run(
            list(command),
            capture_output=True,
            text=True,
            timeout=PROBE_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None


def _stdout(result: Any) -> str:
    return str(getattr(result, "stdout", "") or "")


def _dpkg_owner(stdout: str) -> bool:
    lines = [line for line in (stdout or "").splitlines() if line.strip()]
    if not lines:
        return False
    package = lines[0].split(":", 1)[0].strip()
    return package.startswith(DIST_NAME)


def _pacman_owner(stdout: str) -> bool:
    marker = " is owned by "
    for line in (stdout or "").splitlines():
        if marker in line:
            package = line.split(marker, 1)[1].split()[0]
            return package.startswith(DIST_NAME)
    return False


def _brew_keg(path: Path) -> bool:
    parts = [part.casefold() for part in path.parts]
    return "cellar" in parts and DIST_NAME in parts


def _uv_tools_root(environment: Mapping[str, str], home: Path, platform: str) -> Path:
    override = (environment.get("UV_TOOL_DIR") or "").strip()
    if override:
        return Path(override).expanduser()
    if platform == "win32":
        base = environment.get("APPDATA") or str(home / "AppData" / "Roaming")
        return Path(base) / "uv" / "tools"
    base = environment.get("XDG_DATA_HOME") or str(home / ".local" / "share")
    return Path(base) / "uv" / "tools"


def _pipx_venvs_root(environment: Mapping[str, str], home: Path, platform: str) -> Path:
    override = (environment.get("PIPX_HOME") or "").strip()
    if override:
        return Path(override).expanduser() / "venvs"
    if platform == "win32":
        base = environment.get("USERPROFILE") or str(home)
        return Path(base) / "pipx" / "venvs"
    base = environment.get("XDG_DATA_HOME") or str(home / ".local" / "share")
    return Path(base) / "pipx" / "venvs"


def _pipx_marker(venv: Path) -> bool:
    metadata = venv / PIPX_METADATA_NAME
    if not metadata.is_file():
        return False
    try:
        raw = json.loads(metadata.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    main = raw.get("main_package") if isinstance(raw, Mapping) else None
    if not isinstance(main, Mapping):
        return False
    pinned = str(main.get("package") or "")
    return pinned.split("==")[0].strip().lower() == DIST_NAME


def _direct_url(dist: Any) -> Mapping[str, Any] | None:
    try:
        text = dist.read_text("direct_url.json")
    except Exception:  # noqa: BLE001 - metadata shapes vary across installers
        return None
    if not text:
        return None
    try:
        raw = json.loads(text)
    except ValueError:
        return None
    return raw if isinstance(raw, Mapping) else None


def _editable(direct_url: Mapping[str, Any]) -> bool:
    info = direct_url.get("dir_info")
    return bool(isinstance(info, Mapping) and info.get("editable"))


def _direct_detail(direct_url: Mapping[str, Any]) -> str:
    if "vcs_info" in direct_url:
        return "VCS-direct install"
    if "archive_info" in direct_url:
        return "archive-direct install"
    if "dir_info" in direct_url:
        return "local-directory install"
    return "direct-URL install"
