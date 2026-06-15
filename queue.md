# Sutra — Work Queue (`gui-training` branch)

**This file is a queue, not a state snapshot.** It lists what is being
worked on right now and what is next. Finished work lives in `git log`,
`DEVLOG.md`, and `planning/findings/` — NOT here. When an item is done,
delete it in the same commit as the work and append a dated entry to
`DEVLOG.md` (CLAUDE.md §Workflow Rules). Never leave `[x]` / "DONE" behind.

> **`queue.md` is PER-BRANCH and is EXPECTED to differ between branches (Emma
> 2026-06-14).** Different branches pursue different tasks, so each branch carries
> its own queue. This is by design, NOT drift or a merge mistake: do not "reconcile"
> one branch's queue against another, and do not treat a queue that omits another
> branch's tracks as incomplete. When a branch is created for a focused effort, its
> queue is stripped to that effort (here: GUI). The canonical full agenda still
> lives in `todo.md`; `queue.md` is the active slice for *this* branch. A merge to
> `main` carries the branch's completed work (code + DEVLOG), not its transient
> queue items. **This branch = GUI / the a1 demo + its paper** (below).

---

## ⚠️ Branch discipline — read first (Emma 2026-06-14)

This is the **`gui-training` branch**, a dedicated autonomous GUI-work loop.
`main` is simultaneously running formal-verification work in a *separate*
session. **This loop's crons stay on `gui-training` and NEVER touch `main`.**

- The work-loop cron syncs ONLY `gui-training` (`git fetch origin` +
  `git pull --ff-only`/`--rebase` of `gui-training`). Never `git checkout main`,
  never merge/rebase across to main, never force-push.
- Scope is **GUI work only** (this file). All non-GUI tracks — thrml, formal
  verification, transpiler frontends, WASM, corpus, paper polish — were stripped
  from this branch's queue on purpose; they live on `main`. Do NOT re-add them.
- When the GUI queue is genuinely empty and only Emma-gated items remain
  (e.g. the learned-decoder approach choice), the loop reports that and idles —
  it does NOT pull non-GUI items from `todo.md`.

HARD RAILS (CLAUDE.md): every pixel renders on the substrate; stateful widgets
are substrate-RNNs; the optimizer/compositor host-side parts are named as
host-side (no "one substrate program" overclaim); verify rendered frames against
a reference, MEASURED — never "it ran". No faked results, no weakened tests.

---

## 1. Warmer/colder self-morphing hero demo (the "a1" GUI training demo) — COMPLETE

**The a1 demo is BUILT (1a→1d, 2026-06-14).** The recordable interactive demo
exists: a substrate-rendered hero (θ-parameterized glow + ring + background + RGB
tint + substrate glyph headline) steered by WARMER/COLDER presses through a
host-side SPSA optimizer. Emma records it herself via `steering_window.py`.

> **Build complete — measured:**
> - 1a `frame_hero.su` + `render_hero`/`render_hero_rgb`/`render_hero_with_headline`
>   (θ = cx,cy,invs,bright,radius,accent,bg,cr,cg,cb + headline_w; runtime-parameter,
>   no recompile; oracle-verified ≤1e-6).
> - 1b `hero_spsa.HeroSPSA` (host-side two-sided SPSA; converges; gradient-sign ok).
> - 1c `hero_steering.HeroSteering` + `steering_window.py` (two presses = one SPSA
>   batch; per-frame NaN/blank guard; tkinter WARMER/COLDER + W/K).
> - 1d `experiments/gui_steering_eval.py` SOAK, **measured 2026-06-14**: 100-press
>   session = **101/101 clean frames, 0 NaN, 0 blank** (headline off AND on);
>   directional consistency — a brighter-preferring rater drives `bright`
>   1.000→1.800 (+0.800, the axis ceiling), a darker-preferring rater 1.000→0.200
>   (−0.800, the floor); sign flips with the preference. Tests: `test_hero_*` 14/14.
> - Honest rails held throughout: render is substrate (colour channels + glyph
>   pixels); composition + SPSA + warmer/colder bookkeeping are host-side; steering
>   by a (synthetic, in tests) rater — NOT substrate-native training, NOT one
>   substrate program.
>
> These 1d numbers are the data for paper §7 / task **P7** (pull them in there).
> Remaining demo polish (low priority, NOT blocking the paper): the optional web
> wrapper (deferred); reward EMA smoothing over last-k presses (currently raw ±1,
> the faithful two-sided core — flagged, not faked).

