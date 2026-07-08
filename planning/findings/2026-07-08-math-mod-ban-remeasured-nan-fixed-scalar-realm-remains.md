# `Math.mod` ban re-measured: the NaN collapse is FIXED; the scalar-realm shape limit remains (2026-07-08)

Round-19 (aliases + affordances) audit follow-up. The queue's standing Context note says
"**NEVER use `Math.mod`** (measured vector-collapse/NaN). Use complex rotation for
wrap/periodic" — but `stdlib/modulus.su` beta-reduces `Math.mod(x,m)` → `rotation_mod` and
documents it as verified. Both could not be fully right, so: measured.

## Measured today (runtime_dim=8, torch backend)

Re-ran the exact failure cases from
`planning/findings/2026-06-12-rotation-mod-vector-collapse-complex-rotation-animation.md`:

| case | 2026-06-12 | 2026-07-08 |
|---|---|---|
| `rotation_mod(make_real(0.375), make_real(2.0))` (vector, vector) | **all-NaN** | 0-d tensor, value **0.375**, no NaN |
| `rotation_mod(make_real(0.375), 2.0)` (vector, literal) | 0-d collapse, wrong recurrence | 0-d tensor, value **0.375** (correct) |
| `rotation_mod(-0.1, 1)` (scalar) | 0.9 | **0.9** exact |
| 24-point sweep vs Python floor-mod (x ∈ ±values, m ∈ {1, 2, 3.5}) | — | max circle-distance error **4e-6** |

Why it changed: `rotation_mod` now enters through `_scalar(x)` (the scalar-math entry
boundary added with the numbers-on-substrate work), which projects a number-vector's real
axis before the trig chain — the elementwise `0/0` on non-real axes that produced the NaN
no longer happens.

## What is still true

`rotation_mod` is a **scalar-realm op**: its output is a 0-d tensor, not a number-vector.
Threading it through a `recurring vector` state slot still degrades the state locus
(CLAUDE.md § state-locus audit — the recurrence must stay a vector). For periodic/animation
wrap of VECTOR state, the complex-rotation idiom (`z * e^{iθ}` via complex_mul) remains the
right mechanism — the rotation is inherently periodic, no modulus needed.

## Proposed Context-note rewording (NEEDS-DECISION — Emma; her protective note, not deleted unilaterally)

> **`Math.mod` is scalar-realm only.** It computes floor-mod correctly on scalars/numbers
> (verified 2026-07-08, max err 4e-6; the 2026-06-12 NaN collapse was fixed by the `_scalar`
> entry boundary) but returns a 0-d value — do NOT thread it through vector-typed recurrent
> state. For wrap/periodic on vector state, use complex rotation (`z * e^{iθ}`).

Until Emma approves, the standing "NEVER use Math.mod" note stays as written.
