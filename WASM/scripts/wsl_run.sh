#!/usr/bin/env bash
# Headline path: build analytic transformer weights (MILP schedule + torch) and
# the C++ inference engine, then run all example programs through the transformer.
# This is the ~30K tok/s claim. The C++ engine uses a header-only hull cache, so
# it does NOT need Python.h / python3-dev.
set -uo pipefail
export PATH="$HOME/.local/bin:$PATH"
REPO=/mnt/c/Users/Immanuelle/Documents/Github/replicating-neural-computers-2
VM="$REPO/replication_target/transformer-vm"
mkdir -p "$REPO/results"
cd "$VM"

echo "######## uv run wasm-run (build weights + C++ engine, run all) ########"
/usr/bin/time -v uv run wasm-run 2>&1 | tee "$REPO/results/wasm_run.log"
echo "WASM_RUN_EXIT=${PIPESTATUS[0]}" | tee -a "$REPO/results/wasm_run.log"
echo WASM_RUN_DONE
