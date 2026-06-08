# Content-based soft addressing learns; hard addressing is differentiable-but-inert

**Date:** 2026-06-08
**Context:** Emma's correction on the NTM/DNC track — editing RAM "normally" (indexed
read, a hard `argmax` location read, or a *fixed* per-position weighted sum) is the
easy side and is either non-differentiable in the address or not query-conditioned.
The hard, load-bearing thing is **content-based soft addressing** (the read location
computed by a softmax over query·content scores), because the gradient flows back into
the query so the system can *learn where to look*. Emma's hypothesis: that is what
separates "theoretically differentiable but never improves" from "a logical
differentiable-ness that actually does stuff." Script:
`experiments/attention_on_ram/content_addressed_read.py`; guard
`test_reference.py::test_content_addressing_soft_learns_hard_inert`.

## The test

A "learn to address by content" task: memory rows have keys `K_i` (content) and scalar
values `v_i`. A trainable query `q` is trained by SGD so the read equals a target value
(4.0, row 3). The query can only succeed by attending to the row whose value is the
target — i.e. by moving toward that row's *key*. Two read mechanisms, same task:

- **SOFT:** `w = softmax(β·K q)`, `read = w·v` — addressing is differentiable in `q`.
- **HARD:** `w = onehot(argmax K q)`, `read = w·v` — argmax addressing.

## Result (measured)

| read | loss (init → final) | ‖∇q‖ at step 0 | read → | weight on target row |
|---|---|---|---|---|
| **soft** | 0.983 → **0.000** | **0.479** | **4.0000** (target) | **1.0000** |
| **hard** | 1.000 → **1.000** | **0.000** | 3.0000 (stuck) | 0.0083 |

The soft, content-based read **learns content-based retrieval**: the gradient flows
through the softmax addressing into `q`, the query migrates to the matching row, the
attention weight on the target row goes to 1.0, and the read converges exactly to the
target value. The hard read is **differentiable on paper but inert**: `argmax` gives
`q` *zero* gradient (the loss has no grad path to `q` at all — `loss.requires_grad` is
`False`), so the query never moves and never reaches the target.

## Why this is the load-bearing distinction

The discriminator is precisely *whether the gradient flows through the addressing
itself*, not merely through the values read. `select_field` (hard location read) and
`trainable_read.py` (fixed per-position coefficients) are both on the inert side:
the first has no gradient to its address; the second has no query-conditioned
addressing at all. Content-based soft addressing is the first mechanism on this track
where "learn where to look" is actually realizable — the NTM/DNC core capability, and
the difference between an architecture that is differentiable-on-paper and one whose
differentiability can drive improvement.

## Scope / not claimed; next substrate step

This is a TRAINING experiment (host SGD — the sanctioned compile-time fit role); the
forward read is torch. It does **not** yet run the soft read as a Sutra substrate op:
softmax needs `exp` on the substrate (design-doc open question O1). The query·content
score and the weighted-sum read are matmuls (substrate-ready); the missing primitive to
expose is a substrate **softmax** (exp-based, β-scaled). That is the concrete next step
to make content-based addressing a substrate operation rather than only a host-trained
demonstration — and it is the right next thing on this track, per Emma's point that the
attention-mechanism read is the part that matters.
