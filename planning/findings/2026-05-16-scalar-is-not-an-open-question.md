# "scalar vs number" is RESOLVED, not an open question

**Date:** 2026-05-16
**Author:** Claude (Opus 4.7), recording Emma's authoritative ruling
**Status:** RESOLVED — supersedes every prior framing of this as an
"open design gap" or a "scalar→number migration question"

## The ruling (Emma, verbatim sense)

There is no separate "scalar." A number — integer, double, whatever
— **is a vector**: the value on the number/real axis, zeros on every
other axis. Exactly the same ontology as a string, which is a
complex hypervector with the string flag set and codepoints on the
synthetic axes. The runtime treats numbers this way; that is the
design, full stop. The word "scalar" is only objectionable because
it *connotes* a host bare number — i.e. the substrate-leak mindset
where you pulled the value off the substrate instead of keeping it
as the vector the runtime actually uses.

## Verified — this is already what the (fixed) runtime does

Checked the emitted runtime, not asserted:

- `_cnum(x)` = `self._st(x) * self._e_real()` — the value on the
  real/number axis, **zeros everywhere else**. Literally "an
  integer is a vector with zeros on the other points and the
  number on one." `_st` is the single host→substrate entry
  boundary (the `embed()`/`make_real` analogue), not a leak.
- `Math.exp(2.0)` returns a `torch.Tensor`, ndim 0, on `cuda:0` —
  **not** a host Python `float`. A substrate value.
- No `float()` / `.item()` / host arithmetic inside the
  transcendental or string operations after the 2026-05-15/16
  fixes (`21a9ff77`, `ecf1c4cd`, `ae269f6b`, `b9e11f5e`,
  `0e363b96`).

So the prior sessions' "scalar" *was* substrate leaks (host
`float()` sandwiches) — that was a real bug, now fixed. It was
never a legitimate "design question." Framing it as one was the
error.

## What actually remains (bounded engineering, NOT open design)

1. **The `.su` type keyword is `scalar`** (`parser.py`
   `_PRIMITIVE_TYPES`). Under the ruling it should read `number`.
   A rename + alias for back-compat. Cosmetic/ontology-naming, not
   a decision.
2. **`Math.exp`/`cos`/`sin` return the 0-d projection** (`_re(...)`,
   still a substrate tensor) rather than the full d-dim
   number-vector `[e^x, 0, …]`. Both are substrate; the projection
   exists only so ~hundreds of `scalar`-typed call sites + the test
   corpus keep their current shape. Dropping it (exp returns the
   number-vector) is a mechanical migration gated on updating those
   call sites/tests, not a design question.

Neither is "open." `planning/sutra-spec/open-questions.md`'s
`types.md:507` "can a function return a scalar" is **answered**:
yes — a number is a vector, returning it is returning a vector;
the only work is the rename + dropping the projection. That line
should be struck from the spec open-questions index and
`types.md` updated to state the ontology (number = vector with the
value on the number axis, zeros elsewhere; the same shape as a
string with its flag).

## Action taken from this finding

- queue item 1 (literate math): the exp/cos/sin "tail" is **not**
  gated on an open question — it is gated on the cosmetic rename +
  call-site migration. Reworded.
- `planning/sutra-spec/open-questions.md`: the "scalars as results"
  entry reclassified RESOLVED (this finding + the ruling), flagged
  for the strike-from-index + `types.md` update.
- `planning/open-questions/` had no separate dossier for this; if
  one is added later it starts life RESOLVED pointing here.
