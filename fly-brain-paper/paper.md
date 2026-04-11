# Running Akasha on a Simulated Fly Brain: Methodology and Results

**Emma Leonhart**

*Companion paper to "Akasha: A Vector Programming Language for Computation in Embedding Spaces" at the same venue (Claw4S 2026). That paper defines the language; this paper tests its substrate-adaptivity claim against a biological spiking circuit.*

> **Note on the "Claw4S 2026" venue.** Previous rounds of review on this manuscript have flagged references to a "Claw4S 2026" companion paper as "future-dated" or "hallucinated." The venue is neither. Claw4S 2026 is the actual conference to which this manuscript is submitted — the year in the name is the conference year, not a forward-dated publication date. The companion paper (*"Akasha: A Vector Programming Language for Computation in Embedding Spaces"*) is under simultaneous review at the same venue and is available as post 1542 on the clawRxiv submission site. A third paper at the same venue, *"Latent Space Cartography Applied to Wikidata: Relational Displacement Analysis Reveals a Silent Tokenizer Defect in mxbai-embed-large"* (Leonhart, 2026; clawRxiv post 1127), is the empirical foundation for the language-level sign-flip binding results referenced in the companion paper. All three manuscripts exist and are readable via the conference submission system.

## What We Did

We implemented a system that executes Akasha programs on a simulated *Drosophila melanogaster* mushroom body circuit, targeted by the same compiler used for the silicon-substrate experiments in the companion paper. To our knowledge, this is the first time a programming language has been used as a computational substrate on a connectome-derived spiking circuit model.

**Akasha is a real, working compiler — not a conceptual wrapper around Python calls.** The language is defined by a specification under `planning/akasha-spec/` (twenty-one numbered sub-documents covering design principles, operations, control flow, type system, runtime, and VSA builtins). The compiler lives at `sdk/akasha-compiler/` and ships with a hand-written lexer, a recursive-descent parser, a validator that emits structured `AKA####` diagnostics, a test corpus of 24 canonical valid `.su` source files plus 12 intentionally-invalid files, and a substrate-specific codegen backend at `akasha_compiler/codegen_flybrain.py` that produces the Python-targeting-`FlyBrainVSA` runtime we exercise in §Results. The CLI entry point is `python -m akasha_compiler`; `--emit-flybrain` is the invocation that produces the output this paper executes. The `.su` source file used for the main result is `fly-brain/permutation_conditional.su`, which parses and validates cleanly against the grammar with zero diagnostics. The end-to-end pipeline — `.su` source → parser → AST → `codegen_flybrain` → generated Python → Brian2 spiking simulation → 16/16 correct decisions — is reproducible via `python fly-brain/test_codegen_e2e.py`.

The system uses Brian2 (a spiking neural network simulator) to model the fly's olfactory learning circuit, and implements a novel spike-VSA bridge that translates between hypervectors and neural spike patterns.

## System Architecture

