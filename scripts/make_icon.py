"""Icon pipeline for xrayvpn: PNG master -> multi-size ICO, preview PNG/HTML.

stdlib-only. The raster source of truth is
``assets/icon/master/xrayvpn-icon-master-main.png`` (3072x3072, 8-bit RGBA,
non-interlaced). Downscaling is exact area-average (integer box filter,
round-to-nearest); the 16px and 24px outputs additionally pass a
deterministic 3x3 mode despeckle. No palette quantization, no pixel-art.

Re-run after editing the master:  python scripts/make_icon.py
The PNG reader accepts 8-bit RGB/RGBA non-interlaced files; anything else
raises a clear error.
"""

from __future__ import annotations

import argparse
import base64
import itertools
import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

MASTER = ROOT / "assets" / "icon" / "master" / "xrayvpn-icon-master-main.png"

SIZES: tuple[int, ...] = (16, 24, 32, 48, 64, 128, 256)
DESPECKLE_SIZES: tuple[int, ...] = (16, 24)
PREVIEW_SIZES: tuple[int, ...] = (16, 32, 48, 256)
PREVIEW_PNG_SIZE = 256

OUT_ICO = ROOT / "assets" / "icon" / "windows" / "xrayvpn.ico"
OUT_PREVIEW_PNG = ROOT / "assets" / "icon" / "icon-preview.png"
OUT_PREVIEW_HTML = ROOT / "assets" / "icon" / "icon-preview.html"


def _chunk(tag: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))


def png_decode(data: bytes) -> tuple[int, int, list[bytes]]:
    """Decode an 8-bit RGB/RGBA non-interlaced PNG into RGBA row bytes."""
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG file")
    pos = 8
    width = height = 0
    color_type = 0
    idat = b""
    while pos + 8 <= len(data):
        (length,) = struct.unpack(">I", data[pos : pos + 4])
        tag = data[pos + 4 : pos + 8]
        chunk = data[pos + 8 : pos + 8 + length]
        if tag == b"IHDR":
            width, height, depth, color_type, comp, filt, interlace = struct.unpack(
                ">IIBBBBB", chunk
            )
            if depth != 8 or interlace != 0 or comp != 0 or filt != 0:
                raise ValueError("only 8-bit non-interlaced deflate PNGs are supported")
            if color_type not in (2, 6):
                raise ValueError("only RGB and RGBA color types are supported")
        elif tag == b"IDAT":
            idat += chunk
        elif tag == b"IEND":
            break
        pos += 12 + length
    if not width or not height:
        raise ValueError("missing IHDR")
    bpp = 4 if color_type == 6 else 3
    stride = width * bpp
    raw = zlib.decompress(idat)
    out_stride = width * 4
    mask7 = int.from_bytes(b"\x7f" * out_stride, "big")
    mask8 = int.from_bytes(b"\x80" * out_stride, "big")
    rows: list[bytes] = []
    prev = bytearray(out_stride)
    pos = 0
    accumulate = itertools.accumulate
    for _ in range(height):
        f = raw[pos]
        pos += 1
        line = bytearray(raw[pos : pos + stride])
        pos += stride
        if bpp == 3:
            widened = bytearray(out_stride)
            widened[0::4] = line[0::3]
            widened[1::4] = line[1::3]
            widened[2::4] = line[2::3]
            widened[3::4] = b"\xff" * width
            line = widened
        if f == 0:
            pass
        elif f == 1:
            for c in range(4):
                line[c::4] = bytes(v & 255 for v in accumulate(line[c::4]))
        elif f == 2:
            a = int.from_bytes(line, "big")
            b = int.from_bytes(prev, "big")
            line = bytearray(
                (((a & mask7) + (b & mask7)) ^ ((a ^ b) & mask8)).to_bytes(out_stride, "big")
            )
        elif f == 3:
            for i in range(out_stride):
                left = line[i - 4] if i >= 4 else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 255
        elif f == 4:
            for i in range(out_stride):
                a = line[i - 4] if i >= 4 else 0
                b = prev[i]
                c = prev[i - 4] if i >= 4 else 0
                p = a + b - c
                pa, pb, pc = p - a, p - b, p - c
                if pa < 0:
                    pa = -pa
                if pb < 0:
                    pb = -pb
                if pc < 0:
                    pc = -pc
                if pa <= pb and pa <= pc:
                    pr = a
                elif pb <= pc:
                    pr = b
                else:
                    pr = c
                line[i] = (line[i] + pr) & 255
        else:
            raise ValueError(f"unknown PNG filter {f}")
        rows.append(bytes(line))
        prev = line
    return width, height, rows


