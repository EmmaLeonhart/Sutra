<!--
commit:  705c4b85ae289698b0f1c716cde995d1c71224c8
date:    2026-04-15 12:17:15 -0700
subject: fly-brain paper: narrow to Shiu conditional as single headline
path:    fly-brain-paper/paper.md
-->

# Conditional Branching on a Whole-Brain Drosophila LIF Model Wired from a Real Connectome

**Emma Leonhart**

## Abstract

We compile a conditional program written in Sutra, a vector programming language, to execute on the Shiu et al. 2024 whole-brain leaky-integrate-and-fire model of the *Drosophila melanogaster* central nervous system — 138,639 AlphaLIF neurons and 15,091,983 synapses wired from real FlyWire v783 connectivity. The program encodes four distinct four-way decision rules mapping two binary inputs (odor presence × hunger state) to one of four behavioral outputs. Compiled under Sutra's fuzzy-weighted-superposition conditional form, the same pipeline runs on the whole-brain substrate without parameter tuning and without any MB-equivalent decorrelation circuit, producing **155/160 correct decisions (96.9%) at n=10 seeds** across all four programs and all sixteen input scenarios. Eight of ten runs scored a perfect 16/16. No host-side conditional executes at runtime: program identity enters only through a compile-time prototype-to-behavior table; branch selection is a consequence of spike-count cosine scores against compiled prototypes on the real connectome. This is, to our knowledge, the first four-way fuzzy conditional from a compiled programming language executed on a whole-brain connectome-wired spiking model.

## The Substrate

The execution substrate is the Shiu et al. 2024 whole-brain LIF model of the adult *Drosophila melanogaster* central nervous system:

| Component | Count |
|-----------|-------|
| AlphaLIF neurons | 138,639 |
| Synapses | 15,091,983 |
| Connectivity source | FlyWire v783 (real) |
| Calibrated parameters | `wScale=0.275`, `vThreshold=−45 mV` (Shiu release) |
| Ground-truth match | 91% vs. measured spike activity |

The model reproduces measured fly activity at 91% accuracy against ground-truth spike recordings; we do not modify any calibrated parameter. Simulation is PyTorch CUDA. Drive enters as Poisson input at per-neuron rates; spike counts accumulated over a 100 ms window are the substrate's output representation for Sutra's vector operations.

**What runs where.** Sutra separates scaffolding (scalars, tuples, the four-program prototype-to-behavior map, the argmax readout) from vector operations (bundle, bind, similarity, snap). Every vector operation in a program must run on the substrate at runtime by the Substrate Rule (`planning/sutra-spec/02-operations.md`). In the pipeline reported here, `bundle(a, b) = a + b` runs as substrate-native convergent drive (previously measured cos=0.97 between the substrate response to driving both populations and the linear sum of separate responses; `fly-brain/shiu_bundle_test.py`), `snap(q)` runs as cosine-argmax over a spike-count codebook on the substrate (previously measured 15/16 at a 16-entry codebook; `fly-brain/shiu_snap_test.py`), and the four-way conditional below is built on exactly these primitives. The host runs counting, table lookups, and the final readout — not branching.

## Result: Fuzzy-Weighted Conditional Branching

**Program.** Four decision rules over two binary inputs (smell ∈ {vinegar, clean_air}, hunger ∈ {hungry, fed}) mapping to four behaviors (approach, ignore, search, idle). The four programs share the same prototype set and the same decision pipeline — they differ only in the compile-time prototype-to-behavior map:

| | Program A | Program B | Program C | Program D |
|---|---|---|---|---|
| vinegar + hungry | approach | search | ignore | idle |
| vinegar + fed | ignore | idle | approach | search |
| clean_air + hungry | search | approach | idle | ignore |
| clean_air + fed | idle | ignore | search | approach |

**Compilation.** Per `planning/sutra-spec/03-control-flow.md`, a Sutra conditional compiles to fuzzy weighted superposition rather than a discrete `if`:

    q          = bind(smell_vec, hunger_vec)
    brain_q    = snap(q)                               # runs on substrate
    w_i        = relu(cos(brain_q, prototype_i))       # normalized, sums to 1
    result     = Σ_i w_i · behavior_vec[program_map[prototype_i]]
    winner     = argmax_j cos(result, behavior_vec_j)

All four branches execute simultaneously on the substrate; the prototype-matching circuit produces the weights; the program identity enters only at `program_map` (a compile-time table) and `argmax_j` (a readout). There is no host-side `if`, no sign-flip on the query, no program-dependent rewrite of the input. `fly-brain/fuzzy_conditional.py` is the reference program; `fly-brain/shiu_conditional.py` is the Shiu-substrate driver.

