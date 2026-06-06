#!/usr/bin/env bash
# Optional claim C6: First Futamura projection — bake a single program (collatz)
# into the transformer weights, then run the specialized model (no program prefix
# in the input).
set -uo pipefail
export PATH="$HOME/.local/bin:$PATH"
REPO=/mnt/c/Users/Immanuelle/Documents/Github/replicating-neural-computers-2
VM="$REPO/replication_target/transformer-vm"
mkdir -p "$REPO/results"
cd "$VM"

echo "######## wasm-specialize collatz ########"
uv run wasm-specialize transformer_vm/data/collatz.txt --save-weights=collatz.bin 2>&1 \
  | tee "$REPO/results/futamura.log"
echo "SPECIALIZE_EXIT=${PIPESTATUS[0]}" | tee -a "$REPO/results/futamura.log"

echo "######## run specialized model ########"
uv run wasm-run --model collatz.bin transformer_vm/data/collatz_spec.txt 2>&1 \
  | tee -a "$REPO/results/futamura.log"
echo "RUN_SPEC_EXIT=${PIPESTATUS[0]}" | tee -a "$REPO/results/futamura.log"
echo FUTAMURA_DONE
