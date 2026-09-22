"""`xrayvpn service` — whitelisted recovery actions over the existing SSH transport."""

from __future__ import annotations

import getpass
import re
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated, NoReturn

import typer

from xrayvpn import i18n
from xrayvpn.cli import prompts, repl, theme
from xrayvpn.core.config import find_repo_root, load_settings, merge_overrides
from xrayvpn.core.conn import ConnResolveError, ResolvedConnection, resolve_connection
from xrayvpn.core.inventory import parse_user_inventory
from xrayvpn.core.runtime_paths import RunRoots, resolve_roots
from xrayvpn.core.service_actions import (
    DEFAULT_CONFIG_DIR,
    deep_status_commands,
    logs_journal_command,
    parse_egress,
    parse_reality,
    parse_runtime,
    parse_version,
    parse_warp,
    reboot_command,
    restart_commands,
    status_commands,
)
from xrayvpn.core.transport.remote import CommandResult, FabricRemote, SshConnectError

HOST_OPT = Annotated[
    str | None,
    typer.Option(
        "--host", "-H",
        help=i18n.t("SVC_HOST_OPT"),
    ),
]
USER_OPT = Annotated[
    str,
    typer.Option("--user", "-u", help=i18n.t("COMMON_USER")),
]
PORT_OPT = Annotated[
    int,
    typer.Option("--port", "-p", help=i18n.t("COMMON_PORT")),
]
PKEY_OPT = Annotated[
    Path | None,
    typer.Option(
        "--pkey", help=i18n.t("COMMON_PKEY")
    ),
]
PASS_OPT = Annotated[
    str | None,
    typer.Option(
        "--pass",
        help=i18n.t("COMMON_PASS"),
    ),
]
INVENTORY_OPT = Annotated[
    bool,
    typer.Option(
        "--use-inventory",
        help=i18n.t("SVC_INVENTORY_OPT"),
    ),
]
RU_OPT = Annotated[
    bool,
    typer.Option(
        "--ru",
        help=i18n.t("SVC_RU_OPT"),
    ),
]
NO_INTERACTIVE_OPT = Annotated[
    bool,
    typer.Option(
        "--no-interactive",
        help=i18n.t("SVC_NOINT_OPT"),
    ),
]

SINCE_OPT = Annotated[
    str,
    typer.Option(
        "--since",
        help=i18n.t("SVC_SINCE_OPT"),
    ),
]
LINES_OPT = Annotated[
    int | None,
    typer.Option(
        "--lines",
        help=i18n.t("SVC_LINES_OPT"),
    ),
]
OUT_OPT = Annotated[
    Path | None,
    typer.Option(
        "--out",
        help=i18n.t("SVC_OUT_OPT"),
    ),
]
YES_OPT = Annotated[
    bool,
    typer.Option(
        "--yes",
        help=i18n.t("SVC_YES_OPT"),
    ),
]

_SINCE_RE = re.compile(r"^-?(\d+)(m|h|d)$")

service_app = typer.Typer(
    help=i18n.t("SVC_HELP"),
    no_args_is_help=True,
)


def _fail(message: str) -> NoReturn:
    typer.echo(theme.err(i18n.t("COMMON_ERR", err=message)), err=True)
    raise typer.Exit(2)


def _run(remote: FabricRemote, command: str) -> CommandResult:
    return remote.run(command, warn=True, hide=True)


class _Tee:
    """Streaming mirror for the journal dump: file line by line, a progress
    dot on stderr per 200 lines."""

    def __init__(self, path: Path) -> None:
        self._handle = path.open("w", encoding="utf-8")
        self.lines = 0
        self._dots = 0

    def write(self, text: str) -> None:
        self._handle.write(text)
        self.lines += text.count("\n")
        dots = self.lines // 200
        if dots > self._dots:
            self._dots = dots
            typer.echo(".", err=True, nl=False)

    def flush(self) -> None:
        self._handle.flush()

    def close(self) -> None:
        self._handle.close()


