# Open question: concurrency model, and whether monads are the right frame

Captured 2026-04-14 from a user observation, not yet a design decision.

## What the user said

> I'm thinking that a lot of concurrency will involve two different timings. I think that it's essentially monadic in its nature, or I think monads are a thing to use, but I'm not sure how.

Follow-up, 2026-04-14:

> For concurrency I envision just two or more paths through the vector space.

The follow-up is the load-bearing one. The user's working mental model is geometric, not type-theoretic: concurrency is multiple simultaneous trajectories in the same embedding space, not effectful descriptions to be sequenced by a runtime. Monads were the first frame reached for; "two or more paths" is the frame the user actually wants. This downgrades the monad framing from "likely" to "one possible implementation strategy among several" — and upgrades simpler path/trajectory primitives (parallel branches that eventually rendezvous, futures over vector values) to the default design direction.

## The observation, unpacked

Sutra is purely functional today — every function is a deterministic vector-to-vector map, and the single escape from the pure region is the final name lookup at the program's edge. This is structurally the same property that makes Haskell's IO-free core pure. In Haskell, monads are the machinery that smuggle effects (IO, state, nondeterminism, concurrency) into a pure language without breaking referential transparency: a value of type `IO a` is not an action; it is a *description* of an action that the runtime executes.

If Sutra grows concurrency — "two different timings," e.g. a slow substrate computation and a fast control path, or parallel branches that need to rendezvous on a final answer — the same problem arises: you can't just drop `spawn`/`join`/`await` into a pure function body without inventing an implicit effect layer. The monad framing is a known working solution for that shape of problem. The user is noting that this *might* be the right framing here without committing to it.

## What we currently do

Nothing. The compiler emits straight-line numpy; there is no concurrency primitive, no effect type, no notion of timing. The three demo programs all execute synchronously end-to-end.

## Why the monad framing has force

- It is the textbook answer to "how do I introduce effects into a purely functional language without breaking purity." A well-trodden path.
- It fits the Haskell-shaped comparison the user has already been making about Sutra. Concurrency-as-monad would be consistent with the rest of the language's framing.
- "Two different timings" is exactly the shape of `IO` vs `ST` vs `STM` — different monads for different classes of effect, composable under `do`-notation.
- Monadic bind (`>>=`) would fit cleanly into a language whose primary algebraic operation is already called `bind`. Naming collision is a bug risk but also a point of didactic leverage.

## Why the monad framing might be wrong for Sutra

- Sutra's `bind` is VSA binding (`a * sign(b)`), not monadic bind. Confusing the two in documentation is a real cost.
- Monads in Haskell are a consequence of the type system + typeclasses + `do`-notation. Sutra has no typeclasses and a simpler type system. Importing monads without the surrounding machinery is load-bearing on things the language doesn't have.
- "Two different timings" may be solvable with simpler primitives — e.g. a `future` / `promise` type, or a `parallel { ... } { ... }` construct — that doesn't require the full monad abstraction.
- The user's own correction on hello-world framing ("it's more to do with the program being functional") already pushed back on one monad invocation. The underlying need is purity, not monads specifically.

## What we'd need to decide to close this

1. ~~A concrete use case that forces the issue.~~ **Found 2026-04-22:**
   the MLP-backed Monte Carlo attractor search
   (`examples/_king_queen_mlp_attractor.py`, writeup in
   `planning/findings/2026-04-22-mlp-attractor-king-queen-nomic.md`)
   runs N trajectories through an attractor MLP and collects the
   basin distribution across paths. Currently hand-rolled in Python;
   the language doesn't express it natively yet. See
   `planning/sutra-spec/concurrency.md` §"First concrete use case"
   for how this maps onto the spec's abstract framing.
2. Whether Sutra's type system will grow enough machinery (effect types, typeclasses, or something equivalent) to express monads properly, or whether a simpler primitive-set approach fits better.
3. Whether "bind" as a name can be safely overloaded or whether the concurrency story needs a different word entirely.

## Where this belongs until then

Here. Not in the spec (`planning/sutra-spec/`) — specs should describe what the language *is*, not what it *might become*. Not in CLAUDE.md — that's rules, not speculation. Not in the language paper — the paper should claim what works and say future work is future work. When and if concurrency becomes a real requirement, this doc is the anchor; it moves out (spec update, paper mention, code) rather than sitting here forever.
