"""Icon pipeline contract (scripts/make_icon.py): PNG master -> ICO/PNG/HTML outputs."""

from __future__ import annotations

import importlib.util
import struct
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("make_icon", _ROOT / "scripts" / "make_icon.py")
assert _spec and _spec.loader
icon_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(icon_mod)


@pytest.fixture(scope="session")
def rendered_rows() -> dict[int, list[bytes]]:
    return icon_mod.render(icon_mod.MASTER)


@pytest.fixture(scope="session")
def rendered_pngs(rendered_rows: dict[int, list[bytes]]) -> dict[int, bytes]:
    return {size: icon_mod.png_encode(rows, size) for size, rows in rendered_rows.items()}


def _ihdr(data: bytes) -> tuple[int, int, int, int]:
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    width, height, depth, color_type = struct.unpack(">IIBB", data[16:26])
    return width, height, depth, color_type


def test_master_is_square_rgba() -> None:
    width, height, rows = icon_mod.png_decode(icon_mod.MASTER.read_bytes())
    assert width == height > 0
    assert len(rows) == height and all(len(row) == width * 4 for row in rows)


def test_all_sizes_rendered_8bit_rgba(rendered_pngs: dict[int, bytes]) -> None:
    assert set(rendered_pngs) == set(icon_mod.SIZES)
    for size, data in rendered_pngs.items():
        assert _ihdr(data) == (size, size, 8, 6)


def test_ico_directory(rendered_pngs: dict[int, bytes]) -> None:
    data = icon_mod.ico_bytes(rendered_pngs)
    reserved, image_type, count = struct.unpack("<HHH", data[:6])
    assert (reserved, image_type) == (0, 1)
    assert count == len(icon_mod.SIZES)
    offset = 6 + 16 * count
    for index, size in enumerate(icon_mod.SIZES):
        entry = data[6 + 16 * index : 22 + 16 * index]
        edge_w, edge_h, colors, reserved_b, planes, bpp, length, start = struct.unpack(
            "<BBBBHHII", entry
        )
        assert (edge_w, edge_h, colors, reserved_b, planes, bpp) == (
            0 if size >= 256 else size,
            0 if size >= 256 else size,
            0,
            0,
            1,
            32,
        )
        assert start == offset
        assert data[start : start + 8] == b"\x89PNG\r\n\x1a\n"
        offset += length
    assert offset == len(data)


def test_committed_ico_matches_master(rendered_pngs: dict[int, bytes]) -> None:
    committed = icon_mod.OUT_ICO.read_bytes()
    assert committed == icon_mod.ico_bytes(rendered_pngs)


def test_committed_preview_png_matches_master(rendered_pngs: dict[int, bytes]) -> None:
    committed = icon_mod.OUT_PREVIEW_PNG.read_bytes()
    assert committed == rendered_pngs[icon_mod.PREVIEW_PNG_SIZE]


def test_corners_transparent(rendered_pngs: dict[int, bytes]) -> None:
    for size, data in rendered_pngs.items():
        _, _, rows = icon_mod.png_decode(data)
        first, last = rows[0], rows[-1]
        corners = (
            first[:4],
            first[(size - 1) * 4 : size * 4],
            last[:4],
            last[(size - 1) * 4 : size * 4],
        )
        assert all(tuple(px) == (0, 0, 0, 0) for px in corners), f"{size}px corners"


def test_despeckle_idempotent(rendered_rows: dict[int, list[bytes]]) -> None:
    for size in icon_mod.DESPECKLE_SIZES:
        rows = rendered_rows[size]
        assert icon_mod.despeckle(rows, size) == rows


def test_preview_lists_sizes_and_backgrounds(rendered_pngs: dict[int, bytes]) -> None:
    html = icon_mod.preview_html(rendered_pngs)
    for size in icon_mod.PREVIEW_SIZES:
        assert f"{size}px" in html
    assert "background:#ffffff" in html and "background:#1f2430" in html
