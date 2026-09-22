"""Стражи единого источника констант развёртывания.

Пины версий и пути живут только в `xrayvpn.core.config`; CI-окружение molecule
должно совпадать с `ANSIBLE_CORE_PIN`, а executors — не переобъявлять его.
"""

from __future__ import annotations

import re
from pathlib import Path

from xrayvpn.core import config
from xrayvpn.core.execution import local, remote

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_ansible_core_pin_matches_molecule_ci_env() -> None:
    workflow = (REPO_ROOT / ".github" / "workflows" / "molecule.yml").read_text(encoding="utf-8")
    match = re.search(r'ANSIBLE_CORE_VERSION:\s*"([^"]+)"', workflow)
    assert match, "molecule.yml lost its ANSIBLE_CORE_VERSION env"
    assert match.group(1) == config.ANSIBLE_CORE_PIN


def test_executors_do_not_redeclare_the_pin_or_paths() -> None:
    for module in (remote, local):
        source = Path(module.__file__).read_text(encoding="utf-8")
        assert f'"{config.ANSIBLE_CORE_PIN}"' not in source
        for name in ("SERVER_VENV", "SERVER_STAGING", "CONFIG_SOURCE", "DEFAULT_WSL_VENV"):
            assert not re.search(rf"^{name} = ", source, re.MULTILINE)
        assert f'"{config.GALAXY_COLLECTION}"' not in source


def test_derived_collection_dir_matches_galaxy_layout() -> None:
    assert config.GALAXY_COLLECTION_DIR == "ansible_collections/community/general"
