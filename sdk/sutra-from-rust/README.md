# sutra-from-rust

Rust → Sutra transpiler frontend (MVP). Models on `sutra-from-ocaml` (the
reference frontend). `lower(source)` turns Rust source into Sutra source;
fixtures are verified **compile-AND-run on the substrate** (the OCaml harness
bar), not compile-only.

## Status

First cut (2026-06-12): top-level `fn` items with typed parameters + returns
(i8…i64/u8…u64/usize/isize → int, f32/f64 → number, bool → bool); block bodies
with `let` bindings and a tail expression; integer/float literals with numeric
suffixes stripped; binary arithmetic/comparison/boolean operators; `if/else`
expressions → the defuzz blend; calls; parens. Substrate-verified: `add_main`
= 16, `if_classify` = 100, `let_block` = 17. Ownership/borrowing never reaches
the lowering at this scope (the value domain is copies of numbers); `&`/`mut`,
structs/enums/`match`, loops, and recursion surface as `UNSUPPORTED-*` markers
(recursion until the tail/CPS transforms are ported — never a silent
self-call).

Dependency: `tree-sitter-rust` (`pip install tree-sitter-rust`).

## Next

`match` + enums → tagged axons (Rust's algebraic enums map onto the OCaml
variant pattern); structs → axons; the recursion transforms; `while`/`loop` →
substrate loops; statement-bearing if-arms.
