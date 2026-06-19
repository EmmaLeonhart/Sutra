# `.item("key")` works on an Axon variable, not on a call-result expression

**Date:** 2026-06-18
**Status:** measured limitation; orthogonal to the Clojure recursion-axon fix shipped the same day

## What

The Sutra compiler supports the axon field read `v.item("key")` when `v` is an
**Axon-typed variable**, but NOT when the receiver is a **function-call expression**
(or other non-variable expression).

Measured with hand-written Sutra (`codegen_pytorch`, runtime_dim 256):

```
function Axon make() { Axon a; a.add("x", 1); a.add("y", 2); return a; }

// FAILS: TypeError: TensorBase.item() takes no arguments (1 given)
function number main() { return realvec(make().item("x")); }

// WORKS -> 1.0
function number main() { Axon m = make(); return realvec(m.item("x")); }
```

On a call-result the `.item("x")` is dispatched as PyTorch's tensor `.item()` (no
args) rather than the Axon field-read method — the codegen does not treat the result
of a call as Axon-typed for member dispatch, even when the callee's declared return
type is `Axon`. Binding to an `Axon` local first makes the dispatch resolve.

## Why it matters

It affects **every** Axon-returning function whose result is field-read inline,
across all frontends — not anything recursion-specific. The Clojure keyword accessor
`(:k (f args))` lowers to `realvec(f(args).item("k"))` and so hits this; the
`(let [r (f args)] (:k r))` form does too, because the Clojure `let` lowers via
inline substitution rather than a real `Axon r = …;` temp.

The realistic consume-an-Axon-return pattern that DOES work today is passing the
result as an argument to a function that reads fields off its **param** (an Axon
variable): `(sum (f 3))` with `(defn sum [p] (+ (:x p) (:y p)))` → RUN == 3. That is
how the `map_in_recursion` / `vec_in_recursion` Clojure fixtures validate the
recursion-base map/vector hoist.

## Fix options (not done — pre-existing, low priority)

1. **Compiler:** make member dispatch (`.item`/`.add`) honor the static `Axon` type of
   a call expression, or auto-hoist a call receiver to a temp before a field read.
2. **Frontend (Clojure):** lower `(:k expr)` to a real `Axon _t = expr; … _t.item("k")`
   temp when `expr` is not already a bare identifier (and make `let` bind a real temp
   for Axon-typed values instead of `_SUBST` inlining).

Either unblocks inline field reads off call results. Both are out of scope for the
few-cycles recursion-axon edge case; logged here so a later session does not re-derive
the symptom.
