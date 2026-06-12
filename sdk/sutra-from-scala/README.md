# sutra-from-scala

Scala → Sutra transpiler frontend (MVP). Models on `sutra-from-ocaml` (the reference
frontend). `lower(source)` turns Scala source into Sutra source; fixtures are verified
**compile-AND-run on the substrate** (the OCaml harness bar), not compile-only.

## Status

As of 2026-06-12: top-level `def` functions with Int/Double/Boolean/String params +
return types, integer/float literals, infix arithmetic/comparison/boolean ops, function
calls, parenthesized expressions, `if/else` (→ defuzz blend), block `val` bindings,
literal `match` (→ nested defuzz blend), and **case classes → axons** (the OCaml record
pattern: the def erases to a field prepass; construction `Point(a, b)` hoists to
`Axon t; t.add("x", a); …` anywhere in an expression tree; field reads `p.x` →
`realvec(p.item("x"))`). Substrate-verified fixtures (compile AND run): `add_main` = 16,
`if_classify` = 100/200, `val_block` = 17, `match_literal` = 100/200/300,
`case_class` = 12, `tail_rec` = 15 (tail-recursive accumulator shape → declared
`while_loop`, the OCaml `_try_lower_tail_recursive` port; non-tail recursion surfaces
as `UNSUPPORTED-RECURSION`, never a silent self-call).

Dependency: `tree-sitter-scala` (`pip install tree-sitter-scala`).

## Next (roadmap order, todo.md)

Comparison/boolean match guards, `object`/method dispatch, foldable non-tail
recursion (the OCaml CPS/trampoline shape). New constructs model on the OCaml
frontend's verified-running patterns.
