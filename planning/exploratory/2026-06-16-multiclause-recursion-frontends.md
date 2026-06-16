# Multi-clause recursion in the language frontends — design + breakdown

**Date:** 2026-06-16
**Status:** analysis / not-yet-implemented (the data-structure tier is done; this is the
next transpiler increment, deferred from the aggressive sprint because it refactors the
*working* recursion transforms and so wants careful verification, not a rushed tick).
**Frontends affected:** `sutra-from-erlang`, `sutra-from-elixir`, `sutra-from-haskell`
(all three currently emit `UNSUPPORTED-RECURSION` for the idiomatic pattern-matched
recursive form). Rust/F#/Scala/OCaml/Clojure express recursion via `if`/`cond`, already
handled.

## The unsupported pattern

The idiomatic base-case-by-pattern recursive function, e.g. Erlang:

```erlang
fac(0) -> 1;
fac(N) -> N * fac(N - 1).
```

is *semantically identical* to the single-clause `if` form the frontends already lower:

```erlang
fac(N) -> if N == 0 -> 1; true -> N * fac(N - 1) end.
```

So the work is a **clause→conditional synthesis**, then reuse of the existing recursion
transforms — NOT a new recursion engine.

## Why it isn't a one-line change

The existing transforms (`_try_lower_tail_recursive`, `_try_lower_foldable_nontail`) take
the branch condition as an **AST node** `cond` and use it in exactly two ways:
`_lower_expr(cond)` (the test source) and `_negate_cond(cond)` (the negated test source).
A multi-clause function has no `if`-cond node to hand them — the dispatch lives in the
clause *patterns* (`fac(0)` vs `fac(N)`). We cannot synthesize a tree-sitter node, so the
transforms must be fed the test *source strings* instead.

## Proposed implementation (per frontend, Erlang first)

1. **Refactor the two transforms to take `cond_src: str` + `neg_src: str`** instead of the
   `cond` node. Inside, replace `_lower_expr(cond, src)` → `cond_src` and
   `_negate_cond(cond, src)` → `neg_src`. Everything else (the `while_loop` emission,
   `_self_call_args`, the fold detection) is unchanged.
2. **Update the existing bare-`if` call site** (`_lower_function`) to compute
   `cond_src = _lower_expr(cond, src)` and `neg_src = _negate_cond(cond, src)` from the
   if-cond node *before* calling — preserving today's behaviour exactly.
3. **Add a multi-clause-recursion path** (in/around `_lower_dispatch`, before the
   `UNSUPPORTED-RECURSION` bail): detect the shape
   - exactly 2 clauses (generalize to N literal-base clauses + 1 var clause later),
   - clause A: a single **integer-literal** param pattern `K`, body = base (no self-call),
   - clause B: a single **var** param pattern `V`, body = rec (contains the self-call);
   then synthesize `cond_src = "(V == K)"`, `neg_src = "(V != K)"`, `params = [V]`,
   `then_e = baseBody`, `else_e = recBody`, and call
   `_try_lower_tail_recursive` / `_try_lower_foldable_nontail`. (The var clause's name `V`
   becomes the canonical param; the base body usually doesn't reference the param.)

## Verification (the reason this is careful, not rushed)

- The refactor touches the recursion path that `tail_rec` and `nontail_fact` fixtures
  exercise. **Both must still pass on the substrate after step 1–2**, before adding step 3.
- New fixtures (compile-AND-run): a multi-clause `fac(0)/fac(N)` (→ 120) and a multi-clause
  tail accumulator (→ a known sum). Run on the real substrate, compare to ground truth.
- The boundary-equality caveat applies: the base test is `==` on a literal, which is crisp
  for non-zero literals; for `K == 0` confirm crispness (cf. the 2026-06-16 tag-0 finding —
  a literal *parameter* compared to 0 was measured crisp in the Haskell/Clojure case
  fixtures, unlike an axon-item read, so `(V == 0)` here should be fine, but MEASURE it).

## Scope notes

- Start with **2-clause, single-arity, integer-literal base**. Generalize to N base
  clauses (nested) and multi-arity afterward.
- Guards on the recursive clause (`when`) compose with the synthesized cond (AND them in).
- Elixir and Haskell get the same treatment once Erlang is proven; their transforms have
  the same node-based `cond` shape.