## 2. Paper — substrate-rendered, human-steerable GUI (the a1 paper)

**Emma 2026-06-14: make the paper comprehensive; this is its own paper for this
branch.** A dedicated write-up of the GUI/a1 work: whole-frame rendering executed
entirely on the frozen-LLM semantic substrate, runtime-parameter (no-recompile)
parameterization, substrate text/glyph rendering, and **host-side SPSA steering of
substrate-rendered output by a human warmer/colder signal**. Lives on THIS branch
at `paper/gui-steering/` (a third Sutra paper alongside `paper/paper.md` and
`paper/formal-verification/paper.md` on main — see the per-branch note up top).

Working frame (refine in P1): *the render is substrate; the composition and the
optimizer are host-side, and we say so.* The paper's value is the honest
substrate/host accounting + the measured render fidelity + the steering result —
not an overclaim. Ground truth it must not contradict: `planning/sutra-spec/*.md`,
`docs/gui.md`, the frozen `paper/neurips/` (do NOT touch), and `paper/paper.md`.

INTEGRITY RAILS for every paper item: cite ONLY measured numbers (oracle deltas,
SPSA convergence, soak counts) — never from memory; mirror the §"What we are not
claiming" discipline; no "honest/genuinely" buzzwords; replication/URLs only in the
Reproducibility section. Results that depend on the demo (P7/P8) are GATED on 1c/1d
producing the numbers — draft the method sections first, fill results when measured.

