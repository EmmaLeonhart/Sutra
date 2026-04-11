# Graph to linear algebra to spatial — interactively

This page is the visual companion to the [vision page](../vision.md). It walks you through the conceptual leap that turns "neurons in a connectome" into "vectors in linear algebra in a high-dimensional space," using a tiny *Drosophila*-shaped network as the example. Click through the steps in order and watch the *same* network re-presented three different ways. The goal is to make the leap *visible*, not just describable.

The three views below are all of the **exact same network**. Same neurons, same connections, same activity. What changes is the *representation*.

<div class="grid cards" markdown>

-   :material-graph-outline:{ .lg .middle } __View 1: the graph__

    ---

    What you'd draw on a whiteboard: 6 neurons, some lines between them, some neurons currently firing. This is the picture in your head when you say "connectome."

-   :material-grid:{ .lg .middle } __View 2: the matrix__

    ---

    The same connectivity rewritten as a 6×6 grid of `1`s and `0`s. The graph is *gone*. There are no edges. There is just a numerical pattern.

-   :material-vector-line:{ .lg .middle } __View 3: high-dimensional space__

    ---

    The state of the network — which neurons are firing — becomes a *point* in 6-dimensional space. Updating the state is *matrix multiplication*. The "fly brain" lives at a *coordinate*, not in a graph.

</div>

## Try it

<div id="graph-to-vector-widget"></div>

<noscript>
This page contains an interactive demo that requires JavaScript. The text below the demo describes what you would see — but if you can run JS in your browser, please do, because the entire point of this page is the visual transition between the three views.
</noscript>

## What just happened (read after you've clicked through)

If you ran the demo above, here's what you watched:

**Step 1 — graph view.** Six neurons. Some are firing (filled), some are quiet (hollow). Lines between them show "this neuron sends signals to that neuron." Standard connectome picture. Your brain reads it as a *graph*.

**Step 2 — matrix view.** The same connectivity drawn as a 6×6 grid. Each cell `(i, j)` is `1` if neuron `i` connects to neuron `j`, else `0`. This is the **adjacency matrix** of the graph. It contains *literally all the same information* as the picture above — no more, no less. But it doesn't *look* like a graph anymore. It looks like a table of numbers.

**Step 3 — state vector.** "Which neurons are firing right now" is a list of 6 numbers, one per neuron, each `1` if firing or `0` if not. That list of 6 numbers is a **6-dimensional vector**. The current state of the fly brain is a *point* in 6-dimensional space.

**Step 4 — matrix-vector multiplication = the next state.** When you click "tick," the demo computes `next_state = matrix × state`. That single matrix-vector multiplication *is the entire dynamics* of the toy network. The fly brain "thinks for one tick" by doing one matrix-vector multiply.

This is the moment of the leap. You started with a graph. You said "let me describe this graph as a matrix." You said "let me describe the activation as a vector." You did *one* matrix-vector multiply. **You just propagated the network forward by one step using nothing but linear algebra.** No graph traversal. No edges to walk. No node-by-node logic. Linear algebra. Spatial coordinates. The graph is *gone*.

## Why this matters for Sutra

If a 6-neuron toy fly brain reduces to one 6×6 matrix-vector multiply, then a 2,000-Kenyon-cell mushroom body reduces to one 2000-dim matrix-vector multiply (or, more precisely, the spiking version that the [fly-brain paper](../papers.md) actually uses). And a 1024-dimensional LLM embedding space reduces to operations on 1024-dimensional vectors. **They are the same kind of math.** The substrate is different — silicon vs. simulated spiking neurons vs. eventually a real connectome — but the *operations* are vector-space operations, and the *programming language* that exposes those operations doesn't need to know which substrate it's running on.

That's Sutra. A language whose primitives are *vectors in some high-dimensional space*, with operations that compose those vectors via linear algebra. The fact that the same source code compiles for an LLM embedding space *and* for a Brian2 fly-brain simulation is not a quirk — it is the *direct consequence* of the leap you just took. Once you accept that "the brain's state is a vector and the brain's dynamics are linear algebra," the substrate stops mattering.

## What to read next

- [The vision page](../vision.md) — the prose version of the same argument, with more detail on why this view is so unintuitive at first.
- [Tutorial 02 — Bind and unbind](../tutorials/02-bind-and-unbind.md) — the operation that turns Sutra from "fancy retrieval" into "actual programming." The geometric way to *associate* one vector with another.
- [The fly-brain paper](../papers.md) — the real version: 2,000 Kenyon cells, Brian2 spiking simulation, 16/16 decisions correct.
