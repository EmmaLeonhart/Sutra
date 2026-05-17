# Open question — Cosine as its own transcendental function?

> **VERDICT: GENUINELY OPEN.** Raised by the user 2026-05-17 (voice-vision
> block, preserved verbatim at
> `planning/exploratory/2026-05-17-voice-vision-transcendental-constants.md`).
> It contradicts a currently-shipped design boundary, so it cannot be
> silently kept-as-is *or* silently implemented. Needs a user decision.

## The precise undecided sub-question

The transcendentals as shipped (`ecf1c4cd`/`744ec95e`, then literate
`ae269f6b`/`b9e11f5e`) define:

- `cos(θ) = real(cexp(iθ))`
- `sin(θ) = imag(cexp(iθ))`

i.e. cos/sin are *projections of the complex exponential*, with the
irreducible substrate leaves being `realExp`/`imaginaryExp` (and `ln`).

The user's 2026-05-17 position: **cosine should be its own transcendental
function**, not derived from the algebraic/complex exponential, "because
it's much more complicated when you look at the imaginary output of the
cosine" — and the imaginary output of cosine must be implemented
*geometrically* (substrate-pure), same constraint as tanh.

So the undecided question, in one sentence:

> Does `cos` (and the imaginary part of `cos` for complex arguments) get
> its own dedicated substrate-pure transcendental leaf, or does it stay
> derived from `cexp` via `real(cexp(iθ))` as currently shipped?

## Why each side has force

- **Keep cos = real(cexp(iθ)) (status quo):** fewer irreducible leaves
  (one `cexp` boundary, verified `cexp(iπ)=-1`, `cexp(1+iπ/2)=ie`);
  literate-math chain already green (135 passed / 103 subtests + smoke);
  matches the documented "two lookup leaves" vision.
- **Make cos its own transcendental (user's new position):** the user
  argues the complex-argument imaginary part of cos is structurally
  harder than a projection of cexp and deserves its own geometric
  (substrate-pure) construction; this is the user's clear mathematical
  vision and they reserve the call. Treating it as "already resolved by
  the cexp boundary" would be exactly the
  [[feedback-check-what-is-open-before-pitching-blocker]] failure in
  reverse — declaring a thing closed that the design owner has reopened.

## What would close it

A user ruling on which boundary is canonical, plus — if cos becomes its
own leaf — the substrate-pure construction for `cos` and especially
`imag(cos(z))` for complex `z`, with a ground-truth verification table
(the `21a9ff77` model: tensors in → tensor ops → tensors out, compared to
`cmath.cos`, honest delta reported).

## Status / why this is not being implemented in this autonomous run

This is a design change to a safety-critical substrate boundary. Per
CLAUDE.md ("NO MATH SHORTCUTS", "PEOPLE CAN DIE IF YOU FAKE RESULTS") and
the queue's standing rule that structural substrate work is done
deliberately with a test gate and not as a rushed autonomous edit, it is
recorded here as open and surfaced to the user rather than guessed at.
