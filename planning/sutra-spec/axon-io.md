# Axon I/O — how loop bodies query "did the input arrive?"

> **First cut, 2026-05-09.** This is the small spec extension that
> unblocks Stage-2 promise lowering (queue.md item 1, phase 6).
> Per the user's clarification on the same day: the awaited input
> is the **zero vector** until it arrives, then becomes
> not-the-zero-vector. The loop body's "did the input arrive?"
> check is just "is this axon slot non-zero?"

## The rule

When a Sutra loop body needs to wait for an external input — a
network response, a user keypress, anything the program's own
computation can't produce — the input lives in an **axon slot**
that the loop's enclosing program structure pre-allocated as the
**zero vector**. The substrate-pure way to ask "did the input
arrive yet?" is:

```
arrived = norm(input_slot) > eps
```

That's it. Zero magnitude means not arrived; non-zero magnitude
means arrived. There is no separate "is-populated" flag, no
out-of-band metadata, no host-side polling — the *content* of the
slot tells you, on the substrate, in one substrate operation
(`norm` is a tensor reduction), whether the value is there.

When the external producer (a Yantra subsystem, an OS-level
device wrapper, the user input event loop) eventually has the
value, it writes the value into the slot. The slot stops being all
zeros. The loop body's next iteration computes `norm(input_slot)`,
sees a non-zero, and the halt condition flips.

## Why this works

Three properties that make zero-as-sentinel the right choice for
Sutra specifically:

1. **Substrate-pure.** `norm(v) > eps` is a tensor reduction
   followed by a fuzzy comparison — both are existing substrate
   operations. No host control flow, no scalar extraction inside an
   operation.
2. **No new mechanism.** Loops already have a halt scalar at
   `synthetic[AXIS_LOOP_DONE]`. Awaited-input arrival just feeds
   that halt scalar from `norm(input_slot) > eps` instead of from a
   computation-internal predicate.
3. **The zero vector is already privileged.** It's the additive
   identity for `bundle`; `embed("")` returns it (or close to it);
   `unbind` against an unknown role returns small-magnitude noise
   that's distinguishable from a genuine signal. Treating it as the
   "no value yet" sentinel costs nothing semantically — the values
   programs care about in practice are always non-zero (a real
   embedding, a make_real(...)-tagged number, a make_string(...)
   character array, all have non-trivial magnitude).

## What "arrived" means precisely

`arrived = norm(input_slot) > eps` where `eps` is the same
machine-epsilon-ish constant used elsewhere for divide-by-zero
guards (≈ 1e-7). Not zero exactly — `eps` because:

- A genuine all-zero input is indistinguishable from "not arrived,"
  so the substrate cannot represent the value `[0, 0, ..., 0]` as
  a Promise resolution. This is a real limitation. Programs that
  need to resolve a Promise to "the zero vector" must wrap the
  value in a non-zero tag (e.g., set a synthetic axis to `1`)
  before sending it.
- Floating-point underflow during the producer-side write could
  leave a "near-zero but not exactly zero" residue. `eps` swallows
  that.

The producer side has the corresponding obligation: when writing
to an axon slot, write a value with `norm > eps`. Producers that
genuinely want to send "no value" leave the slot as `zero_vector()`.

## How this composes with the Promise lowering

A Promise's `while_loop` body looks like (sketched, post-Stage-2
lowering):

```
while_loop promise_body(
    norm(in.input_slot) <= eps,    // condition: still pending
    axon in,                        // input slot starts at zero_vector()
    slot vector resolved : vector
) {
    pass in, resolved;
}
```

Each iteration, the substrate computes `norm(in.input_slot) <= eps`.
While true, the loop's halt scalar stays unsaturated → loop spins.
When the producer writes the awaited value, the next iteration's
norm exceeds eps, the halt scalar saturates, and the loop exits
with the value available in `in.input_slot`.

The post-loop code reads `in.input_slot` directly — at that point
the substrate-level promise has resolved to the value sitting in
that slot.

## Producer side — who writes the slot

The Sutra spec stops at the loop body. **Who actually writes the
slot is a Yantra-side question** — the OS layer that wires axons
to external devices, network sockets, user input streams. From the
Sutra program's perspective, the slot is just a vector that
starts at zero and at some point becomes non-zero; the program
doesn't see the producer.

This is the right abstraction boundary because Sutra programs
should be portable across substrates: a program that awaits a
network response on a desktop running Yantra-Linux runs the same
on a Yantra-bare-metal embedded device, just with a different
axon-wiring story below.

## Open questions

1. **Multiple awaits in the same loop.** If a loop body awaits two
   inputs (`await a; await b;`), do we have one input slot per
   await or one combined axon? The Stage-1 desugar pass settles
   this once it can handle multi-await chains (queue.md phase 3+,
   blocked on first-class function values).
2. **Rejection-channel writing.** When the producer wants to
   *reject* (signal an error), does it write a non-zero value to a
   separate `error_slot` axon field, or does it set a synthetic-
   axis flag on the same `input_slot`? The current Stage-2 design
   in `promises.md` has a separate `rejected` halt channel — so the
   producer signals rejection by writing to a second slot. Spec
   needs to land which.
3. **Cancellation from outside.** A long-pending loop could be
   cancelled by an external write that sets the rejection slot. Is
   that a first-class operation or implicit?
4. **Heartbeat observability.** The pending loop's eigenrotation is
   actively cycling — programs (or Yantra) can read the loop's
   intermediate state to see "is this still alive?" Spec for the
   read shape is open.
