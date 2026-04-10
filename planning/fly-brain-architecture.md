# Running Akasha on a Simulated Fly Brain: Architecture

## Goal

Execute Akasha programs on a simulated *Drosophila* connectome, using biological neural circuits as the computational substrate for VSA operations. The mushroom body is the primary target because it already implements sparse random projection — structurally identical to VSA encoding.

## Why This Works (Theoretical Grounding)

The fly's mushroom body performs a **sparse random projection** from ~50 olfactory projection neurons (PNs) to ~2,000 Kenyon cells (KCs). Each KC receives input from ~7 random PNs. This is structurally identical to generating a random hypervector encoding:

- **Bundling** ↔ convergent input from multiple PNs onto a KC (superposition of odor components)
- **Binding** ↔ the sparse random connectivity matrix itself (each KC's unique input pattern acts as a random projection, analogous to sign-flip binding)
- **Snap-to-nearest** ↔ winner-take-all inhibition via APL (anterior paired lateral) neuron, which enforces sparse activation — only ~5% of KCs fire for any given input

The mushroom body output neurons (MBONs) then read out the KC population to drive behavior — this is the decode step, mapping population activity back to a decision vector.

## System Architecture

```
┌─────────────────────────────────────────────────────┐
│                  Akasha Source Code                   │
│         (looks like C#, compiles to VSA ops)         │
└─────────────────────┬───────────────────────────────┘
                      │ compile
                      ▼
┌─────────────────────────────────────────────────────┐
│            Akasha Compiler + Mapping File             │
│    (empirical initiation against fly brain model)    │
└─────────────────────┬───────────────────────────────┘
                      │ VSA operation sequence
                      ▼
┌─────────────────────────────────────────────────────┐
│              Spike-VSA Bridge Layer                   │
│                                                      │
│  encode(hypervector) → spike pattern (input currents)│
│  decode(spike trains) → hypervector (population read)│
└──────────┬──────────────────────────┬───────────────┘
           │ input currents           │ spike trains
           ▼                          │
┌─────────────────────────────────────────────────────┐
│           Brian2 Spiking Neural Network              │
│                                                      │
│  Connectome: FlyWire (Dorkenwald et al. 2024)        │
│  Subsystem: Olfactory circuit (~2,200 neurons)       │
│    - Antennal lobe (ORNs → PNs)                      │
│    - Mushroom body (PNs → KCs → MBONs)               │
│    - APL inhibitory neuron                            │
└─────────────────────────────────────────────────────┘
```

## Components to Build

### 1. Connectome Data Loader

Load the FlyWire connectome data for the olfactory subsystem:
- Neuron IDs, types, and positions for ORNs, PNs, KCs, APL, MBONs
- Synaptic connectivity matrix with weights
- Neurotransmitter types (excitatory/inhibitory sign)

**Data source:** FlyWire (codex.flywire.ai), accessed via `fafbseg-py` or direct CAVE/Codex API.

**Output:** A connectivity matrix and neuron metadata JSON suitable for Brian2 model construction.

### 2. Brian2 Olfactory Circuit Model

A spiking neural network model of the olfactory subsystem:
- **ORNs** (olfactory receptor neurons): Input layer, receives encoded stimuli
- **PNs** (projection neurons): ~50 neurons, relay from antennal lobe to mushroom body
- **KCs** (Kenyon cells): ~2,000 neurons, sparse random projection
- **APL** (anterior paired lateral): Single inhibitory neuron, enforces sparsity via feedback inhibition
- **MBONs** (mushroom body output neurons): ~34 types, readout layer

Neuron model: Leaky integrate-and-fire (LIF) is standard for large-scale connectome simulations. Synaptic weights from FlyWire.

### 3. Spike-VSA Bridge (The Key Innovation)

This is the novel component. Two directions:

#### Encode: Hypervector → Spike Pattern
- Map each dimension of the hypervector to a subset of ORN/PN input currents
- Options:
  - **Rate coding:** Vector component magnitude → firing rate of corresponding neuron group
  - **Population coding:** Distribute the hypervector across the PN population using the PN→KC connectivity as the encoding basis
  - **Direct injection:** Set KC initial membrane potentials proportional to vector components (bypasses antennal lobe, less biologically motivated but simpler)

#### Decode: Spike Trains → Hypervector
- Read MBON population activity over a time window
- Options:
  - **Rate decoding:** Mean firing rate of each MBON type → one component of output vector
  - **Temporal decoding:** Use spike timing patterns, potentially richer but harder
  - **Population vector:** Weighted sum of MBON identity vectors based on firing rates

#### Validation
- Encode a known hypervector, run through the circuit, decode the output
- Measure cosine similarity between input and output (round-trip fidelity)
- Test with multiple vectors to characterize noise and capacity

### 4. Empirical Initiation for Fly Brain Substrate

The Akasha compiler needs a mapping file for the fly brain substrate. This requires:
- Probing binding: encode two vectors, run bind operation through the circuit, measure output
- Probing bundling: encode superposed vectors, check if output is similar to both inputs
- Characterizing noise: how much signal degrades per operation
- Fitting correction matrices: optimize the encode/decode mapping for maximum algebraic fidelity

This is conceptually identical to empirical initiation for embedding models, but the substrate is a spiking neural network instead of a vector space.

### 5. Demo Program

The target demo for the paper: associative memory on the mushroom body.

```akasha
// Encode two odor stimuli as hypervectors
var odorA = embed("apple");
var odorB = embed("vinegar");

// Bind them together (association)
var association = bind(odorA, odorB);

// Store in mushroom body (encode → run → decode)
var stored = snap(association);

// Query: given odorA, retrieve odorB
var retrieved = unbind(odorA, stored);

// Check similarity
var score = similarity(retrieved, odorB);
// Expected: score > 0.5 (successful retrieval)
```

This Akasha code looks like normal C#-style code. But `bind`, `snap`, and `unbind` are executing on the fly brain circuit — bind maps to the KC random projection, snap maps to APL winner-take-all, unbind maps to MBON readout with input masking.

## Prerequisites (What We Need Before Building)

1. **Python environment:** Brian2, fafbseg-py, numpy, scipy
2. **FlyWire data access:** Register for CAVE/Codex API, download olfactory circuit connectivity
3. **Brian2 proficiency:** Build a minimal LIF network first, verify it works
4. **Existing fly brain models:** Check if Shiu et al. (Nature 2024) code is available and reusable
5. **Akasha compiler state:** The compiler needs to be far enough along to emit VSA operation sequences

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Encode/decode fidelity too low | Medium | High | Try multiple encoding schemes; start with direct KC injection |
| Brian2 simulation too slow for iteration | Low | Medium | Use smaller subnetwork; cache simulation results |
| FlyWire data access issues | Low | Medium | Fallback: use published connectivity matrices from papers |
| Mushroom body doesn't behave as VSA | Low | High | This would itself be a publishable negative result |
| Akasha compiler not ready in time | Medium | High | Can demonstrate with manual VSA operations first, add Akasha syntax later |

## Timeline (Rough)

1. Set up Brian2 + FlyWire data access
2. Build minimal olfactory circuit model
3. Implement encode/decode bridge
4. Test round-trip fidelity
5. Run Akasha demo program
6. Write up results

## References

- Dorkenwald et al. (2024). "Neuronal wiring diagram of an adult brain." Nature.
- Shiu et al. (2024). FlyWire whole-brain simulation. Nature.
- Dasgupta et al. (2017). "A neural algorithm for a fundamental computing problem." Science. (Mushroom body as locality-sensitive hashing)
- Kanerva (2009). "Hyperdimensional Computing." Cognitive Computation.
