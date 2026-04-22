# Concurrency

Status: first section of the rebuilt spec. Written strictly from what
the user has stated, not from Claude-invented structure. Open questions
stay inline in this file — the spec can have open questions.

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

## Concurrency is implicit by default (2026-04-22)

Revised user position, 2026-04-22:

> We already have concurrency implicitly anyways, so my view is that
> since I already implicitly implemented concurrency, an explicit
> implementation is only needed if something goes wrong.
>
> Eventually the compiler just will do concurrency, a lot of
> concurrency stuff is just working via formula simplification.

**Implicit-by-default is the spec's direction.** Sutra's functional
algebraic nature gives the compiler license to evaluate independent
sub-expressions in parallel without any programmer-visible syntax.
`bundle(bind(r1, f1), bind(r2, f2))` has two independent binds; the
runtime evaluates them in parallel. `argmax_cosine(v, [c1, c2, c3])`
is N independent cosines; evaluated in parallel. These are algebraic
properties of a pure vector-space language, not concurrency features
added on top. "Formula simplification" is the mechanism — the
compiler rewrites expressions into forms that expose parallel
opportunities.

An earlier version of this section (2026-04-22 morning) committed
to explicit fork-join syntax as the *primary* mode ("explicit fork
syntax right now... for development do it explicitly"). That
framing was revised the same afternoon: implicit is primary,
explicit is a fallback / override for cases where the compiler's
automatic analysis can't figure out the parallelism or the
programmer wants it visibly forced.

### What stays explicit (2026-04-22 afternoon narrowing)

User direction: *"the only concurrencies that need to be explicit
that I can think of now"* are two shapes. The earlier draft of this
section listed more candidates (forced-parallelism-for-tuning,
convergence-terminated splits); those are demoted to "parked, no
user position yet" — they're not blocking anything the language
needs to express today.

The two shapes the explicit mode must cover:

1. **Concurrent looping.** `loop` today is a single trajectory —
   `loop[N]` unrolls at compile time to a bounded iteration,
   `loop(cond)` iterates on the substrate until a data-dependent
   termination. A concurrent form would run N independent
   trajectories in parallel, collecting results into an indexed
   structure. This is not algebraically derivable from the
   straight-line `loop` expression; the compiler has no reason to
   split a single loop into N parallel loops unless the programmer
   says so. Surface syntax TBD (probably an extension of `loop`
   rather than a new keyword, matching the "explicit only when
   needed" framing).

2. **MLP attractor search.** N independent trajectories through a
   trained attractor function, starting from `v0 + noise[i]`, each
   iterated until convergence to a fixed point, collected as a
   basin distribution. This is the concrete use case driving the
   whole concurrency design (see §"First concrete use case"
   below). The mechanism is currently hand-rolled in Python
   (`examples/_king_queen_mlp_attractor.py`); native Sutra support
   for this shape is the benchmark the concurrency primitive has to
   meet.

Everything not in those two shapes is expected to come out of the
compiler's algebraic simplification without new syntax. If another
shape turns out to need explicit handling later, it joins the list;
the list is closed-by-design to what has a concrete use case, not
open-by-default for plausible future needs.

## Open questions

The spec can have open questions inline. These are concrete gaps we
are working out — not filled with defaults.

- **Explicit-mode surface syntax.** When the programmer does need
  to force parallelism (Monte Carlo trials, convergence-terminated
  splits), what does the keyword / construct look like? Still open
  within the explicit-fork-join family.
- **Convergence test.** A split ends when paths agree on "a common
  thing." What is that operationally? Cosine similarity above a
  threshold? `snap` to the same codebook entry? Bit-identical value?
  Not decided.
- **Result of the region.** When the explicit concurrent region
  finishes, what does it return? **User direction 2026-04-22 (weak,
  partial):** *rotation-bound array*. Each path's result lands in
  an indexed slot of a `var[N] slots : vector` array — the same
  rotation-binding slot machinery from the role/var declaration
  syntax. Merge is "collect into an ordered N-slot structure,"
  not "combine into a single vector." The MLP attractor MC's
  histogram-over-attractors result fits this shape: N paths, N
  slots, each slot holds the attractor that path landed in. User
  flagged this as provisional ("might be more stuff to do at some
  point") — other shapes (single-vector merges, first-arrival
  returns) are deferred rather than rejected.
- **Path identity.** Is a "path" a first-class value (passable,
  storable, returnable) or purely a runtime construct? Not decided.
- **Typing.** Does a concurrent computation have a distinct type from
  a single-path computation, or is concurrency transparent at the
  value level? Not decided.
- **Scheduling / ordering.** The user named "two different timings"
  as the shape. How is the timing difference expressed — by the
  program, by the substrate, by the runtime? Not decided.
- **Failure and partial results.** If one path diverges or never
  terminates, what is the semantics of the whole program? Not decided.

The spec-wide index of open questions (across all sections, not just
this one) lives at `planning/sutra-spec/open-questions.md`.

## Prior art surveyed 2026-04-15

Mainstream concurrency primitives the user compared against, with
what each maps to:

- **Go goroutines + channels** — split via `go`, rendezvous via
  receiving from a shared channel. Both paths must complete; no
  convergence-on-value.
- **Haskell `async` + `STM`** — `waitBoth` joins both paths;
  `retry`-based STM can approximate "commit when paths agree."
- **JS `Promise.all` / `Promise.race`** — `all` waits for both,
  `race` takes the first. Purely time-based, no agreement check.
- **Erlang actors** — isolated processes, mailbox rendezvous.

None of these has "terminate when paths converge on a common value"
as the primary termination rule. That piece would be Sutra-specific.
A sketch in that shape:

```
split {
    path a: slow_reasoning(query)
    path b: fast_heuristic(query)
} until similar(a, b, threshold=0.9)
```

Not adopted — parked here as a candidate while the convergence-test
and result-of-region questions are still open.

## First concrete use case — MLP attractor search (2026-04-22)

The abstract framing above ("multiple paths through the vector
space, converging on a common thing") was drafted 2026-04-14/15
without a program that required it — the earlier `concurrency-and-
monads.md` open-question doc explicitly flagged "a concrete use
case that forces the issue" as a prerequisite to closing this
section. As of 2026-04-22, we have one.

The **MLP-backed Monte Carlo attractor search**
(`examples/_king_queen_mlp_attractor.py`, writeup in
`planning/findings/2026-04-22-mlp-attractor-king-queen-nomic.md`)
is the first real instance of the shape this section describes:

- **N trajectories starting from `v0 + noise[i]` for i in 1..N** are
  N *paths through the vector space*, in the exact geometric sense
  committed above.
- **Each path iterates `x ← f(x)` under the same trained MLP**
  independently. No shared mutable state, no cross-path
  coordination — the concurrency is in the multiplicity of paths,
  not in communication between them.
- **Each path terminates when it reaches a fixed point**
  (`||f(x) - x|| < ε`, or equivalently when the snap to the nearest
  codebook entry stabilizes). Different paths terminate at
  different iterations and converge on *different* attractors,
  depending on basin geometry at the starting point.
- **The result of the region is the basin distribution** — a
  histogram over which attractor each path landed in. Not "the
  shared vector" (paths typically do NOT converge on the same
  attractor), not "the first arrival" (all paths are counted).

This is currently hand-rolled in Python — the language does not
express it natively yet. When Sutra gets a concurrency surface
primitive, this use case is the concrete benchmark: the primitive
must be expressive enough to write the MLP attractor MC as a
native Sutra program, not as Python around a compiled fragment.

The open questions above get sharper when read against this case:

- **Convergence test.** For attractors the natural rule is
  `||f(x) - x|| < ε` (fixed-point reached) or `snap(x)` stable
  across k iterations. Either fits the "paths reach a common
  thing" framing; the "common thing" is a codebook attractor rather
  than an identical value.
- **Result of the region.** For attractor MC, the result is the
  *set/histogram* of attractors hit across paths. Not the shared
  vector the 2026-04-14/15 framing imagined. This is worth
  reconciling: "convergence on a common thing" at the path level
  can coexist with "distribution over common things" at the
  region level — each path converges to one attractor, the region
  collects which attractor each path picked.
- **Path identity.** For MC, paths are indexed by trial. Not
  first-class values; transient. This specific use case does not
  need paths to be passable / storable / returnable, which
  downgrades that open question for attractor-style concurrency
  (it may still matter for other shapes).

Nothing above is adopted as a design commitment — this is a
pointer from the abstract framing to a concrete program, to make
sure the two line up before the surface syntax is picked. The
2026-04-22 `_king_queen_mlp_attractor.py` and its findings doc
are the source of truth for what the mechanism actually does.

## Why this section is small

The deprecated spec (`planning/sutra-spec-deprecated/`) was large and
wrong. The rule for the rebuild is: write only what the user has said,
in the user's framing. This section is short because the user has said
little. It will grow only as the user expresses positions, not as
Claude fills in plausible defaults.
