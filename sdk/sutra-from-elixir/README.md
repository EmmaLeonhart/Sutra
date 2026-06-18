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

**Maps → axons** (the Rust-struct / OCaml-record pattern): a map literal `%{x: a, y:
b}` (atom-key shorthand) cannot lower inline — axon construction is statement-shaped
— so it is hoisted to a prelude temp `Axon _ahN; _ahN.add("x", a); …` and the temp
name fills the position where the map appeared (the `_ARG_HOIST` node-id mechanism).
Field read `p.x` (a zero-arg `call` wrapping a `dot`) lowers to
`realvec(p.item("x"))`, and a param read via dot-access types as `Axon` rather than
the default `number`. Substrate-verified: `map_axon` = 13 (`def sum2(p), do: p.x +
p.y`; `sum2(%{x: 5, y: 8})`). A **struct literal `%Name{x: a, y: b}`** also parses as
a `map` (with an extra `struct` child for the nominal type) and lowers to the same
named-field axon — the alias is dropped, since a struct is structurally an axon (the
Rust `struct`-as-axon shape). Substrate-verified: `struct_axon` = 13 (`sum2(%Point{x:
6, y: 7})`). The `%{"k" => v}` arrow form, non-atom keys, and maps in
multi-clause/recursive bodies are later items.

Dependency: `tree-sitter-elixir` (`pip install tree-sitter-elixir`).

## Next

Multi-clause heads with recursion (currently `UNSUPPORTED-RECURSION`); `is_integer`-style
type-test guards (`and`/`or` chains already lower via `_OP_MAP`). (Atom-key maps + struct
literals → axons shipped 2026-06-15. Multi-clause/guarded clause bodies with leading `=`
destructure bindings [`def sel(flag, t) when flag > 0 do {a, b} = t; a + b end`] shipped
2026-06-17. STRING-key arrow-map PATTERN params [`def sum2(%{"x" => a, "y" => b})`] shipped
2026-06-18 — reuse `_map_fields`, which handles both atom-shorthand and string-key forms.
A Bool `case b do true -> … ; false -> … end` dispatches `(b == true)`/`(b == false)`,
shipped 2026-06-18.)
