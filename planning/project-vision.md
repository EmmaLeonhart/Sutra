# Project Vision: Embedding-Mapping

## What This Is
A program that automatically generates a complex vector map from a large number of geodesics. Geodesics are paths through vector space connecting entities that are related by Wikidata triples. Almost everything in the system is a geodesic — the map IS the geodesics.

The output is a dense, structured map of an embedding space that can be compared across different embedding models. Given the same Wikidata input, two different models will produce different geodesic maps — and the differences reveal what each model "understands" about semantic structure.

## Core Question
**What does the geometry of an embedding space actually encode, and how does it differ between models?**

By generating the same geodesic map across multiple vector spaces, you can ask:
- Do the same triples produce similar or different distances?
- Do some models encode certain relations more faithfully than others?
- Where do models agree and disagree about semantic structure?

## How It Works
1. Import entities from Wikidata with all their properties, labels, and aliases
2. Embed every text (labels, aliases, propositional realizations) into a vector space
3. For every triple, generate geodesics connecting subject and object embedding points
4. The resulting geodesic network IS the map — a structured overlay on top of the vector space

Since each entity can have multiple embeddings (label + aliases) and each property can have multiple realizations ("$SUB instance of $OBJ", "$SUB is a $OBJ"), a single triple fans out into many geodesics. The density and structure of this fan-out is itself informative.

## What Makes This Different
- **Not similarity search.** We're not asking "what's near X?" — we're asking "what does the path between X and Y look like, and is it consistent with the path between A and B?"
- **Not visualization.** The geodesic map is a structured data artifact, not a picture. It can be queried, compared, and analyzed programmatically.
- **Model-agnostic.** The same Wikidata source generates maps for any embedding model. The map is the benchmark.

## Starting Point
Mountains (Q8502) — 11 items, ~13K properties with realization templates. Scale up from here.

## Two Interpretation Approaches (to explore)
1. **Supervised grounding** — seed with known relations, see how far they generalize
2. **Unsupervised clustering of displacement vectors** — find consistent axes first, label later
