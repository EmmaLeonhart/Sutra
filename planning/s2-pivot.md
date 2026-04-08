# S2: A Vector Programming Language

## What Is S2?

S2 is a programming language that uses an LLM's embedding space as its computational substrate. Named after System 2 thinking (Kahneman) — slow, deliberate, effortful reasoning — the language literally implements this cognitive model. S2 processing is slow, deliberate, and effortful, and the language uses an LLM's embedding space as the substrate for computation. The language itself *embodies* the cognitive metaphor rather than just borrowing the name.

## Why Pivot From FOL Discovery?

The FOL discovery work proved the foundation: embedding spaces encode consistent vector arithmetic. 86 predicates discovered as FOL operations, r=0.78 correlation between consistency and prediction accuracy, two-hop composition working at 28.3% Hits@10. The question shifts from "can you find logic in embedding spaces?" to "can you *program* in them?"

S2 is the answer to that question.

## Core Design Principles

### Fuzzy-by-Default

Everything operates on fuzzy logic. This is a fundamental inversion of how most languages work — normally you have crisp logic and bolt on probabilistic stuff as a library. In S2, uncertainty is the ground truth and precision is the special case.

This maps directly onto how LLM embeddings actually work — nothing is ever fully true or false in that space.

### Vectors and Matrices as Primitives

Instead of integers and strings, the atomic types are geometric objects in semantic space. Pretty much everything is a vector or a matrix. Operations are things like similarity, projection, interpolation — meaning computation *is* geometry.

All operations are commutative. Every single object is a vector that is decomposed with certain operations.

### Defuzzification via Recursive `is_true`

You can defuzzify the logic to whatever extent you want, but you do that through recursive `is_true` statements. This is essentially a type system where "how true is this" is a first-class concern rather than a boolean afterthought.

`is_true(is_true(x))` could either converge toward certainty or oscillate depending on how you define the operator. Open design question: do you collapse toward 1.0 with each recursion, or is it more nuanced?

### Long-Range Dependencies

The semantics are too rich and context-dependent for any single file to fully capture. There are weird, long-range dependencies that you'd either have to guess at or build into the code somehow. This is a feature, not a bug — it means the tooling must be deeply integrated.

## Runtime Architecture

### S1/S2 Dual Runtime

Mirrors the cognitive architecture directly:

- **S1 layer**: Fast, cached, pattern-matched execution. The companion layer for things that have been resolved before.
- **S2 layer**: Deliberate semantic computation. The actual vector-space reasoning.

A two-tier runtime where S1 handles the well-trodden paths and S2 handles novel reasoning.

### TypeScript Parallel

In terms of how it actually runs, S2 feels like TypeScript — heavy IDE dependency, where the tooling isn't just nice-to-have, it's load-bearing. TypeScript's type checker is basically a second interpreter that runs alongside the code. S2 would be similar — the IDE/MCP layer holds the semantic context that makes the fuzzy vector operations meaningful.

### MCP Server as Runtime Component

An MCP server specifically set up so that it tells AI where an actual thing is. The tooling *becomes* part of the language runtime in a meaningful way. The language's semantics are too rich and context-dependent for any single file to fully capture, so the MCP server resolves those long-range dependencies.

## What Makes It Genuinely Novel

Most "AI-assisted" languages still compile to conventional computation. Using the embedding space as the substrate means the "execution environment" is fundamentally semantic rather than symbolic — operations would have meaning in a way that silicon arithmetic doesn't.

It feels less like a traditional programming language and more like a formal system for *reasoning under uncertainty* — closer to logic programming (Prolog) than Python, but operating in continuous rather than discrete space.

## Open Design Questions

- What are the primitives exactly? Vectors, attention patterns, something else?
- Is "control flow" even the right concept, or does it look more like constraint satisfaction?
- How do you handle determinism — since LLM outputs are probabilistic?
- Does `is_true` convergence collapse toward 1.0 or oscillate? What's the fixed-point behavior?
- Syntax: still solidifying the semantics before syntax design
- How to express the long-range dependencies in source code vs. leaving them to the MCP layer

## Connection to Prior Work

The FOL discovery paper (`VSA-paper/`) established that:
- Embedding spaces encode consistent vector arithmetic for semantic relationships
- These operations are discoverable automatically from Wikidata triples
- Prediction accuracy correlates with operational consistency (r=0.78)
- Multi-hop composition works (28.3% Hits@10)

These findings validate S2's core premise: embedding spaces are a viable computational substrate, not just a similarity lookup table.

## Status

Conceptual design phase. Core ideas are solidifying (fuzzy-by-default, vector primitives, `is_true` defuzzification, dual S1/S2 runtime, MCP-as-runtime). No implementation yet. More documentation incoming.
