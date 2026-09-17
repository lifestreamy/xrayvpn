"""xrayvpn CLI (Typer).

`xrayvpn deploy` — the ansible TARGET is always a remote VPS; `--execution`
picks only the control node (ADR-003, semantics fixed 09.09):

- `--execution remote` (default) — bootstrap the VPS over SSH and run the
  playbook ON the server (Fabric transport; tarball upload; no GitHub);
- `--execution local` — run ansible ON this machine (Windows: via the WSL
  bridge) against the VPS over SSH. Prefer it on very weak VPSes where the
  server-side bootstrap itself would OOM.

Every real run (except `--dry-run`) shows a deploy plan and asks for a
yes/no confirmation; `--no-interactive` skips prompts for CI/scripted use.
The old local-target execution was a test bench and now lives in
`scripts/test` + molecule, not in the client.
"""

from __future__ import annotations

import getpass
import os
import sys
import traceback
from pathlib import Path
from typing import Annotated

import typer

from xrayvpn import __version__, i18n
from xrayvpn.cli import l10n_typer, prompts, repl, service, theme
from xrayvpn.core import runtime_paths, update_check, wsl
from xrayvpn.core.config import find_repo_root, load_settings, merge_overrides
from xrayvpn.core.conn import apply_ssh_config
from xrayvpn.core.execution.base import DeployRequest
from xrayvpn.core.execution.local import DEFAULT_WSL_VENV, LocalExecutor, build_ssh_inventory_vars
from xrayvpn.core.execution.remote import (
    RemoteExecutor,
    bootstrap_commands,
    cleanup_commands,
    playbook_command,
    swap_guard_commands,
    swap_guard_needed,
    swap_status_commands,
)
from xrayvpn.core.inventory import (
    build_inventory,
    parse_user_inventory,
    validate_connection,
    write_inventory,
)
from xrayvpn.core.transport.remote import FabricRemote, SshConnectError

SUPPORTED_RUNTIMES = ("native", "docker")
EXECUTION_MODES = ("remote", "local")

def _harden_stdio() -> None:
    """Redirected Windows streams default to the locale codec (cp1252) and
    crash on Cyrillic; UTF-8 keeps RU output intact in pipes and files."""
    for stream in (sys.stdout, sys.stderr):
        if stream is None or not hasattr(stream, "reconfigure"):
            continue
        if stream.isatty():
            stream.reconfigure(errors="replace")
        else:
            stream.reconfigure(encoding="utf-8", errors="replace")


_harden_stdio()
i18n.preinit()
l10n_typer.apply_palette()
l10n_typer.disable_click_colorama()
if i18n.is_ru():
    l10n_typer.apply_ru()
if os.environ.get("XRAYVPN_THEME_DEBUG") == "1":
    typer.echo(theme.debug_line(), err=True)

app = typer.Typer(
    name="xrayvpn",
    help=i18n.t("MAIN_APP_HELP"),
    no_args_is_help=False,
    invoke_without_command=True,
    add_completion=False,
)


def _settings_for_help() -> dict[str, object]:
    try:
        return load_settings(runtime_paths.payload_root())
    except Exception:  # noqa: BLE001 - help must render without a settings file
        return {}


_HELP_DEFAULTS = _settings_for_help()


def _d(key: str) -> str:
    value = _HELP_DEFAULTS.get(key)
    if isinstance(value, bool):
        return i18n.t("COMMON_DEFAULT_ON") if value else i18n.t("COMMON_DEFAULT_OFF")
    return "settings.yml" if value is None else str(value)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"xrayvpn {__version__}")
        hint = _update_hint()
        if hint:
            typer.echo(theme.muted(hint))
        raise typer.Exit()


def _update_hint() -> str | None:
    return update_check.banner_hint(packaged=runtime_paths.find_repo_dir() is None)


