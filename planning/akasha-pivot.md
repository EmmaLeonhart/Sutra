# Akasha: A Vector Programming Language

> **Language specification draft:** [`akasha-language-spec.md`](akasha-language-spec.md)

## What Is Akasha?

Akasha is a programming language that uses an LLM's embedding space as its computational substrate. Named after the Sanskrit concept of ākaśa — the fundamental space or aether through which all things exist and connect — the language operates in the same continuous, all-encompassing medium that the name evokes. Where the akashic records encode all knowledge in a non-physical plane, Akasha encodes computation in embedding space.

(Previously called "S2" after Kahneman's System 2 thinking. The S1/Akasha dual runtime architecture is retained internally.)

## Why Pivot From FOL Discovery?

The FOL discovery work proved the foundation: embedding spaces encode consistent vector arithmetic. 86 predicates discovered as FOL operations, r=0.78 correlation between consistency and prediction accuracy, two-hop composition working at 28.3% Hits@10. The question shifts from "can you find logic in embedding spaces?" to "can you *program* in them?"

Akasha is the answer to that question.

## Core Design Principles

### Fuzzy-by-Default

Everything operates on fuzzy logic. This is a fundamental inversion of how most languages work — normally you have crisp logic and bolt on probabilistic stuff as a library. In Akasha, uncertainty is the ground truth and precision is the special case.

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

### S1/Akasha Dual Runtime

Mirrors the cognitive architecture directly:

- **S1 layer**: Fast, cached, pattern-matched execution. The companion layer for things that have been resolved before.
- **Akasha layer**: Deliberate semantic computation. The actual vector-space reasoning.

A two-tier runtime where S1 handles the well-trodden paths and Akasha handles novel reasoning.

### TypeScript Parallel

In terms of how it actually runs, Akasha feels like TypeScript — heavy IDE dependency, where the tooling isn't just nice-to-have, it's load-bearing. TypeScript's type checker is basically a second interpreter that runs alongside the code. Akasha would be similar — the IDE/MCP layer holds the semantic context that makes the fuzzy vector operations meaningful.

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

These findings validate Akasha's core premise: embedding spaces are a viable computational substrate, not just a similarity lookup table.

## Design Conversation Archive

These shared conversations contain the architectural thinking behind Akasha. Deduplicated and roughly grouped.

### Core Akasha Design & Architecture
- https://claude.ai/share/6cefb991-f7b7-448c-91fe-e4467be7c8e5
- https://claude.ai/share/93604df1-2b68-44b6-b345-5d327aba38e7
- https://claude.ai/share/5ec27bcd-fd9e-484f-95f8-bf45d8521d2d
- https://claude.ai/share/b0488971-79fb-4cb5-9378-ad1dea1347a5
- https://claude.ai/share/01a2ae73-fab7-4ba2-a573-1a5606b1fa9c
- https://claude.ai/share/994b5cfe-927f-4f32-91e2-e20f80d59a40
- https://claude.ai/share/56bd2436-a5db-4149-9ad9-bb412fa9c796
- https://claude.ai/share/0b447bfc-880e-46f2-9009-66a7dfdda54d
- https://claude.ai/share/5dce9e73-25b4-4768-8916-f49b066430af
- https://claude.ai/share/694adfbb-aefe-4c4d-a348-7076067a6a85
- https://claude.ai/share/cb0a7d2c-6205-421e-a50c-4f391231ca51
- https://claude.ai/share/3396ea4d-4302-45b5-a1c9-d70bfd581c39
- https://claude.ai/share/b042ec32-688a-4f4b-abef-1a7daefee1ca
- https://claude.ai/share/f71f1ec6-f1d8-4b61-b6ad-77842aa73294
- https://claude.ai/share/0ce34966-ecb3-4f53-8939-5fad139f3452
- https://claude.ai/share/0d43ac48-9a4a-4859-aba3-54c740dfdd73
- https://claude.ai/share/faa50762-634e-4336-9a08-8ccac02a8533
- https://claude.ai/share/76f9b5b7-ca7c-4e77-89c2-ee4e8b858dff

### Also Referenced (duplicates from above)
- https://claude.ai/share/f7d0a9ba-f090-41bf-b8f9-c56910750a32
- https://claude.ai/share/48f40d39-183b-4dd2-b6a1-edcba104b8ac

## Status

Conceptual design phase. Core ideas are solidifying (fuzzy-by-default, vector primitives, `is_true` defuzzification, dual S1/Akasha runtime, MCP-as-runtime). No implementation yet. More documentation incoming.
