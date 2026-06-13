# sutra-from-rust

Rust → Sutra transpiler frontend (MVP). Models on `sutra-from-ocaml` (the
reference frontend). `lower(source)` turns Rust source into Sutra source;
fixtures are verified **compile-AND-run on the substrate** (the OCaml harness
bar), not compile-only.

## Status

As of 2026-06-12: top-level `fn` items with typed parameters + returns
(i8…i64/u8…u64/usize/isize → int, f32/f64 → number, bool → bool); block bodies
with `let` bindings and a tail expression; integer/float literals with numeric
suffixes stripped; binary arithmetic/comparison/boolean operators; `if/else`
expressions → the defuzz blend; calls; parens; **algebraic `enum`s + `match` →
tagged axons** (the OCaml variant pattern: the enum erases to a tag/arity
prepass; the enum name maps to `Axon` in param/return types; construction
`E::V(a, b)` hoists to `Axon t; t.add("_tag", …); t.add("_val0", a); …`; a
`match` on an enum param binds `_vtag`/`_val{i}` to clean number-vector locals
first — the inline repeated `realvec(...)` reads do not project crisply,
measured 3.5 vs 2 — then blends by tag with the payload names substituted, the
last arm the exhaustive base). Substrate-verified: `add_main` = 16,
`if_classify` = 100, `let_block` = 17, `enum_match` = 2 (`eval(Expr::Lit 7) +
eval(Expr::Neg 5)`, with a `Pair(a, b)` multi-arg arm), `tail_rec` = 15
(tail-recursive `fn f(p…) { if COND { BASE } else { f(a…) } }` → a declared
`while_loop`, the OCaml/Scala/F# shape; non-tail recursion stays
`UNSUPPORTED-RECURSION`). Ownership/borrowing
never reaches the lowering at this scope; structs, `&`/`mut`, loops, and
recursion surface as `UNSUPPORTED-*` markers (recursion until the tail/CPS
transforms are ported — never a silent self-call). A `match` is supported as a
function-body tail; nested in a larger expression it is a later item.

Dependency: `tree-sitter-rust` (`pip install tree-sitter-rust`).

## Next

Structs → axons; the foldable non-tail CPS transform; `while`/`loop` → substrate
loops; statement-bearing if-arms; nested / non-tail `match`; nullary-variant
values.
