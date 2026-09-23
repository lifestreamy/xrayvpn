#!/usr/bin/env bash
set -euo pipefail

mode="${1:?usage: arch_container.sh <srcinfo|build|install> <source-dir>}"
src="${2:?usage: arch_container.sh <srcinfo|build|install> <source-dir>}"

useradd -m builder
cp -a "$src" /pkg
chown -R builder /pkg
su builder -c "cd /pkg && makepkg --printsrcinfo > .SRCINFO"
test -s /pkg/.SRCINFO

if [ "$mode" = "srcinfo" ]; then
  cp /pkg/.SRCINFO "$src/.SRCINFO"
  exit 0
fi

pacman -Sy --noconfirm --needed base-devel namcap hicolor-icon-theme >/dev/null
su builder -c "cd /pkg && makepkg -f --noconfirm"
namcap /pkg/PKGBUILD
namcap /pkg/*.pkg.tar.zst

if [ "$mode" = "install" ]; then
  pacman -U --noconfirm /pkg/*.pkg.tar.zst
  out="$(XRAYVPN_UPDATE_CHECK=0 xrayvpn --version)"
  printf '%s\n' "$out"
  if [ -n "${EXPECTED_VERSION:-}" ]; then
    printf '%s\n' "$out" | grep -qx "xrayvpn $EXPECTED_VERSION"
  fi
fi
