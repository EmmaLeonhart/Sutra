#!/usr/bin/env bash
# Run scripts/run.py (the CI entry point) under WSL: re-runs the recipe using the
# already-built model.bin + C++ engine (fast inference only) and writes
# results/metrics.json.
set -uo pipefail
export PATH="$HOME/.local/bin:$PATH"
REPO=/mnt/c/Users/Immanuelle/Documents/Github/replicating-neural-computers-2
cd "$REPO"
python3 scripts/run.py "$@"
echo "RUN_PY_EXIT=$?"
