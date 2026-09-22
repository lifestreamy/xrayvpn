from __future__ import annotations

import pytest

from xrayvpn.core.deploy_lock import DeployBusy, deploy_lock


def test_deploy_lock_is_exclusive_and_released() -> None:
    with deploy_lock(), pytest.raises(DeployBusy), deploy_lock():
        raise AssertionError("nested lock must not be acquired")
    with deploy_lock():
        pass