@app.callback()
def main(
    ctx: typer.Context,
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            callback=_version_callback,
            is_eager=True,
            help=i18n.t("MAIN_VERSION_OPT"),
        ),
    ] = False,
    ru: Annotated[
        bool,
        typer.Option(
            "--ru",
            help=i18n.t("MAIN_RU_OPT"),
        ),
    ] = False,
) -> None:
    """xrayvpn — one client, two execution modes (local / remote)."""
    if ru:
        repl.set_session_lang("ru")
    if ctx.invoked_subcommand is None:
        if repl.session_requested():
            raise typer.Exit(repl.start(_repl_dispatch, update_hint=_update_hint))
        typer.echo(ctx.get_help())
        raise typer.Exit(2)


@app.command("repl", hidden=True)
def repl_command() -> None:
    """Open the interactive session (default on a TTY without arguments)."""
    raise typer.Exit(repl.start(_repl_dispatch, update_hint=_update_hint))


app.add_typer(service.service_app, name="service")


def _repl_dispatch(tokens: list[str]) -> int:
    """Run one CLI line in-process; the SystemExit code is the session rc."""
    try:
        app(args=tokens, prog_name="xrayvpn", standalone_mode=True)
    except SystemExit as exc:
        return int(exc.code or 0)
    except Exception as exc:  # noqa: BLE001 - the session must survive any command failure
        typer.echo(i18n.t("REPL_DISPATCH_ERROR", err=exc), err=True)
        return 1
    return 0


def _pause_before_exit() -> None:
    typer.echo(i18n.t("MAIN_PAUSE"))
    try:
        input()
    except (EOFError, OSError):
        pass


def run() -> None:
    """Console entry; a double-clicked packaged build keeps the traceback on
    screen instead of closing the console when the process dies."""
    if runtime_paths.is_frozen() and len(sys.argv) <= 1:
        try:
            app()
        except SystemExit:
            raise
        except KeyboardInterrupt:
            typer.echo(i18n.t("REPL_INTERRUPTED"), err=True)
            sys.exit(130)
        except Exception:  # noqa: BLE001
            traceback.print_exc()
            _pause_before_exit()
            sys.exit(1)
        return
    try:
        app()
    except KeyboardInterrupt:
        typer.echo(i18n.t("REPL_INTERRUPTED"), err=True)
        sys.exit(130)


def _resolve_execution(execution: str | None) -> str:
    if execution is None:
        selected = prompts.select(
            i18n.t("MAIN_EXEC_PROMPT"),
            list(EXECUTION_MODES),
            default="remote",
        )
        execution = selected or "remote"
    if execution not in EXECUTION_MODES:
        typer.echo(i18n.t("MAIN_EXEC_UNKNOWN", mode=execution), err=True)
        raise typer.Exit(2)
    return execution


def _confirm_deploy(plan: list[str], *, no_interactive: bool) -> None:
    typer.echo(theme.accent(i18n.t("MAIN_PLAN_HEADER")))
    for line in plan:
        typer.echo(f"  {line}")
    if no_interactive:
        return
    if not prompts.is_interactive():
        typer.echo(i18n.t("MAIN_CONFIRM_TTY"), err=True)
        raise typer.Exit(2)
    if not prompts.confirm(i18n.t("MAIN_CONFIRM_START"), default=False):
        typer.echo(i18n.t("MAIN_ABORT"))
        raise typer.Exit(0)


def _inventory_creds(
    workspace: Path,
    payload: Path,
    *,
    host: str | None,
    user: str,
    port: int,
    pkey: Path | None,
    password: str | None,
) -> tuple[dict[str, str], dict[str, object]]:
    """Parse + validate personal inventory.yml; shared by both execution modes."""
    if host is not None or pkey is not None or password is not None or user != "root" or port != 22:
        typer.echo(i18n.t("MAIN_INV_OVERRIDES"), err=True)
    try:
        connection, user_vars = parse_user_inventory(workspace, example_dir=payload)
    except (RuntimeError, TypeError) as exc:
        typer.echo(theme.err(i18n.t("COMMON_ERR", err=exc)), err=True)
        raise typer.Exit(2) from exc
    problems = validate_connection(connection)
    if problems:
        personal_inventory = str(workspace / runtime_paths.PERSONAL_INVENTORY_NAME)
        typer.echo(i18n.t("MAIN_INV_NOT_READY", path=personal_inventory), err=True)
        for problem in problems:
            typer.echo(f"  - {problem}", err=True)
        typer.echo(i18n.t("MAIN_INV_FILL"), err=True)
        raise typer.Exit(2)
    if not (
        connection.get("ansible_ssh_private_key_file") or connection.get("ansible_ssh_pass")
    ):
        typer.echo(i18n.t("MAIN_INV_NOAUTH"), err=True)
    return connection, user_vars


