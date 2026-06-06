#!/usr/bin/env bash
set +e
echo "=== uname ==="; uname -a
echo "=== distro ==="; lsb_release -d 2>/dev/null
echo "=== tools ==="
for t in clang clang++ g++ gcc uv python3 cmake ninja curl make; do
  printf '%-9s ' "$t"; command -v "$t" || echo MISSING
done
echo "=== clang wasm32 ==="
clang --print-targets 2>/dev/null | grep -i wasm32 || echo "clang-missing-or-no-wasm32"
echo "=== python version ==="; python3 --version 2>/dev/null
echo "=== internet ==="
curl -sI https://astral.sh 2>/dev/null | head -1 || echo no-net
echo "=== free mem / cpus ==="
nproc; free -h 2>/dev/null | head -2
