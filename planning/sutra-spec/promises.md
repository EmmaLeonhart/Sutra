# Promises and async/await

> **First cut, 2026-05-09.** Per the user's queue.md transpiler note
> from the same day: Promises and async/await get parsed as familiar
> JavaScript-style vocabulary, then beta-reduced into tail-recursive
> eigenrotation loops with axons at the boundary. This document fixes
> the surface syntax, the lowering, and the open questions; the
> implementation tracks against `queue.md` once the design is settled.

## Vision

`async`, `await`, and `Promise<T>` are **first-class Sutra
vocabulary** — not TypeScript imports, not stdlib helpers bolted onto
the side. They're the language's own surface forms, and the desugaring
happens in **two layered stages**:

```
async function   (sugar over)
   ↓
Promise<T>       (sugar over)
   ↓
while_loop with two-channel halt vector  (substrate primitive)
```

**Stage 1: `async` / `await` → `Promise<T>` construction.** An
`async function` body is rewritten so the function returns a
`Promise<T>` value built up from explicit `Promise` construction over
the body's expressions. Each `await` becomes a continuation registered
on the awaited promise's `.then()`. This stage is pure surface
rewriting — no substrate concerns.

**Stage 2: `Promise<T>` → `while_loop`.** A `Promise<T>` value is
itself sugar for a `while_loop` declaration whose halt vector has two
channels (`fulfilled`, `rejected`). The "pending" state is the loop's
eigenrotation actively cycling; the "fulfilled" or "rejected" state
is the corresponding halt channel saturating; the value the promise
will resolve to is the loop's exit-state vector; the input the loop
is waiting on (if any) is an axon connected to the front of the body.

This layering means **standard TypeScript-style code with promises
mostly just runs**. You don't have to translate to Sutra-specific
patterns; the language has the same vocabulary. There's some
adjustment (Sutra's type system is more explicit, the surface is
opinionated about substrate-purity) but the async-shape of programs
is preserved verbatim.

Per CLAUDE.md §"Architecture and Conventions": every Sutra primitive
runs on the substrate. Promises are no exception — the second-stage
lowering bottoms out at a `while_loop`, which already runs on the
substrate. The stage-1 (`async/await` → `Promise`) layer is pure
syntax rewriting at compile time; the stage-2 (`Promise` →
`while_loop`) layer is the substrate-bottom step. Nothing new at the
runtime layer.

## Surface syntax

Three new keywords are reserved at the lexer level: `async`, `await`,
`Promise`. The first two are statement/expression keywords; `Promise`
is a type constructor.

### `async function`

An `async function` declares a Promise-producing function. Its body
may use `await` to gate on incoming axons.

```c
async function Promise<vector> fetch_label(vector query) {
    vector raw   = await network_lookup(query);    // gate on input axon
    vector clean = argmax_cosine(raw, [a, b, c]);
    return clean;                                  // fulfills the promise
}
```

The return type wraps in `Promise<...>`. The `async` modifier on the
function declaration is what enables `await` inside the body — calling
`await` outside an `async` function is a compile-time error (mirrors
JS).

### `await expr`

`await expr` blocks the surrounding async function on `expr`'s
underlying input axon. The expression to the right of `await` must
evaluate to a `Promise<T>`; the result of the `await` is the unwrapped
`T`.

When the awaited promise rejects, the surrounding async function also
rejects (propagation), unless the `await` is wrapped in a `try` block
(see §"Rejection propagation").

### `Promise<T>` type

`Promise<T>` is the type of a not-yet-resolved value of type `T`. It
is parameterised by its eventual resolution type. There is no source-
level constructor — `Promise<T>` values come from calling `async`
functions (or, for low-level programs, from declaring a `while_loop`
whose halt vector has the Promise shape; see §"Lowering").

### `try` / `catch` for promise rejection

```c
async function getOrDefault(vector query) {
    try {
        return await fetch_label(query);
    } catch {
        return default_label;
    }
}
```

`try` / `catch` are already parsed by the Sutra parser but rejected at
codegen (see `control-flow.md`). For async functions specifically, the
catch branch lowers to "if the input promise's rejected channel
saturated, take this value instead." The general non-async `try` /
`catch` remains unimplemented.

## Lowering

Two stages, applied in sequence by the compiler.

### Stage 1: `async` / `await` → explicit `Promise` construction

An `async function` body is rewritten so the function returns a
`Promise<T>` value. Each `await` becomes a chained `.then()` on the
awaited promise; the post-await code becomes the `.then` callback's
body.

This stage is pure surface rewriting: no substrate concerns, no
runtime dependencies, identical to what a JavaScript transpiler
would do to lower `async/await` to `.then()` chains. The output is
still Sutra source; it just no longer mentions `async` or `await`.

Source (stage-1 input):

```c
async function Promise<vector> fetch_label(vector query) {
    vector raw   = await network_lookup(query);
    vector clean = argmax_cosine(raw, [a, b, c]);
    return clean;
}
```

