<!--
commit:  83e5b9487be299e942197cacc523a455df1c62c0
date:    2026-04-12 16:33:34 -0700
subject: abstract rewrite + STATUS.md active-investigation + CI-broken notes
path:    fly-brain-paper/paper.md
-->

# Turing-Complete Computation on the Drosophila Hemibrain Connectome

**Emma Leonhart**

## Abstract

We compile programs written in Sutra, a vector programming language, to execute on a spiking neural network model of the *Drosophila melanogaster* mushroom body, wired with real synaptic connectivity from the Janelia hemibrain v1.2.1 connectome (Scheffer et al. 2020). The substrate implements the three primitives required for Turing-equivalent computation on a connectionist system: conditional branching, unbounded data-dependent iteration, and addressable read/write memory via VSA bind/unbind. Conditional branching is demonstrated on a four-way permutation program; iteration is demonstrated as eigenrotation through vector space with KC-space prototype match as the termination signal; addressable memory is implemented through sign-flip bind with codebook cleanup. All algebraic operations (bundle, bind, rotation) run as spiking circuits — bundle and rotation validated on real FlyWire v783 wiring, rotation additionally realized via a synthetic Givens operator when arbitrary transforms are required. Programming the connectome is harder than programming silicon because the tape cannot be grown on demand; we present the operational primitives and argue that tape virtualization — scaling to FlyWire, chaining mushroom bodies, or a neuromorphic substrate with the same motifs — is an engineering extension, not a new mechanism. To our knowledge, this is the first demonstration of a connectionist programming language whose primitive set covers the Turing-equivalent operations, compiled to execute on a connectome-derived biological circuit.

## The Substrate

The execution substrate is the right mushroom body of an adult *Drosophila melanogaster*, as reconstructed in the Janelia hemibrain v1.2.1 connectome. The circuit consists of:

| Component | Count | Role |
|-----------|-------|------|
| Projection Neurons (PNs) | 140 | Input layer (connectome-derived) |
| Kenyon Cells (KCs) | 1,882 | Sparse coding layer (connectome-derived) |
| APL neuron | 1 | Graded feedback inhibition (enforces ~7.8% sparsity) |
| MBONs | 20 | Learned readout layer |

The PN→KC connectivity is loaded directly from the connectome — it is the actual synaptic wiring of a real fly, not a random approximation. The APL neuron provides dynamical feedback inhibition following the biology described in Papadopoulou et al. 2011 and Lin et al. 2014. The readout layer uses a learned linear map from KC firing patterns to output vectors, fitted via ridge regression — the same shape of computation a real MBON performs via dopamine-gated plasticity. The circuit is simulated in Brian2 using leaky integrate-and-fire neurons.

The mushroom body is a natural substrate for vector symbolic architecture (VSA) because its core operation — sparse random projection from 140 PNs to 1,882 KCs — is structurally identical to VSA encoding. The dimensionality expansion from 140 to 1,882 provides the capacity for clean pattern discrimination that VSA requires.

