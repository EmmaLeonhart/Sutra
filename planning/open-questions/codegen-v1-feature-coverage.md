> **VERDICT — NEARLY CLOSED** (task #15 triage 2026-05-16; narrowed 2026-06-20; re-narrowed
> 2026-07-08 after the daily audit found the cast work had shipped the remaining expression
> forms). Authoritative table: `planning/open-questions/README.md`. Precise open part: only
> **top-level `MethodDecl`** (a `method` declared outside a class body) is still refused
> (`codegen_base.py:975-978`).

---

# Open question: what should the V1 codegen actually cover?

## What is SHIPPED (with authoritative locations)

- **`EmbedExpr`** → `_VSA.embed(...)` (`_embed_expr_src`; also the implicit
  `vector v = "foo"` auto-embed). Verified 2026-06-20.
- **`DefuzzyExpr`** → compile-time expansion of the stdlib `defuzzy` body
  (`_defuzzy_expr_src`). Verified 2026-06-20.
- **`UnsafeCastExpr`** → the pure relabel (`codegen_base.py:3686` — value unchanged, static
  type changes), per `types.md` § "Casting — relabeling, not transformation". Shipped
  2026-07-07 with the full cast-lowering table (`(Type) expr` conversion casts included);
  guards in `tests/test_cast_codegen.py`.
- **`UnsafeOverrideExpr`** → the pure passthrough (`codegen_base.py:3693`). Shipped
  2026-07-08 (round-19 audit); guards in `tests/test_unsafe_override_codegen.py`.
- **Class-body method + operator declarations** → mangled top-level functions with
  inheritance-chain dispatch (`_translate_class_method`); the stdlib String `operator +`
  rides this.

## The remaining open tail

**Top-level `MethodDecl`** — a `method` declared at file scope, outside any class — is
refused (`codegen_base.py:975-978`). Whether that surface should exist at all (vs `function`
being the only file-scope form) is the actual residue of this question; everything else this
doc originally tracked has lowered.

## Status

NEARLY CLOSED (2026-07-08). If Emma rules top-level `method` out of the surface (making
`function` the only file-scope form), this doc retires entirely; if she wants it in, the
work is a small parser/codegen alignment, not a design question.
