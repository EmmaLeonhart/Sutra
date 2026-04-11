# 03 — Snap-to-nearest

> **Status: tutorial stub.** The other tutorials in this series are full walkthroughs; this one is a placeholder while the prose is written. The mechanics described here are correct — what's missing is the side-by-side code-and-explanation polish the other tutorials have.

## What snap is for

Bind, unbind, and bundle are *approximate* operations. Every time you do an unbind, you get a vector that is *similar* to the original filler but contaminated by crosstalk from the other things bundled in. Do enough of these in a row and the noise compounds — eventually the result is closer to nothing in particular than to the answer.

**Snap-to-nearest** is the cleanup pass. You compare the noisy vector against a *codebook* — a set of known-good vectors (your atoms, your basis vectors, your previously-stored fillers) — and you replace the noisy vector with the *nearest* codebook entry. As long as the noise is smaller than the distance to the second-nearest entry, you recover the right answer exactly. Then you continue computing on the cleaned-up vector and the loop can run indefinitely.

This is the operation that makes long Akasha computations numerically stable. Without it, sustained computation hits the noise floor in a few steps. With it, the [chained-computation result from the paper](../papers.md) holds for 10/10 cycles and the [fly-brain compile-to-brain demo](../papers.md) runs 16/16 decisions correctly because the spiking mushroom body itself acts as a biological snap (winner-take-all sparse activation).

## Why it lives in the non-algebraic tier

Snap is the tier-3 ("non-algebraic / vector-graph") operation in the [three-tier model](https://github.com/EmmaLeonhart/Akasha/blob/master/planning/akasha-spec/02-operations.md). The reason it's in tier 3 is that it requires *infrastructure* the algebraic tier doesn't: an Approximate Nearest Neighbor (ANN) index, typically an HNSW, or a smaller exact-search codebook for tiny problems.

Concretely:

```c
// Construct a query vector via a bunch of binds and bundles.
vector noisy = unbind(agent_role, sentence_bundle);

// Clean it up against the codebook.
vector clean = snap(noisy);
```

`snap` returns the codebook vector closest to `noisy`. If you wired up the codebook with `cat`, `dog`, `mouse`, `bird`, and `noisy` is a noisy version of `cat`, you get back the *exact* `cat` vector, not the noisy one. From here on out, all the noise that accumulated in the unbind is gone.

## Cost

On a 20-item codebook, snap is ~31 µs (vs. ~7 µs for bind). On a 1k-item codebook, ~3.5 ms. On a 10k-item codebook, ~31 ms. **The critical observation: even at 10k items, snap is 8× cheaper than embedding a single text via the actual LLM** (~250 ms). So snap is "the expensive one" in the algebraic-vs-non-algebraic split, but cheap relative to the LLM forward pass that produced the embeddings in the first place. You can afford to snap aggressively.

## What's missing from this tutorial

A side-by-side code walkthrough (like in tutorial 02), the formal codebook-construction recipe, and a worked example showing how the cosine similarity to the second-nearest entry sets the noise tolerance. Coming in a future commit.

## Read next

- The [graph-to-linear-algebra interactive demo](../interactive/graph-to-linear-algebra.md) — a small interactive widget that walks you through the conceptual leap from "neurons in a graph" to "vectors in linear algebra," with a tiny fly-brain-shaped network as the example.
- The [Akasha paper](../papers.md) — §6.4 has the snap cost numbers, §6.2 has the chained-computation result that depends on snap working.
