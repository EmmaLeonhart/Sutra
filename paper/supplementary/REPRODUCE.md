# Reproducing the paper results

Reproducibility requires pointing at runnable code; this is the
runnable-code map. Pair with `SKILL.md` (the
agent-runnable shell-block version) and `SYNTAX.md` (the
language reference).

This archive is the reproduction artifact. The compiler,
runtime, demonstration programs, tests, and language reference
are all included.

The package is self-contained; reproduce from the bundled files.
If you get stuck, the current upstream source is at
<https://github.com/EmmaLeonhart/Sutra> (Emma Leonhart) — a
fallback, not the primary path.

## Quick start

```bash
# Working directory: the unzipped archive root.

# Compiler runtime (PyTorch tensor ops)
pip install torch

# Embedding model. Ollama runs locally; nomic-embed-text is the
# default substrate.
ollama pull nomic-embed-text

# SutraDB FFI shared library (for the embedded codebook tests).
cd sutraDB && cargo build --release -p sutra-ffi && cd ..

# Compile + execute the hello-world demonstration.
cd sdk/sutra-compiler
PYTHONPATH=. python -m sutra_compiler --run ../../examples/hello_world.su
```

Three downloads on first run: PyTorch (~2 GB with CUDA
support), `nomic-embed-text` via Ollama (~270 MB), Rust
toolchain for the FFI build (one-time, ~5 minutes).

## Paper claim → command map

| Paper claim | Reproduction |
|---|---|
| §3.2 rotation binding capacity (rotation vs. Hadamard, 3 LLM substrates) | `python experiments/rotation_binding_capacity_llm.py` |
| §3.2 synthetic-vector reference (rotation algebra alone, no LLM) | `python experiments/rotation_binding_capacity.py` |
| §3.2 ESM-2 protein-LM substrate | `python experiments/rotation_binding_capacity_bioinformatics.py` |
| §3.2.1 chained-bind crosstalk depth | `python experiments/crosstalk_chain.py` |
| §3.3 extended-state-vector layout | the runtime class in `sdk/sutra-compiler/sutra_compiler/codegen_pytorch.py` |
| §3.4 first-class loops as soft-halt RNN cells | `pytest sdk/sutra-compiler/tests/test_loop_function_decl.py` (23 tests) |
| §3.4 program-level halt propagation | `tests/test_loop_function_decl.py::TestProgramHaltPropagation::test_unconverged_loop_wipes_output` |
| §3.5 embedded codebook + decode path | `pytest sdk/sutra-compiler/tests/test_sutradb_embedded.py` (7 tests; skips if FFI unbuilt) |
| §3.6 differentiable training through the compiled graph (K=5, before 18.7±9.5% → after 100.0±0.0%, 3 seeds; batched ≈230 s, equivalence-asserted) | `python experiments/differentiable_training_compiled.py --k 5 --per-class 10 --epochs 30 --seeds 0,1,2 --lr 0.01 --batched` |
| §3.7 trained scalar gain baked into `.su` as a literal; recompile round-trip verified (K=3, w*≈1.43) | `python experiments/differentiable_training_weighted.py --k 3 --per-class 8 --epochs 30 --seeds 0,1` |
| §4 compiler pipeline (245+ tests, full suite green) | `pytest sdk/sutra-compiler/tests/` |
| §4.1 substrate-purity invariants | enforced at codegen; see `codegen_pytorch.py` |
| §4.2 compile-time resolution of role rotations | `prewarm_rotation_cache` + the `loop` lowering in `codegen_pytorch.py` |
| §5 demonstration programs (10 in the smoke test, 27 `.su` files total) | `python examples/_smoke_test.py` |
| §5 convergent + non-convergent loop demos | `examples/do_while_adder.su` plus the test corpus |
| §4 `torch.compile` wrapping (opt-in) | `SUTRA_TORCH_COMPILE=1 pytest sdk/sutra-compiler/tests/test_torch_compile_wrap.py` |

## Numerical exactness

Every demonstration program is deterministic given the
embedding model: same `.su` source plus same `nomic-embed-text`
weights produces bit-identical output across runs. The
compile-time disk cache makes second-and-later runs faster but
does not change results. The runtime device (CPU vs. CUDA) does
not change correctness; float32-vs-float64 differences are
inside the substrate's geometric tolerance.

Loop tests (`test_loop_function_decl.py`) use
`assertAlmostEqual(places=2)` because the substrate operates on
fuzzy values: an integer-valued result like "x = 11" lands at
11.00 through the soft-halt cell when the loop converges, near
zero when it does not.

## Hardware

- CPU: 64-bit; the unit suite finishes in ~14 s on a modern
  desktop.
- GPU: CUDA optional. Ollama auto-detects and falls back to CPU
  embedding (slower first call, cached afterward). The compiled
  Sutra graph also picks CUDA when available.
- Memory: 8 GB sufficient.
- Disk: ~3 GB after PyTorch and embedding-model downloads.
- Python: 3.11+.
- Rust: stable; required only for the embedded-codebook test.

## Known limitations

Disclosed in the paper:

- The numpy backend (`codegen.py`) is deprecated but retained
  for emit-shape tests. Behavior tests run on PyTorch.
- Object encapsulation parses but the encapsulation rules are
  not enforced at runtime.
- Capacity drops at high bundle widths
  (e.g., 42% accuracy at k=48 on `all-minilm`).
- Crosstalk in nested bind/unbind chains drops to chance by
  chain length 8 (Appendix D).
