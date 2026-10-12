"""Tests for core/update.py: explicit release discovery.

Network is injected everywhere; parsers are exercised on captured payload
shapes. The explicit path must fail loud (UpdateError), unlike the
fail-silent banner hint in update_check.
"""

from __future__ import annotations

import json

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
