#!/usr/bin/env bash
set -uo pipefail
export PATH="$HOME/.cargo/bin:$PATH"
REPO=/mnt/c/Users/Immanuelle/Documents/Github/replicating-neural-computers-2
T="$REPO/replication_target/transformer-vm/transformer_vm/data/${1:-hello}.txt"
( cd "$REPO/iso/rust" && cargo build --release -q )
( cd "$REPO/iso/ocaml" && dune build )
ISO_TRACE=1 "$REPO/iso/rust/target/release/wasm-ref" "$T" >/dev/null 2>/tmp/rs.trace
ISO_TRACE=1 "$REPO/iso/ocaml/_build/default/bin/main.exe" "$T" >/dev/null 2>/tmp/ml.trace
echo "=== first divergence (rust | ocaml) ==="
diff /tmp/rs.trace /tmp/ml.trace | head -20
echo "=== context: rust lines around divergence ==="
n=$(diff <(cat /tmp/rs.trace) <(cat /tmp/ml.trace) | grep -m1 '^[0-9]' | grep -oE '^[0-9]+' | head -1)
[ -n "${n:-}" ] && sed -n "$((n>3?n-3:1)),$((n+3))p" /tmp/rs.trace
