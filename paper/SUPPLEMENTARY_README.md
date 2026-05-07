# Sutra — NeurIPS 2026 Supplementary Material

This archive contains the source code and reproduction
instructions for the paper *Sutra: Tensor-Op RNNs as a
Compilation Target for Vector Symbolic Architectures*.

## What's here

```
sutra-neurips-supplementary/
├── README.md                  This file.
├── SKILL.md                   Replication skill — agent-runnable
│                              shell blocks that reproduce every
│                              empirical claim in the paper.
├── REPRODUCE.md               Companion narrative: which paper
│                              section maps to which command.
├── sdk/
│   ├── sutra-compiler/        Compiler (Python). Lexer, parser,
│   │                          type system, codegen, stdlib,
│   │                          test suite (245+ tests).
│   ├── intellij-sutra/        IntelliJ language plugin.
│   └── vscode-sutra/          VS Code TextMate grammar.
├── examples/                  27 .su programs covering every
│                              language feature, plus the
│                              10-program smoke test driver
│                              (_smoke_test.py).
├── experiments/               Reproduction scripts for §3
│                              capacity, crosstalk, and
│                              differentiable-training results.
│                              JSON reference outputs included
│                              for diff-against-yours comparison.
├── sutraDB/                   Rust FFI for the embedded
│                              vector-database codebook
│                              (test_sutradb_embedded.py).
├── tests/                     Top-level test scripts.
└── planning/sutra-spec/       Language specification.
```

## Replication via the skill file

`SKILL.md` is the canonical reproduction surface. It is
designed for an agent (Claude Code, Cursor, etc.) but reads
fine to a human: each section is a self-contained shell block
that runs one paper claim, with the assertion line that
captures the success condition the paper states.

To run the full reproduction by hand:

```bash
# 1. Install Python deps
pip install torch torchhd transformers

# 2. Pull the embedding models (Ollama runs locally)
ollama pull nomic-embed-text
ollama pull all-minilm
ollama pull mxbai-embed-large

# 3. (Optional) Build the SutraDB FFI for the embedded
#    codebook tests; without it, those tests skip.
cd sutraDB && cargo build --release -p sutra-ffi && cd ..

# 4. Walk SKILL.md top-to-bottom. Each block is independent;
#    a non-zero exit code from any block means that claim
#    does not reproduce.
```

To delegate to an agent: point the agent at `SKILL.md` and
say "run this skill against the supplementary archive." The
shell blocks are designed to be cut-and-paste runnable in
order.

## Paper claims this archive reproduces

| Paper section | What runs |
|---|---|
| §3.2 capacity sweep (rotation vs. Hadamard, three LLM substrates) | `experiments/rotation_binding_capacity_llm.py` |
| §3.2 protein-LM substrate (ESM-2) | `experiments/rotation_binding_capacity_bioinformatics.py` |
| §3.2.1 chained-bind crosstalk | `experiments/crosstalk_chain.py` |
| §3.4 first-class loops (soft-halt RNN cells) | `pytest sdk/sutra-compiler/tests/test_loop_function_decl.py` (23 tests) |
| §3.5 embedded SutraDB codebook | `pytest sdk/sutra-compiler/tests/test_sutradb_embedded.py` |
| §3.6 end-to-end differentiable training (19 ANDs deep, 95% accuracy) | `experiments/differentiable_training.py` |
| §4 compiler pipeline (245+ tests, full suite green) | `pytest sdk/sutra-compiler/tests/` |
| §5 10-program smoke test | `python examples/_smoke_test.py` |

`REPRODUCE.md` has the full per-section map, including the
hardware/runtime expectations.

## Hardware / environment

- **CPU:** 64-bit, ~14 s for the unit suite.
- **GPU:** CUDA optional. Runtime auto-detects; falls back to
  CPU for both the embedding model (Ollama) and the compiled
  Sutra graph.
- **Memory:** 8 GB sufficient.
- **Python:** 3.11+.
- **Disk:** ~3 GB after embedding-model + PyTorch downloads.

## License + provenance

Sutra is open source under the MIT license. The canonical
upstream repository is
`https://github.com/EmmaLeonhart/Sutra`; this archive is the
state of `master` at submission time. The repository continues
to evolve; reviewers should rely on this archive for
reproduction rather than the live `master` branch.
