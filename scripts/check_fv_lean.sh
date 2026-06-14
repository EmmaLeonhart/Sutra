#!/usr/bin/env bash
# Check every Lean proof under fv-lean/. Requires lean4 (elan). No mathlib.
set -euo pipefail
export PATH="$HOME/.elan/bin:$PATH"
command -v lean >/dev/null || { echo "lean not found (install via elan)"; exit 127; }
fail=0
for f in fv-lean/*.lean; do
  echo "== $f =="
  if lean "$f" 2>&1 | grep -qiE "error|sorryAx"; then echo "FAIL: $f"; fail=1; fi
done
[ "$fail" = 0 ] && echo "fv-lean: all proofs check (no error / no sorry)"
exit $fail
