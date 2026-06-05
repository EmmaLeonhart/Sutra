---
name: replicate-neural-computers
description: Replicate the methods of "Neural Computers" (arXiv:2604.06425) and produce a runnable artifact, a published findings report, and a downloadable replication package.
---

# Replicate: Neural Computers

> **What this project actually replicated (truthful record).** Despite the arXiv
> framing below, the real target was **Percepta's `transformer-vm`** — a
> transformer with analytically-computed weights that simulates a WebAssembly VM
> ("Can LLMs Be Computers?"). It has **no arXiv**: it is published as a GitHub
> repo + blog post + Medium write-up (see `notes/sources.md`). The arXiv
> "Neural Computers" paper below was downloaded by the scaffolder as the nearest
> arXiv relative and is kept as **related work only**.
>
> **The recipe-first methodology still held end-to-end** and is the reusable
> lesson: for a code+blog target the "reproduction recipe" is the repo's own
> README/quickstart (here `uv run wasm-run`). Steps generalize as: *find the
> repo's run command → get consent → add it as a submodule → provision the
> toolchain → run it → verify its self-check/output against the blog's headline
> claims*. Result: **REPLICATED, 6/6 programs PASS** (local + CI from a clean
> clone). The only real work beyond running the recipe was environmental
> (toolchain on WSL Ubuntu). The generic plan below applies; substitute "blog/
> README claims" for "paper" and "repo quickstart" for "e-print recipe".

arXiv:2604.06425 - Mingchen Zhuge, Changsheng Zhao, Haozhe Liu, Zijian Zhou, Shuming Liu, Wenyi Wang, Ernie Chang, Gael Le Lan, Junjie Fei, Wenxuan Zhang, Yasheng Sun, Zhipeng Cai, Zechun Liu, Yunyang Xiong, Yining Yang, Yuandong Tian, Yangyang Shi, Vikas Chandra, Jürgen Schmidhuber - 2026-04-07T20:01:05Z
PDF: https://arxiv.org/pdf/2604.06425v2 - HTML: https://arxiv.org/html/2604.06425v2 *(related work only — not the target)*

## Prerequisite

If `replication_target/source/` is empty, run `python download_paper.py`
first. It fetches the arXiv **LaTeX/e-print source** (https://arxiv.org/src/2604.06425v2), extracts it to
`replication_target/source/`, and saves the PDF as a fallback. Read the `.tex`
in `source/` directly — it is far more token-efficient than the rendered HTML
(no base64 figure blobs) and is where the authors' reproduction recipe usually
lives. Fall back to the PDF only for PDF-only submissions.

## Plan

The efficient path: get the source, **find the authors' reproduction recipe
FIRST**, run it, then verify its output against the paper and fill only the
gaps. Reimplementing from scratch is the fallback, not the default.

> **Consent gate (do this before running anything):** replication runs code you
> did not write (the recipe / cloned scripts / a downloaded zip). Per harness
> safety requirements, ask the user for explicit consent before executing ANY
> such code, and wait for their answer. Reading the paper/source/recipe is fine;
> *running* third-party code is gated. (A future automated security scan is in
> `todo.md`.)

1. **Acquire the LaTeX source.** The scaffolder already downloaded + extracted
   the e-print source to `replication_target/source/` (committed) and saved the
   PDF (gitignored) — read the `.tex` directly. (If `source/` is empty, run
   `python download_paper.py`; that is a plain download, not gated.)

2. **Go live early.** Create a PUBLIC GitHub repo and push
   (`gh repo create --public --source=. --push`) so every later commit pushes
   and Pages/CI build as you go — don't leave it local-only.

3. **Find the reproduction recipe in the source — before reading the whole
   paper.** Authors often ship one near the end of the paper: a `SKILL.md` /
   `AGENTS.md`, a `reproduce.*` / `replicate.*` / `run.sh` script, a `Makefile`
   target, a Dockerfile, or a **replication zip**. `download_paper.py` flags
   candidates; also grep the `.tex` for "reproduc"/"replicat"/"skill"/
   "github.com". Copy a recipe file to `replication_skill.md`; extract a
   replication zip into `replication/`; add the authors' code repo as a **git
   submodule** under `replication_target/`. Record findings in
   `notes/sources.md`.

4. **Run the recipe first** (if any): set up just enough to execute it, capture
   output to `results/`, and assess how much of the paper's headline claims it
   reproduces. With a working recipe the rest is verification, not from-scratch
   reimplementation.

5. **Check ALL references** — every run, recipe or not. Confirm the key cited
   results/datasets/baselines the paper relies on say what it claims.

6. **Record `notes/claims.md`** — scoped to what the recipe didn't cover:
   headline claim(s); datasets (version/hash, location); models/methods in
   re-implementable detail; metrics and exact reported numbers; compute envelope
   (decides if CI can auto-run this).

7. **Reimplement only the gaps** under `src/`; pin `requirements.txt` /
   `environment.yml`. Scope to the headline claim, not every ablation.

8. **Run the replication.** `scripts/run.py` so CI can invoke it; metrics →
   `results/`.

9. **Write the findings.** `FINDINGS.md`: reproduced vs. reported (table);
   what the recipe covered vs. what you filled; gaps and divergences.

10. **Publish.** GitHub Pages deploys the findings + a transportable PDF report
    (`.github/workflows/pages.yml`); a ZIP replication package is built
    (`.github/workflows/package.yml`). The repo must be public with Pages set to
    Source: GitHub Actions.

## Budget guardrails

- If the paper's reported compute is more than ~4 GPU-hours on a single
  consumer GPU, mark this replication **not CI-runnable** in `paper.json` and
  document the reduced-scale variant instead.
- Prefer deterministic seeds and logged hashes so reruns are comparable.

## Definition of done

- `FINDINGS.md` exists and reports at least one headline number from the
  paper, with the reproduced value next to it.
- `scripts/run.py` runs end-to-end from a clean clone (or documents the data
  step that can't be automated).
- The repo is public and pushed; the GitHub Pages site and the ZIP package
  build green in Actions.
- This file still reflects how you actually did it — if you deviated, edit
  the plan above.
