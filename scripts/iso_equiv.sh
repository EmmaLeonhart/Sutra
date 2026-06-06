#!/usr/bin/env bash
# Behavioural-equivalence harness: for every example program, run BOTH the Python
# reference (transformer-vm/wasm/reference.py) and the Rust isomorph, and diff their
# outputs. This is the isomorphism check (equivalence by testing, not proof).
set -uo pipefail
export PATH="$HOME/.cargo/bin:$HOME/.local/bin:$PATH"
REPO=/mnt/c/Users/Immanuelle/Documents/Github/replicating-neural-computers-2
VM="$REPO/replication_target/transformer-vm"
DATA="$VM/transformer_vm/data"
ISO="$REPO/iso/rust"

echo "== building Rust isomorph =="
( cd "$ISO" && cargo build --release -q ) || { echo "BUILD FAILED"; exit 1; }
BIN="$ISO/target/release/wasm-ref"

fail=0
total=0
for prog in hello addition fibonacci collatz min_cost_matching sudoku; do
  txt="$DATA/$prog.txt"
  [ -f "$txt" ] || { echo "SKIP $prog (no $txt — run 'uv run wasm-compile --all')"; continue; }
  total=$((total+1))
  # Python reference output
  py=$(cd "$VM" && uv run python -c "
import sys
from transformer_vm.wasm.reference import load_program, run
prog,inp = load_program('$txt')
_,_,out = run(prog, inp, max_tokens=200_000_000)
sys.stdout.write(out)
")
  # Rust isomorph output
  rs=$("$BIN" "$txt" 200000000 2>/dev/null)
  if [ "$py" == "$rs" ]; then
    echo "PASS  $prog  (${#py} bytes)"
  else
    echo "FAIL  $prog  (py=${#py} bytes, rs=${#rs} bytes)"
    fail=$((fail+1))
  fi
done

echo "== $((total-fail))/$total programs match =="
[ "$fail" -eq 0 ] && echo "ISO_EQUIV_OK" || { echo "ISO_EQUIV_FAIL"; exit 1; }
