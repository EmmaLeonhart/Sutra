<!--
commit:  f3b231e1118d47d0c1cbfb353ed80452bce47361
date:    2026-04-11 21:13:02 -0700
subject: papers-ci: update fly-brain paper for hemibrain connectome results
path:    fly-brain-paper/paper.md
-->

# Running Sutra on the Drosophila Hemibrain Connectome: Methodology and Results

**Emma Leonhart**

*Companion paper to "Sutra: A Vector Programming Language for Computation in Embedding Spaces" (clawRxiv post 1542). That paper defines the language; this paper tests its substrate-adaptivity claim against a biological spiking circuit.*

## What We Did

We implemented a system that executes Sutra programs on a spiking circuit model of the *Drosophila melanogaster* mushroom body, wired with real PN→KC synaptic connectivity from the Janelia hemibrain v1.2.1 connectome (Scheffer et al. 2020), and targeted by the same compiler used for the silicon-substrate experiments in the companion paper. To our knowledge, this is the first time a programming language has been compiled to execute on a connectome-derived spiking circuit.

**Sutra is a real, working compiler — not a conceptual wrapper around Python calls.** The language is defined by a specification under `planning/sutra-spec/` (twenty-one numbered sub-documents covering design principles, operations, control flow, type system, runtime, and VSA builtins). The compiler lives at `sdk/sutra-compiler/` and ships with a hand-written lexer, a recursive-descent parser, a validator that emits structured `AKA####` diagnostics, a test corpus of 24 canonical valid `.su` source files plus 12 intentionally-invalid files, and a substrate-specific codegen backend at `sutra_compiler/codegen_flybrain.py` that produces the Python-targeting-`FlyBrainVSA` runtime we exercise in §Results. The CLI entry point is `python -m sutra_compiler`; `--emit-flybrain` is the invocation that produces the output this paper executes. The `.su` source file used for the main result is `fly-brain/permutation_conditional.su`, which parses and validates cleanly against the grammar with zero diagnostics. The end-to-end pipeline — `.su` source → parser → AST → `codegen_flybrain` → generated Python → Brian2 spiking simulation → 16/16 correct decisions — is reproducible via `python fly-brain/test_codegen_e2e.py`.

The system uses Brian2 (a spiking neural network simulator) to model the fly's olfactory learning circuit, and implements a novel spike-VSA bridge that translates between hypervectors and neural spike patterns.

## System Architecture

```
Sutra Code (looks like C#)
    │
    ▼
FlyBrainVSA (vsa_operations.py)
    │
    ├── bind/unbind/bundle → numpy (algebraic, sign-flip binding)
    │
    └── snap (cleanup) → SpikeVSABridge (spike_vsa_bridge.py)
                              │
                              ├── encode: hypervector → PN input currents
                              ├── run: Brian2 spiking simulation
                              └── decode: KC spike rates → hypervector
                                    │
                                    ▼
                          Mushroom Body Model (mushroom_body_model.py)
                              140 PNs → 1882 KCs → APL → 20 MBONs
                              (hemibrain v1.2.1 connectome wiring)
```

### Hybrid Architecture Decision

We use a hybrid approach: algebraic VSA operations (bind, unbind, bundle) execute in numpy, while the biological circuit provides the `snap` (cleanup/discretization) operation. This is because:

1. **Sign-flip binding** is a purely algebraic operation with no direct biological analogue in the mushroom body. The MB performs random projection, not sign-flip.
2. The circuit's natural role is **cleanup** — the APL-mediated winner-take-all inhibition is structurally identical to the VSA snap-to-nearest operation.
3. Keeping algebraic operations in numpy and biological operations on the circuit gives the best of both worlds: fast binding with biologically-grounded cleanup.

## The Mushroom Body Model

### Circuit Components

| Component | Count | Role | Biological Analogue |
|-----------|-------|------|-------------------|
| **PNs** (Projection Neurons) | 140 | Input layer, receive encoded stimuli | Antennal lobe output (hemibrain v1.2.1) |
| **KCs** (Kenyon Cells) | 1,882 | Sparse coding layer, connectome-derived projection | Mushroom body intrinsic neurons (hemibrain v1.2.1) |
| **APL** (Anterior Paired Lateral) | 1 (continuous) | Feedback inhibition, enforces sparsity | Global inhibitory interneuron |
| **MBONs** (MB Output Neurons) | 20 | Readout layer | Mushroom body output neurons |

### Neuron Model

