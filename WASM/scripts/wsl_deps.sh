#!/usr/bin/env bash
# Unprivileged dependency install (no sudo): uv + uv sync. Safe to run before the
# apt toolchain step; clang/g++ are only needed later at compile/run time.
set -euo pipefail
export PATH="$HOME/.local/bin:$PATH"
if ! command -v uv >/dev/null 2>&1; then
  echo "== installing uv =="
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi
export PATH="$HOME/.local/bin:$PATH"
uv --version
cd /mnt/c/Users/Immanuelle/Documents/Github/replicating-neural-computers-2/replication_target/transformer-vm
echo "== uv sync --extra dev =="
uv sync --extra dev
echo UV_SYNC_DONE
