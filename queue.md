# Sutra — Work Queue (`gui-training` branch)

**This file is a queue, not a state snapshot.** It lists what is being
worked on right now and what is next. Finished work lives in `git log`,
`DEVLOG.md`, and `planning/findings/` — NOT here. When an item is done,
delete it in the same commit as the work and append a dated entry to
`DEVLOG.md` (CLAUDE.md §Workflow Rules). Never leave `[x]` / "DONE" behind.

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

## 1. Warmer/colder self-morphing hero demo (the "a1" GUI training demo)

**The headline GUI training item.** Assembly of parts that already exist —
runtime-parameter whole-frame rendering (`demos/gui/whole_frame.py`,
`frame_moving.su`; params are per-call broadcast buffers, no recompile) + a
batched SPSA optimizer + warmer/colder controls — into one recordable
interactive demo. No new substrate research. (Emma records it herself once
built; building is autonomous.)

- [ ] **Warmer/colder steering demo.** A substrate-rendered hero (headline glyphs
  via the 36-glyph renderer + accent glow/ring + a CTA block) whose
  layout/scale/color/spacing/headline-choice form a parameter vector θ ∈ R^8–16;
  WARMER / COLDER buttons emit scalar reward (+1 / −1, smoothed); a batched SPSA
  step updates θ with [-1,1]^d clamping; the hero visibly morphs. Local window
  first (screen-recordable), optional web wrapper later. Done = a stranger
  steering it sees directionally-consistent morphing within seconds, with no
  NaN/blank frames across a 100-press session. Full build spec (5 steps, with the
  SPSA port source) lives in the private founder hub:
  `../emmas-gstack/business/gtm/2026-06-13-a1-shortest-path.md` (+ the detailed
  `business/gtm/a1-implementation-spec.md`). Honest rails: composition is
  host-side and the optimizer is host-side SPSA over substrate-rendered output —
  do NOT over-claim "one substrate program" or substrate-native training.

**Build order (decompose as the loop reaches each):**
- [ ] **1a-colour. Colour channels for the θ hero.** Render core + headline-glyph
  selector are DONE (`frame_hero.su`/`render_hero()`; `render_hero_with_headline()`
  + `select_headline()` argmax over θ['headline_w'] + substrate-glyph banner; all
  oracle/equality-verified; DEVLOG 2026-06-14). Remaining: add **colour channels**
  to the θ hero (per-channel brightness/hue, the `frame_rgb.su` precedent — 3
  whole-frame substrate fields stacked) so θ also drives colour. Keep
  runtime-parameter (no recompile); verify each colour axis against a reference
  (MEASURED). Then 1a is complete → 1b (SPSA).
- [ ] **1b. Batched SPSA optimizer (host-side).** Port the SPSA step from the
  a1 spec: two-sided perturbation, scalar reward in, θ-update out, [-1,1]^d clamp.
  Unit-test the update direction on a synthetic reward (gradient sign correct).
- [ ] **1c. Warmer/colder controls + window loop.** Wire WARMER/COLDER buttons
  (reward +1/−1, smoothed) into the live window (`live_demo.py`/`window.py` event
  loop) so a press triggers an SPSA step and the hero re-renders. No NaN/blank
  frames.
- [ ] **1d. 100-press soak + record-ready pass.** Run a scripted 100-press soak;
  assert no NaN/blank frame and directionally-consistent morphing. Note the
  measured result in `DEVLOG.md`. Optional web wrapper deferred.

## 2. GUI extensions (deferred, autonomous — todo.md §"GUI")

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
- ⚠️ Non-GUI tracks (thrml / FV / transpiler / WASM / corpus / paper) live on
  `main`, NOT here.
