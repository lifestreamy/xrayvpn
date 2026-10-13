"""Tests for core/update.py: explicit release discovery.

Network is injected everywhere; parsers are exercised on captured payload
shapes. The explicit path must fail loud (UpdateError), unlike the
fail-silent banner hint in update_check.
"""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from xrayvpn.core import update as upd

_SHA = "b" * 64


def _release_payload(tag: str, *, prerelease: bool = False, draft: bool = False) -> dict:
    return {
        "tag_name": tag,
        "prerelease": prerelease,
        "draft": draft,
        "published_at": "2026-01-01T00:00:00Z",
        "html_url": f"https://github.com/lifestreamy/xrayvpn/releases/tag/{tag}",
    }


def test_normalize_tag_strips_prefix_and_suffixes() -> None:
    assert upd.normalize_tag("v0.4.2") == "0.4.2"
    assert upd.normalize_tag("0.4.2") == "0.4.2"
    assert upd.normalize_tag("v0.4.2_experimental") == "0.4.2"
    assert upd.normalize_tag("v0.4.2+local") == "0.4.2"
    assert upd.normalize_tag("v0.4.2-rc1") == "0.4.2"


def test_parse_releases_filters_prerelease_and_drafts() -> None:
    payload = [
        _release_payload("v0.5.0"),
        _release_payload("v0.5.0_experimental", prerelease=True),
        _release_payload("v0.4.3", draft=True),
    ]
    stable = upd.parse_releases(payload)
    assert [release.tag for release in stable] == ["v0.5.0"]
    everything = upd.parse_releases(payload, include_prerelease=True)
    assert [release.tag for release in everything] == ["v0.5.0", "v0.5.0_experimental"]


def test_parse_releases_rejects_malformed_payload() -> None:
    with pytest.raises(upd.UpdateError):
        upd.parse_releases({"not": "a list"})
    assert upd.parse_releases([{"no_tag": True}, "garbage"]) == []


def test_parse_sums_accepts_binary_star_and_skips_malformed() -> None:
    text = f"{_SHA}  xrayvpn-0.4.2-windows-x64-portable.exe\n"
    text += "not-a-hash  file\n"
    text += f"{'c' * 63}  short.txt\n"
    text += "\n"
    text += f"{'d' * 64} *xrayvpn-0.4.2-linux-x64-portable\n"
    sums = upd.parse_sums(text)
    assert sums == {
        "xrayvpn-0.4.2-windows-x64-portable.exe": _SHA,
        "xrayvpn-0.4.2-linux-x64-portable": "d" * 64,
    }


def test_parse_latest_json_and_selection() -> None:
    payload = {
        "version": "0.4.2",
        "assets": {
            "windows-x64": {
                "name": "xrayvpn-0.4.2-windows-x64-portable.exe",
                "url": "https://example.invalid/win",
                "sha256": _SHA,
            },
            "linux-x64": {"name": "n", "url": "u", "sha256": "short"},
            "broken": "garbage",
        },
    }
    assets = upd.parse_latest_json(payload)
    assert set(assets) == {"windows-x64"}
    assert assets["windows-x64"].sha256 == _SHA
    selected = upd.select_asset(assets, platform="win32", machine="amd64")
    assert selected is not None and selected.name.endswith("-portable.exe")
    assert upd.select_asset(assets, platform="darwin", machine="x86_64") is None


def test_parse_latest_json_rejects_unusable_payloads() -> None:
    with pytest.raises(upd.UpdateError):
        upd.parse_latest_json([])
    with pytest.raises(upd.UpdateError):
        upd.parse_latest_json({})
    with pytest.raises(upd.UpdateError):
        upd.parse_latest_json({"assets": {"linux-x64": {"name": "n"}}})


def test_fetch_releases_uses_paged_api_url() -> None:
    seen: list[str] = []

    def http(url: str) -> bytes:
        seen.append(url)
        return json.dumps([_release_payload("v0.4.2")]).encode()

    releases = upd.fetch_releases(http=http, per_page=50, page=2)
    assert releases and releases[0].tag == "v0.4.2"
    assert seen[0] == f"{upd.RELEASES_API_URL}?per_page=50&page=2"


def test_fetch_releases_fail_loud() -> None:
    def boom(url: str) -> bytes:
        raise OSError("dial tcp timeout")

    with pytest.raises(upd.UpdateError):
        upd.fetch_releases(http=boom)
    with pytest.raises(upd.UpdateError):
        upd.fetch_releases(http=lambda url: b"not json")


