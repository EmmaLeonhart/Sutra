# Open question: what should the fly-brain codegen V1 actually cover?

## The question

`sdk/sutra-compiler/`'s `codegen_flybrain.translate_module` deliberately refuses several source-level constructs with a `CodegenNotSupported` error, e.g.:

- method declarations (class methods — not just free functions)
- operator declarations (`operator +` etc.)
- `DefuzzyExpr` (`is_true(...)` unwrap)
- `EmbedExpr` (the `embed "..."` literal form)
- `UnsafeCastExpr`

Programs exist in the repo that use every one of these (see `examples/01-…06.su`, `fly-brain/four_state_conditional.su`, `sutra-demo-program.su`). Those programs pass parser + validator but cannot compile to the live MB substrate.

The question is: which of these should V1 support, which should wait for V2, and which are spec features that were prototyped in `.su` but never made it into the runtime model?

## What we currently do

The lint sweep (run 2026-04-12) found:

| File | Status | First unsupported construct |
|---|---|---|
| `examples/01-objects-and-methods.su` | SKIP | method decl |
| `examples/02-functions-vs-methods.su` | SKIP | method decl |
| `examples/03-types-and-casts.su` | SKIP | `EmbedExpr` |
| `examples/04-control-flow-and-errors.su` | SKIP | `DefuzzyExpr` |
| `examples/05-operators-and-strings.su` | SKIP | operator decl |
| `examples/06-executable-file.su` | SKIP | `EmbedExpr` |
| `examples/workspace/corpus/main.su` | OK | — |
| `examples/workspace/similarity/main.su` | OK | — |
| `fly-brain/four_state_conditional.su` | SKIP | `EmbedExpr` |
| `fly-brain/fuzzy_conditional.su` | OK | — |
| `fly-brain/geometric_loop.su` | OK | — |
| `fly-brain/permutation_conditional.su` | OK | — |
| `sutra-demo-program.su` | SKIP | `UnsafeCastExpr` |

6 PASS, 7 SKIP, 0 FAIL. Nothing is broken; the SKIPs are known feature gaps.

## Why each gap has force (or doesn't)

- **method decls / operator decls.** These are OO-flavored surface syntax. The V1 codegen emits free Python functions and calls `_VSA.op(...)`. To support methods, codegen would need a dispatch layer (class body → Python class, method body → Python method). Doable, not urgent unless a paper-relevant `.su` program wants methods.
- **`EmbedExpr`.** Source-level `embed "foo"` is syntactic sugar for `basis_vector("foo")` (approximately). Easy to lower. Probably should be in V1 — its absence forces every real `.su` program to use `basis_vector(...)` explicitly.
- **`DefuzzyExpr`.** `is_true(...)` maps to the defuzzification threshold. Spec says it's a tier-2 op reducing a vector to a scalar in [0,1]. Should compile to a `_VSA.is_true(...)` call. Missing the runtime method is probably the real blocker.
- **`UnsafeCastExpr`.** Explicit cross-type cast. Semantics in the spec are vague. Low priority.

## What we'd need to decide

1. **Is V1 pinned at "just enough for the paper," or aiming for spec-complete?** Right now we are de facto at "just enough for the paper" — the three `.su` files the paper cites (`permutation_conditional`, `fuzzy_conditional`, `geometric_loop`) all compile. Everything else is illustrative.
2. **If spec-complete is the target, what order?** `EmbedExpr` and `DefuzzyExpr` are cheap and bite the most examples. Methods/operators are expensive. `UnsafeCastExpr` is under-specified.
3. **Should SKIP'd files get a marker?** If an example is authored against a future codegen, that's worth documenting in the file itself — a header comment like "requires codegen V2: method dispatch" — so a lint sweep can classify "known future-feature" vs "accidental drift" without re-running codegen.

## Concrete next steps (when picked up)

- Add `EmbedExpr` lowering to `basis_vector(name)` in `codegen_flybrain.translate_expr`.
- Add `DefuzzyExpr` lowering + matching `FlyBrainVSA.is_true` method.
- Tag each SKIP'd `.su` file with a header comment citing the specific construct it needs.
- Add a CI lint check that fails if an `OK` file regresses to SKIP (distinct from FAIL).

## Status

Unresolved. Not blocking the Claw4S paper. Currently captured as backlog item in STATUS.md.
