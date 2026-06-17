# Yantra — Vision

## What it is

Yantra is a **neuro-symbolic, GPU-native operating system** written in Sutra.
The whole running system is one big differentiable tensor-op graph: kernel,
processes, IPC, GUI. There is essentially no CPU-side runtime — a tiny CPU
exists only to boot the system and orchestrate the GPU, like a glorified
sequencer. Everything that matters happens as Sutra programs exchanging
**axons** (structured embeddings produced by rotation binding).

A `yantra` is a Sanskrit word for a geometric/symbolic instrument used for
computation or meditation — a fitting name for a system where the symbol *is*
the computation, and the OS is what you get when you take that seriously.

## What it is *not*

- It is **not an LLM with tool use**. It is the substrate beneath that.
  The interface between "thought" and "action" dissolves because both happen
  in the same tensor space.
- It is **not a consumer desktop replacement**. Anyone who wants 100 Chrome
  tabs and arbitrary side-loaded software is not the customer.
- It is **not "von Neumann with a GPU instead of a CPU"**. Compute lives in
  the GPU, RAM is a cold-store for suspended processes, persistent storage
  is a conventional file system. The GPU is doing connectionist work, not
  pretending to be a CPU.
- It is **not a video-generation world model** of a computer. It is an
  actual execution substrate. (See `16-related-work.md` for the contrast
  with Meta's *Neural Computers* paper, which inspired the framing but went
  the opposite direction.)

## The thesis

The dominant computing paradigms (von Neumann CPU + RAM, agent-style "LLM
calls tools") were fitted around scarce serial compute and disembodied
language models. As GPUs and accelerators become the default substrate,
and as AI systems start to want to reason continuously rather than emit
strings, the impedance mismatch shows up everywhere:

```
model thought → text → parse → execute → output → re-embed → model thought
```

Yantra collapses that loop:

```
model activation → Sutra program → tensor output → directly consumable
```

Because every Sutra program already lives in the same embedding space the
model is thinking in, perception (e.g. JEPA), reasoning (LLM activations),
and action (Sutra tensor ops) are all first-class operations on the same
representation. There is no translation layer because there is nothing to
translate to.

## Why now

Two trends converge:

1. **GPUs as default**. Critical-systems vendors increasingly ship
   accelerator-heavy boxes anyway. A connectionist OS is not chasing
   exotic hardware; it is using what is already there more directly.
2. **AI is everywhere but feels bolted on**. RAG, MCP, function calling,
   and agent scaffolding are all plumbing around the same hole — that
   models think in vectors but software speaks in bytes. A Sutra-native OS
   is what a substrate looks like once you stop pretending.

A bet underneath all of this: if a credible analog/neuromorphic substrate
emerges, Yantra is already the operating system designed for it. See
`13-hardware-roadmap.md`.

## What "good" looks like

- A process, once allocated, runs at **constant performance** until the
  GPU is fully saturated. No throttling, no scheduler-induced jitter. New
  processes that don't fit simply fail to launch — but the ones already
  running don't slow down.
- The non-AI parts of the system are **formally verifiable**, because
  a beta-reduced tensor-op graph + polynomial Kleene logic + tail-recursive
  loops is a much cleaner verification surface than the average modern
  kernel.
- **Local AI is first-class everywhere** because there is no place where
  it would be second-class. Every process can read and emit axons.
- The **file system is conventional and interpretable** — if you pull the
  drive out of a Yantra box, a forensics tool can still read it.

## Sketch of who would buy it

- Defense, aerospace, autonomous systems, industrial control, medical
  devices — anywhere where "predictable latency under load" and "the
  certifier can read the code" matter more than "it runs Photoshop."
- Air-gapped environments, where the absence of `eval`, service workers,
  arbitrary plugin loading, and a Chromium attack surface is itself the
  feature.

See `12-target-markets.md` for the longer pitch.

## Status

This repo is a **planning corpus** plus a v0.0 kernel nucleus
(`kernel/`). The other artifacts that anchor the vision live elsewhere:

- The Sutra compiler and runtime (separate project).
- The JS/TS transpiler (separate project).
- Connectome/alignment research that pressure-tests the substrate-as-
  -architecture-target idea.

Yantra is being designed in this repo so that when the implementation
starts, there is a coherent target rather than vibes.
