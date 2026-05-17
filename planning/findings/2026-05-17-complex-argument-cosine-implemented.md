# 2026-05-17 — Complex-argument cosine `ccos` implemented (substrate-pure)

**What.** Added `Math.ccos(complex z)` — the complex-argument cosine,
the piece the user flagged in the 2026-05-17 voice-vision ("it's much
more complicated when you look at the imaginary output of the cosine …
implement the imaginary output of the cosine geometrically too").
Closes the genuinely-open part of
`planning/open-questions/cosine-as-its-own-transcendental.md`.

**The reduction (documented, executed on the substrate).**

```
ccos(z) = (e^(i·z) + e^(-i·z)) / 2
```

- `e^(i·z)`, `e^(-i·z)` = `cexp` of `complex_mul(z, ±i)` — the
  verified-pure complex-exponential keystone.
- the sum is `complex_add`; the `/2` is `complex_mul` by `[0.5, 0]` so
  the whole computation stays in canonical-complex-vector space.
- Every step is an already-verified-substrate-pure op
  (`_cnum`/`_mk`/`complex_mul`/`complex_add`/`cexp`). No new substrate
  leaf, no host branch, no scalar extraction, no libm/torch elementwise
  on the hot path. For real `z=a` it collapses to `[cos a, 0]` —
  identical to the paper-cited scalar `cos(x)` eigenrotation path, so
  that path is provably unaffected.

**Where.**
- `sdk/sutra-compiler/sutra_compiler/stdlib/math.su` — declared
  `static intrinsic method complex ccos(complex z);` with the
  reduction in the doc comment. Intrinsic + documented matches the
  `realExp`/`imaginaryExp` precedent; the literate *source spelling*
  of complex transcendentals is explicitly pending per the file
  header, so this is the spec-consistent choice, not a math shortcut.
  Declared `complex` so `_is_complex_expr` routes its result through
  `complex_mul`/`complex_add` (same dispatch path as `cexp`).
- `sdk/sutra-compiler/sutra_compiler/codegen_pytorch.py` — `def
  ccos(self, z)` runtime method after the `exp`/`cexp` block.
- `codegen.py` (numpy, deprecated) — **not** extended; it has no
  `cexp`. The test asserts the canonical PyTorch backend only, with
  the reason stated in-test. This is a scoped negative, not a gap
  silently skipped.

**Ground truth — measured, not asserted.** `Math.ccos` vs Python
`cmath.cos`, torch backend, absolute |Δ| per component:

| z | Re got / true | Im got / true | \|ΔRe\| | \|ΔIm\| |
|---|---|---|---|---|
| 0+0i   | +1.000008 / +1.000000 | +0.000000 / -0.000000 | 8.2e-6 | 0 |
| 0.5+0i | +0.877519 / +0.877583 | +0.000000 / -0.000000 | 6.3e-5 | 0 |
| 0+1i   | +1.543281 / +1.543081 | +0.000000 / -0.000000 | 2.0e-4 | 0 |
| 0.5+1i | +1.354248 / +1.354181 | -0.563449 / -0.563421 | 6.7e-5 | 2.8e-5 |
| 1+2i   | +2.032785 / +2.032723 | -3.051990 / -3.051898 | 6.2e-5 | 9.3e-5 |

- Real-argument case (0.5+0i): imaginary component is **exactly 0.0** —
  zero imaginary leakage; the real cos path is untouched.
- Pure-imaginary case (0+1i): Re ≈ cosh(1) = 1.5431 ✓.
- General complex (0.5+1i, 1+2i): the geometric **imaginary output of
  cosine** is correct to ≤1e-4 (−0.5634, −3.0519 matched).

Worst component error 2.0e-4 — two orders inside the test's 2e-2
absolute bound (the bound is conservative for float32 + N=16384 exp /
N=4096 trig lookup-table precision; the real error is ~1e-4).

**Gate.** New `TestComplexArgumentCosine` (torch-only, 5 cases ×
{real, imag} = 10 subtests) PASS. Full `test_transcendentals.py` PASS
both backends (4 passed / 30 subtests) — real `cos`/`sin`/`exp`/`pow`/
hyperbolics did not regress. Fast full compiler gate (everything except
the ~29-min nightly substrate sweep) + supplementary smoke: see commit.
The substrate sweep is unaffected by construction — no existing op was
changed and no corpus program calls `ccos`, so the set of compiled
programs it scans is unchanged.

**Honest scope note.** `ccos` is the complex *cosine*. A complex `csin`
is the natural symmetric follow-on (`sin(z) = (e^(iz) − e^(−iz))/(2i)`)
but was **not** added this pass — the user asked for cosine
specifically; adding `csin` unrequested would be scope creep. Logged in
`todo.md`/queue as the obvious next step if wanted, not faked as done.
