# Substrate tag-equality is degenerate at 0 — bind the tag to an int local first

**Date:** 2026-06-16
**Context:** F# discriminated-union → tagged-axon lowering (`sdk/sutra-from-fsharp`),
shared by the Haskell/Rust/Elixir variant frontends.

## What happened

A DU variant dispatch lowered as an **inline** tag comparison

```
(realvec(s.item("_tag")) == 0)        // tag of the FIRST variant is 0
```

gave the **50/50 defuzz blend** of the two arms, not the matched arm. Measured: a
`Circle`(tag 0) / `Square`(tag 1) shape with `area (Circle 4)` expected `4*4*3 = 48`
returned **32 = (48 + 16) / 2** — i.e. the `== 0` test returned truth ≈ 0, not 1.

Minimal substrate repro (two-arm blend on a tag-0 axon, inline `realvec(...)==0`):
returned `32`. The same program with the tag bound to an `int` local first —

```
int t = realvec(a.item("_tag"));
(t == 0)
```

returned **48** (crisp). So the int-local round-trip is the fix.

## Why

Equality on the substrate is cosine-flavoured; a **zero-valued** real filler read
straight out of an axon item (`realvec(item)`) is a degenerate vector for that
comparison, so `== 0` is not crisp **at the value 0**. Binding through an `int` local
(`int t = realvec(...)`) normalizes the value so `t == 0` is crisp. Non-zero tags
(1, 2, …) compared inline were already fine — which is why the issue only shows up for
the **first** variant (tag 0) when it is *tested* rather than used as the match base.

This is why the working Haskell frontend already binds `int _vtag = realvec(scrut.item("_tag"))`
before `(_vtag == k)`: its `data_adt` fixture passes for exactly this reason, not by luck.

## Action taken

F# variant `match` now emits `int _vtag{N} = realvec(s.item("_tag"));` to the function
prelude and tests `(_vtag{N} == k)` (commit landing with the F# DU increment). Fixture
`union_axon` → 48 on the substrate.

## Caveat for other frontends

Any frontend that compares a value read from an axon (or any substrate scalar) against
**0** *inline* risks the same degeneracy — including const/literal `match`/`case` arms
that test `== 0` (e.g. a hypothetical `case n of 0 -> …` where `n` is itself a
near-zero filler). The Haskell/Clojure literal-case fixtures happen to pass because
their `== 0` operand is a function **parameter** value, not an axon-item read. **Rule of
thumb:** compare an axon-item read or a possibly-zero substrate scalar against 0 only
after binding it to an `int`/`real` local. Audit the Rust enum dispatch
(`_lower_match_stmts`) — it already binds `_vtag` to a local, so it is fine; this note
is a guard against future inline-equality regressions.
