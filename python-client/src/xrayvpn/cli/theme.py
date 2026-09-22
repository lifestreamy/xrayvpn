"""Semantic color tokens and OSC-8 hyperlinks for CLI output.

Truecolor is emitted when the host signals it (COLORTERM=truecolor|24bit,
Windows Terminal, VS Code) or on a Windows console with VT processing active
(enabled by this module when the host left it off, truecolor since build
15063 — the same capability rich probes, so help panels and banners never
disagree); otherwise a 16-color SGR fallback map keeps output visible. A
Windows console where VT cannot be turned on gets plain output: uninterpreted
ANSI is worse than no ANSI. NO_COLOR or a non-tty stream make all helpers
plain at the source. XRAYVPN_FORCE_COLOR=1 forces truecolor for diagnostics;
XRAYVPN_THEME_DEBUG=1 prints the gate decision (see debug_line()).
Hyperlinks: link() emits OSC-8 only on terminals that render it (Windows
Terminal / VS Code) or when XRAYVPN_HYPERLINK=1 forces it; the fallback
appends the bare URL. The design-time mirror of this palette lives in
assets/color-tokens.json.
"""

from __future__ import annotations

import os
import re
import sys

TOKENS: dict[str, str] = {
    "ok": "#1DB954",
    "error": "#F85149",
    "warn": "#D29922",
    "muted": "#C4CDD8",
    "accent": "#00D587",
}

ANSI16: dict[str, str] = {
    "ok": "32",
    "error": "31",
    "warn": "33",
    "muted": "90",
    "accent": "92",
}

_FORCE_COLOR_ENV = "XRAYVPN_FORCE_COLOR"
_HYPERLINK_ENV = "XRAYVPN_HYPERLINK"
_DEBUG_ENV = "XRAYVPN_THEME_DEBUG"

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
_OSC8_RE = re.compile(r"\x1b\]8;[^\x07\x1b]*(?:\x07|\x1b\\)")


def plain(text: str) -> str:
    return _ANSI_RE.sub("", _OSC8_RE.sub("", text))


def visible_len(text: str) -> int:
    return len(plain(text))


def _is_tty() -> bool:
    stream = getattr(sys, "stdout", None)
    try:
        return bool(stream is not None and stream.isatty())
    except Exception:  # noqa: BLE001
        return False


_VT_PROBE_CACHE: bool | None = None


def _probe_console_vt() -> bool:
    if sys.platform != "win32":
        return False
    try:
        import ctypes

        handle = ctypes.windll.kernel32.GetStdHandle(-11)
        mode = ctypes.c_uint32()
        if not ctypes.windll.kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        return bool(mode.value & 0x0004)
    except Exception:  # noqa: BLE001
        return False


def _console_vt_enabled() -> bool:
    global _VT_PROBE_CACHE
    if _VT_PROBE_CACHE is None:
        _VT_PROBE_CACHE = _probe_console_vt()
    return _VT_PROBE_CACHE


def _enable_console_vt() -> bool:
    if sys.platform != "win32":
        return False
    try:
        import ctypes

        k32 = ctypes.windll.kernel32
        handle = k32.GetStdHandle(-11)
        mode = ctypes.c_uint32()
        if not k32.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        if not k32.SetConsoleMode(handle, mode.value | 0x0004):
            return False
        after = ctypes.c_uint32()
        return bool(k32.GetConsoleMode(handle, ctypes.byref(after)) and after.value & 0x0004)
    except Exception:  # noqa: BLE001
        return False


_VT_READY_CACHE: bool | None = None


def _console_vt_ready() -> bool:
    global _VT_READY_CACHE
    if _VT_READY_CACHE is None:
        _VT_READY_CACHE = _console_vt_enabled() or _enable_console_vt()
    return _VT_READY_CACHE


def _windows_truecolor_capable() -> bool:
    version = sys.getwindowsversion()
    return version.major > 10 or (version.major == 10 and version.build >= 15063)


def _supports_truecolor() -> bool:
    if os.environ.get("COLORTERM", "").lower() in ("truecolor", "24bit"):
        return True
    if os.environ.get("WT_SESSION") or os.environ.get("TERM_PROGRAM") == "vscode":
        return True
    if sys.platform == "win32":
        return _console_vt_ready() and _windows_truecolor_capable()
    return _console_vt_enabled()


def color_mode() -> str:
    if os.environ.get("NO_COLOR") or not _is_tty():
        return "plain"
    if os.environ.get(_FORCE_COLOR_ENV) == "1" or _supports_truecolor():
        return "truecolor"
    if sys.platform == "win32" and not _console_vt_ready():
        return "plain"
    return "16"


def debug_line() -> str:
    env = os.environ
    if sys.platform == "win32":
        version = sys.getwindowsversion()
        win = f"{version.major}.{version.build}"
    else:
        win = "-"
    return (
        f"theme: mode={color_mode()} tty={_is_tty()} vt={_console_vt_ready()} win={win} "
        f"NO_COLOR={env.get('NO_COLOR')!r} "
        f"COLORTERM={env.get('COLORTERM')!r} WT_SESSION={env.get('WT_SESSION')!r} "
        f"TERM_PROGRAM={env.get('TERM_PROGRAM')!r}"
    )


def _rgb(token: str) -> tuple[int, int, int]:
    value = TOKENS[token].lstrip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def _styled(text: str, token: str, *, bold: bool = False) -> str:
    mode = color_mode()
    if mode == "plain":
        return text
    code = "38;2;{};{};{}".format(*_rgb(token)) if mode == "truecolor" else ANSI16[token]
    return f"\x1b[{'1;' if bold else ''}{code}m{text}\x1b[0m"


def ok(text: str) -> str:
    return _styled(text, "ok")


def ok_bold(text: str) -> str:
    return _styled(text, "ok", bold=True)


def err(text: str) -> str:
    return _styled(text, "error")


def warn(text: str) -> str:
    return _styled(text, "warn")


def muted(text: str) -> str:
    return _styled(text, "muted")


def accent(text: str) -> str:
    return _styled(text, "accent")


def _hyperlink_enabled() -> bool:
    override = os.environ.get(_HYPERLINK_ENV)
    if override is not None:
        return override == "1"
    return _is_tty() and bool(
        os.environ.get("WT_SESSION") or os.environ.get("TERM_PROGRAM") == "vscode"
    )


def link(text: str, url: str) -> str:
    if not _hyperlink_enabled():
        return f"{text} ({url})"
    return f"\x1b]8;;{url}\x1b\\{text}\x1b]8;;\x1b\\"