After stage 1 (still Sutra, no `async` / `await`):

```c
function Promise<vector> fetch_label(vector query) {
    return network_lookup(query).then(vector raw -> {
        return Promise.resolve(argmax_cosine(raw, [a, b, c]));
    });
}
```

Multiple awaits chain into nested `.then()`s (or, as an optimiser
pass, fuse into a single multi-callback `Promise.all` shape). A
`try / catch` around an `await` becomes a `.catch()` on the promise
chain. The error / rejection-propagation rules are JavaScript's,
verbatim — that's the point of using JavaScript's vocabulary.

### Stage 2: `Promise<T>` → `while_loop` with two-channel halt

A `Promise<T>` value is itself sugar for a `while_loop` declaration.
Constructing a promise builds a loop; calling `.then()` chains
another loop after the first; resolving / rejecting saturates the
corresponding halt channel.

The lowered shape:

- **State:** the promise's working data (the inputs the body reads,
  the partial result, any captured locals) plus a halt vector with
  two channels (`fulfilled`, `rejected`).
- **Inputs:** an axon carrying any external values the promise is
  waiting on. The body reads from this axon each iteration.
- **Body:** the eigenrotation that checks whether the awaited inputs
  have arrived. When yes, runs the body and saturates `fulfilled`.
  When the input arrives in an error state, saturates `rejected`.
- **Output:** the resolved value plus the two halt channels.

Worked example (carrying the same source through stage 2):

```c
// The promise built in fetch_label's body becomes a while_loop whose
// state is the awaited-input axon plus the result vector.

while_loop fetch_label_body(
    !arrived(in.raw_response) && !in.rejected,
    axon in,
    slot vector result : vector
) {
    // Each iteration: check whether the input arrived. The
    // condition gates re-entry — keep spinning until the input
    // arrives or rejects. When it arrives, the loop exits and the
    // post-iteration code runs.
    pass in, result;
}

function Promise<vector> fetch_label(vector query) {
    axon in   = network_lookup_axon(query);
    slot vector result : vector = zero_vector();
    loop fetch_label_body(in, result);
    // After the loop exits, in.raw_response is populated (or
    // in.rejected is true). Run the post-await code:
    vector clean = argmax_cosine(in.raw_response, [a, b, c]);
    return promise_fulfilled(clean);
    // (or promise_rejected(in.rejection_reason) on the error path)
}
```

A multi-await async function lowers to a sequence of gated loops
(one per await) after stage 1; stage 2 then converts each `Promise`
in the chain to its own `while_loop` declaration. As an optimiser
pass, sequential awaits gating on independent inputs may fuse into
a single multi-channel loop — that's a future optimisation, not a
correctness requirement.

### `await` chaining

```c
async function pipeline(vector q) {
    vector a = await stage_one(q);
    vector b = await stage_two(a);
    return b;
}
```

Lowers to two sequential `while_loop` blocks (one per await), with
the second one's input axon depending on the first's resolved value.
The compiler may fuse these into a single multi-stage loop when both
awaits gate on independent inputs that can be checked in parallel —
that's a future optimisation, not a correctness requirement.

## The three states

| Promise state | Loop state | Substrate semantics |
|---|---|---|
| Pending | Halt vector unsaturated | Eigenrotation cycling, both `fulfilled` and `rejected` channels < 1 |
| Fulfilled | `fulfilled` channel saturated | `fulfilled ≈ 1`, `rejected ≈ 0`; result axon carries the resolved value |
| Rejected | `rejected` channel saturated | `rejected ≈ 1`, `fulfilled ≈ 0`; result axon carries the rejection reason |

The loop's halt mechanism extends the existing one-channel halt scalar
(see `control-flow.md` §"Loops") into a two-channel halt vector. Both
channels live in the synthetic block, no semantic-block contention.
Mutually-exclusive saturation is enforced by the loop body
(`fulfilled = halted * (1 - rejected_flag)`,
`rejected = halted * rejected_flag` — both gated on the underlying
halt scalar).

### Active heartbeat — pending is not silence

Per the queue.md note:

> "The Sutra one does an active heartbeat because, well, that's how
> Sutra works — you literally can't have one that doesn't have an
> active heartbeat."

In JavaScript, `pending` is a passive state — the Promise sits silent
until its callbacks fire. In Sutra, `pending` is active work: the
eigenrotation loop is genuinely cycling at the substrate level, every
tick is an emission. This makes Sutra promises **inherently more
observable** than JS ones — there's no ambiguity between "still
pending" and "silently crashed." If the heartbeat stops, the loop
broke; if it's still emitting, the promise is still alive.

Programs that want explicit heartbeat observation can read the loop's
halt scalar directly (it's a pre-saturation real number ∈ [0, 1] that
indicates "fraction of the way to halting"). Programs that don't care
just `await` and ignore the intermediate state — same as JS.

## I/O at loop boundaries — both ends, both directions

