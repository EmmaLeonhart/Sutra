> **VERDICT — NARROWED, STILL PARTLY OPEN** (task #15 triage 2026-05-16; narrowed 2026-06-20 after the
> daily audit found `EmbedExpr`/`DefuzzyExpr` are SHIPPED, not refused). Authoritative table:
> `planning/open-questions/README.md`. Precise open part: which of the genuinely-still-refused
> constructs (method declarations, operator declarations, `UnsafeCastExpr`) V1 should close.

---

# Open question: what should the V1 codegen actually cover?

## The question

`sdk/sutra-compiler/`'s codegen pipeline still refuses a few source-level constructs with a
`CodegenNotSupported` error:

- method declarations (class methods — not just free functions)
- operator declarations (`operator +` etc.)
- `UnsafeCastExpr`

**SHIPPED since this doc was written (verified 2026-06-20):** `EmbedExpr` and `DefuzzyExpr` now lower.
`EmbedExpr` → `_VSA.embed(...)` (`sdk/sutra-compiler/sutra_compiler/codegen.py` `_embed_expr_src`,
~line 119; also covers the implicit `vector v = "foo"` auto-embed). `DefuzzyExpr` → compile-time
expansion of the stdlib `defuzzy` body (`_defuzzy_expr_src`, ~line 129). Both compile end-to-end
through `codegen_pytorch` (spot-checked: `vector v = embed("hello");` emits `_VSA.embed`; a
`defuzzy(v)` program compiles).

The remaining question is: which of method decls / operator decls / `UnsafeCastExpr` should V1
support, which wait for V2, and which are spec features prototyped in `.su` but never put into the
runtime model.

## What we currently do

The original lint sweep (2026-04-12) tabulated SKIPs against `examples/01-…06.su` /
`examples/_legacy_syntax_tour.su`. **Those example files have since been removed from the tree**, so
the table is dropped as stale. Of the constructs it flagged, `EmbedExpr` and `DefuzzyExpr` now compile
(see above); only method decls, operator decls, and `UnsafeCastExpr` remain refused.

## Why each gap has force (or doesn't)

- **method decls / operator decls.** These are OO-flavored surface syntax. The V1 codegen emits free Python functions and calls `_VSA.op(...)`. To support methods, codegen would need a dispatch layer (class body → Python class, method body → Python method). Doable, not urgent unless a paper-relevant `.su` program wants methods. (See also the OO-encapsulation work in `todo.md`.)
- **`EmbedExpr` — SHIPPED.** Lowers to `_VSA.embed(...)`; also backs the implicit `vector v = "foo"` auto-embed. No longer a gap.
- **`DefuzzyExpr` — SHIPPED.** `defuzzy(...)` lowers by compile-time expansion of the stdlib `defuzzy` body (the defuzzification threshold reduction). No longer a gap.
- **`UnsafeCastExpr`.** Explicit cross-type cast. Semantics in the spec are vague. Low priority.

## What we'd need to decide

1. **Is V1 pinned at "just enough for the paper," or aiming for spec-complete?** Right now we are de facto at "just enough for the paper" — the three `.su` files the paper cites (`permutation_conditional`, `fuzzy_conditional`, `geometric_loop`) all compile. Everything else is illustrative.
2. **If spec-complete is the target, what order?** `EmbedExpr` and `DefuzzyExpr` are cheap and bite the most examples. Methods/operators are expensive. `UnsafeCastExpr` is under-specified.
3. **Should SKIP'd files get a marker?** If an example is authored against a future codegen, that's worth documenting in the file itself — a header comment like "requires codegen V2: method dispatch" — so a lint sweep can classify "known future-feature" vs "accidental drift" without re-running codegen.

## Concrete next steps (when picked up)

- ~~Add `EmbedExpr` lowering~~ — DONE (`_embed_expr_src` → `_VSA.embed`).
- ~~Add `DefuzzyExpr` lowering~~ — DONE (`_defuzzy_expr_src`, compile-time expansion).
- Decide method-decl / operator-decl support (the OO dispatch layer) vs leaving them to the
  TS-transpiler / OO-encapsulation track.
- Pin down `UnsafeCastExpr` semantics (or formally retire it from the surface).

## Status

NARROWED, partly resolved (2026-06-20). The `EmbedExpr` / `DefuzzyExpr` parts are SHIPPED; the
remaining open tail is the OO surface (method/operator decls) + `UnsafeCastExpr`. Authoritative
resolution location for the shipped parts: `sdk/sutra-compiler/sutra_compiler/codegen.py`
(`_embed_expr_src`, `_defuzzy_expr_src`).
