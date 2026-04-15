# Concurrency

Status: first section of the rebuilt spec. Written strictly from what
the user has stated, not from Claude-invented structure. Gaps are not
filled with plausible defaults — they are pointed at
`planning/open-questions/` and wait for the user to close them.

## User's position

> For concurrency I envision just two or more paths through the
> vector space.
> — user, 2026-04-14

> I don't think concurrency is that hard to do. Because you're
> basically just calculating it for each individual concurrent task.
> And it's just multiple paths throughout the thing. We might want
> to make it so that essentially concurrency involves a splitting
> off path — I wouldn't say a branching path — where if they have
> a common common thing in them, it's done.
> — user, 2026-04-15

Concurrency is a **geometric** concept in Sutra, not a type-theoretic
one. A concurrent program is two or more simultaneous trajectories
through the same embedding space. Earlier framing by the user reached
for monads ("I think that it's essentially monadic in its nature") and
was then replaced by the path framing above. The monad framing is
demoted to "one possible implementation strategy among several" — not
the design target.

### What the 2026-04-15 clarification adds

1. **Splitting, not branching.** Concurrency is a *split* — both paths
   continue simultaneously. "Branching" (as in `if`/`select`) implies
   one side is chosen; "splitting" implies both sides are computed.
   This distinction is load-bearing: concurrency is not a form of
   control flow where paths are discarded. Every spawned path runs.

2. **Per-path independent evaluation.** Each concurrent task is
   "just calculating" — a normal Sutra function body executed
   independently, on its own trajectory. The concurrency layer is
   not redefining what happens inside a path; it is running more
   than one of them.

3. **Convergence on a common thing terminates the computation.**
   Paths that end up with "a common common thing in them" — the
   user's phrasing — are done. Convergence to a shared value is
   the natural termination signal for a concurrent region. Exactly
   what "common thing" means, and what "done" means at the language
   level, is an open question (see below) — but the shape is
   convergence-based, not timeout-based or join-based.

4. **The user considers this tractable.** "I don't think it's that
   hard" — concurrency is not being reached for as a research
   problem; it is expected to fall out of the path/trajectory model
   with modest language machinery. This downgrades the priority of
   heavy abstractions (monads, effect types) in favor of direct
   primitives that express "here are two paths, run them, stop
   when they meet."

## What is committed by this section

1. **Concurrency means multiple paths through the vector space.** A
   concurrent Sutra program has more than one trajectory being
   evaluated at once, in the same embedding space. Each path is the
   same shape as a non-concurrent Sutra program — a sequence of vector
   operations over fuzzy / vector values.

2. **Concurrency is not monads.** The monad framing was considered and
   not adopted. Sutra's `bind` is VSA binding (`a * sign(b)`), not
   monadic bind, and the language's type system does not carry the
   typeclass / `do`-notation machinery that makes monadic effect
   descriptions work in Haskell. Any future concurrency primitive
   chosen (future / promise / parallel block / path construct) must
   not collide with VSA `bind` in name or in documentation.

3. **"Two different timings" is a real use case that concurrency must
   serve.** The user has mentioned slow-substrate vs. fast-control-path
   as one instance. Concurrency in Sutra exists to let a program run
   more than one such timing simultaneously rather than serializing
   them through a single straight-line evaluation.

4. **Concurrency is splitting, not branching.** A split runs both
   paths; a branch selects one and discards the other. Sutra's
   existing branching primitive is `select` (fuzzy weighted
   superposition). Concurrency's primitive, whatever its surface
   form ends up being, must not collapse into `select`.

5. **A convergence on a shared value terminates the concurrent
   region.** When two paths reach "a common common thing," the
   concurrent region is done. What "shared value" means
   operationally — cosine within a threshold? identity of snapped
   codebook entries? some new convergence primitive? — is the
   load-bearing open question that blocks writing the surface
   syntax.

That is the extent of what is committed. Everything below is an open
question.

## Open questions (not filled in here)

Each of these is a concrete gap that the spec deliberately does not
fill. When the user resolves one, it moves into this section and the
open-question entry is removed.

- **Surface syntax.** What does a concurrent program look like in
  source? `parallel { ... } { ... }`? A `path` keyword? A pair of
  functions evaluated under a combinator? Nothing has been decided.
- **Rendezvous.** When two paths need to agree on a final answer, how
  is that agreement expressed? Bundle? Snap against a shared codebook?
  Some new primitive? Not decided.
- **Path identity.** Is a "path" a first-class value in the language
  (can it be passed, stored, returned) or purely a construct of the
  runtime? Not decided.
- **Typing.** Does a concurrent computation have a distinct type from
  a single-path computation, or is concurrency transparent at the
  value level? Not decided.
- **Scheduling / ordering.** The user named "two different timings" as
  the shape. How is the timing difference expressed — by the program,
  by the substrate, by the runtime? Not decided.
- **Failure and partial results.** If one path diverges or never
  terminates, what is the semantics of the whole program? Not decided.

The master open-question document for this topic remains
`planning/open-questions/concurrency-and-monads.md`. Items above are
pointers into it; they are not answered here.

## Why this section is small

The deprecated spec (`planning/sutra-spec-deprecated/`) was large and
wrong. The rule for the rebuild is: write only what the user has said,
in the user's framing. This section is short because the user has said
little. It will grow only as the user expresses positions, not as
Claude fills in plausible defaults.
