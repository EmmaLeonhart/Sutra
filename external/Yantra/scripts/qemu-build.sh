#!/usr/bin/env bash
# Build the Yantra multiboot1 kernel (a bare-metal ELF binary
# QEMU's `-kernel` flag boots directly).
#
# Output: bootloader/target/i686-yantra/release/yantra-bootloader
#
# Prerequisites (one-time):
#   - Rust nightly (`rust-toolchain.toml` pins it; rustup auto-installs)
#   - llvm-tools-preview: `rustup component add llvm-tools-preview`
#
# No bootimage tool needed — multiboot1 ELF binaries don't need
# disk-image assembly.
#
# Usage:
#   ./scripts/qemu-build.sh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT/bootloader"

if ! command -v cargo >/dev/null 2>&1; then
  echo "ERROR: cargo not found. Install Rust from https://rustup.rs/" >&2
  exit 1
fi

# -Zjson-target-spec is required because we use a custom JSON
# target spec (no built-in i686-unknown-none target exists).
echo ">>> cargo -Zjson-target-spec build --release..."
cargo -Zjson-target-spec build --release

OUT="target/i686-yantra/release/yantra-bootloader"
if [ -f "$OUT" ]; then
  echo ">>> Built: $OUT ($(stat -c %s "$OUT" 2>/dev/null || stat -f %z "$OUT") bytes)"
  echo ">>> Run with: ./scripts/qemu-run.sh"
else
  echo "ERROR: expected output $OUT not found" >&2
  exit 1
fi
