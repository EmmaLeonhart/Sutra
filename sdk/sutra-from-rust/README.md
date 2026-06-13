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
`UNSUPPORTED-RECURSION`), `nontail_fact` = 120 (foldable non-tail recursion
`LEAF +|* f(REC)` → an accumulator `while_loop` trampoline, the OCaml CPS port;
param-dependent base cases are rejected, not mis-evaluated), `struct_axon` = 12
(**`struct`s → axons**, the OCaml record pattern: the struct def erases to a name
prepass; the struct name maps to `Axon`; `S { x: a, y: b }` constructs a
named-field axon — directly into a `let`, or hoisted to a temp in argument
position; field access `p.x` → `realvec(p.item("x"))`; numeric fields only).

As of 2026-06-13: **imperative `while` loops → substrate `while_loop`** (the
OCaml `_lower_while` shape). A `fn` body of leading `let [mut]` bindings, one or
more `while COND { lhs = rhs; … }` loops, and a bare tail expression lowers to a
hoisted `while_loop` + the `slot`/`loop`/write-back call sequence. The loop's
state is the in-scope names (locals + params) the condition/body touch, threaded
through the loop (the hoisted `while_loop` is top-level and sees only its params,
so params referenced in the loop are threaded read-only); only `mut` locals are
written back. Substrate-verified: `while_sum` = 15 (`let mut acc/i = 0; while i
< n { i = i + 1; acc = acc + i } acc`, `sum_to(5)`). **Loop bounds must use
strict `<` / `>`, not `<=` / `>=`:** at exact equality the substrate comparison
defuzzes false, so a `<=` bound drops the boundary iteration (measured: `<` →
15, `<=` → 10; finding `2026-06-13-while-loop-le-boundary-equality-defuzz`). The
OCaml reference frontend writes all its `while` fixtures with `<` for the same
reason. Rust's unbounded `loop { … break }` (needs a halt-flag transform) is a
later item.

Ownership/borrowing never reaches the lowering at this scope; `&`/borrows,
`loop`/`break`, compound assignment (`+=`), and non-tail/foldable-exempt
recursion surface as `UNSUPPORTED-*` markers (never a silent self-call). A
`match` is supported as a function-body tail; nested in a larger expression it
is a later item.

Dependency: `tree-sitter-rust` (`pip install tree-sitter-rust`).

## Next

`loop { … break }` → substrate loops (halt-flag transform); compound assignment
(`+=`); statement-bearing if-arms; nested / non-tail `match`; nullary-variant
values; struct field-init shorthand / `..base`.
