#!/usr/bin/env bash
# Install the Rust toolchain (rustup) in WSL — unprivileged, into ~/.cargo / ~/.rustup.
set -uo pipefail
if command -v cargo >/dev/null 2>&1; then echo "cargo already present: $(cargo --version)"; exit 0; fi
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal
export PATH="$HOME/.cargo/bin:$PATH"
cargo --version
echo RUST_INSTALL_DONE
