# Meta-demo replication — the symbol-stable Neural Computer demo

## What Meta actually built (arXiv:2604.06425, *Neural Computers*, 2026)

Meta AI + KAUST (authors incl. Mingchen Zhuge, Yuandong Tian, Vikas
Chandra, Jürgen Schmidhuber), submitted April 2026. They fold
computation, memory, and I/O into a single learned runtime state, with
the **Completely Neural Computer (CNC)** — "stable execution, explicit
reprogramming, durable capability reuse" — as the long-term goal.
Their instantiation is **video generation of screen frames**:

- **NCCLIGen (CLIGen) — terminal.** Treats CLI use as
  *text-and-image-to-video*: a CLIP image encoder on the first frame +
  a T5 text encoder on the prompt feed a **DiT (Diffusion
  Transformer)** that rolls out terminal frames. Trained on ~1,100 h
  of asciinema terminal recordings (~824k streams).
- **NCGUIWorld (GUIWorld) — desktop.** The same idea for a GUI, trained
  on ~1,510 h of Ubuntu desktop recordings.
- Headline finding: 110 h of goal-directed data beat 1,400 h of random
  data — quality over volume.
- Stated open problems, in their own words: routine reuse, controlled
  updates, and **symbolic stability**.

That last one is the crack we drive a wedge into.

## What we compete on — and what we don't

**We are not chasing the video.** Generating plausible screen *frames*
is their game, not ours — a diffusion model painting pixels of a
terminal is a fundamentally different (and, for exactness, worse) thing
than *running* the terminal. We could do frame-/video-style work
*later, if and when the GUI layer is up*, but it is explicitly **not
the focus**.

**We compete on symbolic stability — the axis their own paper concedes
is unsolved.** On Yantra a terminal *executes*: the text it shows is
*computed*, not *generated*, so it is exact by construction and does
not drift however long the session runs. Same surface as theirs,
opposite engineering, and we win precisely where they say they are
weak.

**Different architecture is the point, not a liability.** Yantra is not
video diffusion — it is a compiled, differentiable tensor-graph
substrate (Sutra). But it is *still a trainable neural network*: every
Yantra program is differentiable and backprop-trainable, so we sit in
the same "neural computer" design space they opened while taking the
opposite posture (execution, not simulation). "We do it differently"
is a feature — we are not trading away the trainable-NN property to get
exactness; we get both.

## The demos, in order of ambition

### 1. Symbol-stable terminal — the near-term core (answers CLIGen)

A real terminal whose output is computed exactly. It need not even be
keyboard-driven — a scripted or button-driven command sequence is
enough to make the point. Where CLIGen's DiT *hallucinates* plausible
terminal text that drifts, Yantra's terminal prints the exact bytes the
program produced.

**Update (2026-05-24):** built — `apps/terminal/` (a command reader over
kernel-admitted utilities: `echo`, `calc`, `help`). `echo` is bit-exact
through `echo.su`; a scripted N-step trace is exact at every step (zero
drift). See the Stage-2 roadmap entry below for details.

### 2. A visible calculator app — the optimal demo (exceeds what Meta did)

The strongest single thing we can show: a calculator with **buttons you
press**, where the displayed result is *actually computed* on the
substrate and is exact every time. This exceeds Meta outright — their
GUIWorld would *generate a plausible-looking frame* of a calculator and
the arithmetic would be approximate or wrong (a diffusion model does
not compute 4729 × 8831), while ours runs real arithmetic in Sutra
(whose paper measures exact substrate arithmetic) and shows the true
result. It is interactive and visual with no video generation
anywhere. It is a stretch — it needs a minimal GUI (a button grid + a
display) — but it is the demo that makes the contrast undeniable to a
non-expert: *press the buttons, get the right answer, every time.*

