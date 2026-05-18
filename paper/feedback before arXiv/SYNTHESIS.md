# Pre-arXiv feedback — consolidated working plan

**Created:** 2026-05-18. **Sources in this folder:** `discord.md`
(maniospas — the human ML reviewer who *endorsed* the paper for cs.LG;
highest-signal), plus eight LLM passes saved as HTML (DeepSeek, Claude,
Grok, ChatGPT "arXiv Endorsement and Risks", Google Gemini, Meta AI,
Le Chat). The raw HTML + `_files/` asset dirs are saved web pages
(megabytes of JS/CSS) — **noise; do not commit them** (see §6).

This file deduplicates ~8 overlapping reviews into one prioritized,
verified action list. Every paper-content claim below was **checked
against the live `paper/paper.md`** (not trusted from the LLM PDF read)
— status tagged `[verified-real]`, `[partly-addressed]`, or
`[needs-ground-truth]`.

## 0. Repo constraints that bind this work (read first)

- **All edits go to the live `paper/paper.md`.** It is the single
  source of truth; `paper.tex` is a `pandoc paper.md` wrapper, and the
  `[preprint]` (non-anon) build is the arXiv PDF. So content edits here
  flow straight to arXiv.
- **`paper/neurips/` is FROZEN. Do not touch it.** The frozen archive
  is a separate snapshot; arXiv is built from `paper.md`, not it.
- **No fabricated numbers.** Items that say "report std / rerun 5
  seeds / state the L upper bound" require *actually running it or
  reading the logged result*. A made-up ±std is a safety-rule
  violation, not a polish edit.
- **Paper-code durability.** Any `.su` snippet added to the paper must
  be valid current syntax that compiles (it becomes paper-cited code).
- **Already decided this session — do NOT re-litigate.** The
  replication package lives in ONE place: the `## Reproducibility`
  statement before References. Several reviews suggest pushing it into
  the abstract / intro / a checklist appendix — Emma already rejected
  abstract/intro placement. The Reproducibility statement is in place.
  Don't move it back.

## 1. arXiv submit-blockers (process/policy — not paper prose)

Unanimous across reviewers; these gate the upload.

- [ ] **P0 — AI-use disclosure.** Unanimous. The 2026 enforcement
  bans *unverified* LLM output (hallucinated refs, leftover
  meta-comments), not AI-assisted work. Add a disclosure to
  `paper.md` (before References) **and** answer the arXiv form's AI
  question. **Wording is an open decision — see §4.1; do not auto-pick
  a template.** `[verified-real: no AI statement in paper.md]`
- [ ] **P0 — Reference audit.** Biggest risk under the new rule.
  Verify every citation: authors / year / venue. Load-bearing ones to
  hand-check: **ESM-2 = Lin et al., *Science* 2023** (confirm Science,
  not bioRxiv), Siegelmann & Sontag 1992, van Krieken et al. 2022,
  Hájek 1998, Scallop (Li et al. 2023), DeepProbLog (Manhaeve et al.
  2018), HDCC (Vergés et al. 2023). `[verified: refs exist in bib;
  correctness unaudited]`
- [ ] **P0 — LLM-artifact scan.** Ctrl-F the compiled manuscript for
  meta-text ("Here is a…", "As an AI", "200-word summary",
  placeholders, doubled headings). Quick, mandatory.
- [ ] **P1 — Self-overlap check.** This is paper #2 written ~25 days
  after paper #1; arXiv's overlap detector flags reused intro/related
  -work prose. Rephrase any large shared blocks.
- [ ] **P1 — Link/repro liveness.** Confirm the GitHub URL, the
  `sutra-replication-package.zip`, and the project site all resolve
  *now*; sanity-run `SKILL.md` so the reproduction claim holds.
- [ ] **P0 — Categories (consensus).** Primary **cs.LG** (endorsed);
  cross-list **cs.PL** + **cs.AI**; optional 3rd **cs.NE**. `stat.ML`
  auto-added. Avoid cs.CL / cs.CV / cs.AR. Keep cross-lists ≤3.

## 2. Paper-content edits — prioritized

### P0 content (high impact, low effort, consensus)

- [ ] **Add Kingma & Ba (2015) + Adam defaults.** State β1=0.9,
  β2=0.999, ε=1e-8, lr=0.005. `[verified-real: "Adam updates
  (lr=0.005)" line 451; no Kingma in bib]` maniospas + 5 LLMs.
- [ ] **Consolidate a clearly-labelled `Limitations` block.**
  ChatGPT calls this the single highest-value add. Pull the scattered
  limits into one subsection: single-cycle records only (L≥8 → chance),
  substrate dependence, codebook O(vocab), no benchmark vs. other
  neuro-symbolic systems, no learned binding operators yet, no
  perf/runtime benchmark, semantic overlap caps accuracy.
  `[partly-addressed: a "Demonstration, limitations, and future work"
  section exists (line 579) but no consolidated, labelled Limitations
  subsection]`
