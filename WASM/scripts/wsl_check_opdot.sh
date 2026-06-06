#!/usr/bin/env bash
# Analysis: is the op_dot opcode vocabulary extensible for a new native opcode?
# Checks pairwise dot-product separation (op_dot detects op P iff every distinct
# used pair has P.Q <= 32043, so the stepglu indicator is strictly 0 off-match).
set -uo pipefail
export PATH="$HOME/.local/bin:$PATH"
REPO=/mnt/c/Users/Immanuelle/Documents/Github/replicating-neural-computers-2
cd "$REPO/replication_target/transformer-vm"
uv run python - <<'PY'
from transformer_vm.wasm.interpreter import points, OPCODES, pointsR2
n = len(OPCODES)
print(f"opcodes={n}  total_points={len(points)}  spare={len(points)-n}  R2={pointsR2}")
print("all points on circle:", all(x*x+y*y==pointsR2 for x,y in points))
def maxdot(k):
    pts = points[:k]
    m = max(px*qx+py*qy for i,(px,py) in enumerate(pts) for j,(qx,qy) in enumerate(pts) if i!=j)
    return m
for k in (n, n+1, n+2, len(points)):
    m = maxdot(k)
    ok = m <= 32043
    print(f"first {k:2d} points: max pairwise dot = {m}  -> op_dot separates: {ok} (need <=32043)")
PY
