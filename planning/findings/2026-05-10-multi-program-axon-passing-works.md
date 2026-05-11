# Multi-program axon passing works at MVP scale; lazy materialization remains motivated

**Date:** 2026-05-10
**Author:** Claude (Opus) under Emma's direction
**Demo:** `examples/multi_program_axon/`

## What was tested

Two `.su` programs in a single directory, compiled separately into
distinct Python modules. Producer builds a 5-key axon via
`axon_add`. Orchestrator pulls the result vector to CPU, serializes
to a numpy `.npy` file (the wire format). Consumer module loads the
file, hydrates back to a torch tensor, runs `axon_item` reads for
three of the five keys. Cosine analysis (host-side, monitoring only)
checks each recovered vector against the correct producer-bundled
filler and against a never-bundled decoy.

Both programs declare the same embedding model in `atman.toml`
(`nomic-embed-text`, dim 768). Same model + same key string →
same basis vector → same rotation operator. That's the only thing
that makes cross-program decode possible; if the two programs
disagreed on the embedding, the consumer's rotation would not
align with what the producer bundled.

## Result

End-to-end PASS. The recovered vectors are clearly closer to the
correct fillers than to the decoys:

| Key | Recovered cos vs correct filler | Recovered cos vs decoy | Margin |
|-----|---------------------------------|------------------------|--------|
| `animal_2` (`dog` vs `octopus`) | +0.4001 | +0.2004 | +0.1997 |
| `color_1`  (`red` vs `violet`)  | +0.4031 | +0.2052 | +0.1979 |
| `user_1`   (`alice` vs `xavier`)| +0.4498 | +0.1859 | +0.2639 |

The wire is 3600 bytes per axon (868-dim float32 + numpy header).

## Side observation from the earlier draft

The first draft of this demo bundled 12 keys in the producer with
nomic embeddings as fillers. With that bundle size, recovery for
`animal_2` returned `cat` instead of `dog` — both nomic-embedded
animal vectors that cluster tightly in embedding space (cosine
similarity ~0.7). The crosstalk from the other 11 bound pairs was
enough to flip the cosine ranking between two already-close
candidates.

**This is the worst case, not the typical case.** Bundling 12
LLM embeddings into one bundle is the high-crosstalk regime by
construction — 12 × 768-d of structured information squeezed into
868-d of synthetic-block-extended bundle. It's the rotation-
binding capacity property documented in
`2026-04-22-rotation-binding-capacity-results.md`, hitting harder
than usual because the candidate set is already close in embedding
space.

For OS-shaped Sutra IPC the picture is qualitatively different —
see `planning/sutra-spec/axons.md`-adjacent design and the project
memory `project_axon_ipc_payload_is_strings_and_numbers.md`. Real
IPC payloads are strings (codepoint-array packed in the synthetic
block) and numbers (complex hypervectors at AXIS_REAL/IMAG/TRUTH).
Both live in the synthetic block, away from the semantic-block
crosstalk region; the capacity story is much friendlier there.
Embeddings are expensive AND noisy when bundled deep — not the
filler shape OS code should reach for.

The cat/dog 12-key wall is also a reason the spec's lazy-
materialization optimization is worth eventually building (prune
the unread keys at compile time, less to bundle, less crosstalk).
But that's an LLM-embedding-demo-specific motivation; the OS use
case mostly avoids the cap by not using embeddings as fillers in
the first place.

## What this validates in `axons.md`

- ✅ "Underneath the surface API, an axon is a fixed-width vector
  produced by rotation binding over a codebook of roles." — verified;
  the vector that crosses the wire is exactly that.
- ✅ "Same key string → same basis vector across programs" (implicit
  in the spec's "string keys are compile-time identifiers"). The
  cross-program decode would not work otherwise.
- ⚠️ "Only the keys referenced in the receiving code are
  materialized" — *not yet implemented*. The MVP transmits the full
  bundle. Producer-side pruning is the natural next compiler pass.

## What this validates in `program-structure.md`

- The "open question: should multi-file projects exist, and how
  would they share declarations" is *partially* addressed by this
  demo: both programs share an `atman.toml` for embedding-model
  agreement. The Sutra source files themselves don't import from
  each other — they're connected through the orchestrator
  (`_run.py`), which compiles both and pipes one's output to the
  other.
- A more idiomatic shape would be a Sutra-side import or
  cross-program function-call mechanism that keeps the wire-passing
  invisible to the program author. That's substantially more work
  and not blocking — the orchestrator pattern is enough to prove
  the substrate side works.

## Cross-cuts

- **Module imports** (landed 2026-05-10, `5ad16093`) handle inter-
  program declarations at the *single-process* level by inlining.
  This finding handles *separate-process* axon passing through
  serialization. The two together cover the spec's "axons cross
  program boundaries" claim from both angles; lazy materialization
  is the optimization layer on top of either.
- **Capacity** (`2026-04-22-rotation-binding-capacity-results.md`)
  is the underlying limit. Lazy materialization pushes back the
  wall, but doesn't remove it; for very wide axons the right answer
  remains "lift to a richer substrate (extended-state slot
  rotation, MLP attractor cleanup) or reduce key count."

## Decision

Demo lands as-is. Lazy-materialization analyzer is the next layer
when there's a concrete user (Yantra, multi-program TS via the
import system, or a real cross-process Sutra app). The capacity
finding stands as the real-world headwind motivating that work.
