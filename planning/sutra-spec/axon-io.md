# Axon I/O — how loop bodies query "did the input arrive?"

> **First cut, 2026-05-09.** This is the small spec extension that
> unblocks Stage-2 promise lowering (queue.md item 1, phase 6).
> Per the user's clarification on the same day: the awaited input
> is the **zero vector** until it arrives, then becomes
> not-the-zero-vector. The check on the substrate is just
> `norm(slot) > eps`.

## The three input positions

A Sutra program can receive an external input at any of three
syntactic positions:

1. **Beginning of a program** — top-level axon parameters that the
   Yantra-side loader writes before the program starts executing.
2. **Beginning of a loop body** — the await pattern. The loop's
   eigenrotation cycles until the input slot becomes non-zero.
3. **End of a loop body** — continuation pattern. The loop runs to
   completion internally, then waits for an external value before
   producing the final output.

All three behave identically: the slot starts as the zero vector
and becomes non-zero when the producer writes the value.

## The three output positions

Symmetric to the input positions:

1. **Beginning of a loop body** — "starting" / progress events.
2. **End of a loop body** — the resolved value of an `await`.
3. **End of a program** — the program's overall result, written to
   an axon that whatever invoked the program reads.

Outputs are just axons that something else connects to — there's no
substrate-level mechanism that distinguishes them from inputs other
than the direction of the wire (which is a producer/consumer
declaration the runtime tracks, not a substrate property).

## The "did it arrive?" check

The substrate-pure way to ask whether an input slot has been
populated yet is:

```
arrived = norm(input_slot) > eps
```

Zero magnitude means not arrived; non-zero magnitude means
arrived. There is no separate "is-populated" flag, no out-of-band
metadata, no host-side polling — the *content* of the slot tells
you, on the substrate, in one substrate operation (`norm` is a
tensor reduction), whether the value is there.

When the external producer (a Yantra subsystem, an OS-level
device wrapper, the user input event loop) eventually has the
value, it writes the value into the slot. The slot stops being all
zeros. The loop body's next iteration computes `norm(input_slot)`,
sees a non-zero, and the halt condition flips.

## The all-zeros edge case

A genuine "the value is the zero vector" resolution is ambiguous
under the rule above — the substrate can't tell "the producer hasn't
written yet" apart from "the producer wrote `[0, 0, ..., 0]`."

Two values in the language do legitimately encode as the zero
vector if naively constructed:

- `int 0` — synthetic[AXIS_REAL] = 0, everything else 0 → all zeros
- `trit unknown` — synthetic[AXIS_TRUTH] = 0, everything else 0
  → all zeros

If the producer wants to send one of these as an axon input, it
**adds a flag**: a single non-zero element on a dedicated synthetic
axis that says "this slot has been populated, even if the rest of
it looks like zero." Producer side sets the flag at write time;
consumer side reads `arrived = (norm(slot) > eps) || flag_is_set`.

The flag axis is a dedicated synthetic-axis allocation —
`synthetic[AXIS_AXON_POPULATED]` — added to the canonical layout
alongside `AXIS_PROMISE_FULFILLED` / `AXIS_PROMISE_REJECTED`.
Producers wanting to send a non-zero value can leave this flag
clear (the `norm > eps` check covers them); producers wanting to
send a genuinely-zero value set this flag to `1.0` so the consumer
reads "arrived" correctly.

This is the only piece of producer-side ceremony the rule needs;
in the common case (sending a string, an embedding, a
`make_real(non-zero)`, anything with non-trivial magnitude) the
flag is irrelevant and producers don't touch it.

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