**Update (2026-05-24):** the **CLI calculator** ships
(`apps/calc/calc.py`) — full expressions with precedence, `+ - * /`,
exact or refused (`tests/test_calc.py`, 57 cases). **Operation selection
runs ON the substrate** now: `switch.su` computes all four ops and picks
one via Sutra's `select` made a true one-hot by softmax saturation (Sutra
v0.6.1 `dot` for the separating score) — host `OPS[op]` dispatch is gone.
The calc runs the substrate in **float64** (v0.6.2 `runtime_dtype`), so
exact integers hold to 2⁵³ (~9.007e15). **Remaining purity gap:** the
returned value is still a host `Fraction` behind a host-oracle refuse-gate
(step c in `planning/23`) — closing it drops "never a wrong answer," a
product decision left for Emma. Parse-on-substrate is still host-side too.

A host **Tkinter button GUI** was built and then **removed (2026-05-24)**:
a CPU window is not the Yantra GUI, and presenting it as the
"press-buttons" demo overstated what runs on the substrate. The real
press-buttons demo waits on the OS-native GUI — the "everything is a
browser" layer (Sutra-native renderer + HTML/CSS + WebGL), build-sequence
milestone 3, unbuilt. What remains for the *optimal* version:
substrate-pure parse/output (`planning/23`), and arbitrary-precision
numbers past the **float64 2⁵³** ceiling (digit arrays; float64 already
took the calc past float32's 2²⁴), and eventually that OS-native GUI.

### 3. Frame / desktop work — deferred, optional

Only if and when the GUI layer is mature. Not the focus; recorded so
the option is on the books, not as a commitment.

## Making it measurable

A scripted interaction trace of N steps; record every symbol that
should appear (output text, numbers, labels). Yantra target: **100%
exact match at every step, zero drift as N grows.** The contrast
figure — Yantra flat at 100%, a generative (DiT-frame) baseline
decaying with horizon — is the headline result. For the calculator: a
battery of arithmetic where the generative posture is provably
unreliable and ours is provably exact.

This rides on the Sutra empirical foundation (100% bundle decoding
through width k=8; ~1.5×10⁻¹⁵ bind/unbind round-trip) and on what the
kernel already does today: `apps/echo` round-trips a symbol bit-exact.
**First real data point (2026-05-23):** the Stage-1 harness
(`tests/test_symbol_fidelity.py`) measures Yantra at 1024/1024 exact,
max |err| = 0.0, flat across the horizon — the left end of the figure
is pinned at perfect. **Terminal-surface data point (2026-05-24):**
through the actual command reader (`apps/terminal`), an N=60 interaction
trace mixing `echo` (text symbols) and `calc` (numeric symbols) is exact
at every step — drift = 0/60 (`test_zero_drift_as_n_grows`). The same
zero-drift result now holds end-to-end through the *terminal*, not just a
passthrough service. What remains for the full figure is the **baseline**
(the decaying right side): reproduce a CLIGen-shaped DiT-frame model or
cite Meta's published degradation numbers — that is the open piece, not
the Yantra side.

## Shipping it — a downloadable demo on the site

Once enough of a demo exists, put a **downloadable, runnable artifact
on the Yantra website** (yantraos.org) so anyone can run it
and watch the symbol stability for themselves — the terminal first, the
calculator when it lands. A thing people can download and run beats any
screenshot, and it is the natural place to host the contrast against a
drifting generative baseline.

## Roadmap — current state → the demos

Gated on the build sequence (`planning/18`: kernel → CLI → GUI).

- **Stage 0 — already true.** Exact symbol round-trip through the kernel
  router; `apps/echo` preserves text bit-exact. The claim in miniature.
- **Stage 1 — symbol-fidelity harness. DONE (2026-05-23; text added
  2026-05-24).** `tests/test_symbol_fidelity.py` pushes 1024 distinct
  **numeric** symbols through a real Sutra passthrough service + the
  kernel router and recovers every one **bit-exact** (1024/1024, max
  |err| = 0.0, zero drift first-decile vs last-decile), **and** 1024
  distinct **text** lines, each recovered verbatim via
  `make_string`/`string_to_python` — the terminal-text stability axis
  Meta's NCCLIGen lists as unsolved. The left end of the
  symbol-fidelity-vs-horizon figure is pinned at perfect, for both
  numbers and text. No new Sutra primitives were needed.
- **Stage 1b — CLI calculator. DONE (2026-05-24).** `apps/calc/` +
  `tests/test_calc.py` (57 cases, incl. a randomized property test that
  it never returns a wrong answer across 100 fuzzed expressions): type
  `5 * 10 =` → `50` — or a full expression like `2 + 3 * 4 = 14`
  (precedence + parentheses). One `switch.su` computes all four ops and
  **selects on the substrate** via Sutra's `select` (a true one-hot by
  softmax saturation, scored with `dot`; host `OPS[op]` removed), in
  **float64** so exact integers reach 2⁵³. **Never a wrong answer:** every
  result is verified exact against a host oracle and *refused* if it
  can't be confirmed — non-exact quotients (10/3), divide-by-zero, and
  results past float64's 2⁵³ exact range all refuse rather than guess.
  (The returned value is still the host oracle's, not the substrate's
  decode — step c, a product decision; see `planning/23`.) The "text
  parsing + reliable math" proof — the calculator's compute core.
