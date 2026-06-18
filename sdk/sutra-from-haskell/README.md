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

As of 2026-06-14: **`where` clauses and `let … in` → substitution.** Both surface
as a `local_binds` group of `bind`s; each binding's value is lowered (with the
earlier binds active) and substituted for its name (the OCaml `let..in` / Clojure
`let` shape, via `_SUBST`; numbers, so re-evaluation is side-effect-free). `where`
binds wrap the whole equation and are cleaned up so they do not leak to sibling
declarations; they reference params by their source names directly. Substrate-
verified: `where_block` = 31 (`f x = y + z where y = x+1; z = x*2`; `f 10`),
`let_block` = 18 (`g x = let a = x+1; b = a*2 in a + b`; `g 5` — `b` sees `a`).
Mutually-recursive / forward bindings are a later item.

**`data` ADTs → tagged axons** (the OCaml/Rust variant pattern). A `data T = C1 a
| C2 b | …` prepass registers each constructor as a variant `(T, tag, arity)` and
`T` as an ADT type (which maps to `Axon` in signatures). A value construction `C
arg…` is statement-shaped (axon build), so it is hoisted to a prelude temp `Axon
_ahN; _ahN.add("_tag", tag); _ahN.add("_val0", arg); …` (the `_ARG_HOIST` node-id
mechanism). A `case scrut of (C x) -> r; …` at the function tail binds `int _vtag =
realvec(scrut.item("_tag"))` and `int _val{i} = realvec(scrut.item("_val{i}"))` to
clean number-vector locals, then a nested defuzz blend tests `_vtag == tag`;
payload names substitute to the `_val{i}` locals (the last constructor arm, or a
bare-variable/`_` pattern, is the base). Substrate-verified: `data_adt` = 2
(`data Expr = Lit Int | Neg Int`; `evalE` via `case`; `evalE (Lit 7) + evalE (Neg
5)` = 7 + (−5)). A LITERAL `case` in NON-TAIL expression position (`1 + (case n of
0 -> 100; _ -> 200)`) inlines as a nested blend (`case_nontail` = 101, shipped
2026-06-17). Non-variable case scrutinees, nested payload patterns, and a VARIANT
`case` in expression position (needs an int-local) are later items.

Multi-equation/guarded **recursion** surfaces as `UNSUPPORTED-*` markers (until
the relevant transforms are ported — never a silent self-call).

Dependency: `tree-sitter-haskell` (`pip install tree-sitter-haskell`).

## Next

Guarded/multi-equation recursion; mutually-recursive `where`/`let` bindings. (`data`
ADTs → tagged
axons shipped 2026-06-15. A LITERAL `case` in non-tail position [`1 + (case n of
0 -> 100; _ -> 200)`], NESTED tuple `let` patterns [`let (a, (b, c)) = t`], and NESTED
CONSTRUCTOR `let` patterns [`let (Outer (Inner a b) c) = w`], and NESTED CONSTRUCTOR
`case` patterns [`case w of Outer (Inner a b) c -> …`] shipped 2026-06-17/18 — each via
an `Axon` temp per non-leaf prefix (a per-equation destructure prelude / the case prelude).
MIXED tuple/ctor `let` nesting [`let (a, Box b) = t`, `let (Wrap (a, b)) = w`] shipped
2026-06-18 — the tuple- and ctor-path collectors cross-call; `ctor_in_tuple` runs at
runtime_dim 128 because its `_1`/`_val0` key mix cross-talks at the default dim 50.)