> **Progress (2026-06-14):** P0 DONE — `paper/gui-steering/paper.md` scaffolded
> with full abstract + section outline, and FIRST DRAFTS written for the sections
> grounded in shipped 1a/1b code: §1 intro, §2 whole-frame rendering, §3 glyph
> rendering, §4 the θ hero, §5 SPSA method, §6 render-fidelity (prose; exact maxima
> pending the P6 script), §8 "what we are not claiming". §7 steering results are
> GATED on 1c/1d and marked so (no fabricated numbers). Remaining below: finalize +
> the experiment scripts (P6/P7), figures (P8), related-work verification (P10),
> reproducibility commands (P11), CI (P12), cross-check (P13), website (P14). No
> clawRxiv submission yet (no gui-paper-ci.yml until P12 — this branch's pushes
> don't auto-submit).

**Method sections — FIRST DRAFTS in paper.md; finalize + ground each**
- [ ] **P1. §Introduction / motivation.** Why a substrate-rendered UI; the
  fuzzy-by-default framing (geometry as computation); the demo as the artifact;
  contributions list. Tie to Sutra's vision (`planning/sutra-spec/vision.md`).
- [ ] **P1. §Introduction / motivation.** Why a substrate-rendered UI; the
  fuzzy-by-default framing (geometry as computation); the demo as the artifact;
  contributions list. Tie to Sutra's vision (`planning/sutra-spec/vision.md`).
- [ ] **P2. §Whole-frame substrate rendering.** The one-op render model
  (`frame_whole.su` / `frame_hero.su`): the substrate returns the frame as one
  buffer vector; host is I/O. The **broadcast-buffer runtime-parameter mechanism**
  (θ changes are call args, no recompile) — the load-bearing fact. Cite the
  measured oracle deltas (≤1e-6) that already exist.
- [ ] **P3. §Substrate text / glyph rendering.** The antipodal bound-vector font
  (`font_bound_antipodal.su`, 36/36 pixel-exact, measured); the banner as exactly
  the concatenated substrate glyph fields; host-side placement named.
- [ ] **P4. §The θ-parameterized hero.** Axis set (cx,cy,invs,bright,radius,accent,
  bg,cr,cg,cb + headline_w); colour as 3 stacked substrate channels (`hero_channel`);
  headline as a host argmax over a θ-mixture. Measured oracle agreement.
- [ ] **P5. §Host-side preference steering (SPSA).** The `HeroSPSA` optimizer:
  two-sided perturbation, gain schedule, the warmer/colder reward model, batched
  updates. The host/substrate boundary made explicit (optimizer host-side over
  substrate-rendered output). Method now; convergence numbers from P7.

**Results — P6, P7, P8 DONE (2026-06-14)**
> §6 render-fidelity table from `experiments/gui_render_fidelity.py` (max ≤4.0e-7;
> glyph banner exact 0). §7 steering results from `experiments/gui_steering_eval.py`
> (100-press soak: 0 NaN/0 blank; brighter→1.8, darker→0.2; trend corr ±0.446) +
> optimizer convergence. P8 figures from `experiments/gui_figures.py` (hero
> mono/RGB, glyph banner, quad layout, before/after steering pair — before/after
> mean brightness 71→146/255, measured); PNGs git-ignored build artifacts;
> referenced in paper §7/§10. Reproducibility (§10) lists all commands.

**Framing / rigor / infra**
- [ ] **P9. §What we are not claiming.** Composition is host-side; the optimizer is
  host-side SPSA (NOT substrate-native training); the reward is a human button, not
  real traffic; no "one substrate program." Mirror the FV paper's discipline.
- [ ] **P10. §Related work.** VSA/holographic rendering, frozen-embedding
  computation, SPSA, human-preference optimization. Verify each cited claim against
  the source; re-download reference PDFs per session (gitignored cache), never
  commit them (CLAUDE.md §Reference PDFs).
- [ ] **P11. §Reproducibility.** Exact commands: the `demos/gui/` scripts + tests +
  the P6/P7 experiment scripts. URLs only here.
- [ ] **P12. clawRxiv CI workflow — `gui-paper-ci.yml`.** Model on
  `fv-paper-ci.yml` (own `.post_id` supersedes chain, auto-submit + commit the AI
  review back under `paper/gui-steering/reviews/`). DECIDE the trigger branch
  (gui-training vs on-merge-to-main) — note this in the item. Outward-facing: the
  first push creates a real clawRxiv post; keep the integrity rails. (If unsure
  about enabling auto-submit, surface via AskUserQuestion before wiring the push
  trigger.)
- [ ] **P13. Cross-check (no contradiction).** Verify the GUI paper does not
  contradict `paper/paper.md`, the FROZEN `paper/neurips/` (do NOT edit it —
  surface any conflict to Emma), or `planning/sutra-spec/*.md`. Fix the GUI paper,
  not the others.
- [ ] **P14. Website page (optional, human-facing).** A `docs/` page for the demo
  per the audiences split (humans read the site; agents read the repo MD). Keep it
  free of repo-internal scratchpad references. Built by `scripts/build_site.py`.

## 3. GUI extensions (deferred, autonomous — todo.md §"GUI")

- [ ] **Learned decoder / arbitrary-image generation — EMMA-GATED.** A trained
  nonlinear decoder from a latent to an arbitrary frame (constrain-train "every op
  trainable" meets GUI; the analytic whole-frame render is the fixed-weight base
  case). Ties into the weight→code / constrain-train work. **Pick the approach
  with Emma before a large build** — the loop surfaces this via AskUserQuestion
  rather than guessing an architecture. Do NOT start a large build autonomously.
- [ ] **Yantra GUI integration** — the window living in the orchestrator, per the
  Yantra OS. Forward goal; design with the Yantra submodule. Lower priority.

HARD RAILS (todo.md §GUI): every pixel on the substrate; stateful widgets are
substrate-RNNs; verify the rendered frame against a reference, measured.

## Pinned tail (always present — bracket every session)

Per the autonomous-loop skill lifecycle. Not consumed between fires.

- **A. Ensure the crons run** (`CronList`; re-create work-loop :03, auto-flush
  :15, status-report :42 if missing; all `durable: false`; all scoped to the
  `gui-training` branch — they must verify the branch is `gui-training` before
  doing any work and abort if not).
- **B. End-of-session status report** (reporting only, no commits): what advanced
  (shas + one-line), GUI queue state, how the rails held, blockers (esp. the
  Emma-gated learned decoder), test health.

## Pointers

- GUI demos: `demos/gui/`. GUI page: `docs/gui.md`. GUI agenda: `todo.md`
  §"[This year] GUI".
- a1 build spec (private): `../emmas-gstack/business/gtm/2026-06-13-a1-shortest-path.md`,
  `business/gtm/a1-implementation-spec.md`.
- Findings (dated): `planning/findings/`. Devlog: `DEVLOG.md`.
- Paper for THIS branch: `paper/gui-steering/` (the a1 / substrate-steering paper,
  §2 above). The OTHER papers — `paper/paper.md`, `paper/neurips/` (frozen),
  `paper/formal-verification/paper.md` — are main's, NOT this branch's.
- ⚠️ Non-GUI *tracks* (thrml / FV / transpiler / WASM / corpus / paper-polish on
  the main paper) live on `main`, NOT here.
