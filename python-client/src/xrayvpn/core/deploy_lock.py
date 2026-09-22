"""Per-machine deploy mutex; the kernel releases it on crash, Ctrl+C or reboot.

No pidfiles and no TTL holders by design: a stuck lock must be impossible.
Windows uses a named mutex (kernel object), POSIX an flock on a temp file —
both are dropped by the kernel the moment the holding process dies.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager

MUTEX_NAME = "Global\\xrayvpn-deploy"
_ERROR_ALREADY_EXISTS = 183


class DeployBusy(RuntimeError):
    """Another xrayvpn deploy holds the machine-wide lock."""


@contextmanager
def deploy_lock() -> Iterator[None]:
    if os.name == "nt":
        handle = _win_acquire()
        try:
            yield
        finally:
            _win_release(handle)
    else:
        fd = _posix_acquire()
        try:
            yield
        finally:
            _posix_release(fd)


def _win_acquire() -> int:
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    kernel32.CreateMutexW.argtypes = (wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR)
    handle = kernel32.CreateMutexW(None, False, MUTEX_NAME)
    if not handle:
        raise OSError(ctypes.WinError(ctypes.get_last_error()))
    if ctypes.get_last_error() == _ERROR_ALREADY_EXISTS:
        kernel32.CloseHandle(handle)
        raise DeployBusy(MUTEX_NAME)
    return int(handle)


def _win_release(handle: int) -> None:
    import ctypes

    kernel32 = ctypes.windll.kernel32
    kernel32.ReleaseMutex(handle)
    kernel32.CloseHandle(handle)


def _posix_acquire() -> int:
    import fcntl

    path = os.path.join(tempfile.gettempdir(), "xrayvpn-deploy.lock")
    fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        os.close(fd)
        raise DeployBusy(path) from None
    return fd


def _posix_release(fd: int) -> None:
    import fcntl

    fcntl.flock(fd, fcntl.LOCK_UN)
    os.close(fd)
