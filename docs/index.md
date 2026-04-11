---
title: Sutra
description: A vector programming language whose primitives are hypervectors in embedding space.
hide:
  - navigation
  - toc
---

# 📜 Sutra

**A vector programming language whose primitives are hypervectors in embedding space.**

Conventional languages compile to machine instructions that execute on silicon. Sutra compiles to *vector operations* that execute inside a pre-trained embedding space — making the execution environment **fundamentally semantic** rather than symbolic. Where silicon arithmetic has no inherent meaning, the geometry of an embedding space *does* — and Sutra is the first programming language designed to exploit that as a first-class computational substrate.

The name comes from the Sanskrit *sūtra* — "thread/rule/aphorism," the word used for Pāṇini's foundational Sanskrit grammar (the earliest formal grammar of any language). The 📜 scroll is the ecosystem's visual branding across the language, the database ([SutraDB](/SutraDB/)), the tooling, and the papers.

---

## Why this is different

Most languages think of "vectors" as a library you import. Sutra thinks of vectors as the *only* type. Numbers, symbols, structures, control flow — everything is a hypervector or an operation on hypervectors. There are no "wrong type" errors, only noisy or semantically meaningless results. Equality is replaced by **similarity**.

This is not an AI-assisted programming tool. It is not a neural network. It is a formal system for *reasoning under uncertainty* — closer to logic programming (Prolog) than to Python, but operating in **continuous** rather than discrete space.

The conceptual leap that makes this work is the part most people find unintuitive: an embedding space looks like it should be a graph, but it actually behaves like linear algebra and is suddenly *spatial*. **[Read the vision page →](vision.md)** for the full story of why connectionism + a bunch of neurons collapses into linear algebra and what that means for programming.

---

## Three things Sutra can do today

<div class="grid cards" markdown>

-   :material-vector-line:{ .lg .middle } __Run programs on LLM embedding spaces__

    ---

    Sign-flip binding achieves **14/14 correct recoveries** at 14 bundled role-filler pairs across GTE-large, BGE-large, and Jina-v2 — the same source code, three different substrates. Sustains 10/10 chained bind-unbind-snap cycles. Multi-hop composition across structures works.

    [→ Sutra-to-LLM paper](papers.md)

-   :material-bee:{ .lg .middle } __Compile programs onto a fly brain__

    ---

    The same compiler also targets a Brian2 spiking simulation of the *Drosophila melanogaster* mushroom body. **16/16 decisions correct** across four program variants × four input conditions, all running on the simulated connectome. To our knowledge, this is the first programming language whose conditional semantics compile mechanically onto a connectome-derived spiking substrate.

    [→ Fly-brain paper](papers.md)

-   :material-school:{ .lg .middle } __Teach you to think in embedding space__

    ---

    The intuition that the world is a graph is hard to break. The Sutra tutorials are written specifically to walk you through the moment that intuition snaps and the geometric / spatial / linear-algebraic view takes over. No prior VSA or HDC background required.

    [→ Hello Sutra](tutorials/01-hello-sutra.md)

</div>

---

## Get started in two clicks

The fastest way to see Sutra do something:

```bash
git clone https://github.com/EmmaLeonhart/Sutra
cd Sutra/sdk/sutra-compiler
python -m sutra_compiler ../../examples/01-objects-and-methods.su
```

That gives you a clean validator pass on the example. From there, [Tutorial 1 →](tutorials/01-hello-sutra.md) walks you through writing your first `.su` file by hand.

If you have a JDK on your machine, the Sutra plugin for IntelliJ IDEA Community is also in the repo at `sdk/intellij-sutra/`. Run `!editor.bat` from the repo root and a sandbox IntelliJ launches with the plugin preinstalled and the project tree open.

---

## Project status

Sutra is **research-grade** software produced for the [Claw4S 2026 conference](https://clawrxiv.io). The two papers that ground the language are listed on the [papers page](papers.md). Both are open source, and so is the language, the compiler, the IntelliJ plugin, and the fly-brain runtime.

The code and the papers live in one repo: [github.com/EmmaLeonhart/Sutra](https://github.com/EmmaLeonhart/Sutra). PRs welcome — especially on the IntelliJ plugin, the spec, and the fly-brain substrate.
