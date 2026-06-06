#!/usr/bin/env bash
# Light path: graph evaluator (exact arithmetic, no transformer weights) + fast
# tests. Neither needs clang/g++. Captures output into results/.
set -uo pipefail
export PATH="$HOME/.local/bin:$PATH"
REPO=/mnt/c/Users/Immanuelle/Documents/Github/replicating-neural-computers-2
VM="$REPO/replication_target/transformer-vm"
mkdir -p "$REPO/results"
cd "$VM"

echo "######## uv run wasm-eval ########"
uv run wasm-eval 2>&1 | tee "$REPO/results/wasm_eval.log"
echo "WASM_EVAL_EXIT=${PIPESTATUS[0]}" | tee -a "$REPO/results/wasm_eval.log"

echo "######## uv run pytest -m 'not slow' ########"
uv run pytest -m "not slow" 2>&1 | tee "$REPO/results/pytest_fast.log"
echo "PYTEST_EXIT=${PIPESTATUS[0]}" | tee -a "$REPO/results/pytest_fast.log"

echo LIGHTPATH_DONE
