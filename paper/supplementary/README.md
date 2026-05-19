# Sutra — replication package

This archive is the reproduction package for the paper
*Sutra: Tensor-Op RNNs as a Compilation Target for Vector
Symbolic Architectures*. Every file in here is something a
reader needs to verify a paper claim or to read the
language as it is implemented.

Author: Emma Leonhart. Upstream repository:
<https://github.com/EmmaLeonhart/Sutra>.

This package is **self-contained** — reproduce from the files
bundled here, not from the network. The repository link is a
**fallback only**: if you are blocked (a dependency will not
resolve, an artifact looks inconsistent, or you need a fix made
after this archive was cut), the current upstream state is the
place to check. Prefer the bundled copy whenever it suffices.

## Layout

```
sutra-replication-package/
├── README.md                       this file
├── SKILL.md                        agent-runnable replication
│                                   skill: shell blocks that
│                                   reproduce every empirical
│                                   claim in the paper
├── REPRODUCE.md                    paper-section to command map
├── SYNTAX.md                       language reference: types,
│                                   operators, loops, the
│                                   compilation pipeline
│
├── sdk/sutra-compiler/             the compiler — lexer, parser,
│                                   type system, simplifier,
│                                   codegen, stdlib, plus the
│                                   245+ test suite that verifies
│                                   the §4 pipeline. Pure Python,
│                                   no build step.
│
├── examples/                       26 .su programs covering every
│                                   language feature, plus the
│                                   smoke test driver:
│   ├── *.su                        the language demos
│   ├── _smoke_test.py              the 10-program smoke test (§5)
│   ├── _su_harness.py              shared test helper
│   └── atman.toml                  example program config
│
├── experiments/                    reproduction scripts for §3
│                                   results and the optional
│                                   cross-paradigm comparison:
│   ├── rotation_binding_capacity.py
│   ├── rotation_binding_capacity_llm.py
│   ├── rotation_binding_capacity_bioinformatics.py
│   ├── crosstalk_chain.py
│   ├── differentiable_training.py             §3.6 proxy (frozen-record reference)
│   ├── differentiable_training_compiled.py    §3.6 genuine compiled graph (--batched)
│   ├── differentiable_training_weighted.py    §3.7 weighted; trained w baked into .su
│   ├── rotation_hashmap_capacity.py
│   ├── sutra_vs_torchhd.py
│   ├── sutra_vs_torchhd_latency.py
│   ├── synthetic_subspace_validation.py
│   ├── *_results.json              reference outputs for diff
│   └── scallop_compare/            optional Docker image — Sutra
│                                   vs. Scallop / DeepProbLog /
│                                   TorchHD on a 1-hop KG query
│
└── sutraDB/                        Rust source for the embedded-
                                    codebook FFI shared library
                                    (used by
                                    test_sutradb_embedded.py):
    ├── Cargo.toml                  workspace, trimmed to the
                                    four crates the FFI needs
    ├── sutra-core/                 triple storage engine
    ├── sutra-hnsw/                 HNSW index
    ├── sutra-sparql/               SPARQL+ query engine
    └── sutra-ffi/                  the C-compatible shared
                                    library
```

## How to reproduce

```bash
# Working directory: the unzipped archive root.

# 1. Install Python deps.
pip install torch torchhd transformers

# 2. Pull the embedding models (Ollama runs locally).
ollama pull nomic-embed-text
ollama pull all-minilm
ollama pull mxbai-embed-large

# 3. Build the SutraDB FFI for the embedded-codebook test
#    (optional — the test skips if the FFI is not built).
cd sutraDB && cargo build --release -p sutra-ffi && cd ..

# 4. Walk SKILL.md top-to-bottom. Each shell block is
#    independent and asserts the paper's success condition;
#    a non-zero exit code means that claim does not reproduce.
```

To delegate to an agent: point an agent (Claude Code or
similar) at `SKILL.md` and instruct it to run the skill against
the archive. The shell blocks are designed to run in sequence,
each one independent of the others.

## Paper claim → command map

| Paper section | Reproduction command |
|---|---|
| §3.2 capacity sweep (rotation vs. Hadamard, three LLM substrates) | `experiments/rotation_binding_capacity_llm.py` |
| §3.2 protein-LM substrate (ESM-2) | `experiments/rotation_binding_capacity_bioinformatics.py` |
| §3.2.1 chained-bind crosstalk depth | `experiments/crosstalk_chain.py` |
| §3.4 first-class loops (soft-halt RNN cells) | `pytest sdk/sutra-compiler/tests/test_loop_function_decl.py` (23 tests) |
| §3.5 embedded codebook | `pytest sdk/sutra-compiler/tests/test_sutradb_embedded.py` |
| §3.6 differentiable training through the compiled graph (K=5, 18.7→100.0%, 3 seeds) | `experiments/differentiable_training_compiled.py --batched` |
| §3.7 trained weight baked into recompilable `.su` (round-trip verified) | `experiments/differentiable_training_weighted.py` |
| §4 compiler pipeline (245+ tests) | `pytest sdk/sutra-compiler/tests/` |
| §5 ten-program smoke test | `python examples/_smoke_test.py` |

`REPRODUCE.md` has the full per-section map, including hardware
and runtime expectations.

## Hardware

- **CPU**: any 64-bit; the unit suite finishes in ~14 s on a
  modern desktop.
- **GPU**: CUDA optional. The embedding model (Ollama) and the
  compiled Sutra graph both fall back to CPU automatically.
- **Memory**: 8 GB sufficient.
- **Python**: 3.11+.
- **Rust**: stable; required only for the embedded-codebook
  test, which skips otherwise.
- **Disk**: ~3 GB after PyTorch and embedding-model downloads.

## License

The compiler and example sources are MIT-licensed. SutraDB
(the Rust crates in `sutraDB/`) is Apache-2.0; see
`sutraDB/LICENSE`.