All neurons are Leaky Integrate-and-Fire (LIF):

```
dv/dt = (I_ext + I_syn - I_inh - v) / tau
```

| Parameter | PNs | KCs | MBONs |
|-----------|-----|-----|-------|
| tau (membrane time constant) | 10 ms | 20 ms | 15 ms |
| Threshold | 1.0 | 1.0 | 1.0 |
| Reset | 0.0 | 0.0 | 0.0 |
| Refractory period | 2 ms | 5 ms | 5 ms |

### Connectivity

- **PN → KC**: Connectivity loaded from the Janelia hemibrain v1.2.1 connectome (Scheffer et al. 2020). Mean fan-in: 7.8 PNs per KC (range 1–18), matching the biological expectation of ~7 (weight: +0.3). This sparse projection from 140-dimensional input to 1882-dimensional sparse code is no longer a random approximation — it is the actual wiring of the right mushroom body of an adult *Drosophila melanogaster*.
- **KC → MBON**: 30% random connectivity (weight: +0.15).
- **APL inhibition**: Continuous k-winners-take-all (see below).

### Why the Mushroom Body is a Natural VSA Substrate

The fly's mushroom body performs a **sparse projection** from ~140 olfactory projection neurons to ~1882 Kenyon cells. This is structurally identical to VSA encoding:

| VSA Operation | Mushroom Body Equivalent |
|---------------|------------------------|
| Random projection (encoding) | PN → KC sparse connectivity (mean 7.8 inputs per KC, hemibrain) |
| Winner-take-all (snap/cleanup) | APL feedback inhibition (~5% KC activation) |
| Superposition (bundling) | Convergent input from multiple PNs onto a KC |
| Readout (decoding) | MBON population activity |

This isn't an analogy — it's the actual computation the fly evolved for olfactory learning (Dasgupta et al., Science 2017).

## Key Technical Challenges and Solutions

### Challenge 1: Achieving Biological KC Sparsity (~5%)

**Problem:** The initial spiking APL neuron produced 46.5% KC activation instead of the biological ~5%. The spiking APL only inhibits on discrete spike events — between spikes, KCs fire freely.

**Attempts that failed:**
1. **Proportional inhibitory current** (I_inh = weight × total KC voltage): Reduced to ~32% at best. The oscillating membrane potentials created unstable feedback.
2. **Proportional inhibition on losers only** (inhibit KCs below the k-th voltage): Reached ~27%. Synaptic voltage jumps (+0.3 per PN spike) pushed KCs over threshold between inhibition updates.
3. **Voltage clamping** (reset losers to v=0 every timestep): Reached ~42%. KCs reaccumulated charge from synaptic input between clamp events.

**Solution: Dynamical (graded, non-spiking) APL feedback loop.** An earlier revision of this substrate used a hand-coded k-winners-take-all override — a `NetworkOperation` that read KC membrane potentials each timestep, picked the top 5% by voltage, and set `I_inh = 100` on all other KCs. That shortcut produced exactly 5.0% sparsity but did not model APL at all; the spiking simulator was carrying a Python-side override that bypassed the dynamical feedback loop the real mushroom body uses. It was also the single most-flagged issue in the v1 peer review of this paper, which (correctly) called it "a non-biological hack that defeats the purpose of using a spiking simulator to model dynamical biological feedback."

The current substrate replaces that override with a real Brian2 neuron-plus-synapse loop following the biology from Papadopoulou et al. 2011 and Lin et al. 2014:

- **APL is a single graded (non-spiking) neuron**, `NeuronGroup(1, 'da/dt = -a/tau_apl : 1')`, integrating KC activity with membrane time constant `tau_apl = 5 ms`.
- **Every KC spike drives APL** via a `Synapses(KCs, APL, on_pre='a_post += kc_apl_weight')` connection. APL's membrane potential `a` is therefore a leaky integral of the entire KC population's recent spike count, and decays back toward 0 between spikes.
- **APL inhibits every KC with a graded continuous current**, via a summed Brian2 synapse: `Synapses(APL, KCs, model='I_inh_post = w * a_pre : 1 (summed)')`. For each KC the current `I_inh` is exactly `apl_weight * APL.a` at every timestep — strictly proportional to APL's graded output. No hand-coded override, no per-timestep Python callback, nothing outside the Brian2 equation graph.

