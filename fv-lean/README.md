# fv-lean — formal verification of the thrml gadgets in Lean

Machine-checked proofs of the **ground-state** claims the Sutra → thrml
exploration only *measured* (queue.md FV item, Emma 2026-06-14: "verify the thrml
gadgets in Lean"). Each proof shows the arithmetically-correct output of an
energy-based gadget is the **strict global minimum** of its energy — i.e. a
ground-state / min-energy decode is provably exact, not just empirically ~1.0.

## Proven (each: `_min` = correct output attains the energy minimum; `_strict` =
every wrong output strictly higher → unique minimiser; no `sorry`)

- `AndGadget.lean` — the derived AND Ising gadget (biases a:+¼ b:+¼ z:−½,
  couplings ab:−¼ az:+½ bz:+½). The gadget measured at 100% (A2) and re-learned
  by training (C), now formally correct.
- `XorGadget.lean` — the 3-body XOR/parity gadget `E = σx·σy·σz` (negative factor
  weight). Pins the **correct sign** — the one whose sign bug (positive → silently
  XNOR) was found + fixed 2026-06-14; the proof rules out that bug.
- `FullAdder.lean` — the 1-bit full adder (sum = `a⊕b⊕cin` via the 4-body parity
  factor, carry = `MAJ(a,b,cin)` via the pairwise factor). Proves the correct
  (sum, carry) is the strict global minimum for all 8 inputs → **addition's
  ground-state decode is exactly correct.** The 2×2 multiplier is these gates
  (AND + XOR) composed, so its correctness follows from the gate proofs.
- `Composition.lean` — the **general gadget-composition lemma**: a circuit is gadgets
  wired together, and on the energy-based target wiring is *addition of energies*. For any
  finite list of penalty terms over a shared state, if `s₀` minimizes every term and every
  other state makes some term strictly larger at `s₀`, then `s₀` is the **strict** global
  minimum of the sum (`strict_global_min_of_terms`). Each gadget's `_strict` theorem
  supplies those hypotheses, so a circuit of verified gadgets has its correct output as the
  strict global energy minimum — for any number of gadgets, no monolithic re-proof. Core
  Lean (`List.sum` + `omega`); `[propext, Quot.sound]`, no `sorry`. The composed terms are
  the gadgets' **proper penalties** (each raw energy shifted by its own strict minimum, so
  it is 0 when satisfied — the AND gadget's raw min is not a constant, the known Ising
  chaining subtlety). Includes a concrete **two-gate** worked circuit `and3_circuit_strict_min`
  (a 3-input AND = two AND gadgets on a shared spin) verified via the general lemma. Answers
  the reviewer con "no methodology for how the micro-proofs compose to a full program."
- `GibbsChain.lean` — the **single-gadget Gibbs chain reaches the ground state**
  (the "attempt a Lean convergence proof" item, Emma 2026-06-14). The bounded,
  mathlib-free floor under a full convergence theorem: the single-site (Glauber)
  block-Gibbs chain on the AND gadget's `Bool^3` state space is `irreducible`
  (every state reaches every state — the 3-cube is connected) and `aperiodic`
  (every state has a self-loop) — **exactly the hypotheses** the classical
  fundamental theorem of finite Markov chains needs for a unique stationary `π`
  + convergence from any start. Plus `and_gibbs_unique_mode`: the correct output
  is the strict unique MODE of the Gibbs measure for any strictly-antitone weight
  (every β>0 Boltzmann weight). So the chain converges (classical thm, hypotheses
  now machine-checked) to a `π` peaked on the right answer. NOT mechanised (the
  mathlib step): the limit theorem itself + detailed balance, which need
  real-valued probabilities + `exp`. `irreducible`/`aperiodic`/
  `strict_min_is_strict_mode` depend on **no axioms**; `and_gibbs_unique_mode` on
  `[propext, Quot.sound]`.

## Check it

```bash
# needs lean4 (via elan); no mathlib (core `omega` only)
lean fv-lean/AndGadget.lean        # exit 0, prints the axiom dependencies
```

## Mid-size mathlib step (isolated — `mathlib/`)

`mathlib/GibbsMathlib.lean` is a SEPARATE Lake project (`mathlib/lakefile.toml`, pinned
mathlib `v4.30.0`) for the **convergence** results that genuinely need real analysis —
kept isolated so the core files above stay no-mathlib + fast. It machine-checks
(`[propext, Classical.choice, Quot.sound]`, no `sorry`, over the reals):
`stationary_of_detailedBalance` (reversibility ⟹ stationarity, general finite chain),
`gibbsKernel_detailedBalance` + `gibbsKernel_stationary` (the gadget's real-`exp` Gibbs
kernel is reversible → the Gibbs measure is stationary), and `stationary_unique_two_state`
(2-state Perron–Frobenius stationary uniqueness). With the core-only irreducibility +
aperiodicity, this is the reversible-chain picture: positive + irreducible + reversible ⟹
unique stationary = Gibbs. Build it (heavy — `.lake/` gitignored, NOT in CI):

```bash
cd fv-lean/mathlib && lake exe cache get && lake build GibbsMathlib   # needs mathlib oleans
```

Remaining (longer-horizon, beyond Emma's mid-size scope): the t→∞ **mixing rate** /
spectral gap. The core no-mathlib proofs below stay CI-checked.

`scripts/check_fv_lean.sh` runs every top-level `.lean` here (NOT `mathlib/`). CI: `.github/workflows/fv-lean-ci.yml`
runs the script on GitHub Actions — **path-filtered** to `fv-lean/**` (the toolchain
install is heavy, so it only fires when a proof / the toolchain pin / the runner
changes, not on every push), toolchain cached + pinned by `fv-lean/lean-toolchain`
(`leanprover/lean4:v4.30.0`). Next (the remaining mathlib step): the finite-chain
limit theorem + detailed balance for `GibbsChain`, which need real-valued transition
probabilities + `exp`.
