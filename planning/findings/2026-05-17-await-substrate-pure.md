# 2026-05-17 — `await` is substrate-pure (Audit REAL LEAK #3 fixed)

**What.** `Promise.await_value` (the runtime every `await x` lowers
to, via `promise_desugar` → `Promise.await_value(x)`) was a host
Python bounded poll loop with a host branch on the pending
predicate. That is the forbidden host-control-flow-on-a-value
pattern and it was on the live `await` path. Fixed on both backends.

**The fix is the exact reduction of the spec, not a workaround.**
`planning/sutra-spec/promises.md` Stage 2: a `Promise<T>` is a
`while_loop` with a two-channel halt vector (`fulfilled`,
`rejected`) fed by an input axon; `await` is that loop's terminal
value read. Emma's model — "await is just a loop with a bare-minimal
implicit axon (one mutable input slot + a flag)" — is precisely
that Stage-2 shape.

In the current runtime there is **no external axon producer**: the
halt channels are set only by `resolve` / `reject` at construction
(synchronous). Nothing mutates the promise vector `p` between loop
ticks. So:

```
while_loop spin(isPending(p), slot p) { pass p; }   // empty body
```

yields `p` unchanged every tick and terminates with `p` at its
initial value. Its terminal read is therefore **exactly**
`value(p)`, algebraically, for every input (resolved or pending) —
not an approximation, the literal reduction of the spec-2 loop in
the no-producer case. So:

```
def await_value(self, p):
    return self.value(p)
```

`value(p)` is pure tensor ops (clone + zero the two flag axes); no
host scalar, no branch, no loop.

**Why not build the gating loop now?** A substrate `while_loop`
that gates on an arrival flag *nothing ever sets* in the current
runtime would be a no-op added only to look like the model — the
exact kind of theatrical mechanism the safety culture forbids. The
frank move is the correct reduction now, and the real gating loop
when Yantra wires an external axon producer (promises.md Stage 2 /
axon-io.md). Flagged as a tracked future, not faked.

**Verification (measured, both backends).** Emitted runtime: 0
`for _ in range(100)`, 0 `if self.isPending` (the prior leak
signatures, gone). `tests/corpus/valid/async_promise_runtime.su`
(which exercises `await immediate()` + `await g(v1)` through
`chained()`): `main()` = 3.0 on both torch and numpy — semantics
preserved exactly. New `tests/test_await_substrate_pure.py` (4
tests: no-leak + semantics, both backends). Full gate: 227 passed
/ 83 subtests, `examples/_smoke_test.py` PASS, zero regression.
Docstrings phrased without the literal old signature so the
`substrate_leak_sweep` CI gate does not false-positive on the
explanatory text (caught during this work — the first docstring
draft reproduced the grep-able pattern).

**Separate observation, recorded not silently expanded.**
`isPending` / `isFulfilled` / `isRejected` still read the promise
axes via host `float()` and return host scalars. They are surface
`Promise.is*` accessors; after this fix none is on the `await`
runtime-op path. Whether a `Promise.isPending` used *inside a Sutra
expression* must be substrate-pure is its own predicate-accessor
question — logged in `Audit.md` #3 as an observation, not folded
into the #3 fix.

Revert point if a later issue surfaces: tag `v0.5.0` (`84b5ca45`).
