# Sutra → thrml mapping — exploration loop

**Status (Emma 2026-06-13):** "I do not have a massive preconceived notion of how
this works. Focus on trying various ways until we can get our computation to
actually work on this hardware … a giant loop of constantly trying different ways
until it actually works." So this is an **exploration loop**, not a gated design:
try an approach, RUN it on thrml, MEASURE, log it below, iterate. We can change
anything that doesn't work. Direction seed: **vectors → spin-node graph**
(bundle/similarity → factor interactions sampled by block Gibbs). API facts:
`planning/findings/2026-06-13-thrml-api-study.md`.

## Attempt log

- **#1 associative memory — WORKS (2026-06-13).** `experiments/thrml/
  assoc_memory_demo.py`. Sutra value = N-bit spin register; bundle = Hebbian
  couplings `W_ij=(1/N)Σ_μ ξ^μ_i ξ^μ_j` (fully-connected); cleanup = block-Gibbs
  `sample_states`. **Measured (N=16, M=3):** at β=6, **96.8%** of samples within
  overlap ≥0.9 of a stored value vs **0.0%** random baseline (gap 0.968);
  monotone in β (0.5→0.002, 2→0.418, 4→0.884, 6→0.968). Energy convention
  confirmed by measurement (sign +1 = stored values are minima; sign −1 → 0%).
  Single-site blocks (valid Gibbs). → the bundle/cleanup op genuinely computes on
  the thrml substrate.
- **#2 clamped-cue retrieval — WORKS (2026-06-13).** `experiments/thrml/
  clamped_retrieval_demo.py`. The actual *use* of the memory: clamp half a stored
  value's bits (the query), block-Gibbs INFERS the rest. **Measured (N=16, M=3,
  cue=8 bits):** inferred-half per-bit accuracy 0.751/0.868/0.949/**0.992** at
  β=1/2/4/6 vs 0.5 random baseline. Clamping fixes the sign (resolves the
  ±-symmetry of #1). → content-addressable recall (query→answer) computes on the
  substrate.
  **Capacity wall (measured, honest):** at β=6, N=16, recovery is
  1.00 (M≤2) / 0.99 (M=3) / **0.84 (M=4)** / ~0.85–0.89 (M=6,8) — clean up to
  ≈Hopfield capacity (~0.14·N≈2.2 patterns), crosstalk-degraded beyond. Not a
  bug; the known associative-memory limit. Denser codes (a later attempt) would
  push it.
- **#3 bind / unbind — WORKS (2026-06-13).** `experiments/thrml/bind_unbind_demo.py`.
  The transformational op, and the answer to "does it fall out as an energy or need
  a different trick?": **it falls out as an energy — a 3-body factor.** Bipolar VSA
  bind `c = a⊙b` (`c_i=a_i b_i`) is the constraint `a_i b_i c_i = +1`, a 3-body
  interaction — NOT expressible in a pairwise Ising model, but thrml's
  `SpinEBMFactor` takes arbitrary-arity factors (`E = -Σ_k w_k ∏ spins`). A
  positive-weight 3-body factor over `(a_i,b_i,c_i)` enforces bind; **unbind**
  (`b = a⊙c`) falls out of the SAME factor by clamping the other two.
  **Measured (N=16):** bind 0.881/0.979/0.999/**1.000** and unbind
  0.885/0.983/0.999/**1.000** per-bit at β=1/2/4/6 vs 0.5 baseline. Cleaner than
  the memory ops — each bit is an independent constraint, so NO capacity wall.
  → both Sutra op classes now demonstrated on thrml: **memory** (bundle/cleanup/
  retrieval, #1–#2) and **transformational** (bind/unbind, #3).
- next attempts: **arithmetic-as-energy** (add/compare on bit-registers — likely
  needs carry-chain factors); a **composed** pipeline (bind then retrieve); then
  wire a solid pattern into `codegen_thrml`.

## Emma's encoding steer (2026-06-13)

- thrml models computation as **individual memory spaces**; the natural atom is
  that **each spin node = one bit** (a `SpinNode` is ±1).
- A Sutra **memory space = a combination of bits** — i.e. a multi-bit register of
  spin nodes — rather than a continuous-value embedding. (This resolves the
  open "how does a continuous vector component become a discrete spin?" — the
  answer is **bits**, a bit-register encoding.)
- **Bit-width per memory space is open** ("I don't know how many bits it would be
  for any given memory space").

## Interpretation LOCKED (Emma 2026-06-13: "go for your interpretation")

1. **A "memory space" = one whole Sutra value.** One value (a Sutra atom /
   hypervector) ↔ one **register of N spin-node bits**, each bit a `SpinNode`.
2. **Bits are a direct/fixed encoding** of the value (a fixed-point-style
   bit-register), not a learned code, for the first cut. Bit-width N is a
   parameter; small (e.g. 8–16) for the first demos.

## First demonstration (my choice; Emma can redirect)

**Associative memory** — the canonical EBM realization of Sutra's
bundle-as-superposition-memory + cleanup-as-retrieval, and a faithful instance of
"vectors → spin-node graph, bundle/similarity → factor interactions sampled by
block Gibbs":
- A set of stored values = bit-register patterns `{ξ^μ}`.
- **Bundle (build the memory)** → Hebbian couplings `W_ij = Σ_μ ξ^μ_i ξ^μ_j` on a
  fully-connected spin graph (the factor interactions).
- **Cleanup / similarity retrieval** → block-Gibbs `sample_states`: the stored
  patterns are the low-energy modes the sampler concentrates on.
- **Measured** (substrate-honesty bar): fraction of samples within overlap ≥0.9
  of a stored pattern vs a random-spin baseline; the gap is the signal.
See `experiments/thrml/assoc_memory_demo.py`.

## Open specifics (still to settle)

- **Per-op factor forms** for bind / bundle / similarity beyond this first demo,
  and how `sample_states` recovers each op's output.
- **Block partition** keeping each thrml `Block` conditionally independent (the
  first demo uses single-site blocks — valid Gibbs, no parallelism).
- Retrieval **from a clamped partial cue** (vs the unclamped mode-concentration
  the first demo measures).
3. **How each op acts on bit-registers as a factor interaction** (bind / bundle /
   similarity), and how `sample_states` recovers the op's output.
4. **Block partition** that keeps each thrml `Block` conditionally independent
   under that factor topology.

## Non-destructive constraint (carried from queue.md)

The thrml backend is an additive CLI option; it does not touch the PyTorch
pipeline. Nothing here changes that.