def _normalize_since(value: str) -> str:
    match = _SINCE_RE.match(value.strip())
    if not match:
        _fail(i18n.t("SVC_SINCE_INVALID", value=value))
    return f"{match.group(1)}{match.group(2)}"


def _roots() -> RunRoots:
    return resolve_roots(find_repo=find_repo_root)


def _resolve_conn(
    host: str | None,
    user: str,
    port: int,
    pkey: Path | None,
    password: str | None,
    use_inventory: bool,
    no_interactive: bool,
    roots: RunRoots,
) -> ResolvedConnection:
    interactive = prompts.is_interactive() and not no_interactive
    try:
        return resolve_connection(
            workspace=roots.workspace,
            example_dir=roots.payload,
            host=host,
            user=user,
            port=port,
            pkey=pkey,
            password=password,
            use_inventory=use_inventory,
            no_interactive=no_interactive,
            ask_host=(lambda q: prompts.text(i18n.t("COMMON_HOST_PROMPT"))) if interactive else None,
            ask_password=(lambda _q: getpass.getpass(i18n.t("COMMON_SSH_PASS_PROMPT"))) if interactive else None,
        )
    except ConnResolveError as exc:
        _fail(str(exc))


@contextmanager
def _open(conn: ResolvedConnection) -> Iterator[FabricRemote]:
    try:
        with FabricRemote(
            conn.host,
            user=conn.user,
            port=conn.port,
            key_filename=conn.pkey,
            password=conn.password,
        ) as remote:
            yield remote
    except SshConnectError as exc:
        _fail(str(exc))


def _settings_facts(
    roots: RunRoots, use_inventory: bool
) -> tuple[int, int, str, str | None]:
    try:
        settings = load_settings(roots.repo)
    except (RuntimeError, OSError):
        settings = {}
    if use_inventory:
        # deploy-identical override chain: inventory user_vars win over settings.yml
        try:
            _, user_vars = parse_user_inventory(roots.workspace, example_dir=roots.payload)
            settings = merge_overrides(settings, user_vars)
        except (RuntimeError, TypeError):
            pass
    expected = settings.get("xray_version")
    return (
        int(settings.get("xray_port", 443)),
        int(settings.get("xray_watchdog_probe_port", 10820)),
        str(settings.get("xray_config_dir") or DEFAULT_CONFIG_DIR),
        str(expected) if expected is not None else None,
    )


def _apply_ru(ru: bool) -> None:
    if ru:
        repl.set_session_lang("ru")


@service_app.command("status")
def service_status(
    host: HOST_OPT = None,
    user: USER_OPT = "root",
    port: PORT_OPT = 22,
    pkey: PKEY_OPT = None,
    password: PASS_OPT = None,
    use_inventory: INVENTORY_OPT = False,
    ru: RU_OPT = False,
    no_interactive: NO_INTERACTIVE_OPT = False,
) -> None:
    """Show service state, journal tail, listeners and memory."""
    _apply_ru(ru)
    roots = _roots()
    conn = _resolve_conn(host, user, port, pkey, password, use_inventory, no_interactive, roots)
    xray_port, probe_port, config_dir, expected_version = _settings_facts(roots, use_inventory)
    with _open(conn) as remote:
        results = [_run(remote, cmd) for cmd in status_commands(xray_port, probe_port)]
        deep = [
            _run(remote, cmd)
            for cmd in deep_status_commands(xray_port, probe_port, config_dir)
        ]
    active = results[0].stdout.strip() or "?"
    facts = dict(
        line.split("=", 1) for line in results[1].stdout.splitlines() if "=" in line
    )
    storm = results[2].stdout.strip() or "?"
    title = i18n.t("SVC_STATUS_TITLE", host=conn.host, port=conn.port, active=active)
    typer.echo(theme.ok(title) if active == "active" else theme.err(title))
    typer.echo(i18n.t(
        "SVC_STATUS_FACTS",
        n=facts.get("NRestarts", "?"),
        since=facts.get("ActiveEnterTimestamp", "?"),
        sub=facts.get("SubState", "?"),
    ))
    storm_line = i18n.t("SVC_STATUS_STORM", count=storm)
    try:
        storm_hit = int(storm) > 0
    except ValueError:
        storm_hit = False
    typer.echo(theme.warn(storm_line) if storm_hit else storm_line)
    typer.echo(i18n.t("SVC_STATUS_ERRORS"))
    error_lines = [line for line in results[3].stdout.splitlines() if line.strip()]
    if error_lines:
        for line in error_lines:
            typer.echo(f"  {line}")
    else:
        typer.echo(i18n.t("SVC_STATUS_NO_ERRORS"))
    typer.echo(i18n.t("SVC_JOURNAL_TAIL"))
    for line in results[4].stdout.splitlines():
        typer.echo(f"  {line}")
    typer.echo(i18n.t("SVC_LISTENERS"))
    for line in results[5].stdout.splitlines():
        typer.echo(f"  {line}")
    typer.echo(i18n.t("SVC_MEMORY"))
    for line in results[6].stdout.splitlines()[:3]:
        typer.echo(f"  {line}")
    _echo_deep_sections(deep, expected_version)
    raise typer.Exit(0 if active == "active" else 1)


