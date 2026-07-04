# REPL first-run — newcomer experience (2026-07-04)

Launched `sutrac repl` (`python -m sutra_compiler repl`) as a newcomer and drove
it with a handful of expressions. Four findings, one fixed this session, three
filed to `queue.md`.

## Method

Two piped sessions (Ollama backend, CUDA present):
1. Naive guesses: `2 + 3`, `"hello"`, `similarity("cat", "dog")`, `:help`, `:quit`.
2. Documented pattern (from `docs/tutorials/01-hello-sutra.md`): `vector a =
   embed("cat"); vector b = embed("dog"); similarity(a, b); embed("hello")`.

## Findings

**1. FIXED — scalar results leaked torch's raw tensor repr.** With real
`embed()` vectors on CUDA, `similarity(a, b)` displayed as
`tensor(0.6812, device='cuda:0')` — CUDA/dtype internals a newcomer should
never see. Cause: `_decode_result` only formatted 1-d codebook vectors; a 0-d
reduction tensor fell through to `repr(result)`. Fix: format any 1-element
tensor as `= {float:g}` at the sanctioned terminal-display boundary (the same
boundary line 112 already reads the real axis at). Now shows `= 0.681239`.
Regression test `test_scalar_tensor_result_shows_clean_number_not_repr`.
(Note the `make_real` path already returns a host float, so this only bit the
`embed`/CUDA path — which is exactly the documented first-program path.)

**2. FILED — the REPL is completely undocumented.** `grep` over `docs/` finds
zero mentions of the REPL, `:help`, `:decls`, `:quit`, or `sutrac repl`, yet
`sutrac`'s own usage text advertises "sutrac repl → Explore interactively." A
newcomer told to explore has no page telling them what to type or that strings
must be `embed()`-ed first. → queue: write a short REPL doc page.

**3. FILED — a bare string literal crashes the REPL.** Top-level `"hello"`
(not `embed("hello")`) throws `runtime error: TypeError: can't multiply
sequence by non-int of type 'float'` — an internal codegen error for a bare
string-literal expression, not a Sutra-level message or a shown value. Deeper
than display (string lowering in codegen); needs care + its own test. → queue.

**4. FOLDS INTO H1 — naive `similarity("cat","dog")` (string args) gives an
opaque error.** `TypeError: linalg_norm(): argument 'input' must be Tensor,
not str` instead of "similarity expects vectors — did you embed() first?".
This is the deferred v0.2 name-resolution / type-checking gap
(`planning/findings/2026-06-24-h1-name-resolution-is-deferred-v0.2.md`): the
validator can't yet catch a string passed where a vector is required. No new
work — recorded as another concrete newcomer-facing symptom of H1.

## What works well (keep)

- Number expressions: `make_real(2.0) + make_real(3.0)` → `= 5`.
- `embed("hello")` → `~ "hello"  (cos 1.00)` — clean nearest-concept display.
- Declarations (`vector a = embed(...);` → `(added)`), `:help`, `:decls`,
  `:reset`, `:quit` (exit 0). Errors don't kill the loop.
