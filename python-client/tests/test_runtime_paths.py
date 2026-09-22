"""Tests for core/runtime_paths.py: the payload/workspace/ansible-root contract.

Every install shape (repo clone, standalone binary, wheel without a clone)
is resolved by injecting flags and directories — the interpreter is never
emulated as frozen globally. Also covers the derived surfaces: DeployRequest
workspace defaults, binary-aware venv hints, bundle example hints and the
double-click crash-net.
"""

from __future__ import annotations

import shutil
import sys
import tarfile
from pathlib import Path
from types import SimpleNamespace

import pytest

import xrayvpn.cli.main as main_mod
import xrayvpn.core.execution.local as local_mod
from xrayvpn.core import runtime_paths, wsl
from xrayvpn.core.execution.base import DeployRequest
from xrayvpn.core.execution.local import VENV_HINT, LocalExecutor, venv_hint
from xrayvpn.core.inventory import parse_user_inventory
from xrayvpn.core.manifest import allowlist_entries, build_tarball


def _missing_repo() -> Path:
    raise RuntimeError("repository root not found (no deploy.yml)")


def _touch(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _make_source_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    _touch(repo / "deploy.yml", "---\n")
    _touch(repo / "config" / "settings.yml", "a: repo\n")
    _touch(repo / "config" / "inventory.yml", "trap\n")
    _touch(repo / "roles" / "xray_vpn" / "tasks" / "main.yml", "---\n")
    _touch(repo / "roles" / "xray_vpn" / "tasks" / "__pycache__" / "main.pyc", "x")
    _touch(repo / "inventory.yml", "secret\n")
    _touch(repo / "inventory.yml.example", "all: {}\n")
    _touch(repo / "README.md", "out\n")
    return repo


def _make_bundle(package_dir: Path, repo: Path) -> Path:
    """Simulate the build include: allowlist tree + inventory.yml.example."""
    bundle = package_dir / "payload"
    bundle.mkdir(parents=True)
    for entry in allowlist_entries(repo):
        target = bundle / entry.name
        if entry.is_dir():
            shutil.copytree(entry, target)
        else:
            shutil.copy2(entry, target)
    shutil.copy2(repo / "inventory.yml.example", bundle / "inventory.yml.example")
    return bundle


def _tar_names(root: Path, dest: Path) -> set[str]:
    build_tarball(root, dest)
    with tarfile.open(dest) as archive:
        return set(archive.getnames())


# --- is_frozen: PyInstaller sys.frozen OR Nuitka __compiled__ -------------


def test_is_frozen_false_on_plain_python() -> None:
    assert runtime_paths.is_frozen() is False


def test_is_frozen_pyinstaller_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert runtime_paths.is_frozen()


def test_is_frozen_nuitka_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runtime_paths, "__compiled__", object(), raising=False)
    assert runtime_paths.is_frozen()


def test_is_frozen_injected_branches() -> None:
    assert runtime_paths.is_frozen(sys_ns=object(), compiled_ns={}) is False
    assert runtime_paths.is_frozen(sys_ns=SimpleNamespace(frozen=True), compiled_ns={})
    assert runtime_paths.is_frozen(sys_ns=SimpleNamespace(), compiled_ns={"__compiled__": 1})


# --- payload_root: repo walk first, then the marker-checked bundle ---------


def test_payload_root_repo_walk_wins_over_bundle(tmp_path: Path) -> None:
    repo = _make_source_repo(tmp_path)
    package = tmp_path / "pkg" / "xrayvpn"
    _make_bundle(package, repo)
    nested = repo / "python-client" / "src"
    nested.mkdir(parents=True)
    assert runtime_paths.payload_root(cwd=nested, package_dir=package) == repo


def test_payload_root_falls_back_to_bundle(tmp_path: Path) -> None:
    repo = _make_source_repo(tmp_path)
    package = tmp_path / "pkg" / "xrayvpn"
    bundle = _make_bundle(package, repo)
    empty = tmp_path / "empty"
    empty.mkdir()
    assert runtime_paths.payload_root(cwd=empty, package_dir=package) == bundle


def test_payload_root_broken_bundle_raises_binary_friendly_hint(tmp_path: Path) -> None:
    package = tmp_path / "pkg" / "xrayvpn"
    (package / "payload").mkdir(parents=True)
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(RuntimeError, match="standalone binary") as exc:
        runtime_paths.payload_root(cwd=empty, package_dir=package)
    assert str(package / "payload") in str(exc.value)


def test_find_repo_dir_requires_the_project_shape(tmp_path: Path) -> None:
    foreign = tmp_path / "other-ansible-project"
    _touch(foreign / "deploy.yml", "---\n")
    nested = foreign / "roles" / "some_other_role"
    nested.mkdir(parents=True)
    assert runtime_paths.find_repo_dir(nested) is None


