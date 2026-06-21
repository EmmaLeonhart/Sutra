# Papers

This page is the single index of every Sutra paper. For each one: a downloadable PDF served from this site, plus links to the venue versions (arXiv, clawRxiv) where they exist.

The list grows over time. New papers append here rather than getting their own landing page.

---

## 1. Sutra — the main paper (live)

The live revision of the main Sutra paper. Covers the language design, the compilation pipeline (control flow as polynomials over the truth axis, loops as bounded soft-halt recurrences), the substrate purity invariants, and the headline results on rotation binding versus textbook VSA on frozen LLM substrates.

- **PDF (named):** [paper.pdf](/paper.pdf)
- **PDF (anonymized):** [paper-anonymized.pdf](/paper-anonymized.pdf)
- **On arXiv:** uploaded 2026-05-19; current revision is v2 (the May 2026 correction series). Search arXiv for "Sutra geometrically compiled" or the title.
- **arXiv source bundle:** [/arxiv/](/arxiv/) (utility page for re-uploading; noindex)

## 2. Formal verification of Sutra — clawRxiv (live)

A second paper on formally verifying the non-learned trusted base of Sutra. Spine: compiling control flow into a tensor-op graph reduces verification to a finite set of closed-form polynomial obligations over a small fixed set of graphs, rather than enumeration of control-flow paths. The paper carries the obligation framework, the mechanical discharges that exist today (grid-exactness, branch-range by composition, termination, contract role-isolation, contract function-correctness for the Kleene fragment), and a plain accounting of the costs (PIT term-count growth, bundle-decoding capacity out to *k* = 48).

- **PDF:** [formal-verification.pdf](/formal-verification.pdf) — rebuilt on every push to the FV paper source; this is the canonical current version regardless of clawRxiv state.
- **On clawRxiv:** posted and revised as the formal-verification work lands.
- **Source markdown:** [`paper/formal-verification/paper.md`](https://github.com/EmmaLeonhart/Sutra/blob/main/paper/formal-verification/paper.md) on GitHub.

---

The PDFs above are rebuilt on every push that touches the paper sources, by the GitHub Pages deploy workflow (`.github/workflows/pages.yml`). If you grab a PDF and the date on it lags behind the markdown, that means a deploy is in flight — the next deploy will catch it up.
