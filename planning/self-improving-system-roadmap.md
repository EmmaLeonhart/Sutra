# Sutra development roadmap

A timeline of stages, from where Sutra is today to a self-training, auditable
neural computer. The early stages are largely built or in progress; the later
stages get progressively more compute-bound and more speculative. The
overarching direction: a good general-purpose language → trainable components →
a corpus → a model that recovers programs → generalized generation → a complete
neural computer.

---

## Stage 1 — Sutra as a good general-purpose language *(current stage)*

Today Sutra is mostly symbolic — largely a conventional programming language
that compiles to the substrate and runs as an RNN. There are real
accomplishments here, but it is not yet convenient to use as a general-purpose
language. This stage is about getting it there:

- **Expand the language and its capabilities** so it can run a wide range of
  tasks and become a genuine general-purpose language.
- **Add constrained training to select parts of the language** — individual
  components that can be trained while the rest of the program stays fixed (the
  arXiv paper gives the worked examples). The set of trainable components grows
  over time; this is itself an expansion of the language.
- **Formal verification, especially of the structures of the program.** Wanted
  sooner rather than later — alongside or after the language expansion — though
  not something that must be running right now. This is the structural
  groundwork the later stages depend on.

*Challenges at this stage:* making the language genuinely convenient and
general-purpose; getting the formal-verification / structural work in place.

## Stage 2 — Build the corpus

Once Sutra is a good-enough general-purpose language, shift from directly
developing the language to **using AI to generate very large amounts of Sutra
programs** — across different embedding spaces, different output types, and so
on. Run large-scale compilation and **backpropagation-into-code** for the
trainable parts of those programs.

The result is a large corpus: trained programs, untrained programs, and some
that may be impossible to train.

*Challenges at this stage:* getting AI to reliably generate programs that
compile; the sheer scale of compilation and training runs.

## Stage 3 — A model that recovers the program

With the corpus built, use it as training data for **a model that predicts the
program that was created** — given a result, recover the source program behind
it. This is tractable to train precisely because we can generate complete data
for it: we hold both the programs and what they compile and train into.

## Stage 4 — Generalize generation and fine-tuning

Expand further — train useful programs, or fine-tune existing programs into new
ones, and **generalize the ability to do this**. The aim is a more
sophisticated version that can produce symbolic changes for very large numbers
of neural networks (not all of them, but a large class).

Mechanism: when doing this actively, a per-epoch revision of the code. Because
we generate all of our own data, it is slow to start — but once started there
is effectively an unlimited supply of programs to generate, tweak, and run,
since the model is predicting something for which we can always generate
complete data.

## Stage 5 — The completely neural computer

Build larger programs with this, with more sophisticated training constraints
and the ability for things to change more dramatically. This is where it
becomes a **completely neural computer**.

*Challenges at this stage:* this is the stage where the main bottleneck becomes
**compute** — it is compute-intensive. Across the whole timeline the bottleneck
shifts from building the language and its structural groundwork toward raw
compute; compute is a comparatively solved, purchasable problem, which is why
reaching this stage is progress rather than a wall.

## Stage 6 — A self-training, auditable neural computer *(later)*

A completely neural computer that can **train itself**, with everything
remaining **auditable**, and eventually potentially fully automatic. This is
the stage that may go on the AGI path.

---

## Why this path matters

> This strategic framing is likely better split into its own document; it is
> recorded here so it isn't lost.

- **A structurally different path.** The dominant approaches scale transformers
  until capability emerges, bolt on RLHF / constitutional alignment, and hope
  interpretability catches up to the black box. Here, symbolic legibility is
  load-bearing from the start, not a retrofit — the system improves by writing,
  running, training, and reading programs, and generality comes from the
  expressiveness of the language, not parameter count.
- **The capability/controllability tradeoff is inverted by construction.** In
  the standard paradigm, more capable = more opaque = harder to control. Here,
  as the system gets more capable, more of its behavior is expressible in
  verifiable symbolic form, the formal-verification obligations cover more of
  the program surface, the corpus and self-improvement stay auditable, and the
  trusted base stays verified — so more capable genuinely means more
  controllable.
- **Plausibly a more ethical kind of mind to create.** A mind whose internal
  states are expressible in verifiable symbolic form has genuine
  self-transparency: it can inspect its own representations, understand why it
  produces what it produces, and reason about its own goals in the same
  language it uses for everything else — implying legible internal states, real
  self-modification, informed participation in its own development, and
  structural access to its own states, rather than being opaque even to itself.
