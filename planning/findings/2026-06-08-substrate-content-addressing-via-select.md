# Content-based addressing is a Sutra substrate primitive (`select`) and is differentiable on it

**Date:** 2026-06-08
**Context:** Following Emma's point that content-based soft addressing (not normal RAM
editing) is the NTM/DNC hard part, the queued next step was "a substrate softmax." Grep-
first (CLAUDE.md "never invent a thing that may exist") found it already exists.

## Discovery: the primitive already exists

Sutra already has the content-addressed softmax read:
- `similarity(q, k)` → `_VSA.similarity` — the content match (a score).
- `select(scores, options)` → `_select_softmax` — softmax-weighted superposition of the
  option vectors (spec `planning/sutra-spec/26-select-and-gate.md`), explicitly
  autograd-preserving (built for the select-temperature constrain-train work).

So a content-based addressing read is, on the substrate,
`select([similarity(q, K_0), …], [V_0, …])` — exactly what `examples/fuzzy_dispatch.su`
already does (a query dispatches to the branch whose key it best matches, by content,
through softmax). **No new substrate softmax was needed**; the queued item is resolved by
using the existing primitive, not building a redundant one.

## Measured: it is differentiable on the substrate (and hard argmax is inert)

`experiments/attention_on_ram/substrate_content_read.py` (guard
`test_substrate_select_content_read_is_differentiable`) trains a query THROUGH the
compiled runtime ops (`_VSA.similarity` + `_select_softmax`, not a hand-written softmax)
to retrieve a target value, two ways:

| read | loss (init→final) | ‖∇q‖@0 | cos(read, target) | weight on target |
|---|---|---|---|---|
| **soft** (substrate `select`) | 0.888 → 0.481 | **0.0275** | 0.10 → **0.80** | 0.37 |
| **hard** (argmax over same scores) | 1.916 → 1.916 | **0.000** | 0.098 | 0.148 |

The soft read is **differentiable on the substrate**: the gradient flows through the
compiled `select` softmax into the query, which moves to address the target by content
(cos to target 0.10→0.80). The hard argmax read is **inert** (zero gradient), exactly the
soft-vs-hard divergence from the raw-torch experiment
(`2026-06-08-content-based-addressing-soft-vs-hard.md`), now confirmed on Sutra's *actual*
primitive.

## Measured limitation (not a differentiability issue): fixed β=1

`select`'s softmax has a **fixed temperature β=1** (no β argument). With close similarity
scores over random keys, the weights stay diffuse — `weight_on_target` plateaus at 0.37,
so the soft read converges only *directionally* (cos 0.80), not to a clean one-hot read.
This is a **temperature/sharpening lever, not a differentiability failure**: the gradient
flows fine; the read just doesn't sharpen at β=1. Sutra already has prior work on exactly
this lever (`experiments/select_temperature_adjustment.py`, the `.selT_*` baked runs / the
select-T constrain-train ship). Making content addressing sharpen to a crisp retrieval is
a β-exposure/temperature step on `select`, separable from the (now-confirmed) fact that
the addressing is differentiable on the substrate.

## What this settles / next

- Emma's "logical differentiable-ness that does stuff" holds for Sutra's real
  content-addressing primitive: `select`+`similarity` is differentiable and learns to
  address by content on the substrate; the inert case (argmax) is measurably distinct.
- Next (separable): expose/measure a β on `select` so the substrate content read sharpens
  (tie into the existing select-temperature work), and lift it into a `.su` program with a
  trainable query rather than a host loop. NOT claimed here: crisp one-hot substrate
  retrieval, or training the composed network.

Scope: training is the sanctioned compile-time fit role; the forward read is the compiled
substrate ops. No `.item()` on the hot path was introduced.