def _echo_deep_sections(deep: list[CommandResult], expected_version: str | None) -> None:
    runtime_info = parse_runtime(deep[0].stdout)
    version_info = parse_version(deep[1].stdout, expected_version)
    reality_info = parse_reality(deep[2].stdout)
    warp_info = parse_warp(deep[3].stdout)
    egress_info = parse_egress(deep[4].stdout, deep[5].stdout)

    typer.echo(i18n.t("SVC_DEEP_RUNTIME", runtime=runtime_info["runtime"]))
    version = version_info["version"]
    if version is None:
        typer.echo(theme.warn(i18n.t("SVC_DEEP_VERSION_NA")))
    elif version_info["match"] is False:
        typer.echo(theme.warn(i18n.t(
            "SVC_DEEP_VERSION_MISMATCH", version=version, expected=expected_version
        )))
    elif version_info["match"] is True:
        typer.echo(i18n.t("SVC_DEEP_VERSION_OK", version=version))
    else:
        typer.echo(i18n.t("SVC_DEEP_VERSION", version=version))

    if reality_info["mtime"] is None:
        typer.echo(theme.warn(i18n.t("SVC_DEEP_REALITY_NA")))
    else:
        age = i18n.t(
            "SVC_DEEP_AGE", days=reality_info["age_days"], hours=reality_info["age_hours"]
        )
        typer.echo(i18n.t(
            "SVC_DEEP_REALITY",
            age=age,
            prefix=reality_info["public_prefix"] or "?",
            sid=reality_info["short_id"] or "?",
            clients="?" if reality_info["clients"] is None else reality_info["clients"],
        ))

    server_ip = egress_info["server_ip"] or "n/a"
    if warp_info["warp"] is True:
        if egress_info["egress_ip"] is None:
            typer.echo(theme.warn(i18n.t("SVC_DEEP_WARP_NO_PROBE")))
        else:
            line = i18n.t(
                "SVC_DEEP_WARP_ON", egress=egress_info["egress_ip"], server=server_ip
            )
            typer.echo(theme.warn(line) if egress_info["differs"] is False else line)
    elif warp_info["warp"] is False:
        typer.echo(i18n.t("SVC_DEEP_WARP_OFF", server=server_ip))
    else:
        typer.echo(theme.warn(i18n.t("SVC_DEEP_WARP_NA")))


