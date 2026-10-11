"""xrayvpn — Python client for provisioning Xray VLESS + REALITY VPN servers."""

__version__ = "0.4.2"
__release_date__ = "2026-10-11"


def display_version(version: str = __version__) -> str:
    """User-facing version: the number plus the release date."""
    return f"{version} ({__release_date__})"