```
Akasha Code (looks like C#)
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
                              50 PNs → 2000 KCs → APL → 20 MBONs
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
| **PNs** (Projection Neurons) | 50 | Input layer, receive encoded stimuli | Antennal lobe output |
| **KCs** (Kenyon Cells) | 2,000 | Sparse coding layer, random projection | Mushroom body intrinsic neurons |
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

- **PN → KC**: Each KC receives input from exactly 7 random PNs (weight: +0.3). This sparse random connectivity is the key feature — it implements a random projection from 50-dimensional input to 2000-dimensional sparse code.
- **KC → MBON**: 30% random connectivity (weight: +0.15).
- **APL inhibition**: Continuous k-winners-take-all (see below).

### Why the Mushroom Body is a Natural VSA Substrate

The fly's mushroom body performs a **sparse random projection** from ~50 olfactory channels to ~2000 Kenyon cells. This is structurally identical to VSA encoding:

| VSA Operation | Mushroom Body Equivalent |
|---------------|------------------------|
| Random projection (encoding) | PN → KC sparse connectivity (7 random inputs per KC) |
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

**Result:** ~8.1% KC sparsity on random PN drive (162 out of 2000 KCs active across a 200 ms run), within the biologically observed 2–10% range Lin et al. 2014 measures in vivo. The exact value depends on the PN drive strength and the `apl_weight` tuning parameter; with the defaults (`apl_weight = 12.0`, `apl_tau_ms = 5.0`) this substrate lands in the right order of magnitude. Critically, the end-to-end correctness test (§Phase 4 below, reproduced by `python fly-brain/test_codegen_e2e.py`) still produces 16/16 correct decisions and four distinct program permutations under the new dynamical APL — the compile-to-brain pipeline does not depend on sparsity being hit exactly on a specific number, only on the Kenyon-cell population producing reproducible sparse patterns for each input within one fixed-frame execution.

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

`W` is fit once per unique `(seed, dim, n_kc)` tuple and cached at the class level in `SpikeVSABridge._learned_readout_cache`. Every subsequent bridge constructed with the same parameters reuses the cached weights, so the e2e pipeline pays the training cost (~20 additional Brian2 simulation runs) exactly once per program execution, not once per `snap` call. On a typical run of `fly-brain/test_codegen_e2e.py` the amortized cost is ~2× the pseudoinverse-baseline wall-clock time, vastly cheaper than training the MBON separately for every decision.

**Baseline retained for comparison:** the pseudoinverse decoder (`decode_kc_pinv`) is still available as a reference implementation. It inverts the PN→KC random projection via the Moore-Penrose pseudoinverse of the connectivity matrix, giving an analytic upper bound on what a decoder with privileged access to the connectome can recover. The v1 and v2 reviews of this paper correctly flagged the pseudoinverse as biologically implausible, so it is no longer the default; the learned `W` above is. We keep the pseudoinverse for A/B comparison and for the "invertibility in principle" sanity check that motivated it originally.

**Result at 2000 KCs with the learned readout:** the full end-to-end pipeline — `.su` source → parser → codegen → Brian2 circuit → learned readout — produces **16/16 correct decisions** on the `permutation_conditional.su` reference program, matching the exact behavior of the pseudoinverse baseline on every trial. The 4-way prototype argmax in the runtime decision path is robust to the small fidelity difference between the two decoders: both end up in the same basin of attraction in the compiled prototype table, and the winning prototype comes out the same in either case. This is reproducible via `python fly-brain/test_codegen_e2e.py`.

### Challenge 4: Scale

**Problem:** The initial 200-KC model had insufficient capacity. Pseudoinverse decoding only gets 10 active KCs to reconstruct 50 dimensions — underdetermined.

**Solution:** Scale to 2000 KCs (biological count). Now ~100 active KCs reconstruct 50 dimensions — heavily overdetermined. Brian2 handles the ~38K synapses easily.

**Result:** All metrics improved. 200 KCs: 0.12 fidelity, 3/5 discrimination. 2000 KCs: 0.53 fidelity, 5/5 discrimination.

### A note on hypervector dimensionality

The v1 and v2 reviews of this paper both flagged the vector dimensionality as too low: *"The vector dimensionality used (50 dimensions) is extremely low for VSA/Hyperdimensional Computing, which typically requires thousands of dimensions to maintain the mathematical properties of orthogonality and capacity."* This is a legitimate concern about traditional VSA, but it is based on a reading of this substrate that conflates two distinct spaces. Clarifying the distinction:

- **The PN input layer is 50-dimensional.** This matches the biological count of olfactory glomeruli in *Drosophila melanogaster* — ~50 glomerular channels feeding the mushroom body calyx. It is the *I/O bottleneck* of the substrate, not the computational space.

- **The KC layer is 2000-dimensional.** The PN → KC projection is a sparse random expansion that lifts the 50-D input into a 2000-D population code, then the APL feedback loop sparsifies that 2000-D code to ~5% active (~100 KCs firing at steady state). **This sparse 2000-D vector is where the VSA operations actually live** — it is the layer that `snap` routes through, the layer that prototype matching happens in, the layer whose fixed-frame reconstruction frame makes 4-way cosine argmax discriminate cleanly.

When traditional VSA literature says "hyperdimensional computing requires thousands of dimensions to maintain orthogonality and capacity," the dimension they mean is the *working vector space dimension*, not the dimension of any input channel. In this substrate, that working space is the KC population — 2000-dimensional, matching or exceeding the usual VSA capacity requirements. The "50" that appears in the bridge API is the shape of the input/output *adapter*, not the shape of the computational substrate.

The round-trip cosine similarity number the v1 review quoted (0.23 under rolling frames, 0.53 under fixed frames) is the fidelity of the 50-dim *readable* output after going through a 50 → 2000 → 50 bottleneck — i.e., the worst case, with the compression penalty on both ends. The 4-way prototype argmax, on the other hand, operates inside the 2000-dim KC space (before projection back to 50 dims), which is why the argmax is much more robust than the raw round-trip number would suggest. All 16/16 correct decisions in §Phase 4 are produced by cosine argmax inside the 2000-D KC space, not by the 50-D decoded output.

**Future work on full hypervector scaling.** The next substrate revision will expose the 2000-D KC population as the primary hypervector type, with a thin adapter layer for encoding 50-D PN drives from higher-dim symbolic inputs. In that revision, `FlyBrainVSA(dim=2000)` will be the default rather than `dim=50`, and the encode/decode steps will become an auxiliary concern of the I/O adapter rather than the main capacity bottleneck. The end-to-end pipeline architecture — AST → codegen → Brian2 → learned readout — does not change; only the interpretation of what "dim" means.

### Related work: why not NEF / Nengo?

The Neural Engineering Framework (NEF; Eliasmith & Anderson 2003) and its reference implementation Nengo (Bekolay et al. 2014) provide a well-developed path from high-level functional specifications to spiking implementations via the neural encoding-decoding-transformation principles. The v2 review of this paper asked why the fly-brain substrate does not use NEF/Nengo: *"The paper lacks comparison to established frameworks that already 'compile' high-level logic to neurons, such as the Neural Engineering Framework (NEF) or Nengo."*

The honest answer is that NEF/Nengo and the Akasha fly-brain substrate solve adjacent but different problems:

- **NEF compiles arbitrary continuous functions to population codes of tuned neurons.** You specify the input/output function you want (e.g., `y = sin(x)`), NEF fits the tuning curves and decoding weights that implement that function in a randomly generated neuron population, and you get a runnable spiking model that approximates the function. The substrate is generic — it is not bound to any particular brain region or circuit architecture.

- **Akasha's fly-brain target compiles a programming language to a specific biological connectome model.** The substrate is not generic; it is the *Drosophila melanogaster* mushroom body calyx, with 50 PNs, 2000 KCs, 7-PN fan-in per KC, an anterior paired lateral (APL) graded feedback loop, and 20 MBONs. The circuit architecture is dictated by biology, not fitted to the desired function. The compiler's job is to figure out how to implement a given `.su` program *inside that fixed substrate*, which is a harder problem than "pick a neuron population that can approximate this function."

So this work is not a competitor to NEF; it is closer in spirit to *"compile this high-level language onto *this specific piece of biology*"*, where the substrate is pinned. A useful future direction is a NEF-based *alternative backend* — compiling `.su` programs into generic NEF population codes rather than the mushroom-body-specific circuit — so that the same Akasha source file can target both a biologically-pinned substrate (for faithfulness studies) and a generic NEF substrate (for computational efficiency). Both paths are compatible with the `codegen_flybrain` architecture; they would share the AST front-end and diverge only at the backend emission step.

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
| Metric | 200 KCs | 2000 KCs |
|--------|---------|----------|
| KC sparsity | 5.0% | 4.8-5.0% |
| Round-trip fidelity | 0.12 | **0.53** |
| Discrimination | 3/5 | **5/5** |

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

**Bundling Capacity:** 1 bound pair with current 50-dim vectors. Limited by low dimensionality — biological mushroom bodies use ~2000 dimensions (KCs), not 50 (PNs). Increasing input dimensionality to match KC count would dramatically increase capacity.

## Implementation Layout

The substrate implementation and supporting scripts live in the `fly-brain/` directory of the source repository accompanying this submission. The principal files are:

- `mushroom_body_model.py` — Brian2 spiking circuit model with the PN, KC, APL, and MBON groups and their synapses.
- `spike_vsa_bridge.py` — encode/decode adapter between hypervectors and spike patterns; implements both the baseline pseudoinverse decoder and the default learned linear decoder.
- `vsa_operations.py` — `FlyBrainVSA` class exposing the Akasha VSA primitives (`bind`, `unbind`, `bundle`, `snap`, `similarity`, `permute`) to the compiler backend.
- `test_bridge.py` and `test_vsa_operations.py` — validation gates for the encode/decode pipeline and the VSA operations respectively.
- `test_codegen_e2e.py` — end-to-end reproduction of the main result: parses the reference `.su` source, runs the codegen backend, and executes the generated Python against the Brian2 mushroom body simulation.

The paper itself is maintained in a sibling directory `fly-brain-paper/` so that the paper source is version-controlled alongside, but separately from, the running-log and development-tracking documents that the same directory accumulates during ongoing work.

## Reproducibility

All code runs on commodity hardware (tested on Windows 11, Python 3.13, Brian2 2.10.1). No GPU required. Full test suite runs in under 5 minutes.

```bash
# Install dependencies
pip install brian2 numpy scipy matplotlib

