---
title: What is Sutra?
description: A plain-language explanation of what Sutra actually does.
---

# What is Sutra?

A plain-language explanation, no prior programming-language theory required.

## The one-sentence version

Sutra is a **geometric tensor programming language**: every value is a tensor, every operation is tensor arithmetic, and programs describe transformations of a point inside a geometric space rather than step-by-step machine instructions. Most programming languages ask *"what should the computer do, step by step?"* Sutra asks a different question: *"what starting conditions should I set up, so that the reaction I want happens on its own?"*

## Think of a Rube Goldberg machine

The easiest way to picture a Sutra program is a Rube Goldberg machine. You don't tell the marble what to do at each step. You place the ramps, the fans, the tipping buckets, and you drop the marble in. Whether the machine pops the toaster at the end depends on *how you set it up*, not on instructions you send it mid-run.

Sutra is like that, except:

- The "machine" is a brain. Sometimes a simulated spiking-neuron network. Sometimes the real wiring diagram of a fruit fly's brain.
- The things you place inside the machine are not ramps and buckets. They are **ideas**, turned into mathematical objects.

Compilation — running the Sutra compiler on your source code — is the act of *building the machine*. Running the program is dropping the marble in and watching where it lands.

## The weird part: ideas as primitives

In a normal programming language the primitives are things like integers, text, and lists. In Sutra the primitives are **ideas** — concepts like "smell present," "hunger hungry," "approach," "ignore" — each one represented as a tensor (a point, a matrix, or a higher-rank array of real numbers arranged as a coordinate in a geometric space).

This is the weird part, and it's the whole point.

These vectors are not just name tags. They have mathematical structure: you can **add** two of them to mean "both concepts are in play at once," you can **bind** one to another to mean "this idea is filling that role," you can ask how **similar** two of them are and get back a continuous closeness score, and you can **rotate** a state through the space to walk it along a trajectory.

Once you take that structure seriously, you can do arithmetic on meaning the same way you'd do arithmetic on numbers. Most programming languages use ideas as *comments*. Sutra uses them as *values*.

## Seeking outcomes, not following instructions

A normal program is a recipe: do this, then this, then jump here, then loop until that is true. A sequence of discrete instructions, executed one at a time.

A Sutra program is a setup: here are the concepts the brain should know about, here are the patterns it should recognize, here is what each recognition should produce. When the program runs, the substrate — the neural circuit — does the matching and the producing itself, because the geometry of the setup makes that the natural thing for it to do.

You are not telling the machine how to compute. You are arranging things so that when you perturb the system with an input, it *naturally lands* in the state you wanted.

This is the inversion at the heart of the language:

| Normal program | Sutra program |
| --- | --- |
| A list of instructions | An arrangement of initial conditions |
| Control flow is a branch in the code | Control flow is a pattern match in the circuit |
| A loop counter is a number | A loop counter is a position in vector space |
| Logic is a yes/no test | Logic is a weighted blend of similarities |
| The machine does what you said | The machine does what your setup *makes* happen |

## So what does the compiler actually do?

The Sutra compiler's job is not to generate a list of machine instructions. Its job is to **prepare the initial state of the substrate** so that running the program is just dropping in an input and letting the substrate settle.

When the compiler reads a `.su` source file, it produces:

- A set of named **concept vectors** — one for each idea the program uses.
- A **pattern table** — the combinations of concepts the brain should recognize when they appear at its input.
- A **behavior set** — the outputs the brain should produce when each pattern matches.
- If the program has loops, a **rotation operator** — a single matrix whose repeated application walks the internal state forward one step at a time.
- The fixed **wiring** of the chosen substrate (which, for the fly-brain target, is the real synapses of a real animal).

Taken together, this is the starting state of the machine. Everything is fixed before the first input arrives. When an input does arrive, the substrate runs its own dynamics — the input combines with the prepared concepts, the pattern-recognition circuitry fires on whichever match is closest, and the matching behavior comes out as the answer.

The compiler's work is done at that point. What we call "running the program" is the substrate responding to an input from the initial condition the compiler built.

## What does the substrate run on?

The same compiled program is designed to run on different substrates without you changing the source:

- **Your laptop (numpy).** Fast, predictable, for development. The vector math is plain linear algebra.
- **A simulated spiking neural network (Brian2).** The same math, now realized as populations of simulated neurons firing through synaptic weights. Slower, noisier, biologically plausible.
- **A real fly connectome.** The Janelia hemibrain data set: real synaptic wiring from a real fruit fly's mushroom body. The pattern-matching step is performed by the actual circuit a fly uses to decide whether a smell is familiar.

Switching between these is a single setting, not a rewrite. The long-term target — out of scope for the current research papers but guiding the design — is living neurons and neuromorphic hardware whose wiring has been specified to match a connectome.