- **Stage 2 — terminal surface. DONE (2026-05-24).** `apps/terminal/`
  is a command reader over kernel-admitted utilities: `echo <text>`
  carries text **bit-exact** through `echo.su` and shows the substrate's
  decoded string (not a host re-echo); `calc <expr>` evaluates on the
  calc substrate; `help`; unknown commands return a shell-style
  `command not found`. `Terminal.run_script` runs an N-step interaction
  trace exact at **every** step — the § "Making it measurable" zero-drift
  claim at small N. `tests/test_terminal.py` (19 cases);
  `python apps/terminal/demo.py` prints a transcript. **Which utility a
  typed command names is admission/routing = host orchestration by
  design** (the Connectome Manager's job), distinct from calc's
  *which-operation* dispatch (substrate compute). Does NOT close calc's
  step-c purity gap — composes calc as-is. Next: utilities beyond echo
  (`cat`/`ls`/`wc`, gated on Sutra string/IO/FS vocabulary); a keyboard
  front-end belongs to the GUI layer (milestone 3).
- **Stage 3 — the calculator app.** A minimal GUI (button grid +
  display) over real Sutra arithmetic. The optimal demo; needs the GUI
  layer. **Precision note (updated 2026-05-24):** the real-axis encoding
  is now selectable, and the calc runs **float64**, so exact integers hold
  to 2⁵³ (~9.007e15) — the headline product 4729 × 8831 = 41,761,799 is
  exact today (it was refused under float32's 2²⁴). Going past 2⁵³ needs an
  arbitrary-precision digit-array encoding (make_string-style codepoints,
  carries on the substrate), not a single real-axis value — still open.
- **Stage 4 — ship + measure.** A downloadable demo on the site, plus
  the contrast figure against a generative baseline.

## Dependencies — what is not built

- CLI utilities + Sutra string / IO / FS vocabulary for the terminal
  (only `echo` exists).
- The GUI layer (renderer, layout engine, WebGL) for the calculator —
  not started.
- A generative baseline to plot against (reproduce a CLIGen-shaped
  model or cite Meta's reported degradation).

## Open questions

- How large must N be for the contrast to be unanswerable?
- Which baseline — a re-implemented DiT-frame stand-in, an off-the-shelf
  model, or Meta's published numbers?
- Cheapest convincing Stage 1/2 (a minimal shell + a few utilities)
  before the full Q-list in `todo.md` § 2 lands?
- Can the calculator be a small carve-out (a button grid + display)
  ahead of the full GUI layer, since it needs far less than a browser?

## Cross-references

- `planning/16-related-work.md`, `paper/paper.md` § 7 — the Meta
  contrast.
- `planning/18-kernel-browser-readiness.md` — build-sequence gating.
- `todo.md` § 5 — this as a tracked ambition.