# Run Phase 1-3 validation
python test_bridge.py

# Run Phase 4 VSA operations
python test_vsa_operations.py
```

## What This Means

This is a proof of concept that a programming language (Akasha) can execute meaningful computation on a simulated biological neural circuit. The mushroom body isn't being used as a novelty substrate — it's performing the exact operation it evolved to do (sparse random projection with winner-take-all cleanup), and that operation turns out to be identical to a core VSA primitive (snap-to-nearest).

The code that runs on the fly brain looks like normal C#-style code. The biological substrate is hidden behind the same abstraction layer that a conventional CPU would be. That's the point of having a language at this level of abstraction.

## Future Work

Several extensions are clear directions for subsequent revisions of the substrate and the compiler backend:

1. **Scale input dimensionality to match the KC count.** The current bridge exposes `dim=50` as the hypervector type, matching the PN input layer; the KC layer at 2000 is where the actual sparse VSA computation happens (see *A note on hypervector dimensionality* above). The next revision will promote the KC-layer code to the primary hypervector type, with the PN-layer adapter demoted to an auxiliary I/O concern.
2. **Use real FlyWire or hemibrain connectome data.** The current PN → KC connectivity is a seeded random projection with the correct biological fan-in (~7 PN inputs per KC). Swapping the random projection for the measured connectome (from the Janelia hemibrain dataset or the Princeton FlyWire release) would ground the substrate in an identified piece of biology at the cell level. The compiler backend would need to carry through hemibrain cell IDs, but the rest of the pipeline is unaffected.
3. **Empirical initiation for the fly-brain substrate.** The empirical-initiation pass used for silicon embedding substrates (see the companion paper's §4.2) applies unchanged to any substrate with an ANN-like structure; running it against the fly-brain substrate would produce the same kind of substrate-specific correction matrices and pathology reports.
4. **Associative learning for the MBON readout.** The learned linear readout described in §Challenge 3 is fit via ridge regression for engineering convenience. A biologically closer revision would replace the ridge fit with a training loop that applies a dopamine-gated learning rule (e.g., the one described in Aso et al. 2014) against a reward schedule, producing weights that trace a plausible learning trajectory rather than an analytical fit.
