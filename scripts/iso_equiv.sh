#!/usr/bin/env bash
# Behavioural-equivalence harness for the isomorphism program: for every example
# program, run the Python reference AND every language isomorph (Rust, OCaml) and
# diff their outputs. Equivalence by testing (not formal proof).
set -uo pipefail
export PATH="$HOME/.cargo/bin:$HOME/.local/bin:$PATH"
REPO=/mnt/c/Users/Immanuelle/Documents/Github/replicating-neural-computers-2
VM="$REPO/replication_target/transformer-vm"
DATA="$VM/transformer_vm/data"

echo "== building Rust isomorph =="
( cd "$REPO/iso/rust" && cargo build --release -q ) || { echo "RUST BUILD FAILED"; exit 1; }
RS_BIN="$REPO/iso/rust/target/release/wasm-ref"

HAVE_OCAML=0
if command -v dune >/dev/null 2>&1; then
  echo "== building OCaml isomorph =="
  if ( cd "$REPO/iso/ocaml" && dune build 2>&1 ); then
    ML_BIN="$REPO/iso/ocaml/_build/default/bin/main.exe"
    HAVE_OCAML=1
  else
    echo "OCAML BUILD FAILED"; exit 1
  fi
else
  echo "== OCaml/dune not installed; skipping OCaml =="
fi

fail=0; total=0
for prog in hello addition fibonacci collatz min_cost_matching sudoku; do
  txt="$DATA/$prog.txt"
  [ -f "$txt" ] || { echo "SKIP $prog (no $txt)"; continue; }
  total=$((total+1))
  py=$(cd "$VM" && uv run python -c "
import sys
from transformer_vm.wasm.reference import load_program, run
prog,inp = load_program('$txt')
_,_,out = run(prog, inp, max_tokens=200_000_000)
sys.stdout.write(out)
")
  rs=$("$RS_BIN" "$txt" 200000000 2>/dev/null)
  ok=1; detail="py=${#py}"
  [ "$py" == "$rs" ] && detail="$detail rs=ok" || { detail="$detail rs=DIFF(${#rs})"; ok=0; }
  if [ "$HAVE_OCAML" -eq 1 ]; then
    ml=$("$ML_BIN" "$txt" 200000000 2>/dev/null)
    [ "$py" == "$ml" ] && detail="$detail ml=ok" || { detail="$detail ml=DIFF(${#ml})"; ok=0; }
  fi
  if [ "$ok" -eq 1 ]; then echo "PASS  $prog  ($detail)"; else echo "FAIL  $prog  ($detail)"; fail=$((fail+1)); fi
done

echo "== $((total-fail))/$total programs match across all isomorphs =="
[ "$fail" -eq 0 ] && echo "ISO_EQUIV_OK" || { echo "ISO_EQUIV_FAIL"; exit 1; }
