# Runtime Architecture

## S1/Sutra Dual Runtime
Mirrors the cognitive architecture:

- **S1 layer:** Fast, cached, pattern-matched execution. Lookup tables, precomputed results, memoized operations. Handles the well-trodden paths.
- **Sutra layer:** Deliberate semantic computation. The actual vector-space reasoning. Handles novel inputs and complex chains.

Like TypeScript's type checker running alongside JavaScript execution, Sutra's semantic layer runs alongside cached fast-path execution. The S1 cache is populated by Sutra computation — as patterns recur, they graduate from expensive deliberate reasoning to cheap cached lookup.

## MCP Server as Runtime Component
The MCP server is not an IDE add-on. It is part of the runtime:
- Resolves long-range semantic dependencies that no single file can capture
- Holds the semantic context that makes fuzzy vector operations meaningful
- Provides the ANN infrastructure for non-algebraic operations (snap, cone, hop)
- Manages the codebook / cleanup memory
- Handles entity resolution (same surface form → different vectors depending on context)

## Empirical Initiation (Summary)
Sutra does not impose algebraic structure on an embedding space. It **discovers** what structure already exists and calibrates to it.

At compile time, the compiler probes a target embedding model's space:
1. Tests whether binding/unbinding work reliably (they do in most naturally-learned spaces)
2. Fits projection matrices that make the space behave like a well-formed VSA
3. Outputs a mapping file (matrices + lookup tables)

The same Sutra source code compiles differently for different embedding models, like C compiling for x86 vs ARM. The "instruction set" is the geometry of the target space.

See [Empirical Initiation (Expanded)](07-empirical-initiation.md) for full details.