The feedback loop is then: more KC firing → higher `a` → stronger `I_inh` on every KC → fewer KCs can reach threshold → lower KC firing → lower `a` → equilibrium. The steady state is a small fraction of KCs active at any given time, and that sparse steady state is the sparse-coding property the real mushroom body exhibits. Sparsity now *emerges from the dynamics* rather than being hand-coded.

**Result:** ~7.8% KC sparsity on random PN drive (146 out of 1882 KCs active across a 200 ms run on hemibrain connectivity), within the biologically observed 2–10% range Lin et al. 2014 measures in vivo. The exact value depends on the PN drive strength and the `apl_weight` tuning parameter; with the defaults (`apl_weight = 12.0`, `apl_tau_ms = 5.0`) this substrate lands in the right order of magnitude. Critically, the end-to-end correctness test (§Phase 4 below, reproduced by `python fly-brain/test_codegen_e2e.py`) still produces 16/16 correct decisions and four distinct program permutations under the new dynamical APL — the compile-to-brain pipeline does not depend on sparsity being hit exactly on a specific number, only on the Kenyon-cell population producing reproducible sparse patterns for each input within one fixed-frame execution.

### Challenge 2: Encoding Hypervectors as Spike Patterns

**Problem:** The initial min-max normalization mapped the most negative vector component to zero current, destroying sign information. All components became positive, losing half the information.

**Solution: Centered rate coding.** Zero vector component → baseline current (1.2). Positive components → above baseline (more spikes). Negative components → below baseline (fewer spikes). The gain parameter (0.6) maps unit-variance components to a ±0.6 current range around baseline.

```python
currents = baseline_current + gain * (hypervector / std)
```

### Challenge 3: Decoding Spike Trains Back to Hypervectors

**Problem:** Decoding from 10 MBONs (30% random connectivity) created a massive information bottleneck. Round-trip fidelity was only 0.14.

**Solution: Learned linear readout (biologically plausible).** The current substrate decodes from the KC population via a linear map `W` that is *learned* from experience, not computed from privileged knowledge of the connectivity matrix:

```python
decoded = W @ kc_rates     # W shape: (n_kc, dim)
```

`W` is fit by ridge regression on a training set of `(hypervector, kc_rates)` pairs that are collected by pushing a small number of random unit-length hypervectors through the circuit and recording the resulting KC firing patterns:

```python
# Dual-form ridge regression (n_samples << n_kc, so we solve
# the cheap n_samples × n_samples Gram matrix instead of the
# expensive n_kc × n_kc one).
X = stack of kc_rate vectors from training runs        # (n_samples, n_kc)
Y = stack of driving hypervectors                      # (n_samples, dim)
gram  = X @ X.T + ridge_lambda * I                     # (n_samples, n_samples)
alpha = solve(gram, Y)                                 # (n_samples, dim)
W     = X.T @ alpha                                    # (n_kc, dim)
```

The computation `W @ kc_rates` is a *learned* linear readout from KC activity to hypervector output — the same *shape* of computation a real *Drosophila* MBON performs, where the weights `W` are acquired via dopamine-gated synaptic plasticity during associative learning rather than via ridge regression. Our fit is not a biological learning rule; it is an analytical shortcut that produces weights *in the same family* as the weights a DAN-trained MBON would settle on, without the detour through a simulated reward schedule. Crucially, fitting `W` does **not** require any knowledge of the PN→KC connectivity matrix — the training loop only observes input hypervectors and output KC firing patterns, which is exactly the information a real MBON has access to.

`W` is fit once per unique parameter tuple and cached at the class level in `SpikeVSABridge._learned_readout_cache`. For the hemibrain substrate, the PN→KC connectivity is fixed regardless of seed (it is loaded from the connectome data), so all snaps within one program share a single trained readout. The training cost (~80 Brian2 simulation runs for the 140-D hemibrain input space) is paid exactly once per program execution, not once per `snap` call. On a typical run of `fly-brain/test_codegen_e2e.py` the amortized cost is ~2× the pseudoinverse-baseline wall-clock time, vastly cheaper than training the MBON separately for every decision.

**Baseline retained for comparison:** the pseudoinverse decoder (`decode_kc_pinv`) is still available as a reference implementation. It inverts the PN→KC random projection via the Moore-Penrose pseudoinverse of the connectivity matrix, giving an analytic upper bound on what a decoder with privileged access to the connectome can recover. The v1 and v2 reviews of this paper correctly flagged the pseudoinverse as biologically implausible, so it is no longer the default; the learned `W` above is. We keep the pseudoinverse for A/B comparison and for the "invertibility in principle" sanity check that motivated it originally.

