#!/usr/bin/env bash
# Build + test the Rust isomorph, then run the Python-vs-Rust equivalence harness.
set -uo pipefail
export PATH="$HOME/.cargo/bin:$HOME/.local/bin:$PATH"
REPO=/mnt/c/Users/Immanuelle/Documents/Github/replicating-neural-computers-2
cd "$REPO/iso/rust"
echo "######## cargo test --release ########"
cargo test --release 2>&1 | tail -40
echo "CARGO_TEST_EXIT=${PIPESTATUS[0]}"
echo "######## equivalence harness ########"
bash "$REPO/scripts/iso_equiv.sh"