@service_app.command("restart")
def service_restart(
    host: HOST_OPT = None,
    user: USER_OPT = "root",
    port: PORT_OPT = 22,
    pkey: PKEY_OPT = None,
    password: PASS_OPT = None,
    use_inventory: INVENTORY_OPT = False,
    ru: RU_OPT = False,
    no_interactive: NO_INTERACTIVE_OPT = False,
) -> None:
    """Point-restart xray.service (WARP lives inside it; the host is untouched)."""
    _apply_ru(ru)
    roots = _roots()
    conn = _resolve_conn(host, user, port, pkey, password, use_inventory, no_interactive, roots)
    with _open(conn) as remote:
        for cmd in restart_commands()[:2]:
            result = _run(remote, cmd)
            if result.failed:
                _fail(f"{cmd} → rc={result.return_code} {result.stderr.strip()[:200]}")
        after = _run(remote, restart_commands()[2]).stdout.strip()
    typer.echo(theme.ok(i18n.t("SVC_RESTARTED", state=after)))
    raise typer.Exit(0 if after == "active" else 1)


@service_app.command("logs")
def service_logs(
    host: HOST_OPT = None,
    user: USER_OPT = "root",
    port: PORT_OPT = 22,
    pkey: PKEY_OPT = None,
    password: PASS_OPT = None,
    use_inventory: INVENTORY_OPT = False,
    ru: RU_OPT = False,
    no_interactive: NO_INTERACTIVE_OPT = False,
    since: SINCE_OPT = "30m",
    out: OUT_OPT = None,
    lines: LINES_OPT = None,
) -> None:
    """Dump the server journal (xray + obs + watchdog) to a local file."""
    _apply_ru(ru)
    since_norm = _normalize_since(since)
    if lines is not None and lines <= 0:
        _fail(i18n.t("SVC_LINES_INVALID", value=lines))
    roots = _roots()
    conn = _resolve_conn(host, user, port, pkey, password, use_inventory, no_interactive, roots)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    if out is not None and (out.suffix == ".txt" or (out.exists() and out.is_file())):
        local = out.expanduser().resolve()
    else:
        target_dir = (out.expanduser().resolve() if out is not None else roots.workspace / "logs")
        target_dir.mkdir(parents=True, exist_ok=True)
        local = target_dir / f"logs-{conn.host}-{stamp}.txt"
    local.parent.mkdir(parents=True, exist_ok=True)
    tee = _Tee(local)
    try:
        with _open(conn) as remote:
            dump = remote.run(
                logs_journal_command(since_norm, lines), warn=True, out_stream=tee
            )
    except KeyboardInterrupt:
        tee.close()
        typer.echo(
            i18n.t("SVC_LOGS_CANCELLED", path=local, lines=tee.lines), err=True
        )
        raise typer.Exit(130) from None
    tee.close()
    if dump.failed:
        _fail(f"log read failed (rc={dump.return_code}) {dump.stderr.strip()[:200]}")
    typer.echo(theme.ok(i18n.t("SVC_LOGS_SAVED", since=since_norm, path=local, lines=tee.lines)))


@service_app.command("reboot")
def service_reboot(
    host: HOST_OPT = None,
    user: USER_OPT = "root",
    port: PORT_OPT = 22,
    pkey: PKEY_OPT = None,
    password: PASS_OPT = None,
    use_inventory: INVENTORY_OPT = False,
    ru: RU_OPT = False,
    no_interactive: NO_INTERACTIVE_OPT = False,
    yes: YES_OPT = False,
) -> None:
    """Reboot the HOST — the last resort; explicit --yes is mandatory."""
    _apply_ru(ru)
    if not yes:
        typer.echo(i18n.t("SVC_REBOOT_NEED_YES"), err=True)
        raise typer.Exit(2)
    roots = _roots()
    conn = _resolve_conn(host, user, port, pkey, password, use_inventory, no_interactive, roots)
    with _open(conn) as remote:
        result = _run(remote, reboot_command())
    if result.failed:
        _fail(f"reboot failed (rc={result.return_code}) {result.stderr.strip()[:200]}")
    typer.echo(theme.ok(i18n.t("SVC_REBOOTING", host=conn.host)))