def test_fetch_latest_release_parses_and_handles_empty_tag() -> None:
    payload = json.dumps(_release_payload("v0.4.2")).encode()
    release = upd.fetch_latest_release(http=lambda url: payload)
    assert release is not None and release.version == "0.4.2"
    assert upd.fetch_latest_release(http=lambda url: b'{"tag_name": ""}') is None
    with pytest.raises(upd.UpdateError):
        upd.fetch_latest_release(http=lambda url: b"[]")


def test_list_versions_filters_and_clamps() -> None:
    many = [_release_payload(f"v0.5.{index}") for index in range(25)]
    mixed = [_release_payload("v0.6.0_experimental", prerelease=True)] + many

    def http(url: str) -> bytes:
        return json.dumps(mixed).encode()

    stable = upd.list_versions(http=http)
    assert len(stable) == upd.LIST_LIMIT_DEFAULT
    assert all(not release.prerelease for release in stable)
    assert len(upd.list_versions(http=http, limit=999)) == upd.LIST_LIMIT_MAX
    with_pre = upd.list_versions(http=http, limit=30, include_prerelease=True)
    assert any(release.prerelease for release in with_pre)


def test_fetch_latest_json_url_and_parse() -> None:
    seen: list[str] = []
    payload = {
        "assets": {
            "linux-x64": {
                "name": "xrayvpn-0.4.2-linux-x64-portable",
                "url": "https://example.invalid/linux",
                "sha256": _SHA,
            }
        }
    }

    def http(url: str) -> bytes:
        seen.append(url)
        return json.dumps(payload).encode()

    assets = upd.fetch_latest_json("v0.4.2", http=http)
    assert seen[0].endswith("/v0.4.2/latest.json")
    assert assets["linux-x64"].url == "https://example.invalid/linux"


def test_fetch_sums_decodes_utf8_and_rejects_binary() -> None:
    text = f"{_SHA}  xrayvpn-0.4.2-windows-x64-portable.exe\n"
    sums = upd.fetch_sums("v0.4.2", http=lambda url: text.encode("utf-8"))
    assert sums == {"xrayvpn-0.4.2-windows-x64-portable.exe": _SHA}
    with pytest.raises(upd.UpdateError):
        upd.fetch_sums("v0.4.2", http=lambda url: b"\xff\xfe\x00")


def test_platform_token_map() -> None:
    assert upd.platform_token("win32", "AMD64") == "windows-x64"
    assert upd.platform_token("linux", "aarch64") == "linux-arm64"
    assert upd.platform_token("darwin", "arm64") == "macos-arm64"
    assert upd.platform_token("darwin", "x86_64") is None
    assert upd.platform_token("freebsd", "x86_64") is None


def test_download_asset_writes_and_verifies(tmp_path: Path) -> None:
    data = b"fresh-binary"
    digest = hashlib.sha256(data).hexdigest()
    dest = tmp_path / "xrayvpn.new"
    result = upd.download_asset(
        "https://dl/xrayvpn", dest, expected_sha256=digest, opener=lambda url: io.BytesIO(data)
    )
    assert result == digest
    assert dest.read_bytes() == data


def test_download_asset_rejects_bad_hash_and_removes_file(tmp_path: Path) -> None:
    dest = tmp_path / "xrayvpn.new"
    with pytest.raises(upd.UpdateError):
        upd.download_asset(
            "https://dl/xrayvpn",
            dest,
            expected_sha256="0" * 64,
            opener=lambda url: io.BytesIO(b"payload"),
        )
    assert not dest.exists()


def test_download_asset_enforces_size_cap(tmp_path: Path) -> None:
    dest = tmp_path / "xrayvpn.new"
    with pytest.raises(upd.UpdateError):
        upd.download_asset(
            "https://dl/xrayvpn",
            dest,
            expected_sha256="0" * 64,
            opener=lambda url: io.BytesIO(b"x" * 100),
            max_bytes=10,
            chunk_size=7,
        )
    assert not dest.exists()


def test_download_asset_wraps_opener_failures(tmp_path: Path) -> None:
    def boom(url: str) -> io.BytesIO:
        raise OSError("reset by peer")

    with pytest.raises(upd.UpdateError):
        upd.download_asset(
            "https://dl/xrayvpn", tmp_path / "x.new", expected_sha256="0" * 64, opener=boom
        )


def test_cross_check_sums() -> None:
    upd.cross_check_sums("xrayvpn-1-x", _SHA, {"xrayvpn-1-x": _SHA})
    with pytest.raises(upd.UpdateError):
        upd.cross_check_sums("xrayvpn-1-x", _SHA, {"xrayvpn-1-x": "c" * 64})
    with pytest.raises(upd.UpdateError):
        upd.cross_check_sums("xrayvpn-1-x", _SHA, {})