def _redact_secrets(values: dict[str, object]) -> dict[str, object]:
    """Plan-display masking of credential-ish overrides (the -e args stay intact)."""
    redacted: dict[str, object] = {}
    for key, value in values.items():
        low = key.lower()
        redacted[key] = "******" if "pass" in low or "private_key" in low else value
    return redacted


def _plan_lines(
    mode: str,
    *,
    host: str,
    user: str,
    port: int,
    auth_desc: str,
    overrides: dict[str, object],
    clients_dir: Path,
    cleanup: str,
    alias: str | None = None,
) -> list[str]:
    if mode == "remote":
        runner = i18n.t("MAIN_PLAN_RUNNER_REMOTE")
    else:
        runner = i18n.t("MAIN_PLAN_RUNNER_LOCAL")
    lines = [runner]
    if alias is not None:
        lines.append(i18n.t("MAIN_PLAN_ALIAS", alias=alias, host=host, port=port))
    lines += [
        i18n.t("MAIN_PLAN_TARGET", user=user, host=host, port=port),
        i18n.t("MAIN_PLAN_AUTH", desc=auth_desc),
    ]
    if overrides:
        display = _redact_secrets(overrides)
        lines.append(i18n.t("MAIN_PLAN_OVERRIDES", display=display))
    if overrides.get("xray_reality_rotate") is True:
        lines.append(i18n.t("MAIN_PLAN_ROTATE_WARN"))
    if mode == "remote":
        cleanup_text = {
            "full-cleanup": i18n.t("MAIN_PLAN_CLEANUP_FULL"),
            "no-cleanup": i18n.t("MAIN_PLAN_CLEANUP_SKIP"),
        }.get(cleanup, i18n.t("MAIN_PLAN_CLEANUP_DEFAULT"))
        lines.append(cleanup_text)
    lines.append(i18n.t("MAIN_PLAN_DEST", path=clients_dir))
    return lines


def _auth_descriptor(pkey: object, password: object) -> str:
    if pkey:
        return i18n.t("MAIN_AUTH_PKEY", pkey=pkey)
    if password:
        return i18n.t("MAIN_AUTH_PASSWORD")
    return i18n.t("MAIN_AUTH_AGENT")


def _collect_overrides(args: dict) -> dict[str, object]:
    overrides: dict[str, object] = {}
    if args.get("runtime") is not None:
        overrides["xray_runtime"] = args["runtime"]
    if args.get("xray_port") is not None:
        overrides["xray_port"] = args["xray_port"]
    if args.get("num_clients") is not None:
        overrides["num_clients"] = args["num_clients"]
    if args.get("camouflage_domain") is not None:
        overrides["reality_camouflage_domain"] = args["camouflage_domain"]
    if args.get("warp") is not None:
        overrides["warp_enabled"] = args["warp"]
    if args.get("rotate") is not None:
        overrides["xray_reality_rotate"] = args["rotate"]
    if args.get("manage_ufw") is not None:
        overrides["xray_manage_ufw"] = args["manage_ufw"]
    return overrides


