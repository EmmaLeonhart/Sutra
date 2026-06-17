# Yantra dev container — first of the three "VM tiers" planned for Yantra.
#
# This is tier 1 (Docker dev container): a reproducible Python 3.13 +
# CPU torch + Sutra-deps environment that runs the kernel test suite
# (44 tests including 6 real-Sutra integration tests) without the
# user having to manually install anything beyond Docker itself.
#
# Tier 2 (cloud GPU VM, e.g. RunPod) waits on upstream Sutra GPU work
# being something to test. Tier 3 (QEMU full-system emulator) waits on
# a Rust kernel image to boot. See planning/18-kernel-browser-readiness.md
# for the milestone framing.
#
# Source is NOT baked into the image — bind-mount the repo at /workspace
# at runtime so edits flow back to the host. Cuts the rebuild loop to
# zero for normal dev work; only the Dockerfile or pre-installed deps
# changing should trigger a rebuild.
#
# Build:
#   docker build -t yantra-dev .
#
# Use (Linux/macOS):
#   docker run --rm -it -v "$PWD:/workspace" yantra-dev          # interactive shell
#   docker run --rm    -v "$PWD:/workspace" yantra-dev pytest    # one-shot tests
#
# Use (Windows PowerShell):
#   docker run --rm -it -v "${PWD}:/workspace" yantra-dev
#
# Or use the wrappers in scripts/dev-shell.{sh,bat} which figure out
# the bind-mount path for you.

FROM python:3.13-slim

# OS-level deps. git is needed because the kernel-runs-real-Sutra tests
# load .su sources via the external/Sutra submodule, which the user
# init-fetches inside the container if they didn't on the host.
# build-essential covers tree-sitter's compiled wheel extraction on
# arches where a manylinux wheel isn't available.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       git \
       build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

# Pre-install the heavy deps as their own layer so they cache across
# rebuilds when Yantra-side code changes. CPU torch wheel only
# (~200MB); the GPU wheel is multi-GB and isn't useful here because
# the v0.0 kernel doesn't allocate per-process GPU arenas anyway
# (see kernel/README.md "Honestly out of scope" section).
RUN pip install --no-cache-dir \
        pytest \
        numpy \
        tree-sitter \
        tree-sitter-typescript \
    && pip install --no-cache-dir \
        torch \
        --index-url https://download.pytorch.org/whl/cpu

# Tell git that /workspace is OK to use even though the bind-mounted
# host UID may not match the container's UID. Avoids the
# "fatal: detected dubious ownership" error that bites dev-container
# users on Linux hosts.
RUN git config --global --add safe.directory /workspace \
    && git config --global --add safe.directory /workspace/external/Sutra \
    && git config --global --add safe.directory '*'

# Default to an interactive bash shell. Users who want one-shot test
# runs override this on the docker run command line: `docker run ...
# yantra-dev pytest`.
CMD ["bash"]
