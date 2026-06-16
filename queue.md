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

## 🔝 TOP PRIORITY — reference-context system (Emma 2026-06-16, 11:45 incorporation)

A cleanvibe-style **reference-context** system: download reference PDFs/pages we base
research directions on, analyze them for context, but **DO NOT COMMIT them** (copyright —
they are reference material, not repo content). Use robust download + analyze scripts; keep
the artifacts gitignored. May add more links / reorganize later. (Emma's note also: the
work loop comes FIRST — it is already running; this context can wait behind it.)

- [ ] **RC1 — reference-context dir + gitignore.** Create a `reference-context/` directory
  (or similar) and add it to `.gitignore` so the downloaded PDFs are never committed.
  Add a short `reference-context/README.md` (this one CAN be committed) listing the
  sources + the "downloaded for context, not redistributed" rationale.
- [ ] **RC2 — robust download + analyze script.** A script (e.g.
  `scripts/fetch_reference.py`) that robustly downloads a list of URLs into
  `reference-context/` (retries, proper User-Agent, skips existing, handles arXiv
  `/abs/` → `/pdf/`), and can extract text for analysis. Reuse cleanvibe's
  download/analyze pattern if one already exists in-repo before writing new.
- [ ] **RC3 — fetch + analyze the seed references** (download, do not commit):
  - Schmidhuber FKI-126-90 (revised): `https://people.idsia.ch/~juergen/FKI-126-90_%28revised%29bw_ocr.pdf`
  - arXiv 1802.08864: `https://arxiv.org/pdf/1802.08864`
  - arXiv 2604.06425: `https://arxiv.org/abs/2604.06425`
  - metauto.ai neural computer: `https://metauto.ai/neuralcomputer/`
  Then write short context notes (what each contributes to our research directions) under
  `reference-context/` or `planning/` — notes committable, source PDFs not.

---

## ACTIVE — GUI: extend the Adam-RLHF demo (color / position / size + A/B UX)

- [ ] **G3 — multi-axis steering tests.** Beyond color: synthetic raters for POSITION
  (prefer glow toward a corner → centroid moves the right way) and SIZE/spread (prefer
  wider glow → `invs` moves), each measured, finite, and flipping with preference.
  Extend the suite; document which axis each rater exercises.

- [ ] **G4 — RGB window UX.** Update `adam_window.py` (or add `adam_window_rgb.py`) to
  paint the color A/B pair with clear A / B labels and a caption surfacing the moving
  axes / current mean color. I/O only — keep it untested in CI per the existing
  convention (steering logic stays covered headless). Add a `run_adam_rgb_gui.bat` if a
  new entrypoint. Manually smoke once; do NOT claim the window works without running it.

- [ ] **G5 — docs + paper.** Update `docs/gui.md` and `paper/gui-steering/` to cover the
  multi-axis / color extension — measured numbers only, no overclaim. Lower priority;
  after G1–G4 land green.

---

## Pinned tail (always last — autonomous-loop lifecycle)

- [ ] **Ensure the three crons are running** — start them if this session never did,
  restart them if a planning burst / queue re-fill killed them.
- [ ] **Run the status-report action once more, independently** — an end-of-session
  summary of everything that happened this session (shas advanced, queue state, how the
  hard rails held, blockers, test-suite health).