**Realization on Shiu.** Four disjoint 40-neuron random input populations encode the four joint prototypes (PH, PF, AH, AF = vinegar/clean_air × hungry/fed). At query time, weighted-superposition is realized as simultaneous driving of all four behavior populations at rates `w_i · 200 Hz`. Substrate-native bundle, substrate-native snap, spike-count cosine — no MB-equivalent decorrelation circuit, no parameter tuning.

**Result.** Across ten independent seeds on the Shiu whole-brain LIF with real FlyWire v783 W:

| Metric | Value |
|---|---|
| Total correct | **155 / 160** |
| Accuracy | **96.9%** |
| Per-run mean | 96.9% (σ = 7.5%) |
| Perfect runs (16/16) | 8 / 10 |
| Non-perfect runs | 15/16 and 12/16 |
| Per-program accuracy | A 39/40, B 39/40, C 38/40, D 39/40 |

The ~3% residual is weighted-drive collision on particular random seed choices, not a structural failure of the program: no program is systematically degraded, and the misses are single-trial off-by-one mis-snaps. A biological MB-style decorrelation layer (sparse expansion via PN→KC → APL-inhibited readout, as in the *Drosophila* mushroom body) would be expected to close the gap; the result above is what the raw whole-brain spike-count readout delivers without that layer.

Reproducibility: `python fly-brain/shiu_conditional.py --n-runs 10` against the Shiu model at `C:/Users/Immanuelle/shiu-fly-brain` (PyTorch CUDA, ~5 minutes on RTX 4070 Laptop). Full analysis: `planning/findings/2026-04-13-shiu-conditional-branching.md`.

## Methods

**Encoding.** Input hypervectors are encoded as Poisson drive rates over disjoint 40-neuron populations; one such population per prototype, randomly chosen and held fixed across runs.

**Binding and bundling on Shiu.** `bind(a, role) = a * sign(role)` is realized in input-current space; the sign of each role component determines whether the corresponding input population contributes excitatory or (via a shared bias rail giving room for negative drive) reduced drive. `bundle` is the native substrate response to simultaneous drive of multiple populations — §The Substrate above references the cos=0.97 validation.

**Snap.** Cosine-argmax over the 138,639-D spike-count vector against the four compiled prototype responses. The prototype responses are themselves spike-count vectors collected by driving each prototype population in isolation under the same Poisson protocol used at query time.

**Shiu calibration.** No parameter tuning was performed for this work. All runs use Shiu's released calibrated values (`wScale=0.275`, `vThreshold=−45 mV`). The 138,639-neuron model reproduces measured fly activity at 91% accuracy against ground-truth spike recordings; this paper treats that calibrated model as the fixed substrate.

## In-Repo Specification and Compiler

The Sutra language surface, operation model, control-flow semantics, and VSA math axioms are specified in the project repository under `planning/sutra-spec/`. The load-bearing files are `02-operations.md` (scaffolding-vs-vector-operation model and the Substrate Rule referenced here), `03-control-flow.md` (the fuzzy-weighted-superposition conditional form above), and `11-vsa-math.md` (the eight VSA axioms). The compiler is at `sdk/sutra-compiler/`; `.su` programs compile to Python that calls `fly-brain/vsa_operations.py`. The language has an implementation separate from this paper, and the runtime referenced here is the same runtime that executes the language's other programs (bundle, bind, snap demonstrations on Shiu and on hemibrain MB) in the broader Sutra project.

## Reproducibility

Runs on Windows 11 / Python 3.13 / PyTorch with CUDA 12.4, RTX 4070 Laptop (8 GB VRAM). The Shiu model and its weight files live at `C:/Users/Immanuelle/shiu-fly-brain`; the reproducibility command above assumes the Shiu release is present at that path. The conditional harness wall-clock is ~5 minutes.

## Future Work

1. **MB-equivalent decorrelation layer on Shiu.** Adding a substrate-realized sparse-coding stage (PN→KC → APL feedback) between query and snap is the natural next move to close the 3% residual on the whole-brain substrate. The calibrated MB neurons are already in the Shiu model; the wiring to route the query through them is a compile-time change, not a parameter fit.
2. **Iteration (`loop (condition)`) on the broader CX ring subnetwork.** Prior work (separate repository, not reported here) tested whether the 47-neuron EPG slice carries ring dynamics on the Shiu substrate under direct drive and found it does not — the biological ring attractor lives in the wider Δ7+PEN+EPG+R subnetwork, and recruiting it via its biological inputs is an open problem for iteration on real connectome data.
3. **Scale the prototype set.** The current four-way conditional uses a four-prototype codebook. Capacity scaling on Shiu — how many prototypes can be discriminated before random-overlap collisions dominate — is measurable with the existing harness.
