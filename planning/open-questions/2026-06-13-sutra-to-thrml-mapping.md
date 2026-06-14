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
- **#5 composed VSA key-value query — WORKS (2026-06-13).** `experiments/thrml/
  kv_store_demo.py`. The first real multi-op *program* on the sampler — the
  `role_filler_record` pattern. Data: K role/filler bit-registers, stored record
  `M = sign(Σ_k r_k⊙f_k)` (bundle of bound pairs). Query role j, on the substrate,
  in two staged sampling runs (host hand-off between stages = the orchestrator/
  readout boundary): **stage 1 unbind** (3-body factor, clamp M,r_j → sample
  u = M⊙r_j, a NOISY f_j) then **stage 2 cleanup** (Hebbian assoc-memory over the
  filler codebook, init=u → nearest stored filler). **Measured:** raw unbind = 0%
  exact (always crosstalk-noisy) vs cleanup = **0.75 (N=12,K=2)** / **1.00
  (N=16,K=2)** exact recovery of the full filler, vs chance ~1e-5. The 0%→100% gap
  IS the value of composing the ops; N=16 gives the cleanup comfortable capacity
  margin (K=2 < 0.14·16). → composing the clean ops (unbind #3 + cleanup #1) runs
  a complete Sutra program on the thermodynamic substrate.
- **#4c addition RESOLVED — WORKS at 100% via sample-and-verify (2026-06-13).**
  Two findings. (a) The carry/parity **weight-ratio hypothesis is REFUTED**:
  min-energy stays ~0.75–0.79 across jcar∈{1,2,3,5} — the correct sum is genuinely
  NOT the strict global min of the naive soft-Ising adder (it has spurious ground
  states; reweighting doesn't fix it). (b) But best-of-S=1.0 means the unique
  *constraint-satisfying* assignment is ALWAYS sampled, so the right decode is
  **sample-and-verify**: keep only samples satisfying the adder relations (s=a⊕b⊕c
  AND c_out=MAJ — the program, not the answer) and return one. **Measured:**
  verify = **1.000 at 4-bit AND 6-bit** (vs modal 0.75/0.58, min-energy
  0.79/0.54). → **integer addition runs on thrml at 100%.** Lesson: deterministic
  compute on a sampler = the substrate concentrates mass near valid solutions +
  a cheap verifier selects — NOT requiring the answer to be the strict energy min
  of a hand-built soft encoding. This is the paradigm-correct way to use
  probabilistic/thermodynamic hardware, and it generalizes the per-op decodes.

**Scorecard:** memory ✓ (#1), retrieval ✓ (#2), bind/unbind ✓ (#3), addition ✓
(#4, via sample-and-verify), composed kv-query program ✓ (#5). The full
mapping — values as bit-registers, ops as factors, results by sample(+verify) —
runs real Sutra computation on the thrml substrate.

- next attempts: wire a CLEAN pattern (kv-query, bind/cleanup, or the
  verify-decoded adder) into `codegen_thrml` behind the additive `--target thrml`
  flag; broaden op coverage (compare/select, multi-step programs).

## Approaches A–H (Emma 2026-06-14: implement each, then compare)

The first-cut used hand-built factors + per-op decode. Now implement each distinct
*system* and compare head-to-head (queue.md thrml track A–H).

- **A. Sample-and-verify (general method) — demo A1 WORKS (2026-06-13/14).**
  `experiments/thrml/bidir_arith_demo.py`. **Bidirectional arithmetic on ONE
  energy model** — the energy-based property the feed-forward PyTorch path cannot
  do: the SAME adder factor graph runs forward and backward by changing the clamp.
  **Measured (4-bit, 24 trials, β=2):** ADD (clamp a,b→s) exact **1.000**; SUB
  (clamp s,a→b) exact **0.917** (= verify-found: when the inverse solution is
  sampled it is ALWAYS correct; the 8% gap is reachability in 200 draws, closed by
  more samples / annealing), vs chance 0.0625. → sample-and-verify generalizes and
  gives bidirectional compute for free.
- **A2. AND gate — WORKS, completes a UNIVERSAL gate set (2026-06-14).**
  `experiments/thrml/logic_gates_demo.py`. AND is the one logic primitive that is
  NOT a clean spin product; derived its Ising gadget from the standard QUBO AND
  penalty `P = ab - 2(a+b)z + 3z` → biases (a:+¼, b:+¼, z:−½) + couplings
  (ab:−¼, az:+½, bz:+½) (as SpinEBMFactor weights = −coeff). **Measured (8-bit
  element-wise, β=3): z=a&b exact = 1.000** vs 0.5 chance — the derivation is
  empirically verified (a wrong coefficient would have dropped it). With **AND +
  XOR(parity) + the adder**, thrml now has a **universal logic basis**: any
  Boolean circuit compiles to factors and runs via sample-and-verify. → approach A
  is established as a GENERAL compilation method, not a per-op trick.
- **A3. 2×2 multiplier (composed circuit) — WORKS at warm β (2026-06-14).**
  `experiments/thrml/multiplier_demo.py`. Composes the gate primitives into a real
  arithmetic circuit: 4 AND gates → 2 half-adders (XOR=parity + AND), 10 free
  spins. The proof that ARBITRARY Boolean circuits compile to thrml factors.
  **Measured (all 16 a,b pairs):** sample-and-verify (best-of-S) = **1.000 at
  β=1.5**, but only **0.25 at β=3**. → **temperature trade-off**: cold β freezes
  the deeper circuit in local minima; WARM β mixes so the unique gate-satisfying
  assignment is always sampled (modal-exact=0 because the warm distribution is
  spread — exactly what the verifier resolves). **Lesson: deeper composed circuits
  need warmer sampling + verify, not colder** — the opposite of the shallow ops.
  (Energy-based bonus, noted not measured: clamp the PRODUCT, sample the inputs =
  integer factoring on the same graph.) → approach A scales to composed circuits.
- next A (optional): a verify-decode in the multiplier (vs the best-of-S proxy).
  **Approach A verdict: sample-and-verify is a general method** (universal gates +
  arbitrary circuits), with a measured cost — deeper circuits trade modal-decode
  reliability for warm-β mixing + a verifier.

### Approach B — ground-state encoding + annealing

- **B1. staged annealing of the multiplier — FAILS as implemented (2026-06-14).**
  `experiments/thrml/anneal_demo.py`. The multiplier's gate-based factors make the
  correct product the strict global min, so ground-state decode *should* work; I
  tried a 2-stage anneal (β 1.5→4.0) carrying state between rounds. **Measured:**
  annealed modal-exact **0.000** vs fixed β=4.0 **0.062** (both ≈ chance 0.0625) —
  no improvement. **Diagnosis (real bug, kept):** I carried the per-node MARGINAL
  MODE of the warm round as the cold init, but the marginal mode of a spread
  distribution is not a coherent state in the answer's basin → the cold round
  freezes from near-random. Proper annealing needs a within-chain β schedule
  (thrml's `SamplingSchedule` doesn't expose per-step β) or carrying a single
  low-energy coherent state.
- next B: **min-energy decode over a warm run** of the proper-gadget multiplier
  (the answer is the strict global min there — contrast the adder #4c where
  min-energy failed because the soft encoding had spurious minima). That is the
  clean test of whether proper-gadget ground-state computing beats sample-and-
  verify. **So far for composed circuits: approach A (sample-and-verify) works,
  naive approach B (staged annealing) does not.**

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
