# embedding-mapping

## Workflow Rules
- **Commit early and often.** Every meaningful change gets a commit with a clear message explaining *why*, not just what.
- **Commit and push everything.** Always push to remote after committing. No local-only work.
- **Do not enter planning-only modes.** All thinking must produce files and commits. If scope is unclear, create a `planning/` directory and write `.md` files there instead of using an internal planning mode.
- **Keep this file up to date.** As the project takes shape, record architectural decisions, conventions, and anything needed to work effectively in this repo.
- **Update README.md regularly.** It should always reflect the current state of the project for human readers.

## Project Description
Unsupervised ontology induction from embedding spaces. Takes embedding geometry and extracts logical structure (classes, relations, propositions) as RDF. Starting with Wikidata triple imports where each triple = an edge between two embedded concepts.

## Architecture and Conventions
- **Stack:** Python + rdflib (with RDF-star) + numpy + Ollama (mxbai-embed-large). No graph DB yet (start simple).
- **Source data:** Wikidata API + SPARQL endpoint
- **Embeddings:** mxbai-embed-large (1024-dim) via Ollama, matching redoing-paper
- **Planning docs:** `planning/` directory for design decisions and roadmap
- See `planning/architecture-decisions.md` for rationale

## Development Philosophy
- **Adding data IS building the pipeline.** In this early stage, every import is also pipeline development. The import tooling and the data graph grow together.
- **Geodesics are first-class objects.** Each geodesic (line between two embedding points connected by a triple) is its own RDF object with pointers to both endpoint strings, distance, and the parent triple.

# currentDate
Today's date is 2026-03-13.
