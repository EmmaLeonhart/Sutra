#!/usr/bin/env bash
set -uo pipefail
REPO=/mnt/c/Users/Immanuelle/Documents/Github/replicating-neural-computers-2
T="$REPO/replication_target/transformer-vm/transformer_vm/data/${1:-hello}.txt"
echo "=== RUST ==="
"$REPO/iso/rust/target/release/wasm-ref" "$T" >/tmp/rs.out 2>/tmp/rs.err
cat /tmp/rs.err; echo "output:"; head -c 200 /tmp/rs.out; echo
echo "=== OCAML ==="
"$REPO/iso/ocaml/_build/default/bin/main.exe" "$T" >/tmp/ml.out 2>/tmp/ml.err
cat /tmp/ml.err; echo "output:"; head -c 200 /tmp/ml.out; echo
