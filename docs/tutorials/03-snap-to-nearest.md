# 03 — Snap-to-nearest

## What you'll learn

- Why `bind` and `unbind` alone aren't enough to do sustained computation
- What a **codebook** is and how `snap` uses it to clean up noisy vectors
- The geometric condition under which snap always recovers the right answer
- Where snap lives in the [three-tier Sutra model](https://github.com/EmmaLeonhart/Sutra/blob/master/planning/sutra-spec/02-operations.md) and why it's the "expensive" tier
- The empirical cost numbers: ~31 µs on a 20-atom codebook, ~31 ms on a 10k-atom codebook

## What snap is for

Bind, unbind, and bundle are *approximate* operations. Every time you do an unbind, you get a vector that is *similar* to the original filler but contaminated by crosstalk from the other things bundled in. Do enough of these in a row and the noise compounds — eventually the result is closer to nothing in particular than to the answer.

**Snap-to-nearest** is the cleanup pass. You compare the noisy vector against a *codebook* — a set of known-good vectors (your atoms, your basis vectors, your previously-stored fillers) — and you replace the noisy vector with the *nearest* codebook entry. As long as the noise is smaller than the distance to the second-nearest entry, you recover the right answer exactly. Then you continue computing on the cleaned-up vector and the loop can run indefinitely.

This is the operation that makes long Sutra computations numerically stable. Without it, sustained computation hits the noise floor in a few steps. With it, the [chained-computation result from the paper](../papers.md) holds for 10/10 cycles and the [fly-brain compile-to-brain demo](../papers.md) runs 16/16 decisions correctly because the spiking mushroom body itself acts as a biological snap (winner-take-all sparse activation).

## Try it live

Each labeled dot is a codebook atom. The yellow query point is what comes out of your last `unbind` — noisy, approximately-but-not-exactly one of the codebook entries. Drag the query around, or pick a target and push up the noise slider to simulate crosstalk from bundled pairs.

<div id="snap-widget"></div>

What you should see:

- As long as the query is closer to `target` than to any other atom, `snap(query) = target`. This is the success regime.
- As you raise noise (or drag the query past the halfway line between two atoms), snap returns the wrong atom. This is the failure mode — it's exactly what happens in Sutra when bundle depth exceeds the crosstalk budget.
- **The failure is silent.** Snap doesn't know it got the wrong answer. In real Sutra code this is what drives the recommendation to keep codebooks sparse and snap early, before crosstalk accumulates.

## The geometric condition

Snap is correct whenever the query lies in the **Voronoi cell** of the true target — the region of space closer to the target than to any other atom. For a codebook with `N` atoms spaced roughly uniformly, the radius of the Voronoi cell scales with the atom spacing. So:

- **Sparse codebook, few atoms:** large Voronoi cells, snap tolerates a lot of noise. Good for high bundle depth, cheap lookup.
- **Dense codebook, many atoms:** small Voronoi cells, snap breaks under even modest noise. Expensive lookup, too.

This is the fundamental knob you tune when designing Sutra data structures: **how many things do I need to distinguish at this step, and how much noise do I expect?**

## Why it lives in the non-algebraic tier

Snap is the tier-3 ("non-algebraic / vector-graph") operation in the [three-tier model](https://github.com/EmmaLeonhart/Sutra/blob/master/planning/sutra-spec/02-operations.md). The reason it's in tier 3 is that it requires *infrastructure* the algebraic tier doesn't: an Approximate Nearest Neighbor (ANN) index, typically an HNSW, or a smaller exact-search codebook for tiny problems.

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

## When snap is free

On a **biological substrate** — the fly-brain backend — snap isn't a separate operation at all. The mushroom body's Kenyon cells naturally enforce sparse coding via APL-mediated inhibition: only the top ~5% of KCs fire, and the set of firing KCs *is* the cleaned-up pattern. The codebook doesn't live in a Python data structure; it lives in the PN→KC synaptic weights. One circuit pass does `bind + bundle + snap` simultaneously, and it costs whatever the circuit costs to simulate (~300 ms for a 50-PN / 2000-KC / 1-APL / 20-MBON mushroom body in Brian2). See the [fly-brain paper](../papers.md) for the full compilation story.

This is one of the reasons the biological substrate comparison is interesting: `snap` is an infrastructure operation on silicon and a *free emergent property* on a connectome.

## Read next

- The [graph-to-linear-algebra interactive demo](../interactive/graph-to-linear-algebra.md) — a small interactive widget that walks you through the conceptual leap from "neurons in a graph" to "vectors in linear algebra," with a tiny fly-brain-shaped network as the example.
- The [Sutra paper](../papers.md) — §6.4 has the snap cost numbers, §6.2 has the chained-computation result that depends on snap working.
- The [fly-brain paper](../papers.md) — for how the mushroom body implements snap as a biological circuit rather than an algorithm.
