# Changelog

All notable changes to the Sutra language and compiler are recorded
here. Format loosely follows [Keep a Changelog](https://keepachangelog.com/).
Versions follow semantic versioning with the caveat that the language
is pre-1.0 — surface can change between minor versions.

## [Unreleased]

### Removed
- **Fly-brain experimental backend retired** (2026-04-26). The entire
  `fly-brain/` directory (47 tracked files: hemibrain MB scripts, Shiu
  whole-brain LIF probes, FlyWire data loaders, Brian2 substrate code),
  the `codegen_flybrain.py` codegen, the `--emit-flybrain` CLI flag,
  the `--runtime-n-kc` parameter, and the `fly-brain` substrate value
  in `atman.toml` are gone. The substrate work outpaced the language's
  maturity, so it was retired to clear the runway. Findings docs under
  `planning/findings/2026-04-1*-*` are preserved as historical record
  of negative and positive results.

## [0.2.0] — 2026-04-24

First tagged release. The compiler is real, `.su` source parses,
validates, compiles to self-contained Python targeting PyTorch (CUDA
when available, CPU otherwise), and runs. 175 tests pass.

### Language

- **Primitive classes:** `int`, `float`, `complex`, `char`, `bool`,
  `fuzzy`, `trit`, `vector`, `matrix`, `permutation`, `map`, `string`,
  `scalar`, `void`.
- **Extended-state vector layout:** every runtime value is a
  `[semantic (n) | synthetic (100)]` vector. Canonical synthetic axes:
  `real` at `synthetic[0]`, `imag` at `[1]`, `truth` at `[2]`,
  `char_flag` at `[3]`. Semantic block filled by `embed()` from the
  frozen LLM (nomic-embed-text, 768-dim default); synthetic block is
  reserved computational/symbolic space.
- **Literals:** integer (`5`), float (`3.14`), character (`'a'`),
  string (`"cat"`), complex (`5i`, `5 + 5i`), boolean (`true` /
  `false`), three-valued neutral (`unknown` / `unk`).
- **Truth-axis operations (Kleene K₃):**
  - `!v`, `a && b`, `a || b` as Lagrange-interpolated polynomials;
    exact on `{-1, 0, +1}`, smooth everywhere, differentiable.
  - `a == b`, `a != b` as cosine similarity placed on the truth axis.
    Eps-guarded divide so zero-norm inputs give truth=0 (unknown stays
    unknown) without branching.
  - `a > b`, `a < b`, `>=`, `<=` as `tanh(100 · real_axis_diff)`.
    Differentiable, saturates at ±1 for integer differences,
    `tanh(0) = 0` for ties.
  - `defuzzy(v)` — ten-iteration polarize loop along the truth axis.
- **Complex arithmetic as pure tensor ops:** `complex_mul` uses three
  cached matrices (`_swap_ri`, `_cm_real`, `_cm_imag`) plus two
  element-wise multiplies. No scalar extraction; the fusion pass can
  see straight through a chain of complex multiplies.
- **VSA primitives:** `bind`, `unbind` via role-seeded Haar-random
  rotation; `bundle` as normalized superposition; `argmax_cosine`,
  `select` (softmax-weighted); `embed` from frozen LLM.
- **Loops:** `loop(N)` unrolls at compile time for literal N;
  `loop(cond)`, `while`, `do`/`while`, `for` compile to eigenrotation
  with termination by prototype match; `foreach` over literal arrays
  unrolls.
- **Rotation-hashmap:** `map<vector, V>` compiles to a bind-based
  rotation hashmap with O(1) lookup. Capacity at d=868 matches the
  underlying d=768 raw bind/bundle study: 100% up to k=24, 90%
  threshold at k=48.

### Compiler

- **One codegen target:** `--emit` produces a self-contained torch
  module picking CUDA at module init. PyTorch is the compiler library;
  Sutra compiles to tensor ops the way clang compiles to LLVM IR.
- **Auxiliary backends:** `--emit-flybrain` for the fly-brain
  experimental substrate (since retired — see Unreleased changelog
  above); the internal `codegen.py` as the IR step that
  `PyTorchCodegen` inherits from.
- **Simplification pass:** identity rewrites (bundle flattening,
  bundle(v) → v, zero-vector absorption), auto-embed pass,
  complex-literal folds, fuzzy-literal coercion.
- **Fused shapes:** `bundle(bind(r1,f1), bind(r2,f2), ...)` emits one
  stacked einsum; `argmax_cosine` emits one batched matmul.
- **Diagnostics:** file:line:col error messages, JSON output for
  editor integration, `--summary` and `--consistency` modes.

### Standard library (scaffolding)

New `sdk/sutra-compiler/sutra_compiler/stdlib/` directory holds
canonical `.su` definitions for every system function category. All
7 files parse cleanly; **not yet wired into codegen** — user code
still compiles through the hardcoded runtime methods. These are
canonical reference files for the inliner pass in the next release.

- `logic.su` — defuzzy, logical_not/and/or, neq, lt, ge, le
  (implemented); defuzzify_trit, gt (blocked).
- `similarity.su` — neq (implemented); eq, similarity, argmax_cosine,
  select, snap (blocked).
- `numbers.su` — make_real, make_complex, make_char, complex_mul,
  conj (all blocked).
- `vectors.su` — bind, unbind, bundle, permute, basis_vector,
  permutation_key, identity_permutation, compose (all blocked).
- `memory.su` — zero_vector, hashmap_get/set, map_lookup (all blocked).
- `rotation.su` — make_random_rotation, compile_prototypes,
  eigenrotation_loop (all blocked).
- `embed.su` — embed (pure intrinsic).

### Tooling

- **IntelliJ plugin** (`sdk/intellij-sutra/`) — lexer, syntax
  highlighter, color settings page, quote handler, brace matcher,
  completion contributor, external annotator driven by the reference
  compiler. Handles char literals, imaginary suffix (`5i`), all
  primitive types.
- **VS Code extension** (`sdk/vscode-sutra/`) — TextMate grammar
  matching the IntelliJ lexer token set.
- **Docs site** — MkDocs Material at <https://sutralang.dev>, built
  and deployed by `.github/workflows/pages.yml` on push to master.

### Known limitations

- **stdlib inliner not yet wired.** System functions still compile to
  hardcoded runtime methods. The pipeline to land this is the next
  release's active work: loader → inliner → unroll → delete runtime
  methods → intrinsic mechanism → fusion pass. See `STATUS.md`.
- **Fusion pass limited.** Only `bundle(bind,bind,...)` and
  `argmax_cosine` emit fused shapes; mixed sequences like
  `bundle(bind(r,f), c, bind(r2,f2))` still emit sequentially.
  Generalized ANF + dep analysis for cross-pattern fusion is part of
  the next release.
- **Learned-matrix binding deferred.** `role X = learned_from(data)`
  fitting a matrix at compile time is spec'd but not implemented.
  Current `bind` is rotation-only.
- **Fly-brain substrate retired.** See Unreleased / 2026-04-26 entry
  above. The spiking MB and Shiu whole-brain LIF experiments produced
  mixed negative findings (EPG ring-attractor doesn't discriminate
  direction on real connectivity; polar-decomposition `Q` on FlyWire
  is compressive not rotational) preserved as findings docs.

## [0.1.0] — development placeholder

Pre-release placeholder version in `__init__.py`. Never tagged.
