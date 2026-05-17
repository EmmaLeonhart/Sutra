# Open question — Cosine as its own transcendental function?

> **VERDICT: RESOLVED 2026-05-17.** User decided the scope (implement
> it). Complex-argument cosine shipped as `Math.ccos(complex z) =
> (cexp(i·z) + cexp(-i·z))/2` — substrate-pure, built only from the
> verified-pure `cexp` keystone + `complex_mul`/`complex_add`; no new
> leaf, no host branch. Ground-truth vs `cmath.cos` ≤2e-4; real-arg
> case carries exactly zero imaginary leakage (paper-cited real `cos`
> untouched). See
> `planning/findings/2026-05-17-complex-argument-cosine-implemented.md`
> and the implementing commit. Doc kept for rationale until the next
> open-question pruning pass (README rule 3). Follow-on (not done,
> not faked): complex `csin`.

## Corrected framing (2026-05-17 — after reading the emitted code)

This doc originally framed the question as "cos = real(cexp(iθ)),
should it be its own leaf?". **That framing was imprecise.** A
read-only audit of the emitted runtime
(`planning/findings/2026-05-17-transcendentals-realize-stored-constants-vision.md`,
citing `sdk/sutra-compiler/sutra_compiler/codegen_pytorch.py`) found:

- **`cos` already has its own dedicated crosstalk lookup table.**
  `self._COS_VALUES` (`codegen_pytorch.py:289`) is a distinct trig
  codebook, read by `_cos0` (`:1323–1327`) via the same `_lerp`
  crosstalk kernel as the exp/ln leaves. The runtime route is
  cos → `imaginaryExp` → `_cos0` → `_COS_VALUES`. cos is **not
  numerically derived from `exp` at runtime** — it is its own
  table-backed transcendental. So "cosine as its own transcendental"
  is, at the table/substrate level, **already true**.
- The only sense in which cos is "derived" is the *surface routing*
  (`cos(x)` builds a pure-imaginary number and projects
  `imaginaryExp`), not the numerics.

## The precise still-open sub-question

The genuinely-undecided part is narrower and **matches the user's exact
words** ("it's much more complicated when you look at the imaginary
output of the cosine … implement the imaginary output of the cosine
geometrically too"):

`cos(x)` (`codegen_pytorch.py:1383–1390`) coerces its argument onto the
imaginary axis as a *real angle* (`itheta = self._mk(0.0,
self._st(x))`) and returns `_re(imaginaryExp(itheta))`. **There is no
path for `cos(z)` where `z` is itself complex — no `imag(cos(z))`.**

> One sentence: does Sutra grow a substrate-pure **complex-argument
> cosine** — `cos(z)` for complex `z`, including its imaginary part —
> built geometrically, rather than only the real-angle `cos(x)` it has
> today?

## Why each side has force

- **Leave it real-angle-only (status quo):** every shipped test uses
  real-argument cos; complex-argument cos has no current caller; the
  literate-math chain is green (135 passed / 103 subtests + smoke).
- **Add complex-argument cos (user's position):** the user explicitly
  calls out the imaginary output of cosine as the hard, must-be-
  geometric piece; deferring it silently while the surface advertises
  "cos" would be the
  [[feedback-check-what-is-open-before-pitching-blocker]] failure in
  reverse — treating a piece the design owner flagged as undone.

## What would close it

A user ruling on whether complex-argument `cos(z)` is in scope now, and
— if yes — its substrate-pure construction (the geometric imaginary
part), with a ground-truth verification table (the `21a9ff77` model:
tensors in → tensor ops → tensors out, compared to `cmath.cos`, honest
delta reported). The real-angle `cos(x)` table is already substrate-pure
and need not change.

## Status / why this is not being implemented in this autonomous run

This is a design change to a safety-critical substrate boundary. Per
CLAUDE.md ("NO MATH SHORTCUTS", "PEOPLE CAN DIE IF YOU FAKE RESULTS") and
the queue's standing rule that structural substrate work is done
deliberately with a test gate and not as a rushed autonomous edit, it is
recorded here as open and surfaced to the user rather than guessed at.
