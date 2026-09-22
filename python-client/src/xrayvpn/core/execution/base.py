"""Executor protocol and shared deploy request (ADR-003: one client, two modes)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol


def extra_var_args(overrides: dict[str, Any]) -> list[str]:
    """Render overrides as a single JSON `-e` argument.

    Per-key `-e k=v` passes strings ("false" is truthy in Jinja templates);
    JSON keeps real types (bools stay false).
    """
    return ["-e", json.dumps(overrides, sort_keys=True)]


@dataclass
class DeployRequest:
    """Everything an executor needs to run the deploy playbook."""

    repo_root: Path
    workspace: Path | None = None
    overrides: dict[str, Any] = field(default_factory=dict)
    clients_dir: Path | None = None
    dry_run: bool = False
    verbosity: int = 0
    debug: bool = False
    inventory_path: Path | None = None
    download_configs: bool = True

    def resolved_workspace(self) -> Path:
        return self.workspace or self.repo_root

    def resolved_clients_dir(self) -> Path:
        return self.clients_dir or (self.resolved_workspace() / "downloaded-clients")


class Executor(Protocol):
    def deploy(self, request: DeployRequest) -> int: ...

    def fetch_configs(self, request: DeployRequest) -> None: ...

    def cleanup(self, request: DeployRequest) -> None: ...