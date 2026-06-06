#!/usr/bin/env bash
# Run the learned-ops experiment tests inside the transformer-vm uv venv.
set -uo pipefail
export PATH="$HOME/.local/bin:$PATH"
REPO=/mnt/c/Users/Immanuelle/Documents/Github/replicating-neural-computers-2
VM="$REPO/replication_target/transformer-vm"
cd "$VM"
# Run pytest from the venv; conftest puts $REPO/src on sys.path.
uv run python -m pytest "$REPO/src/learned_ops/tests" -p no:cacheprovider -q "$@"
echo "PYTEST_EXIT=$?"
