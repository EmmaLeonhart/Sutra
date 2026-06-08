# Substrate content addressing sharpens to crisp retrieval in a finite-β window

**Date:** 2026-06-08
**Context:** Completing the content-addressing thread (Emma's NTM/DNC hard part). The
prior finding (`2026-06-08-substrate-content-addressing-via-select.md`) showed the
substrate `select`+`similarity` content read is differentiable but, at the fixed β=1 of
`select`'s softmax, stays a *diffuse* blend. The remaining question was whether a
temperature sharpens it to crisp retrieval without losing the gradient — using the
established select-temperature lever (`select([similarity/T, …], …)`; score-scaling, no
primitive change). Script: `experiments/attention_on_ram/substrate_content_read.py`
(`temperature_sweep`); guard `test_substrate_content_read_sharpens_with_temperature`.

## Result (measured): a finite-β "does-stuff" window

Training a query through the compiled substrate `select`+`similarity`, scaling the
content scores by β (= 1/T):

| β (=1/T) | cos(read, target) | weight on target | ‖∇q‖@0 | regime |
|---|---|---|---|---|
| 1  | 0.80 | 0.37 | 0.028 | diffuse (under-sharpened) |
| 4  | 0.9996 | 0.94 | 0.080 | sharp + learnable |
| **16** | **1.0000** | **0.9998** | 0.347 | **crisp retrieval, gradient flows** |
| 64 | 0.06 | 0.0002 | 0.326 | collapsed (over-sharpened) |

At **moderate temperature (β≈4–16)** the substrate content read sharpens to *crisp*
content retrieval — `cos(read, target) → 1.0`, attention weight on the target row → 1.0
— **while the gradient still flows** (‖∇q‖ = 0.35 at β=16). The query learns to address
the right memory row by content *and* reads it cleanly.

## The window is bounded on both sides — and that is Emma's point, measured

- **β too small (=1):** diffuse blend; the read is a blurry mixture (weight 0.37), only
  directionally correct.
- **β too large (=64, toward the `HARD_K → ∞` hardmax limit):** training **collapses**
  (cos 0.06, weight ~0) — the softmax saturates and the useful gradient regime breaks,
  the same saturation that makes the constructed 1e10-hardmax weights untrainable.

So content-based addressing "does stuff" (learns where to look *and* retrieves cleanly)
only in a **finite-temperature window** between diffuse and saturated. This is the
measured form of the distinction Emma drew: a finite-β softmax is the
"logically-differentiable-that-works" regime; the argmax / β→∞ hardmax limit is inert
or unstable. The boundary is not hand-waved — it is on the table above.

## Status of the content-addressing thread

Complete and measured on the substrate, no new primitive:
- content addressing IS a substrate op (`select`+`similarity`, as `fuzzy_dispatch.su`);
- it is differentiable on the compiled substrate (gradient flows into the query);
- it sharpens to crisp retrieval at moderate temperature via the established
  score-scaling lever (`similarity/T`), while staying learnable;
- the useful regime is a finite-β window; the hardmax limit collapses it.

Scope: host SGD (the sanctioned fit role); forward read is the compiled substrate ops.
Not claimed: training the composed reduced network end-to-end (still open); a `.su`
program with a trainable query rather than a host loop (a natural packaging step).
