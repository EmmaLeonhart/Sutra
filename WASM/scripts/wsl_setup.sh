#!/usr/bin/env bash
# Toolchain setup for replicating Percepta transformer-vm, run inside WSL Ubuntu.
#
# Usage (from the repo root, in WSL):
#   bash scripts/wsl_setup.sh            # full setup (will sudo apt install)
#   bash scripts/wsl_setup.sh --no-apt   # skip the privileged apt step
#
# The apt step needs sudo. Everything else is unprivileged.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VM_DIR="$REPO_ROOT/replication_target/transformer-vm"

if [[ "${1:-}" != "--no-apt" ]]; then
  echo "== apt: build-essential clang lld cmake (needs sudo) =="
  sudo apt-get update
  # clang + lld provide the wasm32 target; build-essential gives g++/make for the
  # C++17 inference engine (transformer.cpp). No BLAS: the cblas path is Apple-only.
  sudo apt-get install -y build-essential clang lld cmake
fi

echo "== verify clang wasm32 target =="
clang --print-targets | grep -i wasm32 || { echo "ERROR: clang lacks wasm32"; exit 1; }

echo "== install uv (unprivileged, ~/.local/bin) =="
if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi
export PATH="$HOME/.local/bin:$PATH"
uv --version

echo "== uv sync (deps incl. torch, highspy, ninja) =="
cd "$VM_DIR"
uv sync --extra dev

echo "== DONE: toolchain ready in $VM_DIR =="