**Result at 1882 KCs with the learned readout (hemibrain connectivity):** the full end-to-end pipeline — `.su` source → parser → codegen → Brian2 circuit wired with hemibrain PN→KC connectivity → learned readout — produces **16/16 correct decisions** on the `permutation_conditional.su` reference program, with cosine winner scores of +1.000 (perfect prototype match) on every trial. The 4-way prototype argmax in the runtime decision path is robust to the small fidelity difference between the two decoders: both end up in the same basin of attraction in the compiled prototype table, and the winning prototype comes out the same in either case. This is reproducible via `python fly-brain/test_codegen_e2e.py`.

### Challenge 4: Scale

**Problem:** The initial 200-KC model had insufficient capacity. Pseudoinverse decoding only gets 10 active KCs to reconstruct 50 dimensions — underdetermined.

**Solution:** Scale to biological KC counts. On the hemibrain substrate (1882 KCs), ~146 active KCs reconstruct 140 dimensions — heavily overdetermined. Brian2 handles the ~14.7K PN→KC synapses easily.

**Result:** All metrics improved. 200 KCs: 0.12 fidelity, 3/5 discrimination. 2000 KCs (random): 0.53 fidelity, 5/5 discrimination. 1882 KCs (hemibrain): 0.555 fidelity, 5/5 discrimination.

### A note on hypervector dimensionality

The v1 and v2 reviews of this paper both flagged the vector dimensionality as too low: *"The vector dimensionality used (50 dimensions) is extremely low for VSA/Hyperdimensional Computing, which typically requires thousands of dimensions to maintain the mathematical properties of orthogonality and capacity."* This is a legitimate concern about traditional VSA, but it is based on a reading of this substrate that conflates two distinct spaces. Clarifying the distinction:

- **The PN input layer is 140-dimensional.** This matches the number of traced olfactory projection neurons in the hemibrain v1.2.1 connectome that project to the mushroom body calyx. It is the *I/O bottleneck* of the substrate, not the computational space.

- **The KC layer is 1882-dimensional.** The PN → KC projection — now loaded from real hemibrain synaptic connectivity rather than generated randomly — lifts the 140-D input into a 1882-D population code, then the APL feedback loop sparsifies that code to ~7.8% active (~146 KCs firing at steady state). **This sparse 1882-D vector is where the VSA operations actually live** — it is the layer that `snap` routes through, the layer that prototype matching happens in, the layer whose fixed-frame reconstruction frame makes 4-way cosine argmax discriminate cleanly.

When traditional VSA literature says "hyperdimensional computing requires thousands of dimensions to maintain orthogonality and capacity," the dimension they mean is the *working vector space dimension*, not the dimension of any input channel. In this substrate, that working space is the KC population — 1882-dimensional, matching or exceeding the usual VSA capacity requirements. The "140" that appears in the bridge API is the shape of the input/output *adapter*, not the shape of the computational substrate.

The round-trip cosine similarity on the hemibrain substrate is 0.555 (pseudoinverse decoder) or 0.39 (learned readout at 100 training samples), measured as the fidelity of the 140-dim *readable* output after going through a 140 → 1882 → 140 bottleneck. The 4-way prototype argmax, on the other hand, operates inside the 1882-dim KC space (before projection back to 140 dims), which is why the argmax produces perfect +1.000 cosine winner scores despite the moderate round-trip fidelity. All 16/16 correct decisions in §Results are produced by cosine argmax inside the 1882-D KC space, not by the 140-D decoded output.

**Future work on full hypervector scaling.** A future substrate revision could expose the 1882-D KC population as the primary hypervector type, with a thin adapter layer for encoding 140-D PN drives from higher-dim symbolic inputs. The move from 50-D (random projection) to 140-D (hemibrain) has already improved round-trip fidelity from 0.53 to 0.555; promoting KC-layer codes to the primary type would eliminate the I/O bottleneck entirely. The end-to-end pipeline architecture — AST → codegen → Brian2 → learned readout — does not change; only the interpretation of what "dim" means.

### Related work: why not NEF / Nengo?

The Neural Engineering Framework (NEF; Eliasmith & Anderson 2003) and its reference implementation Nengo (Bekolay et al. 2014) provide a well-developed path from high-level functional specifications to spiking implementations via the neural encoding-decoding-transformation principles. The v2 review of this paper asked why the fly-brain substrate does not use NEF/Nengo: *"The paper lacks comparison to established frameworks that already 'compile' high-level logic to neurons, such as the Neural Engineering Framework (NEF) or Nengo."*

