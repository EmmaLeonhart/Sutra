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

## ACTIVE — GUI: extend the Adam-RLHF demo (color / position / size + A/B UX)

_All G-track items (G1–G5) complete. The Adam-RLHF demo now steers brightness, colour,
position, and size through the differentiable substrate render, with a colour A/B window,
docs, and paper coverage — all measured. Next GUI horizon items live in `todo.md` §GUI
(learned decoder is EMMA-GATED; Yantra integration lower priority)._

---

## Pinned tail (always last — autonomous-loop lifecycle)

- [ ] **Ensure the three crons are running** — start them if this session never did,
  restart them if a planning burst / queue re-fill killed them.
- [ ] **Run the status-report action once more, independently** — an end-of-session
  summary of everything that happened this session (shas advanced, queue state, how the
  hard rails held, blockers, test-suite health).
