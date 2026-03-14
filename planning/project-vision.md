# Project Vision: Embedding-Mapping

## What This Is
A program that automatically generates a complex vector map from a large number of geodesics. Geodesics are paths through vector space connecting entities that are related by Wikidata triples. Almost everything in the system is a geodesic — the map IS the geodesics.

The output is a dense, structured map of an embedding space that can be compared across different embedding models. Given the same Wikidata input, two different models will produce different geodesic maps — and the differences reveal what each model "understands" about semantic structure.

## Goal
Establish semantic relationships as vector operations through geodesics, and classify regions of the embedding space by density:

- **Oversymbolic** — crowded regions where too many unrelated things collide. The embedding model has insufficient resolution here.
- **Isosymbolic** — dense but well-structured regions where related things cluster appropriately. The model "gets it" here.
- **Undersymbolic** — sparse regions with unexpected distances and weirdness. The model hasn't learned coherent structure here.

The program systematically maps these regions by walking through Wikidata, generating geodesics, and tracking where collisions happen and where they don't.

## How It Works (Idealized Workflow)
1. Download/select an embedding model
2. Start from a seed entity on Wikidata (default could be something like Q133284072 "embedding" or customizable)
3. Do a **random walk through Wikidata**, importing entities and filling in geodesics
4. Aggressively seek collisions — try to find where different things land in the same region
5. Keep a running tally of:
   - All geodesics and which ones appear to be common vectors for common relationships
   - Density achieved at each region of the embedding space
   - Which vector operations (if any) each geodesic manifests
6. The walk continues until the map is dense enough to draw conclusions

## Geodesics as Comparable Objects
A geodesic is not just a measurement — it is an **object**. The geodesic connecting "Mount Everest" to "mountain" via P31 exists as a thing that can be compared across embedding spaces. In model A it has one length and direction; in model B it has another. The geodesic is constant; the geometry changes.

Geodesics are manifestations of vector operations. A geodesic is what happens when you perform a vector subtraction (or addition, or other operation) between two embedded texts. The operation is fixed by the triple; the result depends on the model. The core question is whether geodesics of the same property type actually ARE a consistent vector operation in a given space, or not.

There will be thousands of geodesics. The program examines whether they cluster into consistent operations or scatter — and that tells you what the embedding space actually encodes.

## What Makes This Different
- **Not similarity search.** We're not asking "what's near X?" — we're asking "what does the path between X and Y look like, and is it consistent with the path between A and B?"
- **Not visualization.** The geodesic map is a structured data artifact, not a picture. It can be queried, compared, and analyzed programmatically.
- **Model-agnostic.** The same Wikidata source generates maps for any embedding model. The map is the benchmark.

## Extension: LLM Embedding Tracing
As a further goal, run a DeepSeek or other LLM and examine the internal embeddings it uses during inference. Trace the embeddings through the model's layers to get a "vibe chain" — the sequence of embedding-space positions the model traverses while processing a prompt. This is a path toward **explainable AI for LLMs**: if we can map the embedding space with geodesics, we can interpret what the model is "thinking about" at each step by locating its internal states on the map.

## Inspiration
This work is inspired by and builds on the concepts in:
- Tao et al. (2022), "Mapping the Landscape of Artificial Intelligence Applications against COVID-19" (https://dl.acm.org/doi/epdf/10.1145/3503914) — systematic mapping methodology applied to a different domain

See also `redoing-paper/` subtree for prior work on neurosymbolic embedding analysis (oversymbolic/isosymbolic/undersymbolic classification, Linnaean hierarchy experiments, semantic grid analysis).

## Two Interpretation Approaches (to explore)
1. **Supervised grounding** — seed with known relations, see how far they generalize
2. **Unsupervised clustering of displacement vectors** — find consistent axes first, label later
