---
name: akasha-language
description: Reproduce the empirical grounding for "Akasha: A Vector Programming Language for Computation in Embedding Spaces" — sign-flip binding capacity (14/14 on GTE-large/BGE-large/Jina-v2), chained computation (10/10 bind-unbind-snap cycles), multi-hop composition across structures, empirical initiation validation gates across four substrates, and the compile-to-brain extension (see fly-brain-paper/ for details on the biological substrate result).
allowed-tools: Bash(python *), Bash(pip *)
---

# Akasha: A Vector Programming Language

**Author: Emma Leonhart**

This skill reproduces the empirical findings underlying *"Akasha: A Vector Programming Language for Computation in Embedding Spaces"* — the paper that frames LLM embedding spaces as the computational substrate for a programming language, rather than merely a retrieval index or a semantic similarity surface.

**Source:** `sutra-paper/` (this directory), with runtime scripts under `sutra-paper/scripts/`. The biological-substrate result reported in §6.6 is reproduced by the sibling `fly-brain-paper/` skill; see that paper's SKILL.md for the mushroom-body pipeline.

## What this reproduces

1. **Sign-flip binding decisively beats Hadamard on natural embeddings.** The traditional VSA binding operation (Hadamard / elementwise product) fails on frozen general-purpose embedding spaces because natural embeddings are correlated and anisotropic — crosstalk from non-orthogonal role vectors overwhelms the target filler at 2+ bundled pairs. Sign-flip binding (`a * sign(role)`) strips magnitude correlation and achieves **14/14 correct snap recoveries** at 14 bundled role-filler pairs on GTE-large, BGE-large-en-v1.5, and Jina-v2-base-en. Costs 6.6 µs per operation — 4.4× Hadamard. (§6.2 of the paper.)

2. **Sustained computation survives 10 bind–unbind–snap cycles.** Repeatedly constructing a 3-role bundled structure, unbinding the target, snapping, and feeding the result into the next structure gives **10/10 correct** recoveries on sign-flip binding. Cosine stays in 0.58–0.65 throughout the chain. (§6.2.)

3. **Multi-hop composition across structures works.** Extract a filler from structure A (`agent=cat, action=sit`), insert it into a different role in structure B (`agent=dog, patient=extracted_cat`), then extract from B. All three cross-structure extractions return the correct filler. This is the fundamental operation required for multi-step inference. (§6.2.)

4. **Cross-substrate validation via empirical initiation gates.** Four embedding models (GTE-large, BGE-large, Jina-v2, mxbai-embed-large) are probed for algebraic fitness. Sign-flip binding improves effective capacity **3–5×** over Hadamard across all tested substrates. The mxbai pathology (diacritic attention sink) is caught by pathology-specific probes even though mxbai passes all algebraic gates. (§6.3, §6.5.)

5. **Compile-to-brain as the far-edge stress test of substrate-adaptivity.** §6.6 reports that the same compiler used for the silicon experiments in §6.1–§6.5 also targets a Brian2 spiking simulation of the *Drosophila melanogaster* mushroom body, with 16/16 correct decisions across four program variants. Full reproduction lives in `fly-brain-paper/` and its SKILL.md.

## Prerequisites

```bash
pip install numpy scipy sentence-transformers
```

The binding/bundling experiments use the `sentence-transformers` library to load GTE-large, BGE-large-en-v1.5, and Jina-v2-base-en. First-run model downloads are large (each model is 500 MB+); subsequent runs are cached.

## Reproducing each result

Every script in `sutra-paper/scripts/` is runnable standalone and writes its outputs to `sutra-paper/data/` so the paper's tables can be regenerated deterministically.

**Sign-flip binding vs. alternatives (six binding operations on GTE-large):**
```bash
python sutra-paper/scripts/binding_alternatives_experiment.py
```
Outputs `sutra-paper/data/binding-alternatives-gte-large.json`. Produces the table in §6.2 showing Hadamard failing at 2+ roles while sign-flip, permutation, circular convolution, FFT correlation, and rotation binding all achieve 7/7 recovery at 7 bundled roles.

**Deep sign-flip capacity test (14 roles):**
```bash
python sutra-paper/scripts/signflip_deep_test.py
```
Outputs `sutra-paper/data/signflip-deep-gte-large.json` and `sutra-paper/data/signflip-cross-substrate.json`. Runs sign-flip through 14 bundled pairs, 10-step chained computation, and multi-hop composition across all three tested substrates.

