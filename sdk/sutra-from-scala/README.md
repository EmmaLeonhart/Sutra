# sutra-from-scala

Scala → Sutra transpiler frontend (MVP). Models on `sutra-from-ocaml` (the reference
frontend). `lower(source)` turns Scala source into Sutra source; fixtures are verified
**compile-AND-run on the substrate** (the OCaml harness bar), not compile-only.

## Status

First cut (2026-06-12): top-level `def` functions with Int/Double/Boolean/String
params + return types, integer/float literals, infix arithmetic/comparison/boolean ops,
function calls, parenthesized expressions. Substrate-verified: `add_main`
(`def add(a,b)=a+b; def main()=add(7,9)`) runs to 16.

Dependency: `tree-sitter-scala` (`pip install tree-sitter-scala`).

## Next (roadmap order, todo.md)

`if/else` (→ Sutra defuzz blend), `val` bindings, `match` (→ tagged-axon / blend),
case classes (→ axons, like OCaml records/variants), `object`/method dispatch, tail
recursion (→ `while_loop`, reuse the OCaml shape). New constructs model on the OCaml
frontend's verified-running patterns.