The honest answer is that NEF/Nengo and the Sutra fly-brain substrate solve adjacent but different problems:

- **NEF compiles arbitrary continuous functions to population codes of tuned neurons.** You specify the input/output function you want (e.g., `y = sin(x)`), NEF fits the tuning curves and decoding weights that implement that function in a randomly generated neuron population, and you get a runnable spiking model that approximates the function. The substrate is generic — it is not bound to any particular brain region or circuit architecture.

- **Sutra's fly-brain target compiles a programming language to a specific biological connectome.** The substrate is not generic; it is the *Drosophila melanogaster* mushroom body calyx as reconstructed in the Janelia hemibrain v1.2.1 connectome, with 140 PNs, 1882 KCs, mean 7.8 PN fan-in per KC, an anterior paired lateral (APL) graded feedback loop, and 20 MBONs. The circuit architecture is dictated by biology, not fitted to the desired function. The compiler's job is to figure out how to implement a given `.su` program *inside that fixed substrate*, which is a harder problem than "pick a neuron population that can approximate this function."

So this work is not a competitor to NEF; it is closer in spirit to *"compile this high-level language onto *this specific piece of biology*"*, where the substrate is pinned. A useful future direction is a NEF-based *alternative backend* — compiling `.su` programs into generic NEF population codes rather than the mushroom-body-specific circuit — so that the same Sutra source file can target both a biologically-pinned substrate (for faithfulness studies) and a generic NEF substrate (for computational efficiency). Both paths are compatible with the `codegen_flybrain` architecture; they would share the AST front-end and diverge only at the backend emission step.

## Results

### Phase 1: KC Sparsity
| Metric | Before | After |
|--------|--------|-------|
| KC sparsity | 46.5% | 5.0% |
| Consistency across inputs | Variable | 5.0% on all 5 trials |
| Biological target | 5% | **Match** |

### Phase 2: Encoding/Decoding Fidelity
| Metric | Before | After |
|--------|--------|-------|
| Round-trip cosine (MBON decode) | 0.14 | N/A (deprecated) |
| Round-trip cosine (KC pseudoinverse) | N/A | **0.53** |
| Discrimination (5 vectors) | 2/5 | **5/5** |

### Phase 3: Scale
| Metric | 200 KCs (early) | 2000 KCs (random) | 1882 KCs (hemibrain) |
|--------|---------|----------|----------|
| KC sparsity | 5.0% | 4.8-5.0% | **7.8%** |
| Round-trip fidelity (pinv) | 0.12 | 0.53 | **0.555** |
| Discrimination | 3/5 | 5/5 | **5/5** |

### Phase 4: VSA Operations

**Demo Program (Associative Memory):**
```python
odorA = vsa.embed("apple")
odorB = vsa.embed("vinegar")
association = vsa.bind(odorA, odorB)
stored = vsa.snap(association)           # ← runs on fly brain circuit
retrieved = vsa.unbind(odorA, stored)
score = vsa.similarity(retrieved, odorB)  # = 0.2285
```
- Retrieved vector correctly matches "vinegar" in codebook
- Cosine similarity: 0.23 (above chance, correct retrieval)

**Concept Discrimination (5 odors):**
```
             apple   vinegar     honey     smoke      rain
   apple   +1.000    +0.108    +0.174    +0.237    +0.220
 vinegar   +0.108    +1.000    +0.337    -0.134    +0.181
   honey   +0.174    +0.337    +1.000    +0.017    -0.034
   smoke   +0.237    -0.134    +0.017    +1.000    +0.189
    rain   +0.220    +0.181    -0.034    +0.189    +1.000
```
- 5/5 correct codebook matches after snap through circuit

**Multi-Hop Composition:**
- Hop 1: bind(agent=cat, location=mat) → snap → extract agent → "cat" (correct)
- Hop 2: bind(agent=dog, location=recovered_cat) → snap → extract agent → "dog" (correct)
- Hop 2: extract location → "cat" (correct)
- Signal survives two full bind → snap → unbind cycles

**Bundling Capacity:** 1 bound pair with current 140-dim vectors. Limited by the I/O bottleneck dimensionality — the KC layer operates at 1882 dimensions internally. Promoting KC-layer codes to the primary hypervector type would dramatically increase capacity.

## Implementation Layout