@app.command(help=i18n.t("MAIN_DEPLOY_HELP"))
def deploy(
    execution: Annotated[
        str | None,
        typer.Option(
            "--execution",
            help=i18n.t("MAIN_EXEC_OPT", modes="|".join(EXECUTION_MODES)),
        ),
    ] = None,
    runtime: Annotated[
        str | None,
        typer.Option(
            "--runtime",
            help=i18n.t(
                "MAIN_RUNTIME_OPT",
                runtimes=", ".join(SUPPORTED_RUNTIMES),
                d=_d("xray_runtime"),
            ),
        ),
    ] = None,
    xray_port: Annotated[
        int | None,
        typer.Option(
            "--xray-port",
            help=i18n.t("MAIN_PORT_OPT", d=_d("xray_port")),
        ),
    ] = None,
    num_clients: Annotated[
        int | None,
        typer.Option(
            "--num-clients",
            help=i18n.t("MAIN_NUMCLIENTS_OPT", d=_d("num_clients")),
        ),
    ] = None,
    camouflage_domain: Annotated[
        str | None,
        typer.Option(
            "--camouflage-domain",
            help=i18n.t(
                "MAIN_CAMO_OPT", d=_d("reality_camouflage_domain")
            ),
        ),
    ] = None,
    warp: Annotated[
        bool | None,
        typer.Option(
            "--warp/--no-warp",
            help=i18n.t("MAIN_WARP_OPT", d=_d("warp_enabled")),
        ),
    ] = None,
    rotate: Annotated[
        bool | None,
        typer.Option(
            "--rotate/--no-rotate",
            help=i18n.t("MAIN_ROTATE_OPT"),
        ),
    ] = None,
    manage_ufw: Annotated[
        bool | None,
        typer.Option(
            "--manage-ufw/--no-ufw",
            help=i18n.t("MAIN_UFW_OPT", d=_d("xray_manage_ufw")),
        ),
    ] = None,
    inventory: Annotated[
        Path | None,
        typer.Option(
            "--inventory",
            help=i18n.t("MAIN_INV_OPT"),
        ),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help=i18n.t("MAIN_DRYRUN_OPT"),
        ),
    ] = False,
    debug: Annotated[
        bool,
        typer.Option("--debug", help="Ansible -vvv + xray_debug=true"),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", help="Ansible -vvvv + xray_debug=true"),
    ] = False,
    wsl_distro: Annotated[
        str | None,
        typer.Option(
            "--wsl-distro",
            help=i18n.t("MAIN_WSLOPTS_DISTRO"),
        ),
    ] = None,
    wsl_venv: Annotated[
        str,
        typer.Option(
            "--wsl-venv",
            help=i18n.t("MAIN_WSLOPTS_VENV"),
        ),
    ] = DEFAULT_WSL_VENV,
    host: Annotated[
        str | None,
        typer.Option(
            "--host",
            "-H",
            help=i18n.t("MAIN_HOST_OPT"),
        ),
    ] = None,
    user: Annotated[
        str,
        typer.Option("--user", "-u", help=i18n.t("COMMON_USER")),
    ] = "root",
    port: Annotated[
        int,
        typer.Option("--port", "-p", help=i18n.t("COMMON_PORT")),
    ] = 22,
    pkey: Annotated[
        Path | None,
        typer.Option("--pkey", help=i18n.t("COMMON_PKEY")),
    ] = None,
    password: Annotated[
        str | None,
        typer.Option("--pass", help=i18n.t("COMMON_PASS")),
    ] = None,
    use_inventory: Annotated[
        bool,
        typer.Option(
            "--use-inventory",
            help=i18n.t("MAIN_USEINV_OPT"),
        ),
    ] = False,
    clients_dir: Annotated[
        Path | None,
        typer.Option(
            "--clients-dir",
            help=i18n.t("MAIN_CLIENTSDIR_OPT"),
        ),
    ] = None,
    full_cleanup: Annotated[
        bool,
        typer.Option(
            "--full-cleanup",
            help=i18n.t("MAIN_FULLCLEANUP_OPT"),
        ),
    ] = False,
    no_cleanup: Annotated[
        bool,
        typer.Option(
            "--no-cleanup",
            help=i18n.t("MAIN_NOCLEANUP_OPT"),
        ),
    ] = False,
    ru: Annotated[
        bool,
        typer.Option(
            "--ru",
            help=i18n.t("MAIN_RU_OPT"),
        ),
    ] = False,
    no_interactive: Annotated[
        bool,
        typer.Option(
            "--no-interactive",
            help=i18n.t("MAIN_NOINT_OPT"),
        ),
    ] = False,
) -> None:
    """Run the deploy playbook against a remote VPS."""
    if ru:
        repl.set_session_lang("ru")
    if debug and verbose:
        typer.echo(i18n.t("MAIN_ERR_DEBUG_VERBOSE"), err=True)
        raise typer.Exit(2)
    if full_cleanup and no_cleanup:
        typer.echo(i18n.t("MAIN_ERR_CLEANUP_FLAGS"), err=True)
        raise typer.Exit(2)
    if runtime is not None and runtime not in SUPPORTED_RUNTIMES:
        typer.echo(
            i18n.t("MAIN_ERR_RUNTIME", runtimes=", ".join(SUPPORTED_RUNTIMES)),
            err=True,
        )
        raise typer.Exit(2)
    if pkey is not None and password is not None:
        typer.echo(i18n.t("MAIN_ERR_PKEY_PASS"), err=True)
        raise typer.Exit(2)

    mode = _resolve_execution(execution)

    if inventory is not None and mode != "local":
        typer.echo(i18n.t("MAIN_ERR_INV_LOCAL"), err=True)
        raise typer.Exit(2)

    if inventory is not None:
        inventory = inventory.expanduser().resolve()
    if pkey is not None and mode == "local":
        pkey = pkey.expanduser().resolve()
    if clients_dir is not None:
        clients_dir = clients_dir.expanduser().resolve()

    roots = runtime_paths.resolve_roots(find_repo=find_repo_root)
    repo_root, workspace, payload = roots.repo, roots.workspace, roots.payload
    load_settings(repo_root)
    overrides = _collect_overrides(locals())
    verbosity = 4 if verbose else (3 if debug else 0)
    cleanup = "full-cleanup" if full_cleanup else ("no-cleanup" if no_cleanup else "cleanup")

    if mode == "remote":
        _run_remote(
            repo_root,
            workspace=workspace,
            payload=payload,
            overrides=overrides,
            host=host,
            user=user,
            port=port,
            pkey=pkey,
            password=password,
            use_inventory=use_inventory,
            clients_dir=clients_dir,
            cleanup=cleanup,
            dry_run=dry_run,
            verbosity=verbosity,
            debug=debug,
            no_interactive=no_interactive,
        )
        return

    request = DeployRequest(
        repo_root=repo_root,
        workspace=workspace,
        overrides=overrides,
        clients_dir=clients_dir,
        dry_run=dry_run,
        verbosity=verbosity,
        debug=debug,
        inventory_path=inventory,
    )
    # `inventory_path` keeps the user-provided ssh inventory for local mode.
    _run_local(
        workspace,
        payload=payload,
        overrides=overrides,
        request=request,
        host=host,
        user=user,
        port=port,
        pkey=pkey,
        password=password,
        use_inventory=use_inventory,
        cleanup=cleanup,
        wsl_venv=wsl_venv,
        wsl_distro=wsl_distro,
        no_interactive=no_interactive,
    )


