# Empirical Initiation (Expanded)

## The Core Idea

Sutra does not assume any embedding space has the right algebraic properties. It **probes and calibrates** at compile time. This is called empirical initiation — the compiler characterizes the target space before generating code for it.

The analogy: C compiles differently for x86 and ARM because the instruction sets are different. Sutra compiles differently for mxbai-embed-large and nomic-embed-text because the geometric properties are different. The "instruction set" is the geometry of the target space.

## The Probing Process

**Step 1 — Test algebraic operations.**
- Generate random vectors in the target space
- Test binding: does `a * b` produce a vector dissimilar to both `a` and `b`?
- Test unbinding: does `unbind(a, a * b) ≈ b`? How much noise?
- Test bundling: does `a + b` produce a vector similar to both `a` and `b`?
- Test capacity: how many items can be bundled before signal-to-noise drops below a usable threshold?
- Measure noise characteristics: Gaussian? Uniform? Correlated with input?

**Step 2 — Fit correction matrices.**
Naturally learned embedding spaces are not perfect VSA spaces. The algebraic operations work (this is the core finding from the FOL discovery work) but they work approximately. Empirical initiation fits **projection matrices** that improve algebraic fidelity:
- A matrix that rotates the space so binding produces maximally dissimilar outputs
- A matrix that projects onto the subspace where unbinding is most accurate
- A normalization that makes bundling capacity predictable

These matrices are specific to the target embedding model. They are the "compiled" form of Sutra's adaptation to a specific substrate.

**Step 3 — Build the mapping file.**
Output: a binary artifact containing:
- The correction matrices from Step 2
- Noise characterization (expected error per operation, capacity limits)
- Known pathologies detected during probing (degenerate dimensions, attention sinks)
- Codebook initialization (if applicable)

This mapping file is the Sutra equivalent of a compiled binary. The same Sutra source code + different mapping files = same program running on different embedding substrates.

## What "Same Source, Different Targets" Means

A concrete example:

```ak
result = bind(AGENT_role, "cat") + bind(ACTION_role, "sit") + bind(LOCATION_role, "mat")
agent = unbind(AGENT_role, result)
# agent ≈ embedding("cat")
```

On mxbai-embed-large (1024-dim):
- Vectors are 1024-dimensional float64
- Binding noise is ~0.15 cosine distance per operation
- Bundling capacity is ~12 items before SNR < 3
- Correction matrix rotates by ~7° to improve unbinding accuracy
- Known diacritic pathology: flag inputs containing macron characters

On nomic-embed-text (768-dim):
- Vectors are 768-dimensional float64
- Binding noise is ~0.12 cosine distance per operation
- Bundling capacity is ~9 items (lower dimensionality = less capacity)
- Correction matrix is different (different geometry)
- No known pathologies

The Sutra source code is identical. The mapping file handles the differences. The programmer writes semantic operations; the compiler generates substrate-specific code.

## Validation Gates

Empirical initiation should include **validation gates** — minimum requirements a substrate must meet:

- Binding dissimilarity: `similarity(a, a*b) < threshold` (the binding actually encrypts)
- Unbinding accuracy: `similarity(b, unbind(a, a*b)) > threshold` (you can recover fillers)
- Bundling capacity: at least N items before SNR drops below usability
- No catastrophic pathologies detected (attention sinks, degenerate dimensions)

A substrate that fails validation is rejected. The compiler refuses to generate code for it. This is Sutra's equivalent of a platform compatibility check.