**Chain depth and snap cost analysis:**
```bash
python sutra-paper/scripts/chain_depth_experiment.py
```
Outputs `sutra-paper/data/chain-depth-gte-large.json`. Demonstrates that pure bind–unbind chains without snap accumulate unrecoverable noise, while snap-interleaved chains stabilize.

**Bundling noise characterization:**
```bash
python sutra-paper/scripts/bundling_noise_experiment.py
```
Outputs `sutra-paper/data/bundling-noise-gte-large.json`. Quantifies how signal-to-noise degrades as more items are bundled into a single superposition — the main capacity ceiling in the algebraic tier.

**Cross-substrate empirical initiation gates:**
```bash
python sutra-paper/scripts/empirical_initiation.py
```
Outputs four files, one per substrate: `bge-large-initiation.json`, `gte-large-initiation.json`, `jina-v2-initiation.json`, `mxbai-large-initiation.json`. Each reports the substrate's binding dissimilarity, unbinding fidelity, bundling capacity, noise characteristics, and pass/fail on the validation gates.

**End-to-end Akasha demo programs on a live substrate:**
```bash
python sutra-paper/scripts/sutra_demos.py
```
Runs small Akasha programs against a chosen embedding model (GTE-large by default). Each demo shows the three-tier operation model in action: primitive scaffolding, algebraic VSA operations for the core computation, non-algebraic snap-to-nearest for cleanup.

## Runtime architecture

`sutra-paper/scripts/sutra_runtime.py` is the reference runtime used by the demos. It is a standalone Python implementation of:

- **Primitive tier:** scalars, tuples, bounded iteration
- **Algebraic tier:** bind (sign-flip and rotation variants), unbind, bundle, similarity, scalar multiply, projection
- **Non-algebraic tier:** snap-to-nearest via codebook lookup, cone traversal (directed neighborhood query), graph hop (typed traversal)

It loads an embedding model via `sentence-transformers`, runs the empirical initiation probe to measure the substrate's properties, fits correction matrices if needed, and exposes a Python API for executing Akasha programs. This is *not* the same runtime as the fly-brain compile-to-brain pipeline — that one targets Brian2 spiking neurons, lives in `fly-brain/vsa_operations.py`, and is reproduced by the `fly-brain-paper/` SKILL.

## Dependencies between files

- `sutra-paper/scripts/sutra_runtime.py` — reference runtime (imported by demos)
- `sutra-paper/scripts/sutra_demos.py` — end-to-end program demos
- `sutra-paper/scripts/binding_alternatives_experiment.py` — §6.2 binding table
- `sutra-paper/scripts/signflip_deep_test.py` — §6.2 14-role + chained + multi-hop
- `sutra-paper/scripts/chain_depth_experiment.py` — chain noise characterization
- `sutra-paper/scripts/bundling_noise_experiment.py` — bundling capacity curves
- `sutra-paper/scripts/empirical_initiation.py` — §6.3 cross-substrate validation
- `sutra-paper/data/` — JSON outputs consumed by the paper's tables
- `sdk/sutra-compiler/` — the reference Akasha compiler (parser + validator + codegen)
- `sdk/sutra-compiler/tests/corpus/valid/` — canonical `.su` source corpus
- `examples/*.su` — language tour
- `fly-brain-paper/` — the §6.6 biological substrate result, its own SKILL.md

## Limitations and caveats the paper itself states

- **Akasha is not Turing complete on algebra alone.** Fixed dimensionality caps superposition capacity and approximate retrieval introduces compounding errors. The paper argues that VSA algebra + ANN-backed non-algebraic operations + external graph memory is Turing complete, modeled on the CPU + RAM analogy.
- **Bind-precise (rotation) binding is 48× more expensive than sign-flip** (321 µs vs. 6.6 µs) and is only justified when accuracy matters more than speed at >7 bundled roles.
- **Cone traversal is the expensive tier.** Snap is O(log n) via HNSW, but non-algebraic operations always hit an external index.
- **Substrates can be algebraically sound and still have silent pathologies** — the mxbai diacritic defect is the canonical example. Validation must include pathology-specific probes beyond pure algebraic fitness.
- **The fly-brain result in §6.6 deliberately tests substrate-adaptivity at the far edge.** Loops are intentionally unsupported on that substrate, not a codegen oversight — see `fly-brain/STATUS.md` for why.
