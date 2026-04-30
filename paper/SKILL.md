---
name: sutra-language
description: Reproduce the demonstration programs and substrate-purity claims for "Sutra: A Programming Language for Vector-Symbolic Computation in Frozen Embedding Spaces" — the working Sutra compiler + PyTorch tensor-op runtime, three demonstration programs, loop function decls + soft-halt RNN cells, embedded SutraDB codebook with nearest_string decode, opt-in torch.compile wrapping.
allowed-tools: Bash(python *), Bash(pip *), Bash(cd *), Bash(cargo *)
---

# Sutra: A Programming Language for Vector-Symbolic Computation in Frozen Embedding Spaces

**Author: Emma Leonhart**

This skill reproduces the demonstration programs and verifiable
substrate-purity claims of the paper. The paper takes the
algebraic structure of frozen embedding spaces as established by
the prior knowledge-graph-embedding literature (TransE, RotatE,
the word-analogy line) and presents the algorithms and language
that consolidate that structure into composable primitives.
Learned-matrix binding is positioned as next-implementation, not
a finished result; nothing to reproduce there yet.

## What this reproduces

1. **Working compiler end-to-end.** `.su` source → parse → simplify
   → codegen (PyTorch) → execute. Three demonstration programs
   (`hello_world.su`, `fuzzy_dispatch.su`, `role_filler_record.su`)
   plus loop demonstrations all run with expected outputs correct.
2. **Substrate-pure operations.** Bind (rotation), unbind, bundle,
   similarity, arithmetic on canonical synthetic axes, soft-halt
   RNN cells — all execute as tensor operations on the substrate.
3. **First-class loop functions with halt propagation.** Four
   loop kinds (`do_while`, `while_loop`, `iterative_loop`,
   `foreach_loop`); `pass values` and `return NAME(args)` tail-
   call surfaces both supported. Convergent loops return correct
   values; non-convergent loops wipe program output to ~0.
4. **Embedded SutraDB codebook.** Every embedded string in a
   compiled program is in a `.sdb` file at module init. The
   decode operation `_VSA.nearest_string(query)` returns the
   nearest string label for any vector. Round-trips correctly
   including unicode labels.
5. **Opt-in torch.compile wrapping.** With
   `SUTRA_TORCH_COMPILE=1`, every loop function is wrapped with
   `torch.compile(backend='eager')` so Dynamo unrolls the
   per-tick loop at trace time. Programs still produce correct
   results.

## Prerequisites

```bash
pip install torch
# Ollama running locally with nomic-embed-text model installed:
ollama pull nomic-embed-text
# SutraDB FFI shared library:
cd sutraDB && cargo build --release -p sutra-ffi
```

The runtime uses PyTorch (CPU or CUDA) for tensor ops, Ollama for
embedding fetches via `nomic-embed-text` (768-dim), and the
SutraDB FFI for the embedded codebook. Without the FFI build the
codebook decode path returns `None` gracefully; the rest of the
language still works.

## Reproducing each result

All commands run from the repo root. The compiler entry point is
the `sutra_compiler` Python module under `sdk/sutra-compiler/`.

### Working compiler (test suite)

```bash
cd sdk/sutra-compiler
python -m pytest tests/ -q --ignore=tests/test_simplify_egglog.py
```

Expected: **244+ tests pass**. The egglog test is skipped because
its import takes >20 minutes on Windows; the test itself is fine.

### Demonstration programs

```bash
cd sdk/sutra-compiler
PYTHONPATH=. python -m sutra_compiler --run ../../examples/hello_world.su
PYTHONPATH=. python -m sutra_compiler --run ../../examples/fuzzy_dispatch.su
PYTHONPATH=. python -m sutra_compiler --run ../../examples/role_filler_record.su
```

Each program prints its result. The hello-world program emits the
nomic-embed-text embedding of "hello world"; fuzzy_dispatch routes
through soft-mux scoring; role_filler_record demonstrates VSA
algebra with bind/bundle/unbind round-trips.

### Loop demonstrations (function-decl form)

```bash
cd sdk/sutra-compiler
python -m pytest tests/test_loop_function_decl.py -q
```

Expected: **23 tests pass** covering all four loop kinds plus the
`pass`-vs-`return NAME(args)` tail-call equivalence and program-
level halt propagation (a non-convergent `iterative_loop` returns
~0 because the unconverged halt-cum wipes the output).

### Embedded SutraDB codebook

```bash
cd sdk/sutra-compiler
python -m pytest tests/test_sutradb_embedded.py -q
```

Expected: **7 tests pass** covering FFI roundtrip, three-orthogonal-
vector nearest neighbor, top-k, unicode label round-trip, env-var
path override.

If the FFI DLL isn't built, all 7 tests skip; the test runner
prints a hint pointing at the cargo build command.

### Substrate-purity boundary leak fix verification

```bash
cd sdk/sutra-compiler
python -c "from sutra_compiler.codegen_pytorch import PyTorchCodegen; from sutra_compiler import ast_nodes; cg = PyTorchCodegen(); cg._prefetch_strings = []; py = cg.translate(ast_nodes.Module(items=[], span=None)); print('saturate_unit' in py, 'heaviside' in py, 'truth_axis' in py)"
```

Expected: `True True True` — the substrate-pure scalar primitives
are emitted in every module.

### Optional: torch.compile wrapping

```bash
cd sdk/sutra-compiler
SUTRA_TORCH_COMPILE=1 python -m pytest tests/test_torch_compile_wrap.py -q
```

Expected: **3 tests pass**. Backend defaults to `eager`; override
with `SUTRA_TORCH_COMPILE_BACKEND=inductor` for fused CUDA kernels
(requires Triton install).

## What this does NOT reproduce

- **The algebraic-structure premise.** The paper takes as given
  that frozen embedding spaces have algebraic structure; that is
  established by the prior knowledge-graph-embedding literature
  (TransE, RotatE, word-analogy work) and is not re-derived here.
- **Object encapsulation as load-bearing.** Parser handles object
  decls; encapsulation is not enforced. Queued.

## Repository layout

- `sdk/sutra-compiler/` — the compiler + runtime + tests
- `examples/` — `.su` demonstration programs
- `planning/sutra-spec/` — language specification
- `planning/findings/` — dated experimental findings
- `sutraDB/` — sibling RDF + HNSW triplestore (Rust)
- `paper/` — this paper + skill + reproduction docs
- `DEVLOG.md` — full project history (1407 commits, 2026-03-13 →
  2026-04-30)
