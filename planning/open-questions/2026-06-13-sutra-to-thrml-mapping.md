# Sutra → thrml mapping (step 1 — LIVE, Emma-driven, NOT settled)

**Status:** in-progress design conversation with Emma (2026-06-13). This records
her steer as it forms — do NOT treat anything here as final or start codegen off
it until Emma confirms. Direction was set earlier: **vectors → spin-node graph**
(bind/bundle/similarity become factor interactions sampled by block Gibbs). API
facts: `planning/findings/2026-06-13-thrml-api-study.md`.

## Emma's encoding steer (2026-06-13)

- thrml models computation as **individual memory spaces**; the natural atom is
  that **each spin node = one bit** (a `SpinNode` is ±1).
- A Sutra **memory space = a combination of bits** — i.e. a multi-bit register of
  spin nodes — rather than a continuous-value embedding. (This resolves the
  open "how does a continuous vector component become a discrete spin?" — the
  answer is **bits**, a bit-register encoding.)
- **Bit-width per memory space is open** ("I don't know how many bits it would be
  for any given memory space").

## Open specifics (to settle WITH Emma — do not invent)

1. **What is a "memory space" in Sutra terms?** Candidates: a whole Sutra value /
   hypervector (one value = one bit-register); a single vector component/axis;
   the synthetic axes (real/imag/truth); a named variable. (Asked 2026-06-13.)
2. **Bit-width** per memory space, and what the bits mean (fixed-point of a
   component? a learned code? one-hot/thermometer?).
3. **How each op acts on bit-registers as a factor interaction** (bind / bundle /
   similarity), and how `sample_states` recovers the op's output.
4. **Block partition** that keeps each thrml `Block` conditionally independent
   under that factor topology.

## Non-destructive constraint (carried from queue.md)

The thrml backend is an additive CLI option; it does not touch the PyTorch
pipeline. Nothing here changes that.
