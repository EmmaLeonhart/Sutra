# Project Vision: Embedding-Mapping

## Core Question
**Can you do unsupervised ontology induction from an embedding space using vector arithmetic?**

Take any embedding space and discover:
- What consistent relational axes exist (directions that reliably encode some relation)
- What implicit class structure is present
- What propositions the geometry seems to encode

Then represent all of that in an RDF/graph layer as the output.

## Why This Matters
The embedding space encodes semantic relationships geometrically, but those relationships are implicit. This project makes them explicit by extracting logical structure (classes, relations, propositions) directly from vector geometry and expressing it as formal knowledge (RDF triples, ontology).

## Starting Point
Import triples from Wikidata where each triple becomes an **edge** (line between two points) in embedding space. Start with nouns. Propositions and sentences come later.

## Two Interpretation Approaches (to explore)
1. **Supervised grounding** — seed with known relations, see how far they generalize
2. **Unsupervised clustering of displacement vectors** — find consistent axes first, label later

## What This Is NOT
- Not just similarity visualization (Gephi/Sigma.js can do that)
- Not RAG or semantic search
- The graph is a **ground truth layer** compared against embedding geometry, not a visualization of it
