# `(Type) expr` casts and interpolated strings parse + validate but have NO codegen (2026-07-06)

> **UPDATE 2026-07-07 — cast half RESOLVED.** Cast lowering shipped for BOTH `(Type) expr` and
> `unsafeCast<Type>` (design table in `planning/sutra-spec/types.md` § "The shipped lowering
> table"; 18 guards in `tests/test_cast_codegen.py`). unsafeCast = pure relabel; `(Type)` =
> relabel by default with the numeric↔truth axis-move pair; text casts rejected with steers.
> The interpolated-string half is still open (blocked on the substrate number→string formatter).

Found by the real-program-reach usability drive (PINNED TAIL).

## Measured

Both hit the raw codegen fallback `unsupported expression: <Node>` (codegen_base.py:3593):

- **`(Type) expr` (CastExpr)** — EVERY form fails at codegen: `(number) x`, `(fuzzy) 0.5`, `(bool) f`,
  `(vector) v`, and the corpus's own `07_casts.su` (fails at 7:19). `07_casts.su` is in the VALID corpus
  but the corpus test only VALIDATES (asserts 0 errors); it never runs, so this went unnoticed. The
  executable cast is `unsafeCast<Type>(value)`, which codegens fine.
- **Interpolated strings (`$"x={x}"`, InterpolatedString)** — parses (compilation.md §3 documents the
  lexer token sequence) and is listed as a literal form (capabilities.md §5), but codegen has no handler.

## Why these are real gaps, not intended

Both are documented, parseable, validated surface forms with dedicated machinery elsewhere (SUT0111 guards
`(vector) "string"` casts; the lexer emits the interpolation token sequence). A newcomer writes `(int)x`
or `$"n={n}"` from the docs and gets a codegen error. Either implement the codegen or mark the forms
unsupported. (Docs updated to mark both as parse/validate-only for now; steering to `unsafeCast` / manual
`string_concat`.)

## What implementing them needs (not a quick patch)

- **Cast codegen (BOTH `(Type) expr` and `unsafeCast<Type>`)** — a per-target lowering: `(vector) v` is ~identity; `(number)/(int)` route to the
  numeric axes; `(fuzzy)/(bool)` are truth-axis reinterpretations (some are really `is_true` / defuzzify).
  Design: enumerate the legal source→target pairs and their substrate op, reuse the var-decl coercion
  logic that already types initializers. Bounded but real; needs the cast-semantics table.
- **InterpolatedString codegen** — desugar `$"a{e}b"` to `string_concat(make_string("a"), concat(
  to_string(e), make_string("b")))`. The blocker is `to_string(e)` for a non-string `e` (e.g. an `int`):
  number→decimal-string on the substrate is its own subsystem (the same formatting the neural-Unix number
  path would need). Interpolating string-typed exprs is easy; numbers/others need the formatter first.

## Disposition

Two build items (each its own rung), plus the docs already corrected to stop misleading newcomers:
1. CastExpr codegen (cast-semantics table + lowering) — bounded.
2. InterpolatedString codegen — needs a substrate number→string formatter first (prerequisite).
Neither is a cron-sized quick fix; both are genuine feature work with a design step.