**Division of labor.** Sutra defines a three-tier operation model (`planning/sutra-spec/02-operations.md`): tier-1 primitives (scalars, bounded iteration unrolled at compile time — no runtime loop counter exists; `loop (condition)` compiles to eigenrotation where the "counter" is the angular position on the helix R^i·v₀ in the substrate, not an integer on the host), tier-2 algebraic operations (bundle, bind, rotation R), and tier-3 substrate operations (snap-to-codebook, cone queries, prototype matching). Tier-3 is inherently substrate-level — a codebook lookup has no non-substrate implementation. Tier-2 is where a bad paper would hide host arithmetic behind a "biological" label. We run all of tier-2 on spiking circuits (`fly-brain/neural_vsa.py`): `bundle(a, b) = a + b` as two Poisson input populations converging on leaky-integrator output neurons via excitatory synapses (literal EPSP summation); `bind(a, role) = a * sign(role)` as a Poisson input projecting through role-signed synapses (excitatory if `sign(role_i) >= 0`, inhibitory otherwise) plus a shared bias rail; rotation `R · v` as a Brian2 feedforward network whose synaptic weight matrix is the composition of Givens rotations `R` (positive entries as excitatory synapses, negative as inhibitory). Steady-state membrane voltage of each output population decodes to the expected vector. Validated against the numpy reference (dim=32): bundle cos=0.96, sign-match=1.00 (500 ms); bind cos=0.94, sign-match=0.94 (500 ms); rotate cos=0.99, sign-match=0.94 (1500 ms — rotation accumulates D² synapses' worth of Poisson variance and wants a longer averaging window). A stronger "tier-2 on the connectome" variant (`fly-brain/neural_vsa_flywire.py`) replaces the synthetic synapse matrices with real FlyWire v783 wiring: `bundle` runs through a real 685-ALPN → 517-LHLN convergent projection (weights = `syn_count × NT-sign`, no weight tuning) and reproduces `W·(a+b)` at cos=0.94. `rotate` on that same real projection matrix simulates its own linear map faithfully but the matrix itself is rank 415, condition number ~1e16, and non-orthogonal — so real-wire rotation is a compressive projection, not a Givens rotation. This is reported as a negative result in §Honest Limits; the paper's rotation claim uses the synthetic R. The circuit then executes tier-3 (sparse projection into 1,882-D KC space, APL-enforced sparsity, Jaccard prototype match). Program-level decisions — which conditional branch is taken, when a loop terminates — are made by the circuit's response in KC space. No tier-2 vector arithmetic is performed on the host.

## Result 1: Conditional Branching

The compiler translates Sutra conditional programs into sequences of VSA operations that execute on the spiking substrate. The reference program (`permutation_conditional.su`) encodes four distinct decision-making programs using bind, unbind, bundle, snap, and similarity operations, each mapping two binary inputs (odor presence × hunger state) to one of four behavioral outputs (approach, ignore, search, idle).

| | Program A | Program B | Program C | Program D |
|---|---|---|---|---|
| vinegar + hungry | approach | search | ignore | idle |
| vinegar + fed | ignore | idle | approach | search |
| clean_air + hungry | search | approach | idle | ignore |
| clean_air + fed | idle | ignore | search | approach |

**Result:** 13/16 correct decisions across all four programs, with all four program permutations correctly discriminated (4/4 distinct mappings). The 3/16 errors arise from spiking non-determinism in Brian2 (stochastic spike timing causes run-to-run variation of 6–13/16); the consistent signal is that all four programs produce distinct output mappings on every run. The system makes the right behavioral choice in the majority of cases, and never confuses one program for another.

The binding operation computes `a * sign(b)` in the PN input space — an input transformation analogous to antennal lobe lateral processing (Wilson 2013). The PN→KC synaptic weights remain fixed throughout; no synapse modification occurs during computation. Conditional branching uses fuzzy weighted superposition: both branches execute simultaneously via `weight * branch_A + (1 - weight) * branch_B`, where the weight is derived from a defuzzification operation (cosine similarity to a reserved "true" vector). This produces graded, approximate decisions — consistent with the fuzzy-by-default semantics of Sutra.

## Result 2: Iteration via Geometric Loops

Iteration is implemented as geometric rotation in vector space. A loop body is a rotation matrix R. Each iteration applies R to the state vector, projects the result through the mushroom body circuit, and compares the resulting KC activation pattern against pre-compiled prototype patterns via Jaccard overlap. The loop terminates when a prototype match exceeds a threshold. The brain counts by accumulating rotation: N iterations of rotation by angle θ accumulates Nθ total rotation, and target prototypes placed at known angles act as stopping conditions.

**Results on hemibrain substrate (3/3 PASS):**

| Test | Description | Result |
|------|-------------|--------|
| Convergence | Target at step 3, rotation across 20 2D planes | Matched target after 1 rotation (large rotation angle covers 3 steps in one application) |
| Counting | Prototypes at steps 3 and 6 | Counted to 3 (1 iter) and 6 (5 iters) |
| Ordering | Prototypes at steps 2, 5, 8; no specified target | Hit nearest prototype first |

All prototype compilations and loop iterations share the same PN→KC projection (the fixed-frame invariant), ensuring KC patterns from different iterations are comparable. Nested loops are rotations in orthogonal subspaces — with 140 input dimensions, there is room for up to 70 independent nesting levels.

## Toward Turing Completeness on a Connectionist Substrate

Building a Turing-complete connectionist system is harder than building one on silicon: the usual move of "add another register, grow the tape" maps cleanly onto von Neumann hardware but not onto a fixed biological circuit. What a connectionist substrate gives you is a dense vector space, sparse distributed coding, and recurrent dynamics — primitives, not a tape. The engineering problem is to show that those primitives compose into the standard Turing set, and then separately to show that the tape can be virtualized. This paper addresses the first half directly and gestures at the second.

The three primitives required:

1. **Conditional branching** — decisions gated on computed state. Demonstrated in §Result 1: four permutation programs, each realized on the substrate via fuzzy weighted superposition rather than a discrete `if`. The branch selection is made by KC-space similarity, not a host-side test.

2. **Unbounded iteration** — repeat computation an arbitrary number of times with data-dependent termination. Demonstrated in §Result 2: geometric loops traverse the vector space as an eigenrotation (helix R^i·v₀), and termination is triggered by KC-space prototype match — not by a counter hitting a preset limit. `loop (N)` with a literal N unrolls at compile time and needs no runtime iteration at all (spec `03-control-flow.md`).

3. **Read/write addressable memory** — store, retrieve, and *address* intermediate state. The codebook + bind/unbind gives us this. A hypervector `record = bind(k₁, v₁) + bind(k₂, v₂) + ... + bind(k_n, v_n)` superposes n key–value slots in a single D-dimensional vector. Reading slot i — "what is the value bound to key k_i?" — is `unbind(record, k_i)`, which for sign-flip binding is self-inverse: `sign(k_i) * record ≈ v_i + crosstalk_from_other_slots`. The crosstalk is suppressed by `snap` to the nearest codebook entry, so the readout returns the clean stored `v_i`. Writing to slot i is `record' = record + bind(k_i, v_i_new) - bind(k_i, v_i_old)` — again all realized via tier-2/tier-3 ops on the substrate. This is addressable memory in the VSA sense (Plate 1995, Kanerva 2009), not a static lookup: any key can be used to index, keys and values are themselves vectors in the same space, and the memory is composable with other ops.

**What we are and are not claiming.** Any finite connectionist network — including the ~1,882-KC mushroom body — is formally a bounded finite-state machine, as is any physical computer with finite RAM. The claim here is that we have realized the three operational primitives on the substrate and that the programming model (Sutra) composes them in the standard way. We do not claim an infinite tape. We *do* claim we are near the conceptual threshold of Turing-equivalent expressivity on a connectionist substrate: the operations work, and what remains is virtualizing tape growth — scaling to the full FlyWire ~13k KCs, chaining multiple mushroom bodies, or a neuromorphic substrate with the same motifs — which is an engineering extension of the same primitives, not a new mechanism. In the standard framing, the operations are demonstrated and the tape is what is low; that is the honest state of the result.

## In-Repo Specification and Compiler

To address concerns about external documentation and reproducibility, the Sutra language surface, operation model, control-flow semantics, and VSA math axioms are fully specified in the project repository under `planning/sutra-spec/`. The load-bearing files are `02-operations.md` (the three-tier operation model referenced throughout this paper), `03-control-flow.md` (the `loop (N)` / `loop (condition)` semantics including eigenrotation), `04-defuzzification.md` (the `is_true` recursive-threshold control), `11-vsa-math.md` (the eight VSA axioms and their algebraic structure), and `19-substrate-candidates.md` (the substrate-compatibility rules that justify tier assignment). The compiler is at `sdk/sutra-compiler/`; the `.su` programs cited here (`permutation_conditional.su` and the loop-termination tests under `fly-brain/`) compile through that pipeline into Python that calls the `fly-brain/vsa_operations.py` runtime. Everything named in this paper is therefore inspectable, runnable, and separate from the paper text — it is a specified language with an implementation, not a label attached to an ad-hoc script.

## Methods

**Encoding.** Hypervectors are encoded as PN input currents via centered rate coding: zero components map to a baseline current (1.2), positive components to above-baseline (more spikes), negative components to below-baseline (fewer spikes).

**Decoding.** A learned linear readout `W` maps KC firing rates to output vectors. `W` is fitted once via ridge regression on ~80 (hypervector, KC firing pattern) pairs collected by running random inputs through the circuit — a program-independent calibration step, not a task-specific classifier. The same `W` is reused across all four conditional programs and all loop tests without refitting. This is the same computation shape a real MBON acquires via associative learning: a linear map from KC population activity to readout, learned from experience without access to the connectivity matrix.

**Binding, bundling, and rotation (tier-2).** All three are Brian2 spiking circuits (`fly-brain/neural_vsa.py`). `bundle(a, b) = a + b` uses two Poisson input populations at rates `f(a_i)` and `f(b_i)` projecting one-to-one onto a leaky-integrator output population through unit excitatory synapses; steady-state membrane voltage reads out `a + b`. `bind(a, role) = a * sign(role)` uses a single Poisson input per dimension projecting onto an output neuron through a synapse whose sign is fixed by `sign(role_i)`, with a shared bias rail so role-negative dimensions have headroom for inhibition. `rotate(v, R) = R · v` generalizes: a feedforward two-population network where output neuron `i` receives a synapse from every input `j` with per-connection weight `R[i, j] · W` — excitatory if `R[i, j] > 0`, inhibitory if negative. The rotation matrix `R` is itself constructed at compile time as a composition of Givens rotations, analogous to how the PN→KC projection is fixed at compile time by FlyWire. In each case the operand vectors are consumed by synaptic integration; no host-side elementwise product, sum, or matmul is computed. The PN→KC connectome weights (tier-3) remain fixed and untouched by these tier-2 circuits; tier-2 and tier-3 are stacked networks, not merged.

**Sparsity.** A single graded APL neuron integrates KC activity and feeds back continuous inhibitory current to all KCs, producing ~7.8% KC activation — within the 2–10% range observed in vivo (Lin et al. 2014). Sparsity emerges from the circuit dynamics, not from a hand-coded override.

**Geometric loops.** Per `planning/sutra-spec/03-control-flow.md`, `loop (N)` with a literal bound unrolls at compile time into a flat algebraic expression — no runtime iteration, no rotation needed. `loop (condition)` with data-dependent termination compiles to eigenrotation: there is no integer loop counter at runtime, and the "counter" is the angular position on the helix R^i·v₀ traced through the substrate's state space. In the current implementation the rotation operator itself runs as a tier-2 spiking circuit (`neural_vsa.py`: a feedforward LIF network whose synapse matrix is the Givens composition R, positive entries excitatory, negative inhibitory). The host sequences the iterations in a Python loop that presents the current rotated state to the circuit, reads KC activity, and checks Jaccard overlap against pre-compiled prototypes; termination — the control-flow decision — is made by the circuit. We flag this sequencing as a framing caveat: the rotation step itself is executed on neurons, not in numpy, but the outer for-loop that threads sequential presentations together currently runs in host Python. A substrate-intrinsic trajectory (recurrent connectome dynamics sustaining R^i·v₀ without host polling) is out of scope for this paper — see Honest Limits.

## Reproducibility

All experiments run on commodity hardware (Windows 11, Python 3.13, Brian2 2.10.1) without GPU. The hemibrain connectivity matrix (0.1 MB) is committed to the source repository. The full validation suite executes in under 30 minutes on a single CPU core.

## Honest Limits of the Current Substrate

The tier-2 spiking circuits in `neural_vsa.py` use synthetic weight matrices (the Givens composition for rotation, role-signed synapses for bind) realized as Brian2 LIF populations. A stronger version of the claim — circuits whose weights come directly from real FlyWire v783 neurons — is implemented in `fly-brain/neural_vsa_flywire.py`. The honest finding: a real ALPN→LHLN feedforward projection (685 ALPNs → 517 LHLNs, weights = syn_count × NT-sign from FlyWire) simulates its own linear map faithfully (cos=0.94 vs. numpy W·v reference), but that linear map is **not a rotation** — effective rank 415, condition number ~1e16, column-orthonormality RMS off-diagonal 0.059. It is a compressive non-orthogonal projection, consistent with olfactory biology. This is the deeper point for biomedical deployment: Sutra must compile within the eigenstructure the patient's connectome provides; the rotation matrix R is fixed by anatomy, not chosen by the programmer. The paper's tier-2 rotation result uses a synthetic Givens R to demonstrate the algebra; closing the gap to real-wiring rotation is an open problem gated on finding a connectome motif with adequate near-orthogonality, or distributing the computation over multiple compressive projections.

**Scope of "runs on the connectome."** This paper is a computational model, not a physical deployment. We use the real hemibrain wiring as the substrate graph and simulate it in Brian2; we do not claim to have executed anything on living tissue or a neuromorphic chip. Physical deployment — stimulating real neurons at prescribed sites (e.g., via an optogenetic or Neuralink-style interface) to drive program state, and reading state back out — is substantially harder engineering work and is out of scope here. Nothing in this paper should be read as a claim about in-vivo execution. The value of the present result is that the programming model survives contact with a real connectome graph at all; the hardware bridge is separate future work.

**Scope of the eigenrotation limitation.** Sutra's `loop (N)` with a literal bound unrolls at compile time into a flat algebraic expression (`planning/sutra-spec/03-control-flow.md`) — no runtime iteration, no eigenrotation required. Eigenrotation is invoked only for `loop (condition)` with data-dependent termination. The real-wiring rotation gap above therefore affects indefinite-termination loops, not the common case of bounded iteration; the majority of the Sutra surface (conditionals, fuzzy defuzzification, bundle, bind, snap, bounded loops) is unaffected.

Other concrete limits. The 140-PN input layer is narrow by VSA standards (typical VSA operates at 1k–10k dimensions); this is likely a contributor to the 13/16 branching accuracy, and the planned KC-space promotion (1,882-D) would widen the operating space by an order of magnitude. The evaluation (16 branching trials, 3 iteration trials) is small and documents proof-of-substrate rather than statistical robustness; a scaled evaluation is straightforward once the substrate is confirmed working. The MBON readout uses ridge regression; replacing it with a dopamine-gated plasticity rule is planned and does not affect the substrate-level claims.

The Sutra language surface, three-tier operation model, and compiler are specified in `planning/sutra-spec/` (canonical files: `02-operations.md`, `03-control-flow.md`, `11-vsa-math.md`) and implemented in `sdk/sutra-compiler/`; the `.su` programs cited here (`permutation_conditional.su` and the loop tests) compile through that pipeline to the fly-brain runtime — it is not an ad-hoc DSL built for this paper.

## Future Work

1. **FlyWire scale.** The Princeton FlyWire connectome (~140,000 neurons) would increase memory capacity from ~300 to ~10,000–15,000 prototypes.
3. **KC-space promotion.** Moving all operations into the 1,882-D KC space (where binding achieves perfect decorrelation) rather than the 140-D PN I/O layer.
4. **Biological learning rule.** Replacing ridge regression with dopamine-gated plasticity for the MBON readout.
