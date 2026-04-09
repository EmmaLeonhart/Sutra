# Fly Brain Program Plan

## Decisions

- **Substrate**: Literal connectome (FlyWire/FAFB/Hemibrain — real neuron connectivity data)
- **Complexity**: Doesn't need to be complex. Just needs to be something.
- **Role of fuzziness**: Not load-bearing. Fuzziness exists as a decision maker for hyperdimensional processing — it replaces the need for flow control. The if-statement isn't branching logic in the conventional sense; it's the point where a high-dimensional vector computation collapses into a discrete outcome.

## The Idea

Run an S2 program on the literal Drosophila connectome. The program is an if-statement about smell.

The fly's olfactory circuit is already doing what S2 does: vectors in, hyperdimensional processing, fuzzy-to-discrete collapse out. The connectome gives us the actual wiring — the matrix that transforms smell vectors into behavior. S2 doesn't simulate the fly brain. It runs *on* it, treating the connectome as the substrate the way it would treat an LLM's embedding space.

## The Connectome as Substrate

### Available Data
- **FlyWire** — full adult Drosophila brain, ~130,000 neurons, synapse-level connectivity
- **Hemibrain** (Janelia) — half brain, ~25,000 neurons, mature dataset with typed neurons
- **Larval connectome** — complete, smaller (~3,000 neurons), fully mapped

The olfactory circuit is one of the best-annotated subsystems in all of these datasets. The neurons have names. The connections have weights. The glomeruli are identified.

### What "Running On It" Means

The connectome is a weighted directed graph. That graph is a matrix. S2 operations become matrix operations on the connectome's adjacency/weight matrix:

- **`embed()`** = inject an activation pattern at the ORN layer (the "input" to the circuit). Instead of running a string through an LLM, we set activation values on the ~50 ORN types based on known odorant response profiles.
- **`*` (bind)** = matrix multiply through a connectivity layer. Propagating a signal from ORNs through Projection Neurons to Kenyon Cells *is* binding — the connectome's wiring does the transformation.
- **`+` (bundle)** = superposition of activation patterns. Multiple smells or multiple features combining into one representation.
- **`defuzzy()`** = readout from Mushroom Body Output Neurons (MBONs). The MBONs are literally the collapse point — they take the high-dimensional Kenyon Cell representation and produce a low-dimensional approach/avoid signal. That's defuzzification.

No metaphor needed. The connectome *is* the weight matrix. S2 runs on it the same way it runs on any embedding space, except this one is made of neurons.

## The Program

```s2
// Fly smells vinegar. Approach or avoid?
// Substrate: Drosophila connectome (olfactory circuit)

vector smell = embed("vinegar");
fuzzy appetizing = unsafeCast<fuzzy>(smell);

if (defuzzy(appetizing)) {
    return "approach";
} else {
    return "avoid";
}
```

That's it. Eight lines.

What each line actually does on the connectome:
1. `embed("vinegar")` — set ORN activation pattern to vinegar's known response profile (strong Or42b, moderate Or59b, weak others)
2. `unsafeCast<fuzzy>(smell)` — propagate that activation through the connectome: ORNs → AL → PNs → Kenyon Cells → MBONs. The output is a fuzzy value because the MBON response isn't binary — it's a graded signal reflecting how much the Mushroom Body's learned associations say "this is good."
3. `defuzzy(appetizing)` — collapse the MBON output to a decision. The fly's actual circuit does this via competing approach/avoid MBON populations. Whichever side wins is the bool.
4. The if-statement is the behavioral output. Approach or avoid.

The fuzziness here isn't a programming convenience — it's what the connectome actually computes. The `defuzzy()` call is where the hyperdimensional representation becomes a discrete action. No flow control needed in the vector space; the if-statement only exists at the boundary between computation and behavior.

## What's Needed to Make This Real

### 1. Connectome Data Access
Pick a dataset and extract the olfactory subcircuit:
- ORN → PN connectivity (antennal lobe wiring)
- PN → KC connectivity (mushroom body input)
- KC → MBON connectivity (mushroom body output)
- MBON weights for approach vs. avoid

This is a few matrices. The data is public.

### 2. ORN Response Profiles
Known from electrophysiology. The DoOR database (Database of Odorant Responses) has measured responses of each Drosophila ORN type to hundreds of odorants. `embed("vinegar")` becomes a lookup into this data.

### 3. S2 Substrate Binding
The mechanism by which S2 says "use this matrix as your embedding space." Currently S2 assumes an LLM embedding model. The connectome case would need:
- A way to specify the substrate at program initialization (empirical initiation)
- Matrix dimensions matching the connectome layers (50 ORNs → ~150 PNs → ~2,000 KCs → ~34 MBONs)
- `embed()` dispatching to ORN response profiles instead of an LLM

### 4. Nothing Else
The program is eight lines. The connectome does the work. S2 just needs to know which matrices to multiply through.

## Why This Matters

This isn't "running AI on a brain" in the hype sense. It's:
- A real program (if-statement)
- On a real substrate (connectome connectivity data)
- Doing a real computation (smell classification)
- That the substrate actually performs in nature (flies decide to approach vinegar)

S2 claims embedding spaces are computational substrates. The fly connectome is an embedding space (a biological one). If S2 can run on it, that's not a metaphor — it's a proof of concept that the language's computational model generalizes beyond LLMs to any space where vectors are transformed through learned weight matrices.
