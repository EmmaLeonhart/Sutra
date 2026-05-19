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

## ROUND 2 — post-fix reviews (2026-05-18): VERDICT = ready to submit

Emma re-ran the **same 8 reviewers on the updated paper**. Independent
read of all 8 confirms her summary: **consensus is "ready / ship it."**
Verbatim flavour: DeepSeek "post it"; Claude "in good shape… the one
must-fix is the Appendix H seed discrepancy"; Grok "ready for arXiv
submission… upload it today"; ChatGPT "uploading to arXiv is
reasonable"; Gemini "confidently submit… exceptionally strong, clean,
sound"; Meta AI "Now: low risk… you're ready, hit submit"; Le Chat /
forum page: ship. All explicitly confirm the round-1 fixes landed
(AI-use statement, ESM-2 + Kingma refs, softened claims, Limitations
§5.1, code snippet, fuzzy-NN §2.3, multiseed std + plot, method/
experiment tagging).

Concrete residual flags, **each verified against source** (the point
of this file — PDF-reading LLMs garble text):

- `[verified-real → FIXED 2026-05-18]` **Appendix H** differentiable-
  training row still said `1 run × 300 epochs / seed 42`, contradicting
  the new 5-seed body (Claude's sole must-fix). Row updated to
  `differentiable_training_multiseed.py / 5 seeds × 300 epochs /
  seeds 0–4`.
- `[verified NOT-real — PDF garble, no action]` DeepSeek "§1.1 has
  AND twice, NAND/NOR missing" — source lines 62–69 are correct
  (AND,NAND,OR,NOR,NOT,XOR,XNOR distinct). "§3.6 stray 3" and
  "Appendix H paths like rotation_bid@/hkg…" — clean in source;
  pure PDF-extraction artifacts. Do **not** "fix" correct text off
  a mangled read.
- `[optional — partially ACTIONED 2026-05-18 per Emma, "soften a
  bit"]` Measured softening applied: abstract para-1 megasentence
  split + "the substrate is the architecture target" slogan
  dropped; "This collapses the boundary…" → "The same artifact is
  therefore both a logic program and a trainable neural network…";
  Turing framing toned down in body + the Siegelmann&Sontag bib
  annotation (citation KEPT — softening ≠ removing a real ref).
  Still deferred (optional, non-blocking): abstract "≈ chance" →
  "near chance (5.8±2.4%)", early architecture figure, formal
  all-minilm citation, LTN article-number. None gate the post.

**Net:** no open blocker. The one real inconsistency is fixed; the
scary-looking flags were PDF noise. Paper is post-ready; remaining
items are optional next-venue polish.

## ROUND 3 (2026-05-18/19): re-runs + clawRxiv reviewer

Emma re-ran DeepSeek/Meta/Gemini-chat/Le Chat on the latest paper;
all = **"ship it / submittable."** clawRxiv automated reviewer
(Gemini-3-Flash) advanced with the pipeline: post 2582 **Weak
Reject** → post 2583 **Accept**. One real, recurring item, now
**FIXED**: both clawRxiv v64 *and* v65 flagged `as of 2026`
(line 228) as a temporal/AI artifact ("undermines credibility /
synthetic origin") — ironically a round-1 addition of ours.
Reviewer conflict (Meta praised it as a defensible timestamp);
Emma's call → reworded to "(literature reviewed through early
2026)": deliberate scholarly cutoff, not a bare same-year stamp.
Resolves both. DeepSeek's round-3 "must-fixes" (Appendix A
duplicated AND; Appendix H gibberish paths) **verified NOT real
in source** (lines 872–878 & 1133–1136 clean) — same PDF-extraction
garble, migrating location each round (definitive tell). Sources:
all load-bearing refs web-verified across rounds (ESM-2=Science
2023, Kingma&Ba=ICLR 2015, LTN=AIJ 303:103649, van Krieken=AIJ
302:103602, Hájek=Metamath. of Fuzzy Logic Kluwer 1998, Scallop=
PACMPL/PLDI 2023, Siegelmann&Sontag=COLT'92); HDCC characterization
("classification-scoped, no general control flow") web-confirmed.
Fresh AI-artifact scan: clean (no meta-text/placeholders; the one
temporal smell now gone). **No open blocker; ship-ready.**

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
- [x] **P1 — Self-overlap check. RESOLVED 2026-05-18 — no risk.**
  Cloned paper #1 (`latent-space-cartography`) into the gitignored
  `comparisons/` and ran a prose-overlap analysis vs `paper.md`
  (`comparisons/overlap.py`): shared verbatim 8-word runs =
  **5 / 6999 (0.071%)**; strong near-duplicate sentences (≥0.75) =
  **0**; the single ≥0.55 hit is a shared *bibliography* line (the
  Serafini & Garcez LTN citation), not reused prose. Negligible
  overlap — arXiv's overlap detector is not a concern. No rephrasing
  needed.
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

- [x] **`.su` code snippet — DONE 2026-05-18.** Added the
  encode/decode core of `examples/role_filler_record.su` **verbatim**
  (in the smoke test, so paper-durable) to the "Type system and
  surface syntax" subsection, with a one-line note on what it lowers
  to. The optional *toy precomputed-rotation-matrix* sub-ask was
  NOT done (rotation math already lives in Appendix A/F; low value,
  left as optional P2).
- [x] **Fuzzy-NN background citation — DONE 2026-05-18.** Added a
  "Fuzzy logic and neuro-fuzzy systems" Related-Work subsection +
  3 web-verified refs: Zadeh 1965 (*Inf. & Control* 8:338–353),
  Jang 1993 (ANFIS, *IEEE T-SMC* 23(3):665–685), Buckley & Hayashi
  1994 (*Fuzzy Sets & Systems* 66(1):1–13). Distinguishes Sutra
  (fixed Lagrange-Kleene connectives; only embeddings learn) from
  membership-function learning.
- [x] **std / aggregate runs — DONE 2026-05-18 (real run).**
  Faithful 5-seed replication (seeds 0–4, identical architecture,
  `differentiable_training.py` untouched). Measured: before
  5.8±2.4%; epoch-50 95.2±0.1%; epoch-299 95.3±0.0%; loss
  1.154±0.000; knee ep.22, post-knee s.d. 0.03 pp; grad-norm
  0.94–4.29 all nonzero. Seed-invariant — corroborates the
  single-run numbers. Paper abstract/§3.6/table updated to n=5
  mean±s.d.; finding `planning/findings/2026-05-18-differentiable-
  training-multiseed.md`.
- [x] **Accuracy-over-epochs plot — DONE 2026-05-18.** Plain-TikZ
  figure (mean + ±1 s.d. band), coordinates from the real run,
  only the already-loaded `tikz` package (build-safe, no
  pgfplots/graphicx). `\label{fig:diff-train}`.
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

### 4.2 Restructure — DONE light, 2026-05-18 (Emma's call)

Emma chose the lowest-risk variant: **subsection-header tagging
only**, no top-level renumber, no reorder, no cross-ref churn.
Implemented in `## Consolidation into Canonical Primitives`: a
one-line roadmap after the opener + every `###`/`####` subsection
title now tagged `— method` or `— experiment`. The §3.2/§3.2.1/
§3.6 numbers are unchanged (heading text edits are numbering-
neutral; the literal cross-refs stay valid). Full Methodology/
Experiments split + §4 merge remains deferred to the next venue
(bigger diff, not arXiv-blocking).

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
