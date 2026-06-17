#!/usr/bin/env bash
# Build the bare-metal Linux 0.00 replica (32-bit multiboot1 ELF,
# the 2nd binary in the bootloader crate).
#
# Output: bootloader/target/i686-yantra/release/linux000
#
# Reuses the bootloader crate's i686-yantra.json target spec,
# linker.ld, and pinned nightly. `[unstable] json-target-spec` is
# set in bootloader/.cargo/config.toml so a bare `cargo build`
# works; we still pass -Zjson-target-spec for parity with
# qemu-build.sh and older configs.
#
# Usage:
#   ./scripts/linux000-build.sh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT/bootloader"

if ! command -v cargo >/dev/null 2>&1; then
  echo "ERROR: cargo not found. Install Rust from https://rustup.rs/" >&2
  exit 1
fi

echo ">>> cargo -Zjson-target-spec build --release --bin linux000..."
cargo -Zjson-target-spec build --release --bin linux000

OUT="target/i686-yantra/release/linux000"
if [ -f "$OUT" ]; then
  echo ">>> Built: $OUT ($(stat -c %s "$OUT" 2>/dev/null || stat -f %z "$OUT") bytes)"
  echo ">>> Run with: ./scripts/linux000-run.sh"
else
  echo "ERROR: expected output $OUT not found" >&2
  exit 1
fi
