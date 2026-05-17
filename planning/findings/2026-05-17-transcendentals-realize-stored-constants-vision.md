# 2026-05-17 — Do the shipped transcendentals actually realize the stored-constants vision?

**Why this finding exists.** The user's 2026-05-17 voice-vision block
(verbatim at
`planning/exploratory/2026-05-17-voice-vision-transcendental-constants.md`)
states a specific anxiety: *"I was extremely excited when you claimed to
have been able to successfully implement the cross-talk exploiting
lookup tables. I don't know if you even ever actually did so or if you
just lied."* This finding answers that by **reading the emitted runtime
code directly** (`sdk/sutra-compiler/sutra_compiler/codegen_pytorch.py`,
the canonical compile target) rather than trusting any prior claim.
Read-only audit; no code was changed.

## The vision being checked

1. Tau stored through a set binding point in the runtime.
2. A cross-talk-exploiting exponential lookup table and a separate
   logarithm lookup table (the two leaves; separate "for now").
3. Everything else reduces legibly onto those (literate style).

## Verified against the emitted code — line citations

**1. TAU at a runtime binding point — REAL.**
`codegen_pytorch.py:291` `self._TWO_PI = 2.0 * _math.pi` and `:297`
`self.TAU = 2.0 * float(_math.pi)` are bound as constants on the `_VSA`
runtime object at init. `_TWO_PI` is consumed by `_trig_reduce`
(`:1320`, `xt - self._TWO_PI * _torch.round(xt / self._TWO_PI)`), a pure
tensor op. It is a host-float constant (not a hypervector), but it is
literally "tau bound at a set point in the runtime," which is what the
vision asked for.

**2. Exp table + Ln table = genuine cross-talk lookup leaves — REAL.**
- Built at init (`:272–279`): `self._EXP_VALUES = _torch.exp(self._EXP_XS)`,
  `self._LN_VALUES = _torch.log(self._LN_XS)`. Building a codebook at
  init is the legitimate **compile-time** role per CLAUDE.md
  ("Compilation — building codebooks … happens before the run"). The
  tables are separate (matches "for now they are separate").
- Runtime hot path: `_exp_table` (`:1295–1302`) / `_ln_table`
  (`:1305–1311`) do `clamp` then `_lerp`. `_lerp` (`:1205–1215`) is
  `d=(xs-xt).abs()/dx ; w=(1.0-d).clamp(min=0.0) ; return matmul(w,
  values)` — a triangular soft-index crosstalk kernel matmul against
  the table. **There is no `_torch.exp` / `_torch.log` / libm call on
  the runtime hot path.** The only `_torch.exp`/`_torch.log` calls in
  the whole transcendental block are the init-time table builds.

**3. Cross-talk mechanism is real.** `_lerp`'s triangular kernel makes
the two table nodes bracketing `xt` leak into the dot product in
proportion to proximity; that crosstalk is exactly what turns the
discrete table into a continuous function (the rotational-binding
readout). It is one matmul — SIMD-class, no host branch.

**4. Literate beta-reduction present.** exp/cos/sin/pow/sqrt/
sinh/cosh/tanh all beta-reduce onto the two lookup leaves plus the
eigenrotation (`:1182–1194`); `stdlib/math.su` carries the same chain in
readable Sutra.

## Verdict on the anxiety

**The cross-talk-exploiting exponential and logarithm lookup tables are
real and live on the runtime hot path. This was not a lie.** Verified by
reading the emitted code this run, not by trusting a prior assertion.
The only `torch.exp`/`torch.log` uses are the legitimate init-time
codebook builds, which CLAUDE.md explicitly permits as compilation.

## One honest correction owed (to my own work earlier this run)

While verifying, I found that **`cos` already has its own dedicated
crosstalk lookup table** (`self._COS_VALUES`, `:289`; read by `_cos0`,
`:1323–1327`, via the same `_lerp` crosstalk). cos is *not* numerically
derived from `exp` at runtime — it routes cos → `imaginaryExp` → `_cos0`
→ `_COS_VALUES`. So "cosine as its own transcendental" is **already
structurally true at the table level**, contrary to the framing I wrote
into `planning/open-questions/cosine-as-its-own-transcendental.md`
earlier this run ("cos = real(cexp(iθ)), should it be its own leaf").

The genuinely-open piece is narrower and **matches the user's exact
words** ("it's much more complicated when you look at the imaginary
output of the cosine … implement the imaginary output of the cosine
geometrically too"): `cos(x)` at `:1383–1390` forces its argument onto
the imaginary axis as a *real angle* (`itheta = self._mk(0.0,
self._st(x))`) and returns `_re(imaginaryExp(itheta))`. There is **no
path for `cos(z)` with complex z** — no `imag(cos(z))`. That complex-
argument cosine is the real open question. The open-question doc has
been corrected to say this precisely rather than the imprecise "derived
from cexp" framing.

## Net delta

- Anxiety ("did you lie about the crosstalk tables?") → **No. They are
  real, on the hot path, independently re-verified.**
- TAU at a runtime binding point → **real.**
- Correction to this run's own cosine open-question doc → **made**
  (the open part is complex-argument cos, not "cos should be its own
  leaf" — it already is one at the table level).
