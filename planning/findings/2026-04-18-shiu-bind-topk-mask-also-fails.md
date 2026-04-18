---
name: Balanced top-k role mask on Shiu also fails (different failure mode)
description: Follow-up to 2026-04-13-shiu-bind-unbind. Balanced top-k mask solves the imbalance problem but introduces a coverage problem — only 86-120 of 138,639 dims are signed, so bind zeros out most of the value vector and self-inverse cos drops to 0.02. The substrate's point-drive response is too sparse to encode roles as signed masks under any threshold method tried so far.
type: project
---

# 2026-04-18: Balanced top-k role mask on Shiu — new failure, not a fix

Follow-up to `2026-04-13-shiu-bind-unbind.md`, which flagged Option (1)
("balance the mask differently") as the cheapest next step. Tried. It
does not fix the discrimination problem — it replaces it with a
coverage problem. `bind(v, r) = v * sign(r)` on Shiu point-drive
substrate is structurally blocked regardless of thresholding method.

## What was measured

Added `--role-method topk` to `fly-brain/shiu_bind_test.py`. Construction:

- Drive each role population (40 neurons, 200 Hz, 100 ms).
- Read spike-count vector.
- Top-k of the *nonzero* response → +1.
- Random k from the *zero-response* pool → -1.
- Everything else → 0 (masked out of the bind).

k defaults to min(|nonzero|, 60). Four value vectors × three role masks
built this way. Same bind/unbind/separation metrics as the 2026-04-13
run.

## Raw result

| metric | median-split (prior) | top-k balanced (new) | expected |
|--------|---------------------:|---------------------:|---------:|
| self-inverse cos   | 1.0000   | 0.0203 | 1.0 |
| cross-unbind cos   | 0.9989   | 0.0000 | ~0  |
| bind separation mean | 0.1431 | 0.1023 | low |
| bind separation max  | 0.8360 | 0.9383 | low |
| +1 / -1 / 0 dims (r0) | 43 / 138596 / 0 | 43 / 43 / 138553 | balanced |

Self-inverse collapsed from 1.000 to 0.02. Cross-unbind from 0.999 to
0.000. The bind operation with a 86–120-dim signed mask on a 138,639-D
vector zeros out essentially all of the value's content (the value
vector's activity is on different dimensions than the role mask
covers). What's left is a tiny cosine that's mostly noise.

## Why both methods fail

Median-split failed because Shiu's point-drive response is sparse —
median of a mostly-zero vector is zero, so the +1 population is ~40
dims and the -1 population is ~138,600, making all roles ≈ -1. Every
bind is approximately `v * -1 = -v`, which is self-inverse but does
not discriminate between roles.

Top-k balanced fails because Shiu's point-drive response is *also
localized*. The +40 / -40 signed dimensions cover <0.1% of the full
138,639 space. When a value vector (activity on one cluster of
dimensions) is bound with a role mask (signs on a different cluster of
dimensions), the elementwise product is nearly all zero.

The common cause: **the spec's `bind(v, r) = v * sign(r)` assumes
value and role vectors occupy the same space**, and in particular that
role signs cover the dimensions where value activity lives. On Shiu,
value and role populations are disjoint and their substrate responses
are localized — they overlap only incidentally. Sign-flip binding
over the full 138,639-D space is geometrically incompatible with
point-drive encoding.

## Options remaining

The bind-unbind finding listed four options. Now with one tried:

1. ~~**Balance the mask differently.**~~ Tried; doesn't work on this
   substrate for the reasons above.
2. **Compile roles via a denser drive.** Drive role populations across
   a much larger set of neurons (e.g. 1000 instead of 40) so the
   substrate response covers more of 138,639. Expensive, untested.
3. **Use a different bind operation.** HRR circular convolution
   requires FFT and does not run natively on spiking substrate.
   Blocked for the same reason the spec avoids it.
4. **Redefine role on this substrate.** A role on Shiu is the *signed
   spike-count pattern itself*, used as a soft multiplicative key.
   Bind becomes `v .* r` (elementwise product with signed counts, not
   ±1). Self-inverse no longer holds exactly — `unbind` becomes
   division, not multiplication. This changes the spec and the
   algebraic properties, but it is the only encoding that actually
   uses Shiu's native output.

Option (2) is worth a small experiment (one script) but probably hits
wall-clock limits before producing a balanced mask. Option (4) is the
spec-level move and is where this work should land if we care about
closing the gap, but it's not in scope for the Hail-Mary push — it
needs a spec discussion with the user.

## Implication for the paper

Same as before, slightly harder: `bind`/`unbind` does not work on
Shiu under the current spec, and a straightforward "balance the mask"
patch does not rescue it. The fly-brain paper should continue to
restrict the substrate result to bundle + snap + fuzzy conditional,
which do run on real W. The bind/unbind negative is a clean story:
"the spec's sign-flip binding assumes overlapping support for value
and role, which point-drive encoding on Shiu does not produce."

Queue item 3 is now fully resolved on the fly-brain side. Rotation
(generic and CX-restricted) already negative; bind/unbind negative
under two role-encoding schemes. No further Shiu library-op
experiments are queued.
