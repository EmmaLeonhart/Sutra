#!/usr/bin/env bash
# Drop into the Yantra dev container with the repo bind-mounted.
#
# First run builds the image (~5-10 min, dominated by torch CPU wheel
# download); subsequent runs reuse the layers.
#
# Usage:
#   ./scripts/dev-shell.sh                # interactive bash
#   ./scripts/dev-shell.sh pytest         # one-shot test run
#   ./scripts/dev-shell.sh pytest -v -k kernel
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
IMAGE_TAG="yantra-dev"

# Build only if image is missing. Force a rebuild by deleting the
# image first: `docker rmi yantra-dev`.
if ! docker image inspect "$IMAGE_TAG" >/dev/null 2>&1; then
  echo ">>> Building $IMAGE_TAG (first run takes ~5-10 minutes)..."
  docker build -t "$IMAGE_TAG" "$REPO_ROOT"
fi

# `-it` only when stdin is a TTY (so `./dev-shell.sh pytest | tee log`
# from a script still works).
if [ -t 0 ] && [ -t 1 ]; then
  TTY_FLAGS="-it"
else
  TTY_FLAGS=""
fi

exec docker run --rm $TTY_FLAGS \
  -v "$REPO_ROOT:/workspace" \
  -w /workspace \
  "$IMAGE_TAG" \
  "$@"
