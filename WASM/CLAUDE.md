# replicating-neural-computers

## Project Description

This is a **paper replication** project (scaffolded by `cleanvibe replicate`).
The goal is to reproduce the headline results of:

> **Neural Computers**
> arXiv:2604.06425 - Mingchen Zhuge, Changsheng Zhao, Haozhe Liu, Zijian Zhou, Shuming Liu, Wenyi Wang, Ernie Chang, Gael Le Lan, Junjie Fei, Wenxuan Zhang, Yasheng Sun, Zhipeng Cai, Zechun Liu, Yunyang Xiong, Yining Yang, Yuandong Tian, Yangyang Shi, Vikas Chandra, Jürgen Schmidhuber - 2026-04-07T20:01:05Z
> PDF: https://arxiv.org/pdf/2604.06425v2 - HTML: https://arxiv.org/html/2604.06425v2

It produces three compounding artifacts (see `docs/replication_framing.md`
in the cleanvibe repo for the full framing): the runnable replication, a
legibility layer (the published findings report), and `SKILL.md` — the
reusable, agent-executable replication methodology.

## Architecture and Conventions

- **The efficient path is recipe-first.** Authors very often ship a
  reproduction recipe right in the paper's e-print source (usually near the
  end). Find and run it FIRST, then verify its output against the paper and
  fill only the gaps. A from-scratch reimplementation is the fallback, not the
  default — it is what burned a huge amount of tokens before this convention.
- **`replication_target/`** holds the real target:
  - `replication_target/transformer-vm/` — the authors' code as a **git
    submodule** (this is what we replicate; ships the reproduction recipe).
  - NOTE: the scaffolder's `download_paper.py` extracted the unrelated arXiv
    paper "Neural Computers" (2604.06425) into `replication_target/source/` and
    committed it. That was wrong — it is **not** our target — and it has been
    **purged from the repository and from git history**. Do not re-add it.
- **`replication_skill.md`** (repo root) — if the source/paper ships a
  reproduction recipe, copy it here and run it first. **`replication/`** — if a
  replication zip is shipped/linked, extract it here (the zip is gitignored,
  its contents committed).
- **`data_lake/`** — other downloaded/supplied material (datasets, notes,
  exports). Same cleanvibe convention as every project. The paper is NOT here.
- **`src/`** — your reimplementation (only the gaps the recipe didn't cover).
  **`scripts/run.py`** — the entry point CI invokes. **`results/`** — metrics
  JSON (gitignored). **`FINDINGS.md`** — the report (reproduced vs. reported,
  what the recipe covered vs. what you filled, gaps, divergences).
- **Go live early.** Create a PUBLIC GitHub repo and push near the start so
  every commit pushes and CI/Pages build as you go — don't leave it local-only.
- **Deliverables are built by GitHub Actions, not committed.**
  `.github/workflows/pages.yml` publishes a **themed** GitHub Pages findings
  site (the shared `report-theme.css` cleanvibe report theme + a color-coded
  replication status badge driven by `paper.json` `status`) + PDF report;
  `.github/workflows/package.yml` builds the downloadable ZIP replication
  package. Just make the repo **public** — `pages.yml` **auto-enables Pages**
  itself (`actions/configure-pages` with `enablement: true`), so there is no
  manual Settings toggle to do.
  Vision for the site shape: http://latent-space.emmaleonhart.com/

## Workflow Rules

- **Commit early and often.** Every meaningful change gets a descriptive commit.
- **Plan into `queue.md` first, then execute.** The replication plan already
  lives in `queue.md` (derived from `SKILL.md`). Work it top to bottom.
- **Finishing a queue item = delete from `queue.md` + append dated entry to
  `devlog.md`**, in the same commit as the work, then push. Never tick
  boxes in place. `devlog.md` is also where you record the replication's
  releases/milestones (source acquired, recipe found/run, environment pinned,
  first reproduced number, FINDINGS published, Pages live).
- **Keep `SKILL.md` truthful.** It is the compounding artifact. If you
  deviated from its plan, edit the plan to match what you actually did.
- **Keep this file and `README.md` current** as the replication takes shape.

## Writing

- Do not use "honest", "honesty", or "honestly" — and do not swap in "frank", "frankly", "candid", "candidly", or "transparently", which are the same self-congratulatory move in a different coat. When something failed, name the failure: "it didn't work", "I got that wrong", "this failed" — flat, no qualifier. Tagging a report "honest" implies the rest aren't, and couching a failure as honesty asks for credit for the admission, which is worse than the failure itself. Use a precise positive word ("accurate", "plainly", "truly") only when that is genuinely the meaning — never as a halo on a bad outcome.
