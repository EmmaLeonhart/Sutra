# Sutra — GUI branch Work Queue

**This file is a queue, not a state snapshot.** It lists what is being
worked on right now and what is next. Finished work lives in `git log`,
`DEVLOG.md`, and `planning/findings/` — NOT here. When an item is done,
**delete it** in the same commit as the work and append a dated entry to
`DEVLOG.md`. Never leave "✅ DONE / SHIPPED" status in this file.

`todo.md` is longer-horizon. Items migrate `todo.md` → `queue.md` →
deleted on completion. Keep the task tool in sync with this file.

---

## Branch context (read first, do not work on)

- **This is the `gui` branch (Emma 2026-06-16, remote control).** A dedicated
  branch for GUI work, split off `main` so the GUI loop is not swallowed by the
  transpiler / FV / training backlog. The non-GUI backlog stays on `main`; this
  branch's queue is GUI-only.
- **Primary GUI direction (Emma 2026-06-16):** *extend the Adam-RLHF demo* —
  richer preference dimensions (color / position / size), pairwise A/B preference
  UX, more render params exposed to Adam. Bounded, incremental, integrity-railed.
  (The full learned-decoder / arbitrary-image generation remains EMMA-GATED and is
  NOT in scope here — see `todo.md` §GUI; pick the approach with Emma before any
  large decoder build.)
- **NEVER use `Math.mod`** (Emma 2026-06-12 — measured vector-collapse/NaN, finding
  `2026-06-12-rotation-mod-vector-collapse-…`). For wrap/periodic behavior use
  complex rotation (`demos/gui/live_frame.su`).
- **HARD RAILS (CLAUDE.md):** every pixel is rendered on the substrate; stateful
  widgets are substrate-RNNs; every gradient is real autograd through the substrate
  render; the reward head + optimizers are host-side and named so. Verify the
  rendered frame / gradient against a reference, measured. No overclaiming.
- **`paper/paper.md` UNFROZEN; `paper/neurips/` permanently FROZEN (do NOT touch).**
- **CI on this branch: use `gh workflow run demos-ci.yml --ref gui` (workflow_dispatch),
  then watch the run — do NOT open a PR to main.** `demos-ci`/`compiler-ci` only auto-run on
  push-to-main or PRs, and a PR from this isolated branch conflicts with main (so it can't
  even run pull_request CI). gui is kept SEPARATE from main by design — no merging to main.
  Note also: local-green ≠ CI-green here — CI runs on CPU, local is CUDA; always verify on CI.

## Existing demo state (the base this track extends)

- `demos/gui/hero_adam.py` — `HeroAdam`: pairwise online-RLHF (Bradley-Terry reward
  head) over 7 MONO θ axes (cx, cy, invs, bright, radius, accent, bg); Adam backprops
  the preference THROUGH the differentiable `render_hero_torch` substrate render.
- `demos/gui/adam_window.py` — tkinter window: current vs proposed pair, WARMER/COLDER.
- `demos/gui/whole_frame.py` — `render_hero_torch` (mono, DIFFERENTIABLE) and
  `render_hero_rgb` (3-channel color, **NOT differentiable** — uses
  `torch.full(..., float(val))` which severs autograd; `cr/cg/cb` tints applied on the
  substrate via `hero_channel`). Tests: `test_hero_adam.py`, `test_hero_differentiable.py`.

---

## ✅ DONE foundation — Adam-RLHF demo (G1–G5)

_G1–G5 complete: the Adam-RLHF demo steers brightness, colour, position, and size through
the differentiable substrate render, with a colour A/B window, docs, and paper coverage —
all measured, CI-green on CPU. This is the foundation the trainable-button track builds on._

## 🎯 ACTIVE VISION — trainable click-button (owner preference + CTR) — Emma 2026-06-16

> **✅ DESIGN APPROVED (Emma "barrel through", 2026-06-16).** Spec:
> `docs/superpowers/specs/2026-06-16-trainable-click-button-design.md`. Defaults locked:
> Phase 1 (substrate core) before Phase 2; preset copy ("Buy now"/"Get started"/"Learn more")
> as placeholders. Now executing Phase 1 (B1→B2→B3) via TDD, CI-green on CPU.

**Vision (Emma):** a clickable, *JS-like* button that we **train** to optimize for *what the
website owner wants* AND *what gets the biggest CTR*. A demo, linked to the `sutra-from-ts`
(JS) frontend. Builds directly on the Adam-RLHF machinery above.

**Settled design decisions (from Emma, 2026-06-16 brainstorm):**
- **CTR signal = BOTH** — a deterministic *simulated audience* model drives training/CI;
  *real clicks* in a live browser drive the demo.
- **Trainable surface = visual + preset copy** — continuous θ (bg/text colour, width,
  height, corner-radius, cx/cy) + a *discrete* copy choice (argmax over a preset set), i.e.
  the hero's continuous-θ + discrete-headline split reused.
- **Objectives = weighted blend + knob** — `R(θ) = α·owner_pref + (1−α)·CTR`; owner_pref is
  the existing pairwise Bradley-Terry head (warmer/colder), CTR the click signal; α slider
  shows the taste-vs-clicks tension.
- **JS linkage = real HTML/JS button + substrate twin** — live demo is a real `<button>`
  (real clicks); training/CI uses a *differentiable substrate-rendered twin*; button spec
  authored in TS → `sdk/sutra-from-ts/`.

**Provisional decomposition (NOT yet started — pending the spec):**

_Phase 1 — substrate core (CI-testable, mirrors G1–G5):_
- [ ] **B3 — `ButtonAdam` dual-reward controller.** Generalize `HeroAdam`: combined
  `R = α·owner_pref + (1−α)·CTR`, continuous-θ Adam through the twin + discrete-copy argmax.
  TDD: CTR-pref raises CTR, owner-pref moves to owner taste, α knob trades off — measured,
  flips, robust seeds, CPU.

_Phase 2 — live browser / JS layer (after Phase 1 green):_
- [ ] **B4 — live HTML/JS button + click logging.** Real `<button>` styled from θ; clicks →
  CTR; owner A/B control → owner_pref. Local bridge server (the `counter_substrate_server.py`
  pattern). I/O layer, untested in CI; smoke manually.
- [ ] **B5 — `sutra-from-ts` button spec.** Author the button spec in TS, run through the
  TS frontend → Sutra program — the concrete JS tie-in.
- [ ] **B6 — docs + paper.** Cover the trainable-button demo, measured.

---

## Pinned tail (always last — autonomous-loop lifecycle)

- [ ] **Ensure the three crons are running** — start them if this session never did,
  restart them if a planning burst / queue re-fill killed them.
- [ ] **Run the status-report action once more, independently** — an end-of-session
  summary of everything that happened this session (shas advanced, queue state, how the
  hard rails held, blockers, test-suite health).
