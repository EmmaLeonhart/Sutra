# Trainable click-button demo — design

**Date:** 2026-06-16 · **Branch:** `gui` · **Status:** approved (Emma, "barrel through")

## Vision

A clickable, JS-like button that we **train** to optimize two objectives at once — *what the
website owner wants* and *what gets the biggest click-through rate (CTR)*. A demo, linked to
the `sutra-from-ts` (JavaScript) frontend, built directly on the Adam-RLHF substrate-steering
machinery already shipped (G1–G5: differentiable substrate render + preference gradient).

## Settled decisions

1. **CTR signal = BOTH.** A deterministic *simulated audience* model drives training/CI; real
   clicks in a live browser drive the demo.
2. **Trainable surface = visual + preset copy.** Continuous θ (button bg colour, text colour,
   width, height, corner sharpness, position `cx,cy`) + a *discrete* copy choice (argmax over
   a preset set: `"Buy now" / "Get started" / "Learn more"`). Same continuous-θ +
   discrete-headline split as the hero.
3. **Objectives = weighted blend + knob.** `R(θ) = α·owner_pref + (1−α)·CTR`. `owner_pref` is
   the existing pairwise Bradley-Terry reward head (warmer/colder); `CTR` is the click signal.
   `α ∈ [0,1]` is a tradeoff knob (1 = pure owner taste, 0 = pure clicks) that surfaces the
   tension between a tasteful button and a garish high-CTR one.
4. **JS linkage = real HTML/JS button + substrate twin.** Live demo is a real `<button>`
   (authentic clicks); training/CI uses a *differentiable substrate-rendered twin*; the button
   spec is authored in TypeScript and run through `sdk/sutra-from-ts/`.

## Architecture

### Phase 1 — substrate core (CI-testable, mirrors G1–G5)

- **B1 — substrate button render.** `demos/gui/button_frame.su` + `render_button_torch(size,
  θ)` (in `whole_frame.py` or a new module). The button field is a smooth squircle mask
  expressible in substrate arithmetic — `inside ≈ 1 − ((dx/w)^4 + (dy/h)^4)` clamped — filled
  with the bg tint, over a page background; the chosen copy's glyph banner (existing substrate
  font/headline machinery) is composited in the text tint (host-side compositing, named).
  Returns an `(size,size,3)` RGB frame, **differentiable** in the continuous θ. Floor the
  colour/brightness boxes against the all-black collapse trap (lesson from the hero colour fix:
  `tint·0 = 0`).
- **B2 — simulated audience (CTR) model.** A deterministic host-side function mapping a
  rendered button (+ its copy choice) → click probability in [0,1]. Rewards legible contrast
  (text vs button vs page), a readable-but-not-huge size, and punchier preset copy. Labeled
  *simulated* — not real traffic.
- **B3 — `ButtonAdam` dual-reward controller.** Generalize `HeroAdam`: combined reward
  `R = α·owner_pref + (1−α)·CTR`; Adam ascends `R(render(θ))` through the differentiable twin
  for continuous θ; the discrete copy is chosen by argmax of `R` over the preset set each
  round. Owner preference trained via the existing pairwise BT head on warmer/colder choices.

### Phase 2 — live browser / JS layer (after Phase 1 green)

- **B4 — live HTML/JS button + click logging.** A real `<button>` styled from the current θ
  (bg/text colour, size, radius, copy); user clicks → CTR signal; an owner A/B control →
  owner_pref. Browser↔controller via a small local bridge server (the existing
  `demos/gui/counter_substrate_server.py` pattern). I/O layer, untested in CI; smoke manually.
- **B5 — `sutra-from-ts` button spec.** Author the button spec in TypeScript, run through the
  TS frontend → Sutra program — the concrete JS tie-in.
- **B6 — docs + paper.** Cover the trainable-button demo (owner pref + CTR, the α tradeoff),
  measured, no overclaim.

## Data flow (training loop, Phase 1)

```
θ (continuous + discrete copy)
  → render_button_torch  (differentiable substrate twin, RGB frame)
  → [ owner_pref head R_o(frame) ]   (host, pairwise BT, from warmer/colder)
  → [ simulated audience CTR(frame, copy) ]  (host, deterministic)
  → R = α·R_o + (1−α)·CTR
  → Adam ascends R through the substrate render → updates continuous θ;
    argmax R over preset copy → updates discrete copy
```

## Testing / CI (Phase 1, CPU, via `gh workflow run demos-ci.yml --ref gui`)

- Button-twin **render fidelity** vs a per-pixel host oracle (like the hero fidelity table).
- **Gradient** flows to continuous θ through the substrate button render (grad_fn set, non-zero
  on colour/size/position axes), finite.
- **CTR steering:** with α=0, a high-CTR-seeking run raises the simulated CTR; **owner steering:**
  with α=1, an owner-preference run moves toward the owner's taste; **α knob:** intermediate α
  trades off, measured and flipping. Robust across seeds, on CPU.
- Local-green ≠ CI-green: always confirm on CI (CPU), per the colour-trap lesson.

## Hard rails

Every pixel of the twin is rendered on the substrate; every gradient is real autograd through
it; the reward heads, the simulated audience, Adam, and the browser bridge are host-side and
named so. Real clicks are a real signal; the simulated audience is labeled simulated. No
overclaim of an end-to-end substrate program.

## Out of scope

Free-text generated copy (decoder-adjacent, EMMA-gated). Real ad-network traffic. Multi-button
layout optimization. These are later horizons, not this demo.