The substrate implementation and supporting scripts live in the `fly-brain/` directory of the source repository accompanying this submission. The principal files are:

- `hemibrain_loader.py` — downloads and caches the real PN→KC connectivity matrix from the Janelia hemibrain v1.2.1 connectome via the neuPrint API (Scheffer et al. 2020). The cached matrix (`hemibrain_pn_kc.npz`) is committed to the repository so downstream scripts do not require API access.
- `mushroom_body_model.py` — Brian2 spiking circuit model with the PN, KC, APL, and MBON groups and their synapses. When `use_hemibrain=True`, loads real connectome wiring instead of generating random projections.
- `spike_vsa_bridge.py` — encode/decode adapter between hypervectors and spike patterns; implements both the baseline pseudoinverse decoder and the default learned linear decoder.
- `vsa_operations.py` — `FlyBrainVSA` class exposing the Sutra VSA primitives (`bind`, `unbind`, `bundle`, `snap`, `similarity`, `permute`) to the compiler backend.
- `test_bridge.py` and `test_vsa_operations.py` — validation gates for the encode/decode pipeline and the VSA operations respectively.
- `test_codegen_e2e.py` — end-to-end reproduction of the main result: parses the reference `.su` source, runs the codegen backend, and executes the generated Python against the Brian2 mushroom body simulation.

The paper itself is maintained in a sibling directory `fly-brain-paper/` so that the paper source is version-controlled alongside, but separately from, the running-log and development-tracking documents that the same directory accumulates during ongoing work.

## Reproducibility

All code runs on commodity hardware (tested on Windows 11, Python 3.13, Brian2 2.10.1). No GPU required. The hemibrain connectivity matrix is committed to the repository as `hemibrain_pn_kc.npz` (0.1 MB), so no neuPrint API access is needed to reproduce the results.

```bash
# Install dependencies
pip install brian2 numpy scipy matplotlib neuprint-python

# Run Phase 1-3 validation
python test_bridge.py

# Run Phase 4 VSA operations
python test_vsa_operations.py

# Run full e2e on hemibrain connectome (16/16 gate)
python test_codegen_e2e.py --hemibrain
```

## What This Means

This is a proof of concept that a programming language (Sutra) can execute meaningful computation on a connectome-derived biological neural circuit. The mushroom body isn't being used as a novelty substrate — it's performing the exact operation it evolved to do (sparse projection with winner-take-all cleanup), and that operation turns out to be identical to a core VSA primitive (snap-to-nearest). The PN→KC wiring is no longer a random approximation — it is the actual synaptic connectivity of an adult *Drosophila melanogaster* right mushroom body, as reconstructed in the Janelia hemibrain v1.2.1 connectome.

The code that runs on the fly brain looks like normal C#-style code. The biological substrate is hidden behind the same abstraction layer that a conventional CPU would be. That's the point of having a language at this level of abstraction.

## Future Work

Several extensions are clear directions for subsequent revisions of the substrate and the compiler backend:

1. **Promote KC-layer codes to the primary hypervector type.** The current bridge exposes `dim=140` as the hypervector type, matching the hemibrain PN input layer; the KC layer at 1882 is where the actual sparse VSA computation happens (see *A note on hypervector dimensionality* above). A future revision would promote the KC-layer code to the primary hypervector type, with the PN-layer adapter demoted to an auxiliary I/O concern.
2. **Scale to the full FlyWire adult connectome.** The current substrate uses the Janelia hemibrain v1.2.1 right mushroom body (140 PNs, 1882 KCs). The Princeton FlyWire release (Dorkenwald et al. 2024) provides the full adult *Drosophila* brain at ~140,000 neurons, which would increase prototype capacity from ~200–300 items to an estimated ~10,000–15,000 — enough to explore game-logic compilation targets (see `fly-brain/DOOM.md`).
3. **Empirical initiation for the fly-brain substrate.** The empirical-initiation pass used for silicon embedding substrates (see the companion paper's §4.2) applies unchanged to any substrate with an ANN-like structure; running it against the fly-brain substrate would produce the same kind of substrate-specific correction matrices and pathology reports.
4. **Associative learning for the MBON readout.** The learned linear readout described in §Challenge 3 is fit via ridge regression for engineering convenience. A biologically closer revision would replace the ridge fit with a training loop that applies a dopamine-gated learning rule (e.g., the one described in Aso et al. 2014) against a reward schedule, producing weights that trace a plausible learning trajectory rather than an analytical fit.

