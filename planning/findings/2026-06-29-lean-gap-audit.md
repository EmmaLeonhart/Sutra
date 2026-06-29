# Lean-gap audit — what the FV paper proves in Lean vs. what it only measures

**Date:** 2026-06-29. **Author:** FV re-spine session.
**Scope:** `paper/formal-verification/paper.md` as of this commit. Line numbers are
as-of-commit (paper.md is live; re-grep if it drifts). Section numbers are stable.

## Why this file exists

The FV paper makes claims at three different assurance tiers, and conflating them is
the integrity bug to avoid. Emma is comparatively new to formal verification and
cannot easily vet speculative Lean work, so unsupervised proof-writing is out of
scope; the value here is an **honest inventory** of what is actually machine-checked
in Lean, what is discharged by an *exact* (symbolic) Python checker, and what is
only a *numerical measurement* — plus a prioritized list of the Lean work that still
needs doing. This is the inventory, NOT the proofs.

### The three tiers

- **L = Lean-machine-checked.** A theorem in `fv-lean/`, `sorry`-free, axioms checked
  by `#print axioms` (`[propext, Quot.sound]` core; `+ Classical.choice` for the
  mathlib layer). Run by `scripts/check_fv_lean.sh` / `.github/workflows/fv-lean-ci.yml`.
- **S = exact symbolic / closed-form discharge by a Python checker.** A real proof
  (exact rational/finite-field arithmetic, induction coded as a check), but in a
  Python `fv_*` module, **not** a proof assistant. Not floating-point.
- **M = numerical measurement.** A floating-point computation on the real substrate
  or the real energy landscape, via `fv_*` / `experiments/`. The strongest *empirical*
  evidence, but not a proof of anything for all inputs.

The paper's title says "formal verification"; the body must keep S and M visibly
distinct from L. **The continuous-time / multi-state convergence is M, not L** — this
is the spot most at risk of being misread, and it is labeled "measured, not
Lean-proved" in the abstract (L32), contributions (L127-128), §7 head (L781-782),
§7 body (L894-898, L914), and conclusion (L984).

## Inventory table

| # | Claim / result | Tier | paper.md | Code / Lean |
|--:|----------------|:----:|----------|-------------|
| 1 | AND gadget: correct output is the strict global energy minimum | **L** | §7 L806-812 | `fv-lean/AndGadget.lean` (`_min`,`_strict`) |
| 2 | XOR/parity gadget strict minimiser; correct sign (excludes XNOR bug) | **L** | §7 L813-815 | `fv-lean/XorGadget.lean` |
| 3 | 1-bit full adder: (sum,carry) strict global min for all 8 inputs ⇒ addition's ground-state decode exact | **L** | §7 L816-819 | `fv-lean/FullAdder.lean` |
| 4 | Gadget composition = sum of energies; `strict_global_min_of_terms` general lemma; `and3_circuit_strict_min` two-gate worked circuit; `half_adder_strict_min` heterogeneous (XOR+AND) worked circuit | **L** | §7 L820-827 | `fv-lean/Composition.lean` |
| 5 | Glauber chain on AND gadget irreducible + aperiodic (⇒ unique stationary π, convergence from any start) | **L** | §7 L825-832 | `fv-lean/GibbsChain.lean` (`irreducible`,`aperiodic`; no axioms) |
| 6 | Correct output is strict unique **mode** of π for any strictly-antitone weight | **L** | §7 L833-837 | `fv-lean/GibbsChain.lean` (`and_gibbs_unique_mode`,`strict_min_is_strict_mode`) |
| 7 | Detailed balance ⇒ stationarity; Gibbs kernel reversible w.r.t. Gibbs measure ⇒ stationary; 2-state Perron–Frobenius uniqueness | **L** | §7 L839-847 | `fv-lean/mathlib/GibbsMathlib.lean` (`stationary_of_detailedBalance`, `gibbsKernel_*`, `stationary_unique_two_state`) |
| 8 | **Two-state** mixing rate: TV decays as \|λ₂\|ⁿ; gadget kernel λ₂=0 ⇒ mixes in one step | **L** | §7 L856-873 | `fv-lean/mathlib/GibbsMathlib.lean` §4-5 (`two_state_step_contraction`, `two_state_tv_mixing`, `gibbs_lambda2_zero`, `gibbs_mixes_in_one_step`) |
| 9 | **Multi-state** (8-state) spectral gap γ=0.0397 > 0; master-ODE TV decay rate 0.0397 (ratio 1.0000); π stationary (1.4e-17) + reversible (4.2e-22) | **M** | §7 L875-900, §9 L980-983 | `fv_sampler_convergence.py`; `tests/test_fv_sampler_convergence.py` 6/6 |
| 10 | Continuous-**space** overdamped Langevin `dX=−∇U dt+√(2/β)dW` | **none (open)** | §7 L895-897, L914 | not built — named, not claimed |
| 11 | Loop linear core `state←R·state` marginally stable (Z-transform poles = eigenvalues of R; 868 poles on unit circle, R orthogonal) | **M** | §3.3 L381-392 | `fv_loop_convergence.py`; `tests/test_fv_loop_convergence.py` 6/6 |
| 12 | Connective range-soundness: exact range [−1,+1] over [−1,+1]² | **S** | §3.2 L309-316 | `fv_poly_bound.py` (sympy exact extrema); `tests/test_fv_poly_obligation_checker.py` |
| 13 | Range-soundness scales to any depth by induction on the expression tree | **S** | §3.3 L402-422 | `fv_obligation_checker.py` (`range_sound_by_composition`) |
| 14 | Program equivalence = same compiled graph by polynomial identity (exact `expand`, and poly-time Schwartz–Zippel) | **S** | §2 L180-211, §3.3 L442-481 | `fv_obligation_checker.py`; `tests/test_fv_general_checker.py` |
| 15 | Contract role-isolation (read/write confinement) | **S** (kernel test) | §3.1 L233-243 | `external/Yantra/tests/test_kernel.py` |
| 16 | Contract function-correctness for the Kleene fragment | **S** | §3.1 L243-247 | `fv_obligation_checker.py` (`reduces_to_same_graph`); `test_fv_general_checker.py` |
| 17 | Contract key-soundness `runtime_keys ⊆ AXON_KEYS` (execution-witnessed, per-run) | **S/M** | §3.1 L247-257 | `fv_key_soundness.py`; `tests/test_fv_key_soundness.py` |
| 18 | Kleene grid-exactness: worst \|error\| = 0.0 (codegen-correspondence regression guard) | **M** | §3.2 L278-293 | `tests/test_fv_kleene_grid_exactness.py` |
| 19 | Bundle decoding capacity table (100% through k=8; ≥99% through k=32 on 768-d) | **M** | §4.1 L535-570 | repo companion finding; capacity experiment |
| 20 | Reversibility ‖unbind(R,bind(R,x))−x‖ = 1.5e-15 | **M** | §4.2 L584-586 | repo experiment |
| 21 | Bit-exact arithmetic dispatch (calc 11/11, demos 32/32) — *supporting precision, not the claim* | **M** | §4.3 L588-614 | `demos/calc`, `demos/echo` |
| 22 | Dimension / state-locus / signal-separation audits | **M** | §4.4 L616-643 | substrate-purity audits |
| 23 | Differentiability probe; `defuzz β` end-to-end train | **M** | §4.5 L645-664 | `experiments/defuzz_gain_adjustment.py` |
| 24 | Digit-array carry: range-soundness (step-indexed) + termination (structural); 9 bit-exact worked cases | **S** (bound) / **M** (cases) | §3.4 L495-498 | `experiments/bigint_worked_example.py` |

