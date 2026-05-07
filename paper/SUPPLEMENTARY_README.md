# Sutra — NeurIPS 2026 Supplementary Material

This archive is a tightly-scoped reproduction package for the
paper *Sutra: Tensor-Op RNNs as a Compilation Target for Vector
Symbolic Architectures*. Every file in here is something a
NeurIPS reviewer needs to verify a paper claim. Tooling
(IDE plugins), unrelated SutraDB sub-projects, exploratory
scripts, run logs, and trained-weight binaries have all been
left out.

## Layout

```
sutra-neurips-supplementary/
├── README.md                       This file.
├── SKILL.md                        Replication skill — agent-runnable
│                                   shell blocks that reproduce every
│                                   empirical claim in the paper.
├── REPRODUCE.md                    Companion narrative: which paper
│                                   section maps to which command.
│
├── sdk/sutra-compiler/             The compiler. Lexer, parser, type
│                                   system, simplifier, codegen, stdlib,
│                                   plus the 245+ test suite that
│                                   verifies the §4 pipeline. Pure
│                                   Python; no build step.
│
├── examples/                       26 .su programs covering every
│                                   language feature, plus the smoke
│                                   test driver and harness:
│   ├── *.su                        the language demos
│   ├── _smoke_test.py              the 10-program smoke test (§5)
│   ├── _su_harness.py              shared test helper
│   └── atman.toml                  example program config
│
├── experiments/                    Reproduction scripts for §3 results
│                                   and the optional cross-paradigm
│                                   comparison:
│   ├── rotation_binding_capacity.py
│   ├── rotation_binding_capacity_llm.py
│   ├── rotation_binding_capacity_bioinformatics.py
│   ├── crosstalk_chain.py
│   ├── differentiable_training.py
│   ├── rotation_hashmap_capacity.py
│   ├── sutra_vs_torchhd.py
│   ├── sutra_vs_torchhd_latency.py
│   ├── synthetic_subspace_validation.py
│   ├── *_results.json              reference outputs (diff vs your run)
│   └── scallop_compare/            optional Docker image — Sutra vs
│                                   Scallop / DeepProbLog / TorchHD on
│                                   the same 1-hop KG query
│
├── sutraDB/                        Rust source for the embedded-codebook
│                                   FFI shared library (used by
│                                   tests/test_sutradb_embedded.py):
│   ├── Cargo.toml                  workspace, trimmed to the four
│                                   crates the FFI needs
│   ├── sutra-core/                 triple storage engine
│   ├── sutra-hnsw/                 HNSW index
│   ├── sutra-sparql/               SPARQL+ query engine
│   └── sutra-ffi/                  the C-compatible shared library
│
└── docs/                           Syntax + language documentation
                                    (the same pages served at
                                    sutralang.dev). Describes what
                                    is implemented today, not
                                    speculative design:
    ├── what-is-sutra.md             overview
    ├── primitive-classes.md         type system
    ├── operators.md                 operator surface
    ├── loops.md                     loop forms (do_while, while_loop,
    │                                iterative_loop, foreach_loop)
    ├── logical-operations.md        Kleene three-valued logic
    ├── numeric-math.md              numeric primitives
    ├── memory.md                    extended-state-vector layout
    ├── compilation.md               compiler pipeline
    ├── ontology.md                  class system
    ├── paradigms.md                 comparison with imperative OO
    ├── vision.md                    the geometric-compilation framing
    └── tutorials/                   step-by-step walkthroughs
```

## How to reproduce

```bash
# 1. Install Python deps.
pip install torch torchhd transformers

# 2. Pull the embedding models (Ollama runs locally).
ollama pull nomic-embed-text
ollama pull all-minilm
ollama pull mxbai-embed-large

# 3. Build the SutraDB FFI for the embedded-codebook test
#    (optional — the test skips gracefully without it).
cd sutraDB && cargo build --release -p sutra-ffi && cd ..

# 4. Walk SKILL.md top-to-bottom. Each shell block is independent
#    and asserts the paper's success condition; a non-zero exit
#    code means that claim does not reproduce.
```

To delegate to an agent: point Claude Code or a similar agent at
`SKILL.md` and say "run this skill against the supplementary
archive." The shell blocks are designed to be cut-and-paste
runnable in order.

## Paper claim → command map

| Paper section | Reproduction command |
|---|---|
| §3.2 capacity sweep (rotation vs. Hadamard, three LLM substrates) | `experiments/rotation_binding_capacity_llm.py` |
| §3.2 protein-LM substrate (ESM-2) | `experiments/rotation_binding_capacity_bioinformatics.py` |
| §3.2.1 chained-bind crosstalk depth | `experiments/crosstalk_chain.py` |
| §3.4 first-class loops (soft-halt RNN cells) | `pytest sdk/sutra-compiler/tests/test_loop_function_decl.py` (23 tests) |
| §3.5 embedded SutraDB codebook | `pytest sdk/sutra-compiler/tests/test_sutradb_embedded.py` |
| §3.6 end-to-end differentiable training (19 ANDs deep, 95% accuracy) | `experiments/differentiable_training.py` |
| §4 compiler pipeline (245+ tests, full suite green) | `pytest sdk/sutra-compiler/tests/` |
| §5 ten-program smoke test | `python examples/_smoke_test.py` |

`REPRODUCE.md` has the full per-section map, including hardware
and runtime expectations.

The full project tree (DEVLOG, todo, CI workflows, broader
SutraDB project, language tooling) lives at the upstream
repository: `https://github.com/EmmaLeonhart/Sutra`. Reviewers
should rely on this archive for reproduction; the upstream
master branch continues to evolve.

## Hardware / environment

- **CPU:** any 64-bit; the unit suite finishes in ~14 s on a
  modern desktop.
- **GPU:** CUDA optional. Both the embedding model (Ollama) and
  the compiled Sutra graph fall back to CPU automatically.
- **Memory:** 8 GB sufficient.
- **Python:** 3.11+.
- **Rust:** stable; only required if you want to run the
  embedded-codebook test (otherwise it skips).
- **Disk:** ~3 GB after downloading PyTorch and the three
  embedding models.

## License

Sutra is open source under the MIT license. SutraDB (the Rust
crates in `sutraDB/`) is Apache-2.0 (see `sutraDB/LICENSE`).