def test_payload_root_foreign_deploy_tree_cannot_hijack_bundle(tmp_path: Path) -> None:
    repo = _make_source_repo(tmp_path)
    package = tmp_path / "pkg" / "xrayvpn"
    bundle = _make_bundle(package, repo)
    foreign = tmp_path / "other"
    _touch(foreign / "deploy.yml", "---\n")  # no roles/xray_vpn — not a clone
    assert runtime_paths.payload_root(cwd=foreign, package_dir=package) == bundle


# --- workspace_root: repo (dev) / $XRAYVPN_HOME → exe → cwd (packaged) ----


def test_workspace_root_dev_clone_is_repo(tmp_path: Path) -> None:
    repo = _make_source_repo(tmp_path)
    nested = repo / "roles"
    assert runtime_paths.workspace_root(cwd=nested, frozen=False) == repo


def test_workspace_root_wheel_without_repo_is_cwd(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    assert runtime_paths.workspace_root(cwd=empty.resolve(), frozen=False) == empty.resolve()


def test_workspace_root_packaged_home_wins(tmp_path: Path) -> None:
    home = tmp_path / "vpn-home"
    exe_dir = tmp_path / "bin"
    workspace = runtime_paths.workspace_root(
        cwd=tmp_path,
        frozen=True,
        env={"XRAYVPN_HOME": str(home)},
        argv=[str(exe_dir / "xrayvpn.exe")],
    )
    assert workspace == home.resolve()


def test_workspace_root_packaged_falls_to_exe_folder(tmp_path: Path) -> None:
    exe_dir = tmp_path / "bin"
    exe_dir.mkdir()
    workspace = runtime_paths.workspace_root(
        cwd=tmp_path,
        frozen=True,
        env={},
        argv=[str(exe_dir / "xrayvpn.exe")],
    )
    assert workspace == exe_dir.resolve()


def test_workspace_root_packaged_falls_to_cwd(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    workspace = runtime_paths.workspace_root(
        cwd=empty, frozen=True, env={}, argv=[""], home=tmp_path / "home"
    )
    assert workspace == empty.resolve()


def test_packaged_workspace_unwritable_dirs_fall_to_state_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    exe_dir = tmp_path / "Program Files" / "xrayvpn"
    exe_dir.mkdir(parents=True)
    monkeypatch.setattr(
        runtime_paths, "_writable", lambda path: "Program Files" not in str(path)
    )
    env = {
        "XRAYVPN_HOME": "",
        "LOCALAPPDATA": str(tmp_path / "localappdata"),
        "XDG_DATA_HOME": str(tmp_path / "xdg"),
    }
    home = tmp_path / "home"
    workspace = runtime_paths.workspace_root(
        cwd=exe_dir, frozen=True, env=env, argv=[str(exe_dir / "xrayvpn.exe")], home=home
    )
    assert workspace == runtime_paths._state_workspace(env, home)
    assert workspace.is_dir()


def test_packaged_existing_state_dir_wins_over_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    exe_dir = tmp_path / "Program Files" / "xrayvpn"
    exe_dir.mkdir(parents=True)
    env = {"LOCALAPPDATA": str(tmp_path / "localappdata")}
    state = runtime_paths._state_workspace(env, tmp_path / "home")
    state.mkdir(parents=True)
    monkeypatch.setattr(
        runtime_paths, "_writable", lambda path: "Program Files" not in str(path)
    )
    workspace = runtime_paths.workspace_root(
        cwd=tmp_path, frozen=True, env=env, argv=[str(exe_dir / "xrayvpn.exe")],
        home=tmp_path / "home",
    )
    assert workspace == state


def test_packaged_workspace_raises_when_nothing_writable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    occupied = tmp_path / "occupied"
    occupied.write_text("not a dir", encoding="utf-8")
    monkeypatch.setattr(runtime_paths, "_writable", lambda path: False)
    env = {"LOCALAPPDATA": str(occupied), "XDG_DATA_HOME": str(occupied)}
    # on darwin the state dir derives from `home`, so block that path too
    with pytest.raises(RuntimeError, match="XRAYVPN_HOME"):
        runtime_paths.workspace_root(
            cwd=tmp_path, frozen=True, env=env, argv=["xrayvpn.exe"], home=occupied
        )


# --- stage_bundle: copy of payload + settings overlay ----------------------


def test_stage_bundle_overlays_user_settings(tmp_path: Path) -> None:
    repo = _make_source_repo(tmp_path)
    package = tmp_path / "pkg" / "xrayvpn"
    bundle = _make_bundle(package, repo)
    workspace = tmp_path / "ws"
    _touch(workspace / "config" / "settings.yml", "a: user\n")
    staged = runtime_paths.stage_bundle(bundle, workspace, tmp_path / "staged")
    assert (staged / "deploy.yml").is_file()
    assert (staged / "roles" / "xray_vpn" / "tasks" / "main.yml").is_file()
    assert (staged / "inventory.yml.example").is_file()
    assert (staged / "config" / "settings.yml").read_text(encoding="utf-8") == "a: user\n"
    assert (bundle / "config" / "settings.yml").read_text(encoding="utf-8") == "a: repo\n"


def test_stage_bundle_keeps_bundled_settings_without_user_file(tmp_path: Path) -> None:
    repo = _make_source_repo(tmp_path)
    package = tmp_path / "pkg" / "xrayvpn"
    bundle = _make_bundle(package, repo)
    workspace = tmp_path / "ws"
    workspace.mkdir()
    staged = runtime_paths.stage_bundle(bundle, workspace, tmp_path / "staged")
    assert (staged / "config" / "settings.yml").read_text(encoding="utf-8") == "a: repo\n"


def test_stage_bundle_creates_empty_settings_when_nowhere(tmp_path: Path) -> None:
    payload = tmp_path / "payload"
    payload.mkdir()
    _touch(payload / "deploy.yml", "---\n")
    workspace = tmp_path / "ws"
    workspace.mkdir()
    staged = runtime_paths.stage_bundle(payload, workspace, tmp_path / "staged")
    assert (staged / "config" / "settings.yml").read_text(encoding="utf-8") == ""


def test_stage_bundle_keeps_bundled_settings_when_bundle_has_none_and_overlay_has_one(
    tmp_path: Path,
) -> None:
    payload = tmp_path / "payload"
    payload.mkdir()
    _touch(payload / "deploy.yml", "---\n")
    workspace = tmp_path / "ws"
    _touch(workspace / "config" / "settings.yml", "a: user\n")
    staged = runtime_paths.stage_bundle(payload, workspace, tmp_path / "staged")
    assert (staged / "config" / "settings.yml").read_text(encoding="utf-8") == "a: user\n"


# --- resolve_roots: the three install shapes ------------------------------


def test_resolve_roots_dev_clone_identity(tmp_path: Path) -> None:
    repo = _make_source_repo(tmp_path)
    roots = runtime_paths.resolve_roots(
        cwd=repo / "roles",
        frozen=False,
        find_repo=lambda: repo,
        new_temp_root=lambda: pytest.fail("dev must not stage"),
    )
    assert roots == runtime_paths.RunRoots(repo, repo, repo)


def test_resolve_roots_frozen_inside_clone_uses_repo_payload(tmp_path: Path) -> None:
    repo = _make_source_repo(tmp_path)
    exe_dir = tmp_path / "tools"
    exe_dir.mkdir()
    roots = runtime_paths.resolve_roots(
        cwd=repo,
        frozen=True,
        env={},
        argv=[str(exe_dir / "xrayvpn.exe")],
        find_repo=lambda: repo,
        new_temp_root=lambda: pytest.fail("a repo is writable; never stage"),
    )
    assert roots.payload == repo
    assert roots.repo == repo
    assert roots.workspace == exe_dir.resolve()


def test_resolve_roots_frozen_stages_readonly_bundle(tmp_path: Path) -> None:
    repo = _make_source_repo(tmp_path)
    package = tmp_path / "pkg" / "xrayvpn"
    bundle = _make_bundle(package, repo)
    exe_dir = tmp_path / "bin"
    _touch(exe_dir / "config" / "settings.yml", "a: bin\n")
    roots = runtime_paths.resolve_roots(
        cwd=tmp_path / "somewhere",
        frozen=True,
        package_dir=package,
        env={},
        argv=[str(exe_dir / "xrayvpn.exe")],
        find_repo=_missing_repo,
        new_temp_root=lambda: tmp_path / "temp1",
    )
    assert roots.payload == bundle
    assert roots.workspace == exe_dir.resolve()
    assert roots.repo == tmp_path / "temp1" / "repo"
    assert (roots.repo / "config" / "settings.yml").read_text(encoding="utf-8") == "a: bin\n"
    assert (bundle / "config" / "settings.yml").read_text(encoding="utf-8") == "a: repo\n"


def test_resolve_roots_wheel_without_repo_stages_bundle(tmp_path: Path) -> None:
    repo = _make_source_repo(tmp_path)
    package = tmp_path / "pkg" / "xrayvpn"
    bundle = _make_bundle(package, repo)
    workspace = tmp_path / "run"
    workspace.mkdir()
    roots = runtime_paths.resolve_roots(
        cwd=workspace,
        frozen=False,
        package_dir=package,
        find_repo=_missing_repo,
        new_temp_root=lambda: tmp_path / "temp2",
    )
    assert roots.payload == bundle
    assert roots.workspace == workspace
    assert roots.repo == tmp_path / "temp2" / "repo"
    src = _tar_names(repo, tmp_path / "src.tar.gz")
    staged = _tar_names(roots.repo, tmp_path / "staged.tar.gz")
    assert src == staged
    assert not any(name.endswith("inventory.yml") for name in staged)
    assert "inventory.yml.example" not in staged


def test_resolve_roots_errors_when_no_repo_and_no_bundle(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(RuntimeError, match="standalone binary"):
        runtime_paths.resolve_roots(
            cwd=empty,
            frozen=True,
            package_dir=tmp_path / "pkg",
            env={},
            argv=[],
            find_repo=_missing_repo,
        )


def test_resolve_roots_default_lookup_walks_cwd(tmp_path: Path) -> None:
    repo = _make_source_repo(tmp_path)
    roots = runtime_paths.resolve_roots(cwd=repo, frozen=False)
    assert roots.repo == repo


# --- derived surfaces: DeployRequest, hints, inventory example --------------


def test_resolved_clients_dir_prefers_workspace(tmp_path: Path) -> None:
    bare = DeployRequest(repo_root=tmp_path / "repo")
    assert bare.resolved_clients_dir() == tmp_path / "repo" / "downloaded-clients"
    with_workspace = DeployRequest(repo_root=tmp_path / "repo", workspace=tmp_path / "ws")
    assert with_workspace.resolved_clients_dir() == tmp_path / "ws" / "downloaded-clients"
    pinned = DeployRequest(
        repo_root=tmp_path / "repo",
        workspace=tmp_path / "ws",
        clients_dir=tmp_path / "here",
    )
    assert pinned.resolved_clients_dir() == tmp_path / "here"


def test_venv_hint_repo_versus_binary() -> None:
    assert venv_hint(frozen=False) == VENV_HINT
    binary = venv_hint(frozen=True)
    assert "scripts/dev" not in binary
    assert "ansible-core" in binary


def test_preflight_uses_binary_hint_when_frozen(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(wsl, "is_windows", lambda: False)
    monkeypatch.setattr(local_mod.shutil, "which", lambda name: None)
    monkeypatch.setattr(runtime_paths, "is_frozen", lambda: True)
    executor = LocalExecutor(wsl_venv=str(tmp_path / "no-venv"))
    with pytest.raises(RuntimeError, match="ansible-core") as exc:
        executor.preflight(password_auth=False)
    assert "scripts/dev" not in str(exc.value)


def test_parse_user_inventory_hint_points_at_bundle_example(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    _touch(bundle / "inventory.yml.example", "all: {}\n")
    with pytest.raises(RuntimeError) as exc:
        parse_user_inventory(workspace, example_dir=bundle)
    message = str(exc.value)
    assert str(workspace / "inventory.yml") in message
    assert str(bundle / "inventory.yml.example") in message


# --- crash-net: double-clicked packaged builds keep the console ------------


def test_run_crash_net_on_frozen_no_args(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    def boom() -> None:
        raise ValueError("exploded payload")

    entered: list[str] = []
    monkeypatch.setattr(runtime_paths, "is_frozen", lambda: True)
    monkeypatch.setattr(sys, "argv", ["xrayvpn.exe"])
    monkeypatch.setattr(main_mod, "app", boom)
    monkeypatch.setattr(main_mod, "_pause_before_exit", lambda: entered.append("paused"))
    with pytest.raises(SystemExit) as exc:
        main_mod.run()
    assert exc.value.code == 1
    assert entered == ["paused"]
    assert "exploded payload" in capsys.readouterr().err


def test_run_without_net_when_args_given(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom() -> None:
        raise ValueError("kaboom")

    monkeypatch.setattr(runtime_paths, "is_frozen", lambda: True)
    monkeypatch.setattr(sys, "argv", ["xrayvpn.exe", "deploy"])
    monkeypatch.setattr(main_mod, "app", boom)
    monkeypatch.setattr(
        main_mod, "_pause_before_exit", lambda: pytest.fail("net must not fire with args")
    )
    with pytest.raises(ValueError, match="kaboom"):
        main_mod.run()


def test_run_without_net_in_dev_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom() -> None:
        raise ValueError("kaboom")

    monkeypatch.setattr(runtime_paths, "is_frozen", lambda: False)
    monkeypatch.setattr(sys, "argv", ["xrayvpn"])
    monkeypatch.setattr(main_mod, "app", boom)
    monkeypatch.setattr(
        main_mod, "_pause_before_exit", lambda: pytest.fail("net must not fire unfrozen")
    )
    with pytest.raises(ValueError, match="kaboom"):
        main_mod.run()
