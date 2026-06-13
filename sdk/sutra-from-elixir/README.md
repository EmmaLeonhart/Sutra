# sutra-from-elixir

Elixir → Sutra transpiler frontend (MVP). Models on `sutra-from-ocaml` (the
reference frontend). `lower(source)` turns Elixir source into Sutra source;
fixtures are verified **compile-AND-run on the substrate** (the OCaml harness
bar), not compile-only.

## Status

First cut (2026-06-12): a single `defmodule` whose `def`s lower to top-level
Sutra functions (module-internal calls are bare, so no prefixing needed at this
scope); inline (`, do: expr`) and `do … end` block bodies; integer/float
literals; binary arithmetic/comparison/boolean operators; `if/else` → the
defuzz blend; calls; parens. Elixir is dynamically typed — every value lowers
as Sutra `number`. Substrate-verified: `add_main` (`add(7, 9)`) = 16,
`if_classify` (`classify(5)`) = 100, `tail_rec` (`sum_to(0, 5)`) = 15
(tail-recursive `def f(p…) do if COND do BASE else f(a…) end end` → a declared
`while_loop`, the OCaml/Scala shape). Non-tail recursion surfaces as
`UNSUPPORTED-RECURSION` (never a silent self-call).

Dependency: `tree-sitter-elixir` (`pip install tree-sitter-elixir`).

## Next

The foldable non-tail CPS transform; `case` → defuzz blends; multi-clause `def`
heads (pattern dispatch); maps/structs → axons; pipe operator.