def area_average(rows: list[bytes], side: int, size: int) -> list[bytes]:
    """Exact integer box downscale side -> size with round-to-nearest."""
    if side % size:
        raise ValueError(f"side {side} is not divisible by target size {size}")
    ratio = side // size
    denom = ratio * ratio
    half = denom // 2
    out: list[bytes] = []
    accum: list[int] = []
    for y, row in enumerate(rows):
        r0, r1, r2, r3 = (row[c::4] for c in range(4))
        red = [0] * (size * 4)
        base = 0
        for j in range(size):
            start = j * ratio
            stop = start + ratio
            red[base] = sum(r0[start:stop])
            red[base + 1] = sum(r1[start:stop])
            red[base + 2] = sum(r2[start:stop])
            red[base + 3] = sum(r3[start:stop])
            base += 4
        if y % ratio == 0:
            accum = red
        else:
            accum = [a + b for a, b in zip(accum, red)]
        if y % ratio == ratio - 1:
            out.append(bytes((v + half) // denom for v in accum))
    return out


def _majority_pass(pixels: list[list[tuple[int, int, int, int]]], size: int):
    """One 3x3 mode pass: a pixel is replaced only when its clamped
    neighbourhood holds a strict majority value (count >= 5 of 9) that
    differs from the pixel. At most one value can hold a strict majority,
    so the pass is deterministic."""
    out = []
    for y in range(size):
        ym = y - 1 if y > 0 else 0
        yp = y + 1 if y + 1 < size else size - 1
        line = []
        for x in range(size):
            xm = x - 1 if x > 0 else 0
            xp = x + 1 if x + 1 < size else size - 1
            original = pixels[y][x]
            counts: dict[tuple[int, int, int, int], int] = {}
            for yy in (ym, y, yp):
                row = pixels[yy]
                for xx in (xm, x, xp):
                    value = row[xx]
                    counts[value] = counts.get(value, 0) + 1
            chosen = original
            for value, count in counts.items():
                if count >= 5 and value != original:
                    chosen = value
                    break
            line.append(chosen)
        out.append(line)
    return out


def despeckle(rows: list[bytes], size: int, max_passes: int = 16) -> list[bytes]:
    """Iterate the strict-majority 3x3 mode pass to a fixed point, which makes
    the filter idempotent: re-running it on its own output is a no-op."""
    pixels = [[tuple(row[x * 4 : x * 4 + 4]) for x in range(size)] for row in rows]
    for _ in range(max_passes):
        nxt = _majority_pass(pixels, size)
        if nxt == pixels:
            break
        pixels = nxt
    return [b"".join(bytes(px) for px in line) for line in pixels]


def png_encode(rows: list[bytes], size: int) -> bytes:
    body = b"".join(b"\x00" + row for row in rows)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
        + _chunk(b"IDAT", zlib.compress(body, 9))
        + _chunk(b"IEND", b"")
    )


def ico_bytes(pngs: dict[int, bytes]) -> bytes:
    header = struct.pack("<HHH", 0, 1, len(SIZES))
    entries = b""
    offset = 6 + 16 * len(SIZES)
    for size in SIZES:
        data = pngs[size]
        edge = 0 if size >= 256 else size
        entries += struct.pack("<BBBBHHII", edge, edge, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
    return header + entries + b"".join(pngs[size] for size in SIZES)


def preview_html(pngs: dict[int, bytes]) -> str:
    cells = []
    for size in PREVIEW_SIZES:
        src = "data:image/png;base64," + base64.b64encode(pngs[size]).decode("ascii")
        cells.append(
            f"<tr><th>{size}px</th>"
            f'<td style="background:#ffffff"><img width="{min(size, 128)}" '
            f'src="{src}" alt="light {size}"></td>'
            f'<td style="background:#1f2430"><img width="{min(size, 128)}" '
            f'src="{src}" alt="dark {size}"></td></tr>'
        )
    return (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        "<title>xrayvpn icon preview</title>"
        "<style>body{font-family:monospace}table{border-collapse:collapse}"
        "td,th{padding:10px;border:1px solid #555;text-align:center}</style>"
        "</head><body><h2>xrayvpn icon — area-average from the PNG master</h2>"
        "<table><tr><th>size</th><th>light bg</th><th>dark bg</th></tr>"
        + "".join(cells)
        + "</table></body></html>"
    )


def render(master: Path = MASTER) -> dict[int, list[bytes]]:
    """Decode the master and produce RGBA row bytes for every icon size."""
    width, height, rows = png_decode(master.read_bytes())
    if width != height:
        raise ValueError(f"master must be square, got {width}x{height}")
    rendered: dict[int, list[bytes]] = {}
    for size in SIZES:
        scaled = area_average(rows, width, size)
        if size in DESPECKLE_SIZES:
            scaled = despeckle(scaled, size)
        rendered[size] = scaled
    return rendered


def render_pngs(master: Path = MASTER) -> dict[int, bytes]:
    return {size: png_encode(rows, size) for size, rows in render(master).items()}


def write_outputs(pngs: dict[int, bytes]) -> list[Path]:
    written = []
    for path, data in (
        (OUT_ICO, ico_bytes(pngs)),
        (OUT_PREVIEW_PNG, pngs[PREVIEW_PNG_SIZE]),
        (OUT_PREVIEW_HTML, preview_html(pngs).encode("utf-8")),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        written.append(path)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--master", help=f"source PNG master (default: {MASTER})")
    args = parser.parse_args(argv)
    master = Path(args.master) if args.master else MASTER
    for path in write_outputs(render_pngs(master)):
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
