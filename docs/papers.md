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

## 2. Sutra at NeurIPS 2026 — frozen submission archive

The exact camera-ready Sutra paper as submitted to NeurIPS 2026. Permanent, immutable; the canonical record of what the reviewers saw. The live paper above evolves toward the next venue; this archive stays put.

- **PDF (named):** linked from [/neurips-2026/](/neurips-2026/)
- **PDF (anonymized):** linked from [/neurips-2026/](/neurips-2026/)
- **Frozen commit:** [`ea6f8a01`](https://github.com/EmmaLeonhart/Sutra/commit/ea6f8a01) (2026-05-07)

## 3. Formal verification of Sutra — clawRxiv (live)

A second paper on formally verifying the non-learned trusted base of Sutra. Spine: compiling control flow into a tensor-op graph reduces verification to a finite set of closed-form polynomial obligations over a small fixed set of graphs, rather than enumeration of control-flow paths. The paper carries the obligation framework, the mechanical discharges that exist today (grid-exactness, branch-range by composition, termination, contract role-isolation, contract function-correctness for the Kleene fragment), and an honest cost characterization (PIT term-count growth, bundle-decoding capacity out to *k* = 48).

- **PDF:** [formal-verification.pdf](/formal-verification.pdf) — rebuilt on every push to the FV paper source; this is the canonical current version regardless of clawRxiv state.
- **On clawRxiv:** auto-resubmitted on every push by `fv-paper-ci.yml`. The chain starts fresh whenever clawRxiv's revise endpoint returns 404 on a previously-pinned post (server-side bug observed mid-2026); the `.post_id` file in the paper directory tracks the current chain head.
- **Source markdown:** [`paper/formal-verification/paper.md`](https://github.com/EmmaLeonhart/Sutra/blob/main/paper/formal-verification/paper.md) on GitHub.

---

The PDFs above are rebuilt on every push that touches the paper sources, by the GitHub Pages deploy workflow (`.github/workflows/pages.yml`). If you grab a PDF and the date on it lags behind the markdown, that means a deploy is in flight — the next deploy will catch it up.
