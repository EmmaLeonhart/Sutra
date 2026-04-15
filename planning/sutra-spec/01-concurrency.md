# Concurrency

Status: first section of the rebuilt spec. Written strictly from what
the user has stated, not from Claude-invented structure. Gaps are not
filled with plausible defaults — they are pointed at
`planning/open-questions/` and wait for the user to close them.

## User's position

> For concurrency I envision just two or more paths through the
> vector space.
> — user, 2026-04-14

Concurrency is a **geometric** concept in Sutra, not a type-theoretic
one. A concurrent program is two or more simultaneous trajectories
through the same embedding space. Earlier framing by the user reached
for monads ("I think that it's essentially monadic in its nature") and
was then replaced by the path framing above. The monad framing is
demoted to "one possible implementation strategy among several" — not
the design target.

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
