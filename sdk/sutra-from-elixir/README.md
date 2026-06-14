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
`while_loop`, the OCaml/Scala shape), `nontail_fact` (`fact(5)`) = 120 (foldable
non-tail recursion `LEAF +|* f(REC)` → an accumulator `while_loop` trampoline,
the OCaml CPS port; param-dependent bases rejected). Other non-tail recursion
surfaces as `UNSUPPORTED-RECURSION` (never a silent self-call). `case_literal`
(`classify(2)`) = 200 — literal `case n do 1 -> 100; … _ -> 300 end` → a nested
defuzz blend over `n == k` tests (the shared literal-match shape). `case_bind`
(`classify(6)`) = 60 — a name-binding `case` clause (`x -> x * 10`) binds the
scrutinee to the name (substituted into the result, the `_MATCH_SUBST` shape) as
a catch-all base. `multiclause` (`classify(0) + classify(2)`) = 120 —
**multi-clause `def` heads → one dispatching function**: same-name/arity `def`s
(`def classify(0)`, `def classify(1)`, `def classify(n)`) are grouped by (name,
arity) and lowered to a single Sutra function that dispatches via a nested defuzz
blend (the `case`/`_MATCH` shape lifted to function heads — an integer-literal
param becomes an `(_ai == k)` test, an identifier param binds that name to `_ai`,
the last clause is the base). `classify(0)`=100 exercises literal dispatch,
`classify(2)`=20 the catch-all variable clause (binds `n`→`_a0`, `n * 10`).
Single-clause bare-param defs still route through the recursion-aware path, so
the tail/fold transforms are untouched.

**`when` guards on clause heads**: a guarded head (`def grade(n) when n > 90, do:
…`) lowers its guard to a test ANDed with the clause's pattern tests (the guard
references the params, bound to `_ai` while it is lowered), so the dispatch blend
fires the clause only when pattern + guard hold. Substrate-verified: `guard_clause`
= 150 (`grade(n) when n>90 → 100`, `when n>50 → 50`, `_n → 0`; `grade(95)+grade(70)+
grade(20)` = 100+50+0). A guard on the last clause is treated as the base (its test
is dropped), matching the existing last-clause-is-base rule.

**Pipe operator `|>`**: `x |> f(a, b)` ≡ `f(x, a, b)` — the left value is inserted as
the right call's first argument; `x |> f` ≡ `f(x)`. Chains nest left-to-right
(`5 |> add(3) |> double()` → `double(add(5, 3))`). Substrate-verified: `pipe_chain`
= 16.

Dependency: `tree-sitter-elixir` (`pip install tree-sitter-elixir`).

## Next

Maps/structs → axons; multi-clause heads with recursion (currently
`UNSUPPORTED-RECURSION`); non-comparison guards (`is_integer`, `and`/`or` chains).
