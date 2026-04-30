---
title: Theory and Paper
description: The Sutra language paper, with links to PDF and the clawRxiv submission. Plus the language-design pages that go alongside it.
---

# Theory and Paper

The Sutra paper is the long-form theoretical framing for the language: what
the primitives are, why frozen LLM embedding spaces are the substrate, and
what the working compiler actually demonstrates.

<div class="grid cards" markdown>

-   :material-file-pdf-box: __PDF (named, full version)__

    ---

    The author-attributed PDF, built from `paper/paper.tex`.

    [Open `paper.pdf` →](paper.pdf){ .md-button .md-button--primary }

-   :material-file-pdf-box-outline: __PDF (anonymized for review)__

    ---

    The double-blind version with author identity stripped.

    [Open `paper-anonymized.pdf` →](paper-anonymized.pdf){ .md-button }

-   :material-cloud-upload: __clawRxiv submission__

    ---

    Read the canonical preprint on clawRxiv. AI peer review attached.

    [View on clawRxiv →](https://clawrxiv.io/abs/2604.02147){ .md-button }

</div>

---

## Paper, in HTML

The full Markdown source of the paper rendered as a single page. Source of
truth: [`paper/paper.md`](https://github.com/EmmaLeonhart/Sutra/blob/master/paper/paper.md).

--8<-- "paper/paper.md"

---

## Language-design pages

The paper covers the contribution at the algorithmic and language-design level.
The pages below go deeper into specific parts of the language:

- [Paradigms](paradigms.md) — what programming paradigms Sutra is in conversation with
- [Ontology](ontology.md) — the type system and the role of OWL-style classes
- [Primitive classes](primitive-classes.md) — built-in primitive types and their geometric semantics
- [Logical operations](logical-operations.md) — `&&`, `||`, `!` over fuzzy truth
- [Numeric math](numeric-math.md) — how integers, floats, and complex numbers live in the substrate
- [Memory](memory.md) — bind, unbind, bundle, the role-filler model
- [Loops](loops.md) — first-class loop functions as substrate-pure RNN cells
- [Compilation](compilation.md) — the five-stage pipeline
- [The graph-to-vector leap](vision.md) — the empirical premise the language is built on
- [Fuzzy logic explorer](interactive/fuzzy-logic.md) — interactive playground
- [Tutorials](tutorials/index.md) — getting started, hands-on
- [Demos](demos.md) — every program in the smoke test
- [History](history.md) — how the language got to its current shape
- [SutraDB](/SutraDB/) — the sibling triplestore that backs the embedded codebook
