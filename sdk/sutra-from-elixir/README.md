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
`if_classify` (`classify(5)`) = 100. Recursion is detected and surfaces as
`UNSUPPORTED-RECURSION` until the tail/CPS transforms are ported (never a
silent self-call).

Dependency: `tree-sitter-elixir` (`pip install tree-sitter-elixir`).

## Next

Tail recursion → `while_loop` + the foldable non-tail CPS transform (port the
Scala/OCaml shapes — recursion IS iteration in Elixir, so this is the
load-bearing increment); `case` → defuzz blends; multi-clause `def` heads
(pattern dispatch); maps/structs → axons; pipe operator.
