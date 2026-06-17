#!/usr/bin/env bash
# Boot the bare-metal Linux 0.00 replica in QEMU.
#
# Expects bootloader/target/i686-yantra/release/linux000 (run
# scripts/linux000-build.sh first).
#
# Faithful Linux 0.00: two hardcoded tasks (A writes 'A', B writes
# 'B') alternated by the real 8253 PIT -> 8259 PIC -> timer ISR,
# output to the VGA text buffer (0xB8000) AND COM1 serial. Each
# task does one char then `hlt`, so the timer tick drives the
# switch: the serial stream is a clean kernel-mediated A/B
# alternation, then `[linux000 DONE]` at LIMIT, then halt.
#
# This run is interactive (-serial stdio). It halts after LIMIT
# chars but QEMU stays open — exit with Ctrl+A then X. For an
# automated/headless capture instead:
#
#   timeout 8 "<qemu>" -kernel <bin> -serial file:out.txt \
#       -display none -no-reboot -no-shutdown ; cat out.txt
#
# Prerequisite: QEMU (see bootloader/README.md).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

KERNEL="$REPO_ROOT/bootloader/target/i686-yantra/release/linux000"
if [ ! -f "$KERNEL" ]; then
  echo "ERROR: kernel not found at $KERNEL" >&2
  echo "Run scripts/linux000-build.sh first." >&2
  exit 1
fi

if command -v qemu-system-x86_64 >/dev/null 2>&1; then
  QEMU="qemu-system-x86_64"
elif [ -f "/c/Program Files/qemu/qemu-system-x86_64.exe" ]; then
  QEMU="/c/Program Files/qemu/qemu-system-x86_64.exe"
else
  echo "ERROR: qemu-system-x86_64 not found." >&2
  echo "Install QEMU: see bootloader/README.md for platform instructions." >&2
  exit 1
fi

echo ">>> Booting bare-metal Linux 0.00 in QEMU. Ctrl+A then X to exit."
exec "$QEMU" \
  -kernel "$KERNEL" \
  -serial stdio \
  -display none \
  -no-reboot
