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
- next: retrieval from a *clamped partial cue*; bind/unbind; arithmetic-as-energy;
  then wire the working pattern into `codegen_thrml`.

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
