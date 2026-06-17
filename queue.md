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

_Phase 1 — substrate core (CI-testable, mirrors G1–G5): **✅ COMPLETE (B1–B3).**_
_The substrate button (B1), simulated audience (B2), and ButtonAdam dual-reward controller
(B3) are built, tested, and robust across seeds on CPU. Owner-only → owner's blue taste;
CTR-only → warm high-contrast + "Buy now" (CTR ~0.95); the α knob trades off. CI-verify on
the gui branch via `gh workflow run demos-ci.yml --ref gui` before relying on it._

_Phase 2 — live browser / JS layer: **✅ COMPLETE (B4–B6).**_
_B4 `button_server.py` (`ButtonBridge` + HTTP) + `button_page.html`: a real `<button>` styled
from θ, owner A/B → `prefer`, visitor clicks → tallied CTR. Bridge logic CI-tested
(`test_button_server.py`) and the HTTP layer smoked headlessly; the in-browser DOM
rendering/clicking is the only un-smoked piece (needs a browser — Emma to exercise). B5
(sutra-from-ts) + B6 (docs/paper) done._

**🎉 Trainable click-button (B1–B6) complete.**

## 🟦 Yantra GUI integration — UNBLOCKED (Emma 2026-06-16: shallow-clone, no submodule)

> Correction: Yantra is NOT blocked on a missing submodule. It is shallow-cloned (depth-1, no
> submodules) into `external/Yantra/` (gitignored, preserved here / re-freshed by the cron):
> `git clone --depth 1 --no-recurse-submodules https://github.com/EmmaLeonhart/Yantra external/Yantra`.

**Integration contract (from the clone):** Yantra `apps/` GUI entries are HOST SURFACES over
substrate compute — `apps/gui-rust/` (a `minifb` Rust window) spawns the Sutra substrate
server `external/Sutra/demos/gui/counter_substrate_server.py` and paints its per-frame output;
apps are admitted via the kernel (`Init.admit_from_path`), processes described by `.yprc`
manifests. The richer GUI demos already live Sutra-side under `external/Sutra/demos/gui/`. So
"the window living in the orchestrator" = the substrate GUI window as a Yantra-orchestrated
surface that spawns a Sutra substrate-server.

- [ ] **Y1 — button substrate-server (Sutra-side, the Yantra-spawnable bridge).** A
  stdin/stdout substrate server for the trainable button mirroring
  `counter_substrate_server.py` (Yantra's gui-rust spawns that pattern): commands in (init /
  click current|variant / owner-prefer / quit), substrate-rendered button frame + state out.
  Reuses `ButtonAdam`/`render_button_torch`. Sutra-side, CI-testable (protocol test, no
  browser/Rust). This is the buildable-here half of the integration.
- [ ] **Y2 — Yantra apps/ entry (in the Yantra repo).** A `apps/gui-button/` surface that
  spawns Y1, mirroring `gui-rust`. Lives in `external/Yantra` (the Yantra repo) — drafted here,
  applied in a Yantra session (Sutra is pinned there as `external/Sutra`). Not committable from
  Sutra.
- [ ] **Y3 — integration docs.** Note the button↔Yantra surface in `docs/gui.md` / CLAUDE.md
  §"Cross-repo workflow", measured.

- [ ] **B8 — browser smoke of `button_page.html` (Emma + browser).** NOT autonomous — needs a
  real browser. Run `python demos/gui/button_server.py --live-ctr` (or default), click in the
  page, confirm the buttons restyle, CTR tallies, and (live-ctr) the design tracks clicks.

_B7 (learned visual CTR head) ✅ + B9 (click-driven copy bandit) ✅ — the real-click CTR loop
is FULLY closed: clicks train both the differentiable visual reward (ascended through the
render) and a UCB bandit over copy (settles on "Buy now"). Only B8 (browser smoke) remains —
browser-blocked._

---

## Pinned tail (always last — autonomous-loop lifecycle)

- [ ] **Ensure the three crons are running** — start them if this session never did,
  restart them if a planning burst / queue re-fill killed them.
- [ ] **Run the status-report action once more, independently** — an end-of-session
  summary of everything that happened this session (shas advanced, queue state, how the
  hard rails held, blockers, test-suite health).
