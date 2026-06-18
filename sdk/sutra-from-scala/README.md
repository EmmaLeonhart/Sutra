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
`while_loop`, the OCaml `_try_lower_tail_recursive` port; non-tail recursion outside
the supported shapes surfaces as `UNSUPPORTED-RECURSION`, never a silent self-call),
`match_guard` = 60 (guards `case x if x > 0 => …` AND-combine with the pattern test;
name-binding patterns substitute the bound name to the scrutinee, the OCaml
`_MATCH_SUBST` shape), `nontail_fact` = 120 (foldable non-tail recursion
`LEAF +|* f(REC)` → accumulator `while_loop` trampoline, the OCaml CPS port — with a
stricter guard rejecting param-dependent base cases, which the transform would
mis-evaluate).

`object_dispatch` = 26 (singleton `object`s lower as namespaces: `object Calc`
methods emit as top-level `Calc_add(…)` functions; `Calc.add(7, 9)` call sites and
bare sibling calls inside the object rewrite to the prefixed names).

Dependency: `tree-sitter-scala` (`pip install tree-sitter-scala`).

## Next

The named roadmap set is complete. Further breadth (closures, generics, traits,
instance classes, String operations) models on the OCaml frontend's
verified-running patterns as needs arise. (NESTED tuple destructure [at
`runtime_dim ≥ 100` — finding 2026-06-17] and case-class MATCH patterns
[`case Point(a, b) => …` → positional `realvec(scrut.item("x"))`] shipped 2026-06-17;
NESTED case-class `val` patterns [`val Outer(Inner(a, b), c) = o` → an `Axon` temp per
non-leaf prefix over declared field names] + a Bool `match { case true => …; case false
=> … }` [`(b == true)`/`(b == false)`] shipped 2026-06-18; multi-variant case-class match
needing `_tag` tests is a later item.)
