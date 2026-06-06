#!/usr/bin/env bash
# Train a set of value-output arithmetic ops to 100% exact (E4).
set -uo pipefail
export PATH="$HOME/.local/bin:$PATH"
REPO=/mnt/c/Users/Immanuelle/Documents/Github/replicating-neural-computers-2
VM="$REPO/replication_target/transformer-vm"
export PYTHONPATH="$REPO/src:${PYTHONPATH:-}"
cd "$VM"
for op in "$@"; do
  echo "######## training $op ########"
  uv run python "$REPO/src/learned_ops/train_and.py" --op "$op" --width 256 --epochs 1500
done
echo ALL_OPS_DONE