Per the user's 2026-05-09 clarification: an axon at the **front** of a
loop is an input that gates entry; an axon at the **end** of a loop is
an output that emits the resolved value. Both can be present
simultaneously. Either can be reversed: an axon at the front can be an
output (emit "starting" event), and an axon at the end can be an
input (receive a continuation value). All four combinations are
valid.

| Position | Direction | Use case |
|---|---|---|
| Front of loop | Input | Standard `await`: gate body on input arrival |
| End of loop | Output | Standard `return`: emit resolved value |
| Front of loop | Output | "Starting" event: notify subscribers the loop began |
| End of loop | Input | Continuation: receive a downstream value before final exit |

The substrate doesn't distinguish input axons from output axons
mechanically — both are just bound vectors flowing through the
state. The "input" / "output" labels are programmer-facing intent;
the lowering treats them uniformly.

This generality is the reason Sutra unifies Promises, generators,
streams, and observables under a single primitive (the gated loop)
rather than offering each as its own construct.

## Standard library — the controlled vocabulary

`stdlib/promises.su` will declare:

```c
class Promise<T> extends Axon {
    static intrinsic method Promise<T> resolve(T value);
    static intrinsic method Promise<T> reject(T reason);
    method bool isFulfilled();
    method bool isRejected();
    method bool isPending();
    method T value();           // valid only when isFulfilled()
    method T reason();          // valid only when isRejected()
}
```

These intrinsics route through the runtime's existing axon ops; no
new substrate primitives are needed. A `Promise<T>` value is just an
axon with a known field schema.

`Promise.all([p1, p2, p3])` and `Promise.race([p1, p2])` are
combinators that lower to single fused loops with multi-channel input
axons — out of scope for the first cut.

## TS transpiler integration

TypeScript's `async function`, `await`, and `Promise<T>` already
appear in the TS transpiler's input. With this spec landed, the
transpiler can pass them through verbatim instead of erroring on
async syntax:

| TypeScript | Sutra |
|---|---|
| `async function f(): Promise<T> { ... }` | `async function Promise<T> f() { ... }` |
| `await expr` | `await expr` |
| `Promise<T>` | `Promise<T>` |
| `try { await x } catch (e) { ... }` | `try { await x } catch { ... }` (no exception variable yet) |

Postponed JS Promise APIs (`.then()`, `.catch()`, `Promise.all`,
`Promise.race`, `Promise.allSettled`, `setTimeout` returning a
promise) stay deferred until concrete demand drives them.

## Rejection propagation

If an awaited promise rejects and the surrounding async function does
not catch it, the surrounding promise also rejects with the same
reason. Lowered: the loop body checks the awaited input's `rejected`
channel; if set, the surrounding loop's `rejected` channel saturates
and the loop exits without running the post-await code.

`try { await ... } catch { ... }` lowers to: gate the post-await code
on the awaited input's `fulfilled` channel; if `rejected` saturates
instead, run the catch body and saturate the surrounding loop's
`fulfilled` channel with the catch body's value.

There is no exception object — Sutra has no raise/throw primitive
(see `control-flow.md` §"try-catch"). The `catch` block runs
unconditionally on rejection, no exception variable is bound. The
rejection reason from the underlying promise is recoverable via
the promise's `.reason()` method if needed.

## Open questions

These are flagged for follow-up, not decided yet:

1. **Reject-channel encoding.** Two-scalar (`fulfilled`, `rejected`)
   vs one signed scalar (positive = fulfilled, negative = rejected).
   Two-scalar is more decomposable; signed-scalar is denser.
2. **Multi-await fusion.** When and how aggressively to fuse multiple
   sequential awaits into a single loop with a multi-channel input
   axon. Affects compile time and runtime parallelism.
3. **Promise composition with `axon` types.** A `Promise<axon X>` —
   does the wrapping flatten? `Promise<Promise<T>>` should auto-flatten
   to `Promise<T>` (JS semantics), but Sutra doesn't have generics
   in the same way; needs spec.
4. **Cancellation.** JS Promises can't be cancelled mid-flight. Sutra's
   eigenrotation loops genuinely could — set `rejected = 1` from
   outside, the loop exits. Worth offering as an explicit primitive,
   or leave it implicit?
5. **Backpressure / streaming.** A loop that resolves multiple
   outputs over time looks more like a generator than a promise.
   Should `async function*` (JS async generator) be a separate
   construct, or unify with `async function` via "produces an axon
   with multiple write events"?
6. **The exception object.** Sutra has no raise/throw and so no
   exception value to bind in `catch (e)`. JS allows arbitrary
   throw values; Sutra's `catch` currently has no variable. Decide
   whether to expose the awaited promise's `.reason()` as an
   implicit binding inside `catch`.
7. **Top-level await.** JS module-level `await` is allowed. Sutra
   doesn't have modules in the same sense — `main()` is the entry
   point. Either: `main()` can be `async`, or top-level `await` is
   compile-time error pending modules.
