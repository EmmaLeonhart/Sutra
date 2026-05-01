# Multi-system neuro-symbolic comparison environment.
#
# Sutra is one of several neuro-symbolic systems with overlapping
# but non-identical scopes. This image installs the systems we
# compare against in the paper so reviewers can re-run the
# comparison end-to-end:
#
#   - Sutra        (this repo, mounted at /work)
#   - Scallop      (Datalog + probabilistic semantics, Rust source build)
#   - DeepProbLog  (Prolog + neural facts, pip)
#   - TorchHD      (VSA library on PyTorch, pip)
#
# These solve different problems. The shared-task benchmark
# (`run_compare.py`) is restricted to a 1-hop knowledge-graph
# query that all four can express. The qualitative
# strengths/weaknesses matrix lives in the paper itself.
#
# Build:
#     docker build -t sutra-neurosym -f experiments/scallop_compare/Dockerfile .
#
# Run (mount the repo):
#     docker run --rm -v "$PWD:/work" -w /work sutra-neurosym \
#         python experiments/scallop_compare/run_compare.py
#
# Publish for reproducibility (after `docker login`):
#     docker tag sutra-neurosym <your-hub-username>/sutra-neurosym:latest
#     docker push <your-hub-username>/sutra-neurosym:latest

FROM python:3.11-slim

# System deps for Rust + scallop build.
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates build-essential pkg-config git make \
    && rm -rf /var/lib/apt/lists/*

# Install Rust nightly (Scallop's hard requirement).
ENV RUSTUP_HOME=/usr/local/rustup CARGO_HOME=/usr/local/cargo \
    PATH=/usr/local/cargo/bin:$PATH
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \
    | sh -s -- -y --default-toolchain nightly --profile minimal \
    && rustc --version

# Python ML / VSA / NSP deps. Split into steps so a single failing
# package doesn't invalidate the whole layer. Default PyPI for
# everything (CPU torch index turned out unreliable for these deps).
RUN pip install --no-cache-dir maturin numpy
RUN pip install --no-cache-dir torch torchhd
RUN pip install --no-cache-dir transformers
RUN pip install --no-cache-dir problog pysdd deepproblog

# Build Scallop + the Python bindings (`scallopy`).
RUN git clone --depth 1 https://github.com/scallop-lang/scallop.git /opt/scallop
WORKDIR /opt/scallop
RUN make install-scallopy

# Sanity check: every package imports.
RUN python -c "import scallopy, deepproblog, torchhd, torch, numpy; \
print('scallopy', scallopy.__name__); \
print('deepproblog', deepproblog.__name__); \
print('torchhd', torchhd.__version__); \
print('torch', torch.__version__)"

WORKDIR /work
CMD ["bash"]
