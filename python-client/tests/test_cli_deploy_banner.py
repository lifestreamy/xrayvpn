from __future__ import annotations

from pathlib import Path

import pytest

from xrayvpn import i18n
from xrayvpn.cli import main as cli_main


def test_deploy_success_banner_lists_configs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "client_0.json").write_text("{}")
    (tmp_path / "clash_client_0.yaml").write_text("")
    cli_main._deploy_success_banner(tmp_path)
    out = capsys.readouterr().out
    assert i18n.t("MAIN_DEPLOY_OK_TITLE") in out
    assert i18n.t("MAIN_DEPLOY_OK_CONFIGS") in out
    assert "client_0.json" in out
    assert "clash_client_0.yaml" in out
    assert i18n.t("MAIN_DEPLOY_OK_HINT", path=str(tmp_path)) in out


def test_deploy_success_banner_without_dir(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cli_main._deploy_success_banner(tmp_path / "missing")
    out = capsys.readouterr().out
    assert i18n.t("MAIN_DEPLOY_OK_TITLE") in out
    assert i18n.t("MAIN_DEPLOY_OK_CONFIGS") not in out