def _swap_guard(remote: FabricRemote, *, no_interactive: bool) -> None:
    """Low-memory guard: opt-in 1G swapfile before bootstrap (never silent)."""
    detect_mem, detect_swap = swap_status_commands()
    mem = remote.run(detect_mem, warn=True)
    swaps = remote.run(detect_swap, warn=True)
    try:
        mem_kb = int(mem.stdout.strip())
        swap_entries = int(swaps.stdout.strip())
    except ValueError:
        return
    if not swap_guard_needed(mem_kb, swap_entries):
        return
    typer.echo(
        i18n.t("MAIN_SWAP_LOW", mb=mem_kb // 1024),
        err=True,
    )
    if no_interactive or not prompts.is_interactive():
        typer.echo(i18n.t("MAIN_SWAP_NO_TTY"), err=True)
        return
    if not prompts.confirm(i18n.t("MAIN_SWAP_PROMPT")):
        typer.echo(i18n.t("MAIN_SWAP_DECLINED"), err=True)
        return
    for command in swap_guard_commands():
        result = remote.run(command, warn=True)
        if result.failed:
            typer.echo(
                i18n.t("MAIN_SWAP_FAIL", command=command, err=result.stderr),
                err=True,
            )
            raise typer.Exit(result.return_code or 1)
    typer.echo(i18n.t("MAIN_SWAP_DONE"))


def _run_remote(
    repo_root: Path,
    *,
    workspace: Path,
    payload: Path,
    overrides: dict[str, object],
    host: str | None,
    user: str,
    port: int,
    pkey: Path | None,
    password: str | None,
    use_inventory: bool,
    clients_dir: Path | None,
    cleanup: str,
    dry_run: bool,
    verbosity: int,
    debug: bool,
    no_interactive: bool,
) -> None:
    """Remote-mode entry: auth resolution, optional preview, then the executor."""
    user_vars: dict[str, object] = {}
    connection: dict[str, str] = {}
    if use_inventory:
        connection, user_vars = _inventory_creds(
            workspace,
            payload,
            host=host,
            user=user,
            port=port,
            pkey=pkey,
            password=password,
        )
        extra_vars = merge_overrides(user_vars, overrides)
        resolved_host = connection.get("ansible_host")
        resolved_user = connection.get("ansible_user", "root")
        resolved_port = int(connection.get("ansible_port", "22"))
        resolved_pkey = connection.get("ansible_ssh_private_key_file")
        resolved_password = connection.get("ansible_ssh_pass")
        flag_values = (host, pkey, password)
        if any(v is not None for v in flag_values):
            host = None
            pkey = None
            password = None
    else:
        extra_vars = dict(overrides)
        resolved_host = (host or "").strip() or None
        resolved_user = user
        resolved_port = port
        resolved_pkey = pkey
        resolved_password = password

    if dry_run:
        _preview_remote(repo_root, extra_vars, resolved_host, cleanup, verbosity, debug)
        return

    if not resolved_host:
        if no_interactive:
            typer.echo(i18n.t("MAIN_ERR_HOST_REMOTE"), err=True)
            raise typer.Exit(2)
        selected = prompts.text(i18n.t("COMMON_HOST_PROMPT"))
        if not selected:
            typer.echo(i18n.t("MAIN_ERR_HOST_REMOTE"), err=True)
            raise typer.Exit(2)
        resolved_host = selected

    if not use_inventory:
        resolved_host, resolved_user, resolved_port, alias_key = apply_ssh_config(
            str(resolved_host), str(resolved_user), int(resolved_port)
        )
        if resolved_pkey is None and resolved_password is None and alias_key:
            resolved_pkey = alias_key

    if resolved_pkey is not None and resolved_password is not None:
        typer.echo(i18n.t("MAIN_ERR_KEY_AND_PASS"), err=True)
        raise typer.Exit(2)
    if resolved_pkey is not None:
        key_path = Path(os.path.expandvars(str(resolved_pkey))).expanduser()
        if not key_path.is_file():
            typer.echo(i18n.t("MAIN_ERR_KEY_NOT_FOUND", path=key_path), err=True)
            raise typer.Exit(2)
    elif resolved_password is None:
        if no_interactive:
            typer.echo(i18n.t("MAIN_ERR_NOAUTH_NOINTERACTIVE"), err=True)
            raise typer.Exit(2)
        resolved_password = getpass.getpass(i18n.t("COMMON_SSH_PASS_PROMPT"))
        if not resolved_password:
            typer.echo(i18n.t("MAIN_ERR_EMPTY_PASSWORD"), err=True)
            raise typer.Exit(2)

    _confirm_deploy(
        _plan_lines(
            "remote",
            host=str(resolved_host),
            user=str(resolved_user),
            port=int(resolved_port),
            auth_desc=_auth_descriptor(resolved_pkey, resolved_password),
            overrides=extra_vars,
            clients_dir=Path(clients_dir or workspace / "downloaded-clients"),
            cleanup=cleanup,
        ),
        no_interactive=no_interactive,
    )

    request = DeployRequest(
        repo_root=repo_root,
        workspace=workspace,
        overrides=overrides,
        clients_dir=clients_dir,
        verbosity=verbosity,
        debug=debug,
    )
    if cleanup == "full-cleanup":
        typer.echo(i18n.t("MAIN_SWAP_KEPT_NOTE"), err=True)
    try:
        with FabricRemote(
            resolved_host,
            user=resolved_user,
            port=resolved_port,
            key_filename=str(key_path) if resolved_pkey else None,
            password=resolved_password,
        ) as remote:
            _swap_guard(remote, no_interactive=no_interactive)
            executor = RemoteExecutor(remote, cleanup=cleanup)
            rc = executor.deploy(request, extra_vars=extra_vars)
    except SshConnectError as exc:
        typer.echo(theme.err(i18n.t("COMMON_ERR", err=exc)), err=True)
        raise typer.Exit(2) from exc
    raise typer.Exit(rc)


def _preview_remote(
    repo_root: Path,
    extra_vars: dict[str, object],
    host: str | None,
    cleanup: str,
    verbosity: int,
    debug: bool,
) -> None:
    """Remote dry-run: show the plan without connecting anywhere."""
    typer.echo(i18n.t("MAIN_PREVIEW_REMOTE", host=host or "<host>"))
    typer.echo(i18n.t("MAIN_PREVIEW_SWAP_GUARD"))
    for command in bootstrap_commands():
        typer.echo(f"[preview] $ {command}")
    typer.echo(i18n.t("MAIN_PREVIEW_UPLOAD"))
    from xrayvpn.core import manifest

    for entry in manifest.allowlist_entries(repo_root):
        typer.echo(f"[preview]   {entry.name}")
    request = DeployRequest(repo_root=repo_root, overrides={}, verbosity=verbosity, debug=debug)
    typer.echo(f"[preview] $ {playbook_command(request, extra_vars)}")
    for command in cleanup_commands(cleanup):
        typer.echo(f"[preview] $ {command}")


def _key_for_runner(pkey: str) -> str:
    if wsl.is_windows():
        if pkey.startswith(("~", "/")):
            return pkey
        return wsl.to_wsl_path(pkey)
    return str(Path(pkey).expanduser())


def _key_exists_for_runner(pkey: str) -> bool:
    if wsl.is_windows():
        path = Path(pkey)
        if path.drive or pkey.startswith("~"):
            return path.expanduser().is_file() or pkey.startswith("~")
        return True
    return Path(pkey).expanduser().is_file()


def _run_local(
    workspace: Path,
    *,
    payload: Path,
    overrides: dict[str, object],
    request: DeployRequest,
    host: str | None,
    user: str,
    port: int,
    pkey: Path | None,
    password: str | None,
    use_inventory: bool,
    cleanup: str,
    wsl_venv: str,
    wsl_distro: str | None,
    no_interactive: bool,
) -> None:
    """Local control-node mode: ansible runs here, the target over SSH is the VPS."""
    user_vars: dict[str, object] = {}
    if use_inventory:
        connection, user_vars = _inventory_creds(
            workspace,
            payload,
            host=host,
            user=user,
            port=port,
            pkey=pkey,
            password=password,
        )
        resolved_host = connection.get("ansible_host")
        resolved_user = connection.get("ansible_user", "root")
        resolved_port = int(connection.get("ansible_port", "22"))
        resolved_pkey = connection.get("ansible_ssh_private_key_file")
        resolved_password = connection.get("ansible_ssh_pass")
    else:
        resolved_host = (host or "").strip() or None
        resolved_user = user
        resolved_port = port
        resolved_pkey = (
            str(Path(os.path.expandvars(str(pkey))).expanduser()) if pkey is not None else None
        )
        resolved_password = password

    extra_vars = merge_overrides(user_vars, overrides)
    request.overrides = extra_vars

    if request.dry_run:
        typer.echo(
            i18n.t(
                "MAIN_PREVIEW_LOCAL",
                user=resolved_user,
                host=resolved_host or "<host>",
                port=resolved_port,
            )
        )
        if wsl.is_windows():
            typer.echo(i18n.t("MAIN_PREVIEW_WSL"))
        typer.echo(
            f"[preview] $ {LocalExecutor(wsl_venv=wsl_venv).venv_binary()} deploy.yml -i <inventory> …"
        )
        return

    if not resolved_host:
        if no_interactive:
            typer.echo(i18n.t("MAIN_ERR_HOST_LOCAL"), err=True)
            raise typer.Exit(2)
        selected = prompts.text(i18n.t("COMMON_HOST_PROMPT"))
        if not selected:
            typer.echo(i18n.t("MAIN_ERR_HOST_LOCAL"), err=True)
            raise typer.Exit(2)
        resolved_host = selected

    alias: str | None = None
    if not use_inventory:
        requested = str(resolved_host)
        resolved_host, resolved_user, resolved_port, alias_key = apply_ssh_config(
            requested, str(resolved_user), int(resolved_port)
        )
        if resolved_host != requested:
            alias = requested
        if resolved_pkey is None and resolved_password is None and alias_key:
            resolved_pkey = alias_key

    if resolved_pkey is not None and resolved_password is not None:
        typer.echo(i18n.t("MAIN_ERR_KEY_AND_PASS"), err=True)
        raise typer.Exit(2)
    if resolved_pkey is not None and not _key_exists_for_runner(resolved_pkey):
        typer.echo(i18n.t("MAIN_ERR_KEY_NOT_FOUND", path=resolved_pkey), err=True)
        raise typer.Exit(2)
    if not resolved_pkey and not resolved_password:
        if no_interactive:
            typer.echo(i18n.t("MAIN_ERR_NOAUTH_NOINTERACTIVE"), err=True)
            raise typer.Exit(2)
        resolved_password = getpass.getpass(i18n.t("COMMON_SSH_PASS_PROMPT"))
        if not resolved_password:
            typer.echo(i18n.t("MAIN_ERR_EMPTY_PASSWORD"), err=True)
            raise typer.Exit(2)

    runner_pkey = _key_for_runner(resolved_pkey) if resolved_pkey else None

    _confirm_deploy(
        _plan_lines(
            "local",
            host=str(resolved_host),
            user=str(resolved_user),
            port=int(resolved_port),
            auth_desc=_auth_descriptor(runner_pkey, resolved_password),
            overrides=extra_vars,
            clients_dir=request.resolved_clients_dir(),
            cleanup=cleanup,
            alias=alias,
        ),
        no_interactive=no_interactive,
    )

    executor = LocalExecutor(wsl_venv=wsl_venv, wsl_distro=wsl_distro or None)
    inventory = request.inventory_path
    temp_inventory: Path | None = None
    if inventory is None:
        content = build_inventory(
            {},
            connection="ssh",
            host_params=build_ssh_inventory_vars(
                {
                    "host": str(resolved_host),
                    "user": str(resolved_user),
                    "port": str(resolved_port),
                    **({"pkey": str(runner_pkey)} if runner_pkey else {}),
                    **({"password": str(resolved_password)} if resolved_password else {}),
                }
            ),
        )
        temp_inventory = write_inventory(workspace, content)
        temp_inventory.chmod(0o600)
        inventory = temp_inventory

    try:
        try:
            executor.preflight(password_auth=bool(resolved_password))
        except RuntimeError as exc:
            typer.echo(theme.err(i18n.t("COMMON_ERR", err=exc)), err=True)
            raise typer.Exit(2) from exc
        rc = executor.deploy(request, inventory)
        if rc != 0:
            raise typer.Exit(rc)
        fetch_rc = executor.fetch_configs(request, inventory)
        if fetch_rc:
            typer.echo(
                i18n.t("MAIN_ERR_FETCH_CONFIGS", rc=fetch_rc),
                err=True,
            )
            raise typer.Exit(fetch_rc)
    finally:
        if temp_inventory is not None:
            temp_inventory.unlink(missing_ok=True)
    typer.echo(theme.ok(i18n.t("MAIN_DONE_LOCAL", path=request.resolved_clients_dir())))


if __name__ == "__main__":
    sys.exit(app())