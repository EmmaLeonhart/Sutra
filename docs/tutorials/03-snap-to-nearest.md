# 03 — Snap-to-nearest

## What you'll learn

- Why `bind` and `unbind` alone aren't enough for sustained computation
- What a **codebook** is and how cleanup uses it to recover noisy vectors
- The geometric condition under which cleanup always recovers the right entry
- How `argmax_cosine` (the cleanup primitive Sutra demos use today) and `snap` (the spec name for the operation backed by a real cleanup circuit) relate

## What cleanup is for

Bind, unbind, and bundle are *approximate* operations. Every unbind returns a vector that is *similar* to the original filler but contaminated by crosstalk from the other things bundled in. Do enough of these in a row and the noise compounds — eventually the result is closer to nothing in particular than to the answer.

**Cleanup** is the pass that fixes this. You compare the noisy vector against a *codebook* — a set of known-good vectors (your atoms, your basis vectors, your previously-stored fillers) — and replace the noisy vector with the *nearest* codebook entry by cosine. As long as the noise is smaller than the distance to the second-nearest entry, you recover the right answer exactly. Then you continue computing on the cleaned-up vector and the loop can run indefinitely.

This is what makes long Sutra computations stable. Without it, sustained computation hits the noise floor in a few steps.

## Try it live

Each labeled dot is a codebook atom. The yellow query point is what comes out of your last `unbind` — noisy, approximately-but-not-exactly one of the codebook entries. Drag the query around, or pick a target and push up the noise slider to simulate crosstalk from bundled pairs.

<div id="snap-widget"><noscript>(This page hosts an interactive snap-to-nearest widget that requires JavaScript. The prose below covers the same material; the widget is a live playground, not load-bearing content.)</noscript></div>

What you should see:

- As long as the query is closer to `target` than to any other atom, the cleanup returns `target`. This is the success regime.
- As you raise noise (or drag the query past the halfway line between two atoms), cleanup returns the wrong atom. This is the failure mode — exactly what happens in Sutra when bundle depth exceeds the crosstalk budget.
- **The failure is silent.** The cleanup primitive doesn't know it got the wrong answer. In real Sutra code this drives the recommendation to keep codebooks sparse and clean up early, before crosstalk accumulates.

## The geometric condition

Cleanup is correct whenever the query lies in the **Voronoi cell** of the true target — the region of space closer to the target than to any other atom. For a codebook with `N` atoms spaced roughly uniformly, the Voronoi cell radius scales with the atom spacing.

- **Sparse codebook, few atoms** — large Voronoi cells; cleanup tolerates a lot of noise. Good for high bundle depth, cheap lookup.
- **Dense codebook, many atoms** — small Voronoi cells; cleanup breaks under even modest noise. Expensive lookup, too.

This is the fundamental knob you tune when designing Sutra data structures: *how many things do I need to distinguish at this step, and how much noise do I expect?*

## How it shows up in `.su` source

Today the demos use `argmax_cosine` — the cleanup primitive that runs against an explicit candidate list (a Python tuple at the call site, a stacked-candidate matmul plus argmax in the emitted module):

```c
// Construct a noisy query via binds and bundles.
vector noisy = unbind(agent_role, sentence_bundle);

// Clean it up against the codebook.
vector clean = argmax_cosine(noisy, [v_cat, v_dog, v_mouse, v_bird]);
```

`argmax_cosine` returns the codebook vector closest to `noisy` by cosine. If you wired up the codebook with `cat`, `dog`, `mouse`, `bird`, and `noisy` is a noisy version of `cat`, you get the *exact* `cat` vector back, not the noisy one. From here on out, the noise that accumulated in the unbind is gone.

The spec also defines `snap` — a more general cleanup operation backed by a real attractor / cleanup circuit (rather than an explicit candidate list). The current PyTorch substrate doesn't have such a circuit, so `snap` is rejected at codegen time; programs use `argmax_cosine` against an explicit codebook instead. See [`planning/sutra-spec/operations.md`](https://github.com/EmmaLeonhart/Sutra/blob/master/planning/sutra-spec/operations.md) for the formal specification of both.

## Cost

The codebook lookup is one matrix-vector multiply (against a stacked-candidate matrix) plus an argmax. On a 20-entry codebook this is the cheap part of the program; on a 10k-entry codebook it is still cheap relative to a single LLM forward pass (which Ollama serves at hundreds of milliseconds per call). You can afford to clean up aggressively.

## Read next

- The [Sutra paper](../theory-and-paper.md) — characterizes the chained-computation regime that depends on cleanup working.
- The [operations spec](https://github.com/EmmaLeonhart/Sutra/blob/master/planning/sutra-spec/operations.md) — formal definitions of `argmax_cosine`, `snap`, and the rest of the primitive surface.
