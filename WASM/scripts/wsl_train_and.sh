#!/usr/bin/env bash
# Train the i32.and op-local block (E1) inside the transformer-vm uv venv.
set -uo pipefail
export PATH="$HOME/.local/bin:$PATH"
REPO=/mnt/c/Users/Immanuelle/Documents/Github/replicating-neural-computers-2
VM="$REPO/replication_target/transformer-vm"
export PYTHONPATH="$REPO/src:${PYTHONPATH:-}"
cd "$VM"
uv run python "$REPO/src/learned_ops/train_and.py" "$@"
echo "TRAIN_AND_EXIT=$?"
