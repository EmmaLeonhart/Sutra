#!/usr/bin/env bash
# Boot the Yantra multiboot1 kernel in QEMU.
#
# Expects bootloader/target/i686-yantra/release/yantra-bootloader
# to exist. Run scripts/qemu-build.sh first if not.
#
# QEMU args:
#   -kernel ...                     load multiboot1 ELF directly
#   -serial stdio                   forward COM1 to host stdout
#   -display none                   no graphical window — pure terminal
#   -no-reboot                      don't restart after halt; just exit
#
# Output: the kernel prints "Yantra bootloader v0.0 - hello from
# bare metal" to stdout. Then halts. Exit QEMU with Ctrl+A then X.
#
# Prerequisite: QEMU installed. On Windows: `winget install
# SoftwareFreedomConservancy.QEMU`. On Linux: distro package
# (`apt install qemu-system-x86`, `pacman -S qemu`). On macOS:
# `brew install qemu`.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

KERNEL="$REPO_ROOT/bootloader/target/i686-yantra/release/yantra-bootloader"
if [ ! -f "$KERNEL" ]; then
  echo "ERROR: kernel not found at $KERNEL" >&2
  echo "Run scripts/qemu-build.sh first." >&2
  exit 1
fi

# Find QEMU. Prefer PATH; fall back to the standard Windows install
# location which winget uses.
if command -v qemu-system-x86_64 >/dev/null 2>&1; then
  QEMU="qemu-system-x86_64"
elif [ -f "/c/Program Files/qemu/qemu-system-x86_64.exe" ]; then
  QEMU="/c/Program Files/qemu/qemu-system-x86_64.exe"
else
  echo "ERROR: qemu-system-x86_64 not found." >&2
  echo "Install QEMU: see bootloader/README.md for platform instructions." >&2
  exit 1
fi

echo ">>> Booting Yantra kernel in QEMU. Ctrl+A then X to exit."
exec "$QEMU" \
  -kernel "$KERNEL" \
  -serial stdio \
  -display none \
  -no-reboot
