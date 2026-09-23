"""Render the README badge set into assets/badges from the release tag and channel states.

Consumed by the docs finalize wave and by channel-state changes: reads the templates
under packaging/badges and the palette from assets/color-tokens.json, then writes
self-contained SVG badges with their own background and border, readable on both
GitHub themes.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

from release_common import normalized_version
from render_channels import read_template, substitute

PAD = 8.0
RADIUS = 4
INK = "#0B1F16"
INK_NEUTRAL = "#161B22"

# Advance widths of Arial-compatible 12px text, measured in Chromium on 2026-09-26.
WIDTHS_400 = {
    "0": 6.67, "1": 6.67, "2": 6.67, "3": 6.67, "4": 6.67, "5": 6.67,
    "6": 6.67, "7": 6.67, "8": 6.67, "9": 6.67,
    "a": 6.67, "b": 6.67, "c": 6.0, "d": 6.67, "e": 6.67, "f": 3.33, "g": 6.67,
    "h": 6.67, "i": 2.67, "j": 2.67, "k": 6.0, "l": 2.67, "m": 10.0, "n": 6.67,
    "o": 6.67, "p": 6.67, "q": 6.67, "r": 4.0, "s": 6.0, "t": 3.33, "u": 6.67,
    "v": 6.0, "w": 8.67, "x": 6.0, "y": 6.0, "z": 6.0,
    "A": 8.0, "B": 8.0, "C": 8.67, "D": 8.67, "E": 8.0, "F": 7.33, "G": 9.33,
    "H": 8.67, "I": 3.33, "J": 6.0, "K": 8.0, "L": 6.67, "M": 10.0, "N": 8.67,
    "O": 9.33, "P": 8.0, "Q": 9.33, "R": 8.67, "S": 8.0, "T": 7.33, "U": 8.67,
    "V": 8.0, "W": 11.33, "X": 8.0, "Y": 8.0, "Z": 7.33,
    " ": 3.33, ".": 3.33, "-": 4.0, "+": 7.01,
    "Р": 8.0, "у": 6.0, "с": 6.0, "к": 5.25, "и": 6.7, "й": 6.7, "о": 6.67, "р": 6.67,
}
WIDTHS_700 = {
    "0": 6.67, "1": 6.67, "2": 6.67, "3": 6.67, "4": 6.67, "5": 6.67,
    "6": 6.67, "7": 6.67, "8": 6.67, "9": 6.67,
    "a": 6.67, "b": 7.33, "c": 6.67, "d": 7.33, "e": 6.67, "f": 4.0, "g": 7.33,
    "h": 7.33, "i": 3.33, "j": 3.33, "k": 6.67, "l": 3.33, "m": 10.67, "n": 7.33,
    "o": 7.33, "p": 7.33, "q": 7.33, "r": 4.67, "s": 6.67, "t": 4.0, "u": 7.33,
    "v": 6.67, "w": 9.33, "x": 6.67, "y": 6.67, "z": 6.0,
    "A": 8.67, "B": 8.67, "C": 8.67, "D": 8.67, "E": 8.0, "F": 7.33, "G": 9.33,
    "H": 8.67, "I": 3.33, "J": 6.67, "K": 8.67, "L": 7.33, "M": 10.0, "N": 8.67,
    "O": 9.33, "P": 8.0, "Q": 9.33, "R": 8.67, "S": 8.0, "T": 7.33, "U": 8.67,
    "V": 8.0, "W": 11.33, "X": 8.0, "Y": 8.0, "Z": 7.33,
    " ": 3.33, ".": 3.33, "-": 4.0, "+": 7.01,
    "Р": 8.0, "у": 6.67, "с": 6.67, "к": 6.01, "и": 7.38, "й": 7.38, "о": 7.33, "р": 7.33,
}
DEFAULTS = {400: 7.0, 700: 7.5}


def text_width(text: str, weight: int) -> float:
    table = WIDTHS_400 if weight == 400 else WIDTHS_700
    return sum(table.get(char, DEFAULTS[weight]) for char in text)


def segment_width(text: str, weight: int) -> int:
    return math.ceil(text_width(text, weight) * 1.02 + 2 * PAD)


def shade(hex_color: str, factor: float = 0.84) -> str:
    channels = (int(hex_color[index : index + 2], 16) for index in (1, 3, 5))
    return "#" + "".join(f"{round(channel * factor):02X}" for channel in channels)


def load_palette(root: Path) -> dict[str, str]:
    raw = (root / "assets" / "color-tokens.json").read_text(encoding="utf-8")
    return json.loads(raw)


def render_two_segment(
    template: str, label: str, value: str, gradient: tuple[str, str], ink: str, alt: str
) -> str:
    label_width = segment_width(label, 400)
    value_width = segment_width(value, 700)
    total = label_width + value_width
    return substitute(
        template,
        {
            "W": str(total),
            "IW": str(total - 1),
            "X2": str(label_width),
            "ARCS": str(total - 1 - RADIUS),
            "XRIGHT": str(total - 1),
            "X2T": str(label_width + int(PAD)),
            "LABEL": label,
            "VALUE": value,
            "G1": gradient[0],
            "G2": gradient[1],
            "INK": ink,
            "ALT": alt,
        },
    )


def render_single_segment(
    template: str, text: str, gradient: tuple[str, str], ink: str, alt: str
) -> str:
    total = segment_width(text, 700)
    return substitute(
        template,
        {
            "W": str(total),
            "IW": str(total - 1),
            "TEXT": text,
            "G1": gradient[0],
            "G2": gradient[1],
            "INK": ink,
            "ALT": alt,
        },
    )


def channel_badges(version: str, winget_live: bool) -> list[tuple[str, str, str, str, str]]:
    tag = f"v{version}"
    winget_value_ru = tag if winget_live else "скоро"
    winget_value_en = tag if winget_live else "soon"
    winget_tone = "accent" if winget_live else "warn"
    return [
        ("release.svg", "release", tag, "accent", f"release {tag}"),
        ("brew.svg", "brew", tag, "accent", f"brew {tag}"),
        ("winget-ru.svg", "winget", winget_value_ru, winget_tone, f"winget {winget_value_ru}"),
        ("winget-en.svg", "winget", winget_value_en, winget_tone, f"winget {winget_value_en}"),
        ("apt.svg", "apt", tag, "accent", f"apt {tag}"),
        ("pip.svg", "pip", tag, "accent", f"pip {tag}"),
        ("uv.svg", "uv tool", tag, "accent", f"uv tool {tag}"),
        ("python.svg", "python", "3.12+", "muted", "python 3.12+"),
        ("license.svg", "license", "AGPL-3.0", "muted", "license AGPL-3.0"),
    ]


def language_badges() -> list[tuple[str, str, str]]:
    return [
        ("lang-ru.svg", "Русский", "accent"),
        ("lang-ru-muted.svg", "Русский", "muted"),
        ("lang-en.svg", "English", "accent"),
        ("lang-en-muted.svg", "English", "muted"),
    ]


def badge_files(root: Path, version: str, winget_live: bool) -> dict[Path, bytes]:
    templates = root / "packaging" / "badges"
    palette = load_palette(root)
    gradients = {
        tone: (palette[tone], shade(palette[tone])) for tone in ("accent", "warn", "muted")
    }
    inks = {"accent": INK, "warn": INK, "muted": INK_NEUTRAL}
    two_segment = read_template(templates / "badge.svg")
    single_segment = read_template(templates / "badge-lang.svg")
    files: dict[Path, bytes] = {}
    for name, label, value, tone, alt in channel_badges(version, winget_live):
        rendered = render_two_segment(
            two_segment, label, value, gradients[tone], inks[tone], alt
        )
        files[Path(name)] = rendered.encode("utf-8")
    for name, text, tone in language_badges():
        rendered = render_single_segment(
            single_segment, text, gradients[tone], inks[tone], text
        )
        files[Path(name)] = rendered.encode("utf-8")
    return files


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", required=True, help="released tag, e.g. v0.4.1")
    parser.add_argument(
        "--winget-live",
        action="store_true",
        help="render the winget version instead of the placeholder",
    )
    parser.add_argument("--out", type=Path, help="output directory (default assets/badges)")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args(argv)
    version = normalized_version(args.tag)
    out = args.out or args.root / "assets" / "badges"
    files = badge_files(args.root, version, args.winget_live)
    for relative, data in sorted(files.items()):
        target = out / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        print(f"wrote {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())