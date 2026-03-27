# Trajectories

## What is a trajectory in this project?

A trajectory is a **line between two points in embedding space** that exists because a Wikidata triple connects the two entities at those points.

Given a triple like `Mount Everest (Q513) — instance of (P31) — mountain (Q8502)`:
- **Mount Everest** has embedding points (one for the label, one for each alias)
- **mountain** has embedding points (one for the label, one for each alias)
- The trajectory connects a specific Mount Everest text to a specific mountain text

Since Mount Everest has 17 embeddings (1 label + 16 aliases) and mountain has 4 embeddings (1 label + 3 aliases), this single triple produces **17 × 4 = 68 trajectories**.

## What a trajectory is NOT

A trajectory does **not** connect a subject or object to the property (predicate).

In `Mount Everest — instance of — mountain`:
- There IS a trajectory between "Mount Everest" and "mountain"
- There is NO trajectory between "Mount Everest" and "instance of"
- There is NO trajectory between "instance of" and "mountain"

The property "instance of" (P31) IS embedded as an entity in the vector space — it has a position and can participate in density analysis — but the relationship between a property and the things it connects is structural, not linguistic. The trajectory captures the semantic/linguistic distance between the subject and object.

## What properties do on trajectories

The property is stored as **metadata** on each trajectory. Every trajectory knows which triple it came from:
- `emb:subjectEntity` — the subject QID
- `emb:objectEntity` — the object QID
- `emb:predicate` — the property that connects them (e.g. P31)

This means you can query "show me all trajectories that exist because of P31 triples" without P31 itself being an endpoint.

## Trajectory properties

Each trajectory object stores:
- **subjectText / objectText** — the specific strings at each end (e.g. "Mt. Everest", "mtn.")
- **subjectTextType / objectTextType** — whether it's a "label" or "alias"
- **cosineDistance** — 1 - cosine similarity between the two embedding vectors
- **cosineSimilarity** — direct cosine similarity
- **euclideanDistance** — L2 distance between the vectors

## Why this matters

Trajectories let you ask questions like:
- What is the average distance for P31 (instance of) trajectories vs P17 (country) trajectories?
- Do aliases cluster tightly around their label, or spread out?
- Are there triples where subject and object are very far apart in embedding space? (potential mismatches between ontological and distributional semantics)

## Future: propositional trajectories

The property could participate in trajectories if we embed the full proposition as a sentence — e.g. "Mount Everest is an instance of mountain." This propositional form would create a new embedding point, and trajectories could connect it to the subject, object, and property embeddings. This is not yet implemented.
