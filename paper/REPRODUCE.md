# Reproducing the Sutra Paper Results

NeurIPS reproducibility checklist requires pointing at runnable
code; this is the runnable-code map. Pair with `paper/SKILL.md`
(the agent-facing skill description) and `DEVLOG.md` (the
historical context).

The Sutra repository at
`https://github.com/EmmaLeonhart/Sutra`
is the reproduction artifact. The compiler, runtime, demonstration
programs, tests, and language specification are all here.

## Quick start

```bash
git clone https://github.com/EmmaLeonhart/Sutra
cd Sutra

# Compiler runtime (PyTorch tensor ops)
pip install torch

# Embedding model (Ollama runs locally; nomic-embed-text is the default substrate)
ollama pull nomic-embed-text

# SutraDB FFI shared library (for the embedded codebook)
cd sutraDB && cargo build --release -p sutra-ffi && cd ..

# Compile + execute the hello-world demonstration
cd sdk/sutra-compiler
PYTHONPATH=. python -m sutra_compiler --run ../../examples/hello_world.su
```

Three downloads required: PyTorch (~2 GB with CUDA support),
`nomic-embed-text` via Ollama (~270 MB), Rust toolchain for the
SutraDB FFI build (one-time, ~5 minutes).

## What each paper claim maps to

| Paper claim | Reproduction |
|---|---|
| §3 — rotation binding works on natural anisotropic embeddings | `python -m pytest sdk/sutra-compiler/tests/test_codegen.py` (verifies the emitted `bind`/`unbind` shape; round-trip in the demo programs) |
| §3.1 — capacity tables (rotation vs Hadamard, 3 LLM substrates) | `python experiments/rotation_binding_capacity_llm.py` (the three tables in §3.1 are this script's output; embeddings cached to a gitignored dir on first run) |
| §3.1 — synthetic-vector reference (rotation algebra alone, no LLM) | `python experiments/rotation_binding_capacity.py` (controls for the rotation algebra independent of substrate distribution) |
| §3.2 — extended-state-vector layout | the `_TorchVSA` runtime class in the PyTorch codegen module |
| §3.3 — first-class loops as RNN cells | `python -m pytest sdk/sutra-compiler/tests/test_loop_function_decl.py -q` (23 tests) |
| §3.3 — halt propagation wipes output for unconverged loops | `tests/test_loop_function_decl.py::TestProgramHaltPropagation::test_unconverged_loop_wipes_output` |
| §3.4 — embedded SutraDB codebook + decode path | `python -m pytest sdk/sutra-compiler/tests/test_sutradb_embedded.py -q` (7 tests) |
| §4 — compiler 5-stage pipeline | `python -m pytest sdk/sutra-compiler/tests/ -q --ignore=tests/test_simplify_egglog.py` (244+ tests; full suite green) |
| §4.1 — substrate-purity invariants | the runtime-substrate-purity-audit and substrate-purity-leak-enumeration finding docs under `planning/findings/` |
| §4.2 — compile-time resolution to tensor normal form | rotation precomputation + fixed-depth loop unroll; see `codegen_pytorch.py` `prewarm_rotation_cache` and `loop` methods |
| §5 — demonstration programs (13 in smoke test, 23 `.su` files total) | `python examples/_smoke_test.py` runs the smoke-test corpus end-to-end; full file listing in `examples/` |
| §5.4 — convergent + non-convergent loop demos | `examples/do_while_adder.su` plus the test corpus in `tests/test_loop_function_decl.py` |
| §4 — `torch.compile` wrapping (opt-in) | `SUTRA_TORCH_COMPILE=1 python -m pytest sdk/sutra-compiler/tests/test_torch_compile_wrap.py -q` |

## Numerical exactness

Every demonstration program is deterministic given the embedding
model: same `.su` source + same `nomic-embed-text` weights → bit-
identical output across runs. The compile-time disk cache makes
second-and-later runs faster but does not change results. The
runtime device (CPU vs CUDA) does not change correctness; numerical
differences from float32 vs float64 are in the noise relative to
the substrate's geometric tolerance.

The loop tests (`test_loop_function_decl.py`) use
`assertAlmostEqual(places=2)` because the substrate operates on
fuzzy values; "x = 11" through the soft-halt cell ends at 11.00
when convergent, near zero when not.

## Hardware

- CPU: any 64-bit; tests run in ~14 seconds on a modern desktop.
- GPU: CUDA-capable card recommended for the embedding model.
  Ollama auto-detects; if no GPU, falls back to CPU embedding
  (slower first call; cached afterward).
- Memory: 8 GB sufficient for the demonstration programs.

## Honest limitations

These are real and disclosed in the paper:

- Numpy backend (`codegen.py`) is deprecated but retained for
  emit-shape tests. Behavior tests run on PyTorch.
- Object encapsulation parses but rules are not enforced.

## Reporting issues

Open a GitHub issue at
`https://github.com/EmmaLeonhart/Sutra/issues`. For NeurIPS
double-blind review, the anonymized PDF (queue sub-item 1e)
strips author names + repo URL; non-anonymized version available
post-acceptance.
