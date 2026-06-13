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
- **#4 integer addition (ripple-carry) — PARTIAL (2026-06-13).** `experiments/
  thrml/adder_demo.py`. The first attempt that does NOT cleanly work — and the
  most informative. n-bit adder as spin factors, ALL correct: sum bit = 4-body
  parity factor (`a⊕b⊕c⊕s=0` ⟺ `∏σ=+1`); carry = MAJ(a,b,c) = sign(σ-sum) for 3
  spins, so three **pairwise** factors `−J σ_cout(σ_a+σ_b+σ_c)`. The ground state
  IS the correct sum. **Measured (4-bit, 30 random pairs):** exact-sum
  0.80/0.77/0.70/0.667 at β=1.5/2/6/8 vs **0.031 chance** — well above chance, so
  addition genuinely computes, but NOT reliable. **Accuracy DROPS as β rises** —
  the signature of single-site block-Gibbs **freezing into local minima** on the
  carry chain before it relaxes to the global min. **Lesson:** ops with long
  *sequential dependency chains* (carry propagation) don't reliably relax under
  naive Gibbs, unlike per-bit-independent ops (bind #3 = 100%) and shallow memory
  ops (#1–2). Fixes to try next: **annealing** (β schedule), **carry-chain-aware
  blocking**, or a **carry-lookahead** encoding (shorter dependency depth).
- **#4b adder diagnosis (2026-06-13).** Added `best-of-S` and a `min-energy`
  decode to `adder_demo.py`. **Key finding: best-of-S = 1.000** (4- and 6-bit) —
  the correct sum is among the drawn samples in EVERY trial, so it is a
  *concentration/decode* problem, NOT *reachability*; the substrate does reach the
  answer. BUT a `min-energy` decode (rank samples by the adder Hamiltonian, return
  the lowest) did **worse** than modal: 0.75 vs 0.85 (4-bit), 0.50 vs 0.60
  (6-bit). Since the energy formula matches the factors built, this means the
  arithmetically-correct assignment is a heavily-sampled low-energy state but NOT
  the strict global min — the classic **Ising/QUBO penalty-weighting** problem
  (uniform J lets spurious states sit at/below the answer). Also: concentration
  degrades with width (modal 0.85 @4-bit → 0.60 @6-bit). NOT claiming min-energy
  as a fix.
- next attempts: **penalty-weighted adder** — boost the constraint weights (or add
  the missing penalty terms) so the correct sum is the STRICT global min, then
  min-energy decode should hit ~1.0; a **composed** pipeline (bind then retrieve);
  then wire a CLEAN pattern (bind/unbind or memory) into `codegen_thrml`.

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