**Headline count.** Of the 24 rows: **8 are Lean-machine-checked (L)** (rows 1-8),
**~7 are exact-symbolic Python-checker discharges (S)** (rows 12-17, 24-bound), and
**~9 are numerical measurements only (M)** (rows 9, 11, 18-23, 24-cases). Row 10 is
open (neither). The convergence *spine* is split: the **discrete-time, two-state**
picture is L (rows 5-8); the **multi-state and continuous-time** pieces are M (rows
9, 11); continuous-space Langevin is unbuilt (row 10).

## Prioritized TODO — the Lean work still needed ("what we didn't do in Lean")

Gated on Emma's call (heavy toolchain; do not write speculative proofs unsupervised).
This list is the *spec* for queue.md re-spine item 1.

1. **Machine-check the multi-state spectral gap (row 9).** Currently measured
   (γ=0.0397 on the 8-state AND-gadget chain via `fv_sampler_convergence.py`). The
   Lean target: lift `GibbsMathlib.lean`'s two-state rate to a general finite-state
   reversible chain — the gap is the second-largest eigenvalue of the π-self-adjoint
   generator. Hardest piece; needs mathlib spectral-theory machinery. **Highest
   value, highest cost.**
2. **Machine-check the continuous-time master-ODE decay (row 9, tail).** That
   `‖p(t)−π‖ ≤ e^{−γt}‖p(0)−π‖` for the jump-process generator Q. Depends on (1)
   (the gap) plus a Grönwall / semigroup-contraction argument. Do after (1).
3. **Continuous-space overdamped Langevin (row 10).** `dX=−∇U dt+√(2/β)dW` on a
   relaxed energy — currently **not built at all**, named only. Largest scope; a
   genuinely new result, not a lift of an existing measurement. Lowest priority;
   confirm it is in scope before starting.
4. **(Sharpening, optional) Multi-gate composed-circuit ground-state in Lean beyond
   the two-gate `and3_circuit` (row 4).** The general lemma already covers any size;
   a larger concrete worked instance (e.g. the 2×2 multiplier) would be illustration,
   not new theory. Low value. **PARTLY DONE 2026-06-29:** added `half_adder_strict_min`
   — a *heterogeneous* composed circuit (XOR-gadget sum + AND-gadget carry), proving the
   composition lemma is gadget-type-agnostic, not AND-only. Sound, sorry-free,
   `[propext, Quot.sound]`. The 2×2 multiplier remains as further illustration only.

**Do NOT** attempt 1-3 as unsupervised proof-writing. They are the inventory of the
gap; closing them is a deliberate, Emma-gated Lean session.

## Integrity check performed this session

Walked every "prove/proof/machine-checked/measured" occurrence in paper.md. The
measured-only convergence results (rows 9, 11) are labeled "measured, not Lean-proved"
at every headline location (abstract, contributions, §7 head/body, conclusion). No
spot was found that reads as Lean-proved while being only measured. The exact-symbolic
(S) discharges call themselves "proofs" (e.g. §3.2 "a proof, not a sampled min/max")
— this is accurate (exact arithmetic) but is **not** Lean; that distinction is the
S-vs-L row above, recorded here so a future reader does not upgrade S to L.
