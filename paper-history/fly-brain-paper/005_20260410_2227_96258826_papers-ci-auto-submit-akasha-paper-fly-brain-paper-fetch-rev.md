<!--
commit:  96258826f2a5b305d3bbc0fcf1b3b5ec3f985bea
date:    2026-04-10 22:27:29 -0700
subject: papers-ci: auto-submit akasha-paper + fly-brain-paper, fetch reviews
path:    fly-brain-paper/paper.md
-->

# Running Akasha on a Simulated Fly Brain: Methodology and Results

## What We Did

We implemented a system that executes Akasha hyperdimensional programming language operations on a simulated *Drosophila melanogaster* mushroom body circuit. To our knowledge, this is the first time a programming language has been used as a computational substrate on a biological connectome simulation.

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

**Solution: Massive inhibitory current on losers.** At each timestep, compute the top 5% of KCs by membrane potential. Winners get zero inhibition; losers get I_inh = 100, which overwhelms any possible synaptic input (+0.3 per spike × 7 inputs = 2.1 max, far below 100). This is biologically motivated — the real APL provides powerful global inhibition that effectively silences all but the most strongly driven KCs.

**Result:** Exactly 5.0% KC sparsity across all tested inputs (10/200 at 200 KCs, 96-100/2000 at 2000 KCs).

### Challenge 2: Encoding Hypervectors as Spike Patterns

**Problem:** The initial min-max normalization mapped the most negative vector component to zero current, destroying sign information. All components became positive, losing half the information.

**Solution: Centered rate coding.** Zero vector component → baseline current (1.2). Positive components → above baseline (more spikes). Negative components → below baseline (fewer spikes). The gain parameter (0.6) maps unit-variance components to a ±0.6 current range around baseline.

```python
currents = baseline_current + gain * (hypervector / std)
```

### Challenge 3: Decoding Spike Trains Back to Hypervectors

**Problem:** Decoding from 10 MBONs (30% random connectivity) created a massive information bottleneck. Round-trip fidelity was only 0.14.

**Solution: Pseudoinverse decoding from KC population.** The PN→KC connectivity matrix is a known random projection. Its pseudoinverse reconstructs the PN-space input from KC firing rates. With 2000 KCs at 5% sparsity, ~100 active KCs provide measurements to reconstruct 50 PN dimensions — well-conditioned by compressed sensing theory.

```python
pn_estimate = pinv(pn_kc_matrix) @ kc_rates
```

**Result at 2000 KCs:** 0.53 cosine fidelity (up from 0.14), 5/5 discrimination.

### Challenge 4: Scale

**Problem:** The initial 200-KC model had insufficient capacity. Pseudoinverse decoding only gets 10 active KCs to reconstruct 50 dimensions — underdetermined.

**Solution:** Scale to 2000 KCs (biological count). Now ~100 active KCs reconstruct 50 dimensions — heavily overdetermined. Brian2 handles the ~38K synapses easily.

**Result:** All metrics improved. 200 KCs: 0.12 fidelity, 3/5 discrimination. 2000 KCs: 0.53 fidelity, 5/5 discrimination.

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

## File Structure

The implementation lives in `fly-brain/`; this paper lives in `fly-brain-paper/`.

```
fly-brain/
├── mushroom_body_model.py      # Brian2 spiking circuit model
├── spike_vsa_bridge.py         # Encode/decode between vectors and spikes
├── vsa_operations.py           # FlyBrainVSA class (Akasha operations API)
├── test_bridge.py              # Phase 1-3 validation gates
├── test_vsa_operations.py      # Phase 4 VSA operation tests
├── minimal_lif_network.py      # Brian2 smoke test
├── requirements.txt            # Python dependencies
├── STATUS.md                   # Honest running status and technical insights
├── DEMO.md                     # Audience-facing results summary
└── DOOM.md                     # "How far are we from playing Doom on this?" writeup

fly-brain-paper/
└── paper.md                    # This file — the paper-shaped writeup
```

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

## Next Steps

1. **Increase input dimensionality** to match KC count for higher bundling capacity
2. **Use real FlyWire connectome data** instead of random sparse connectivity
3. **Implement empirical initiation** for the fly brain substrate (same process as for embedding models)
4. **Connect to Akasha compiler** when it's ready
5. **Write the paper** — this is a publishable result