def test_swap_in_place_renames_and_keeps_backup(tmp_path: Path) -> None:
    target = tmp_path / "xrayvpn.exe"
    staged = tmp_path / "xrayvpn.exe.new"
    target.write_bytes(b"old")
    staged.write_bytes(b"new")
    backup = upd.swap_in_place(staged, target)
    assert backup == target.with_name("xrayvpn.exe.old")
    assert target.read_bytes() == b"new"
    assert backup.read_bytes() == b"old"
    assert not staged.exists()


def test_swap_in_place_restores_backup_on_failure(tmp_path: Path) -> None:
    target = tmp_path / "xrayvpn.exe"
    target.write_bytes(b"old")
    with pytest.raises(upd.UpdateError):
        upd.swap_in_place(tmp_path / "missing.new", target)
    assert target.read_bytes() == b"old"
    assert not target.with_name("xrayvpn.exe.old").exists()


def test_cleanup_backup_variants(tmp_path: Path) -> None:
    target = tmp_path / "xrayvpn.exe"
    assert upd.cleanup_backup(target) is True
    backup = target.with_name("xrayvpn.exe.old")
    backup.write_bytes(b"stale")
    assert upd.cleanup_backup(target) is True
    assert not backup.exists()
    backup.mkdir()
    assert upd.cleanup_backup(target) is False


def test_relaunch_uses_injected_spawner(tmp_path: Path) -> None:
    target = tmp_path / "xrayvpn.exe"
    calls: list[list[str]] = []
    upd.relaunch(target, spawner=lambda argv: calls.append(argv))
    assert calls == [[str(target)]]


class _Http:
    def __init__(self, responses: dict[str, bytes]) -> None:
        self.responses = responses
        self.urls: list[str] = []

    def __call__(self, url: str) -> bytes:
        self.urls.append(url)
        for fragment, payload in self.responses.items():
            if fragment in url:
                return payload
        raise AssertionError(f"unexpected URL {url}")


_ASSET_DATA = b"new-binary"
_ASSET_SHA = hashlib.sha256(_ASSET_DATA).hexdigest()
_ASSET_NAME = "xrayvpn-9.9.9-windows-x64-portable.exe"


def _responses(
    *, tag: str = "v9.9.9", name: str = _ASSET_NAME, sha: str = _ASSET_SHA
) -> dict[str, bytes]:
    latest_json = {
        "assets": {"windows-x64": {"name": name, "url": f"https://dl/{name}", "sha256": sha}}
    }
    return {
        "releases/latest": json.dumps(_release_payload(tag)).encode(),
        "releases?per_page": json.dumps([_release_payload(tag)]).encode(),
        "latest.json": json.dumps(latest_json).encode(),
        "SHA256SUMS.txt": f"{sha}  {name}\n".encode(),
    }


def test_perform_standalone_update_updates_and_backs_up(tmp_path: Path) -> None:
    target = tmp_path / "xrayvpn.exe"
    target.write_bytes(b"old")
    outcome = upd.perform_standalone_update(
        target,
        current="0.4.2",
        platform="win32",
        machine="amd64",
        http=_Http(_responses()),
        opener=lambda url: io.BytesIO(_ASSET_DATA),
    )
    assert outcome.status == upd.STATUS_UPDATED
    assert outcome.version == "9.9.9"
    assert outcome.backup == target.with_name("xrayvpn.exe.old")
    assert target.read_bytes() == _ASSET_DATA
    assert outcome.backup.read_bytes() == b"old"


def test_perform_standalone_update_up_to_date_skips_download(tmp_path: Path) -> None:
    target = tmp_path / "xrayvpn.exe"
    target.write_bytes(b"old")

    def opener(url: str) -> io.BytesIO:
        raise AssertionError("up-to-date must not download")

    outcome = upd.perform_standalone_update(
        target,
        current="9.9.9",
        platform="win32",
        machine="amd64",
        http=_Http(_responses()),
        opener=opener,
    )
    assert outcome.status == upd.STATUS_UP_TO_DATE
    assert target.read_bytes() == b"old"


def test_perform_standalone_update_pinned_version_allows_downgrade(tmp_path: Path) -> None:
    target = tmp_path / "xrayvpn.exe"
    target.write_bytes(b"old")
    http = _Http(_responses(tag="v0.4.2"))
    outcome = upd.perform_standalone_update(
        target,
        current="9.9.9",
        platform="win32",
        machine="amd64",
        requested_version="0.4.2",
        http=http,
        opener=lambda url: io.BytesIO(_ASSET_DATA),
    )
    assert outcome.status == upd.STATUS_UPDATED
    assert outcome.version == "0.4.2"
    assert any("releases?per_page" in url for url in http.urls)


