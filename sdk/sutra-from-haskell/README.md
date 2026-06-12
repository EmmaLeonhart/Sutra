# sutra-from-haskell

Haskell → Sutra transpiler frontend (MVP). Models on `sutra-from-ocaml` (the
reference frontend). `lower(source)` turns Haskell source into Sutra source;
fixtures are verified **compile-AND-run on the substrate** (the OCaml harness
bar), not compile-only.

## Status

First cut (2026-06-12): top-level function equations (`add a b = a + b`) and
zero-arg binds (`main = …`); `signature` declarations supply param/return types
(the arrow chain flattens; Int/Integer → int, Double/Float → number, Bool →
bool); curried application spines flatten to Sutra calls (`add 7 9` →
`add(7, 9)`); infix arithmetic/comparison/boolean operators (`/=` → `!=`);
`if/then/else` → the defuzz blend. Substrate-verified: `add_main` = 16,
`if_classify` = 100. **Laziness is not modeled** — Sutra is strict, and the MVP
scope (total arithmetic programs) is insensitive to evaluation order; programs
relying on laziness are out of scope, stated plainly. Pattern equations, guards,
`where`/`let`, and recursion surface as `UNSUPPORTED-*` markers (recursion until
the tail/CPS transforms are ported — never a silent self-call).

Dependency: `tree-sitter-haskell` (`pip install tree-sitter-haskell`).

## Next

The recursion transforms (tail → `while_loop`, foldable non-tail CPS — port the
Scala/OCaml shapes); pattern equations (multi-clause dispatch → blends); guards;
`where`/`let` bindings; `data` ADTs → tagged axons (the OCaml variant pattern).