- [ ] **Soften over-strong claims** (don't delete — qualify):
  - line 486 "remaining 5% gap reflects **irreducible** semantic
    overlap" → "we hypothesize the remaining gap largely reflects…".
    `[verified-real]`
  - line 229 "no published HDC system combines…" — already hedged
    "To the authors' knowledge"; add "as of 2026" and keep the
    explicit HDCC/TorchHD contrast nearby. `[verified-real, mild]`
  - line 116 "the first use of a high-dimensional rotation…" →
    "we are unaware of prior…". `[verified-real]`
- [ ] **Frame the §3.6 training experiment precisely.** Reviewers
  read 95% as test accuracy. Either add a held-out split (real rerun,
  no fabrication) **or** add one sentence: this demonstrates gradient
  flow through the compiled graph, not generalization; no test split
  is claimed. (The precise-framing option is cheap and defensible.)

### P1 content (medium effort; strong for arXiv, expected for a venue)

- [ ] **Add a small `.su` code snippet + a toy precomputed-rotation
  example** in the body. maniospas + Claude + Gemini + Le Chat. Must
  be valid, compiling syntax (paper-code durability).
- [ ] **Fuzzy-logic background citation.** Situate polynomial Kleene
  against fuzzy-NN literature (Zadeh 1965 and/or a fuzzy-NN survey).
  `[verified-real: no Zadeh/Pal/"fuzzy neural" cite; van Krieken +
  Hájek are cited but are t-norm/metamath, not fuzzy-NN background]`
- [ ] **Accuracy-over-epochs plot** (Figure) from the existing
  training JSON, replacing/【supplementing the before/after table.
- [ ] **std / aggregate runs.** Rerun 5 seeds, report mean±std at
  epoch 50 and 300, and std after the convergence knee. **Requires
  real runs — log them, don't invent.** `[needs-ground-truth]`
- [ ] **Move one diagram early** (soft-halt cell or compiler pipeline)
  to page 1–2 for skimmers.

### P2 content (venue-grade; optional for the preprint)

- [ ] Ablation table (rotation vs Hadamard vs circular conv;
  ±mean-centering; ±normalization; synthetic-block width). "Ablations
  convert demos into science" (ChatGPT). `[needs-ground-truth]`
- [ ] Section restructure: split Methodology vs Experiments, merge the
  thin §4. maniospas/DeepSeek want it; Claude/Grok call it
  venue-specific, **not arXiv-blocking** → defer unless Emma wants it
  now (see §4.2).
- [ ] One paragraph: *why this polynomial interpolant specifically*
  (vs. standard smooth t-norm approx) — what inductive bias it sets.
- [ ] Hyperparameter-sensitivity note routed to an appendix.
- [ ] Typo/precision sweep — **nuanced, not blanket**: prose
  "heaviside" (lines 103, 358) could capitalize to match the math's
  `\mathrm{Heaviside}`, but backticked `` `heaviside` `` (line 554)
  is a code identifier and **must stay lowercase**. Specify the L
  upper bound on line ~330 ("L ∈ {1,2,4,8,…}") only with the real
  experimental max. `[needs-ground-truth for L max]`

## 3. Feedback the reviewers got wrong / already handled — don't burn effort

- "No reproducibility info / add it prominently / abstract SEO" —
  superseded; the Reproducibility statement exists and its placement
  is Emma's settled decision (§0).
- "Add Broader-Impact / AI-alignment framing" (Le Chat, Meta) —
  scope creep; the paper is a systems/PL contribution. Emma herself
  said she doesn't know how much it ties to alignment. Skip unless she
  wants it.
- "Paper hides failure modes" — false; it documents L=8→chance and
  snap degradation. Grok explicitly praised this. Keep as-is.
- "Anonymous-author placeholder left in" — false; the `[preprint]`
  build stamps Emma Leonhart / EmmaLeonhart999@gmail.com.
- Heavy "soften 10–15% of all rhetoric" — apply surgically to the
  three claims in §2-P0, not as a global tone-down (the voice is a
  deliberate asset; over-sanding it is its own loss).

## 4. Open decisions for Emma (these change what we write)

### 4.1 AI-disclosure extent — the one real values call

Emma stated (Le Chat thread) that AI involvement was *substantial*:
ideation, getting into VSAs, ~"50% of the thinking"; her own driving
contribution was making the implementation real and **substrate-
faithful** (she caught AI taking numpy shortcuts that broke the
compilation pipeline — the exact failure this repo is built to
prevent). The LLM templates mostly understate AI to "assistant".
This repo's core ethos is *not faking*. The disclosure should be
**truthful about substantial AI collaboration while stating the human
drove implementation, substrate-purity verification, and final
correctness.** Wording spectrum is a decision, not a default — see the
question posed alongside this doc.

### 4.2 Restructure now or defer

Split Methodology/Experiments + merge §4: helps a venue submission,
**not** an arXiv blocker. Decide: do it now (bigger diff, risk to the
frozen-paper-cited section refs) or defer to the next-venue revision.

## 5. Suggested execution order

1. P0 process: ref audit, artifact scan, link liveness, self-overlap.
2. P0 content: Adam cite, Limitations block, soften 3 claims, §3.6
   framing sentence.
3. AI disclosure (after §4.1 decision).
4. Submit to arXiv (cs.LG + cs.PL + cs.AI).
5. P1/P2 as a v2 after posting (arXiv allows unlimited revisions —
   reviewers confirmed it won't be insta-removed; you get emailed to
   revise).

## 6. Housekeeping for this folder

`discord.md` and this `SYNTHESIS.md` are worth keeping in git. The
saved `.html` pages + `_files/` asset dirs are ~8 MB of browser JS/CSS
— same rationale as the repo's "don't commit reference PDFs" rule.
Recommendation: add `paper/feedback before arXiv/*.html` and
`paper/feedback before arXiv/*_files/` to `.gitignore`, commit only
`discord.md` + `SYNTHESIS.md`. (Not done unilaterally — Emma's call;
the raw pages are hers and deletion is destructive.)
