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
`if_classify` = 100, `tail_rec` = 15 (tail-recursive `f p… = if COND then BASE
else f a…` → a declared `while_loop`, the OCaml/Scala shape), `nontail_fact`
= 120 (foldable non-tail recursion `LEAF +|* f REC` → an accumulator `while_loop`
trampoline, the OCaml CPS port; param-dependent base cases rejected). **Laziness
is not modeled** — Sutra is strict, and the MVP
scope (total arithmetic programs) is insensitive to evaluation order; programs
relying on laziness are out of scope, stated plainly.

As of 2026-06-13: **pattern equations + guards → dispatch blends.** Same-name/
arity equations (`classify 0 = 100`, `classify 1 = 200`, `classify n = n * 10`)
group by (name, arity) into ONE dispatching function — an integer-literal
pattern becomes an `(_ai == k)` test, a variable pattern binds that name to the
canonical arg `_ai` (`_SUBST`), the last equation is the base (the Elixir multi-
clause shape ported). A **guarded** equation (`classify n | n == 0 = … | n == 1
= … | otherwise = …`) lowers its `match`/`guards` clauses to the same nested
blend, guards as the tests and `otherwise` as the base; its params are real
Sutra params, so guards reference them directly. Substrate-verified: `pattern_eq`
= 120 (`classify 0 + classify 2`, literal dispatch + catch-all bind),
`guards` = 120 (same via guard conditions). Single-equation functions still route
through the recursion-aware path, so the tail/fold transforms are untouched.

`where`/`let` bindings, `data` ADTs, and multi-equation/guarded **recursion**
surface as `UNSUPPORTED-*` markers (recursion until the relevant transforms are
ported — never a silent self-call).

Dependency: `tree-sitter-haskell` (`pip install tree-sitter-haskell`).

## Next

`where`/`let` bindings; `data` ADTs → tagged axons (the OCaml variant pattern);
guarded/multi-equation recursion; non-integer literal patterns.