def test_perform_standalone_update_unknown_pin_fails(tmp_path: Path) -> None:
    target = tmp_path / "xrayvpn.exe"
    target.write_bytes(b"old")
    with pytest.raises(upd.UpdateError):
        upd.perform_standalone_update(
            target,
            current="0.4.2",
            platform="win32",
            machine="amd64",
            requested_version="0.1.0",
            http=_Http(_responses()),
        )


def test_perform_standalone_update_rejects_missing_sum_line(tmp_path: Path) -> None:
    target = tmp_path / "xrayvpn.exe"
    target.write_bytes(b"old")
    responses = _responses()
    responses["SHA256SUMS.txt"] = f"{_ASSET_SHA}  other-file\n".encode()
    with pytest.raises(upd.UpdateError):
        upd.perform_standalone_update(
            target,
            current="0.4.2",
            platform="win32",
            machine="amd64",
            http=_Http(responses),
            opener=lambda url: io.BytesIO(_ASSET_DATA),
        )
    assert target.read_bytes() == b"old"


def test_perform_standalone_update_platform_without_build(tmp_path: Path) -> None:
    target = tmp_path / "xrayvpn.exe"
    target.write_bytes(b"old")
    with pytest.raises(upd.UpdateError):
        upd.perform_standalone_update(
            target,
            current="0.4.2",
            platform="linux",
            machine="mips",
            http=_Http(_responses()),
        )


def test_perform_standalone_update_missing_target_probes_nothing(tmp_path: Path) -> None:
    http = _Http({})
    with pytest.raises(upd.UpdateError):
        upd.perform_standalone_update(
            tmp_path / "absent.exe",
            current="0.4.2",
            platform="win32",
            machine="amd64",
            http=http,
        )
    assert http.urls == []


def test_manager_plan_execute_only_uv_and_pipx() -> None:
    uv = upd.manager_plan(upd.UV_TOOL)
    pipx = upd.manager_plan(upd.PIPX)
    assert uv is not None and uv.executable
    assert pipx is not None and pipx.executable
    assert uv.commands == (("uv", "tool", "upgrade", "xrayvpn"),)
    for kind in (upd.PIP, upd.BREW, upd.APT, upd.PACMAN, upd.WINGET):
        plan = upd.manager_plan(kind)
        assert plan is not None and not plan.executable
    assert upd.manager_plan(upd.UNKNOWN) is None
    assert upd.manager_plan(upd.STANDALONE) is None


def test_manager_plan_apt_and_winget_shapes() -> None:
    apt = upd.manager_plan(upd.APT)
    assert apt is not None
    assert apt.commands[0][:2] == ("sudo", "apt")
    winget = upd.manager_plan(upd.WINGET)
    assert winget is not None
    assert "--exact" in winget.commands[0]
    assert "Lifestreamy.XrayVpn" in winget.commands[0]


def test_pin_hints() -> None:
    assert upd.pin_hint(upd.PIP, "0.4.2") == 'python -m pip install "xrayvpn==0.4.2"'
    assert upd.pin_hint(upd.UV_TOOL, "0.4.2") == "uv tool install xrayvpn==0.4.2"
    assert upd.pin_hint(upd.BREW, "0.4.2") == "brew pin xrayvpn"
    assert upd.pin_hint(upd.UNKNOWN, "0.4.2") is None
    assert upd.pin_hint(upd.STANDALONE, "0.4.2") is None


def test_run_manager_command_executes_only_allowed_kinds() -> None:
    calls: list[list[str]] = []

    def runner(argv: list[str], **kwargs: object) -> object:
        calls.append(argv)
        return SimpleNamespace(returncode=0)

    rc = upd.run_manager_command(upd.PIPX, ["pipx", "upgrade", "xrayvpn"], runner=runner)
    assert rc == 0
    assert calls == [["pipx", "upgrade", "xrayvpn"]]
    with pytest.raises(upd.UpdateError):
        upd.run_manager_command(upd.PIP, ["python", "-m", "pip", "install", "xrayvpn"], runner=runner)
    assert len(calls) == 1


def test_run_manager_command_wraps_failures() -> None:
    def runner(argv: list[str], **kwargs: object) -> object:
        raise OSError("exec format error")

    with pytest.raises(upd.UpdateError):
        upd.run_manager_command(upd.UV_TOOL, ["uv", "tool", "upgrade", "xrayvpn"], runner=runner)


def test_run_manager_command_reports_returncode() -> None:
    def runner(argv: list[str], **kwargs: object) -> object:
        return SimpleNamespace(returncode=5)

    assert upd.run_manager_command(upd.PIPX, ["pipx", "upgrade", "xrayvpn"], runner=runner) == 5
