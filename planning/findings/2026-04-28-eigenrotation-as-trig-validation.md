# 2026-04-28 — Eigenrotation as trig: mixed result, cost speculation refuted

**Experiment:** `experiments/eigenrotation_as_trig.py`.
**Hypothesis source:** `planning/exploratory/eigenrotation-for-sine-and-modulus.md`,
written 2026-04-28 from a user insight raised mid-chats-triage.

## What was tested

The exploratory doc made three composite claims:

1. **Identity.** `R(theta) @ (1, 0) = (cos theta, sin theta)` exactly,
   so trig is computable via the existing `rotate_slot` substrate
   primitive.
2. **Modulus for free.** `R(theta + 2*pi) = R(theta)`, so feeding
   unreduced angles to the rotation route gives correct results
   without explicit range reduction.
3. **Cost.** "When you need both sin and cos, the rotation route
   saves a trig call" (one rotation build + matvec vs. two separate
   libm calls).

The script runs four tests against numpy/CPU, mirroring the math used
by `rotate_slot` in `sdk/sutra-compiler/sutra_compiler/codegen.py`
line 913.

## Results

### Identity (test 1) — confirmed, trivially

`R(theta) @ (1, 0)` matches `(np.cos(theta), np.sin(theta))` to zero
error across the eight test angles. This is true by construction —
the rotation builder calls `np.cos` and `np.sin` to fill R, then
applies it to `(1, 0)` and returns those same values. Not a
substantive validation; just a sanity check.

### Modulus for free (test 2) — confirmed, but it's a libm property

For angles ranging from `3*pi` to `1e15`, the rotation route and
direct `np.cos / np.sin` agree to floating-point precision. The
manually-reduced `(theta + pi) % (2*pi) - pi` path also matches up
to about `1e9`; at `1e15` the manual reduction loses precision
because the angle itself can no longer be represented exactly in
float64.

**Honest framing:** the "modulus for free" claim is real, but it's a
property of libm's range reduction, not a Sutra-specific feature.
Sutra inherits it for free because it's calling the same trig
functions, but no other language is *worse* on this axis — they all
inherit the same libm property. The exploratory doc should not
position this as a Sutra differentiator.

### Cost (test 3) — REFUTED

1M scalar trig evaluations:

| Path                                | Wall clock | Ratio vs scalar-direct |
|-------------------------------------|-----------:|----------------------:|
| A: rotation, scalar Python loop     | 1.961 s    | 1.41×                 |
| B: `np.cos`/`np.sin` vectorized     | 0.020 s    | 99× faster than A     |
| C: `np.cos`/`np.sin` scalar loop    | 1.396 s    | 1.00× (baseline)      |

The rotation path is **strictly more work** than direct trig on
numpy CPU. It performs the same two libm calls (one for `cos`, one
for `sin`) and then adds a 2x2 matvec on top. The "saves a trig
call" speculation in the exploratory doc was wrong: the rotation
builder *itself* needs both sin and cos, so there's no compute
saving — there's a compute cost.

This refutation does not invalidate the architectural framing.
"Substrate-uniformity, one fewer kind of operation in the runtime"
is independent of per-op cost. But the cost story has to be removed
from any Exact-tier marketing.

The cost-win story would only materialize on a substrate where
rotation is a hardware primitive cheaper than two libm calls (e.g.
CORDIC on FPGA, or a future native rotation instruction). That is
not where Sutra runs today.

### Large-angle precision (test 4) — confirms the dtype caveat

For `theta = N * 2*pi + 0.1`, error vs. `sin(0.1) / cos(0.1)`:

| N    | Error  |
|-----:|-------:|
| 1    | 6e-16 |
| 10   | 1e-15 |
| 100  | 3e-14 |
| 1e6  | 8e-10 |
| 1e9  | 3e-7  |

At very large angles the float64 representation of the angle
itself loses fractional precision before any trig is called.
Float32 would degrade earlier; bfloat16 much earlier. The
`[backend] dtype` interaction the exploratory doc flagged as an
open question is real: any "Exact-tier" claim has to come with a
domain-restriction clause, or the dtype has to be float64 minimum
for the bound to mean anything.

## What this changes

The exploratory doc as written has two valid claims and one wrong
one. Updating it (this commit) to:

- Keep the architectural-uniformity claim — that's the surviving
  Sutra-specific value.
- Remove the "saves a trig call" cost speculation. Replace with the
  honest "no compute saving on numpy CPU; cost-win requires hardware
  rotation primitive."
- Re-frame the modulus-for-free claim as inherited-from-libm rather
  than Sutra-specific.
- Promote the dtype caveat from "open question" to "documented
  constraint."

The todo.md entry is also being updated: the "first step is the
cheap pure-math validation" sub-item is now done; what remains is
the architectural integration question (does it actually simplify
the math-tier code path enough to be worth the build cost?), which
is a question for when the math approximation work is actively
being done, not now.

## What this does NOT change

The exploratory doc still belongs in `planning/exploratory/`. The
core insight — rotation matrices contain trig values by construction
— is mathematically right and the architectural argument is valid.
The doc just needs to stop claiming a speed win that the
measurements refute.

The architectural value (one substrate primitive instead of two
runtime code paths for trig) is real but small. It does not justify
prioritizing this work over the existing math-approximation tiers.
This is a "nice cleanup if/when we touch this code" item, not a
priority feature.
