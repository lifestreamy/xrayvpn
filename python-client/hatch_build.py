"""Hatchling build hook: bundle the repo payload into the wheel (MYXRAY-31).

Staging reuses the binary contract in `build_support` (upload allowlist + example).
When the project is built outside a repo checkout (e.g. from an sdist), bundling
is skipped: wheels are the shipped artifact; sdists stay source-only.
"""

from __future__ import annotations

import sys
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_support


class PayloadBundleHook(BuildHookInterface):
    def initialize(self, version: str, build_data: dict) -> None:
        repo_root = Path(self.root).parent
        if not (repo_root / "deploy.yml").is_file():
            return
        stage = Path(self.root) / "build" / "payload-wheel"
        build_support.stage_payload(stage, repo_root)
        mapping = build_data.setdefault("force_include", {})
        for source, arc in build_support.payload_map(stage):
            mapping[source.relative_to(self.root).as_posix()] = arc