## Sutra has no control flow

This is the part that is worth stating flatly, because it takes a while to sink in:

**Sutra has no `if`, no `else`, no `while`, no `for`, no `switch`, no jump, no return-address stack.** There are only two control primitives:

- **`select`** — "which process should I apply to this?" — is a softmax-weighted blend of continuous options. All branches execute, the weights decide how much of each one ends up in the output, the trajectory never stops.
- **`gate`** — "I am now in a different mode" — defuzzifies a condition and commits the trajectory to one regime or another. Used for loop exit and for crossing boundaries where continued fuzzy blending would be meaningless.

Everything that a conventional language does with branches and jumps is absorbed into geometry. A conditional is a weighted sum. A loop is a rotation that keeps moving. A loop exit is a gate that opens on a trajectory state, not a predicate that stops the flow.

The consequences are the reason it matters:

- **GPU-native and connectionist-native.** Everything is a matmul, a sum, or a cosine. No branch predictor, no divergent warps, no call stack — which is exactly the shape a GPU or a spiking neural circuit wants.
- **End-to-end differentiable.** The operations that normally break backpropagation (discrete branches, `if` predicates, `while` condition tests) are not in the language. A Sutra program minus the final defuzzification step is a composition of differentiable operations, which means gradients flow through an entire program the way they do through a neural network layer — an unusual property for a programming language to have.
- **Decompilable in principle.** Because the primitives are geometric rather than symbolic, a trained connectionist system can in principle be characterized as a specific composition of Sutra primitives. This is an interpretability story, not a universal claim, but it is a story no conventional programming language can tell about a neural network.

This is also the cost: Sutra is not a portable general-purpose language. You do not write a web server in it, or a GUI event loop, or a filesystem walker. What you write in it is a narrow, substrate-resident program — a conditional, a pattern lookup, a bounded trajectory — running natively on whichever connectionist substrate you are compiling for.

## Why bother?

Three things fall out of designing a language this way:

1. **Meaning is native.** The vector `approach + hunger` has a meaning that the substrate understands. The number `0x2A + 0x10` does not. Programs built out of meaningful primitives can be reasoned about in ways programs built out of opaque bit patterns can't.
2. **Noise is not an error.** A fuzzy match is the default; a crisp yes/no is something you deliberately produce when you need one. This matches how real neural hardware actually works, instead of fighting it.
3. **The substrate is swappable.** A source file written once can be evaluated on silicon, on simulated neurons, or on a real connectome. That is the path from "this idea works in simulation" to "this idea runs on neural tissue" without re-implementing anything.

## What looks absurd and why it isn't

Sutra probably reads like a troll language on first contact. `1 + 1 = 2` is computed by adding two 800-dimensional vectors together. `5 * 3` is a matrix multiplication. `if n > 3` dispatches through a softmax-weighted superposition of branches. Each of these looks wildly inefficient compared to what any normal language would do.

Locally, it *is* inefficient. Sutra isn't aiming for local efficiency.

What it aims at is a **radically unified runtime** — every value has the same shape, every operation has the same shape, the whole program is a chain of tensor operations with no escape hatches. That uniformity is what makes compile-time simplification possible at the whole-program level:

- A chain of integer operations is a chain of matrix multiplications. It folds to one cached matrix.
- That folded matrix feeds an `if`, which compiles to a softmax. The softmax composes into the next operation's matrix.
- The `if`'s branches feed into fuzzy logic. The fuzzy logic is polynomial arithmetic. It folds into the same graph.
- The whole chain — int math, conditional branching, fuzzy logic — reduces to a single tensor computation the compiler fuses into one stream of kernel launches.

Step by step, each operation looks absurd. At the whole-program level, the uniform representation lets the compiler cut through what would otherwise be a Gordian knot of separate type systems, dispatch layers, control-flow machinery, and optimization passes. There is one kind of thing; there is one kind of operation on that thing; the whole program is transparent to the simplifier.

That's why the primitives look the way they do. The "waste" on `1 + 1` buys global cohesion that normal languages pay for with enormous type-dispatch, JIT, and branch-prediction infrastructure. Sutra doesn't need any of that — because there isn't anything to dispatch on, and there aren't any branches.

If you came in expecting a language where integers are cheap, this is going to feel wrong. If you came in expecting a language where the entire program composes into a single GPU kernel chain, you've found it.

## Where to go next

- [**The vision page →**](vision.md) explains *why* embedding spaces let you do this — why a graph of concepts collapses into linear algebra, and why that makes computation suddenly spatial.
- [**Hello Sutra →**](tutorials/01-hello-sutra.md) walks through writing your first `.su` program by hand.
- [**The papers →**](papers.md) are the empirical grounding: Sutra programs running on LLM embedding spaces, and Sutra programs running on the fruit-fly mushroom body.
