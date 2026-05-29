# 2026-05-28 — Complex-argument sine `csin(z)` shipped (the ccos follow-on)

Closes the only genuinely-open residue of
`planning/open-questions/cosine-as-its-own-transcendental.md`: complex
sine. Companion to the 2026-05-17 `ccos` work
(`planning/findings/2026-05-17-complex-argument-cosine-implemented.md`).

## What shipped

`Math.csin(complex z)` — the documented reduction

```
sin(z) = (e^(i·z) − e^(−i·z)) / (2i)
```

- **Declaration:** `sdk/sutra-compiler/sutra_compiler/stdlib/math.su` —
  `static intrinsic method complex csin(complex z);` (declared `complex`
  so `_is_complex_expr` routes the result through the complex dispatch
  path, same as `cexp` / `ccos`).
- **Implementation:** `sdk/sutra-compiler/sutra_compiler/codegen_pytorch.py`
  `def csin(self, z)`:

  ```
  zc        = _cnum(z)
  iz        = complex_mul(zc, [0, +1])      # i·z
  miz       = complex_mul(zc, [0, −1])      # −i·z
  inv_two_i = [0, −0.5]                      # 1/(2i) = −i/2
  return complex_mul(complex_sub(cexp(iz), cexp(miz)), inv_two_i)
  ```

## Substrate purity

Built only from the verified-pure `cexp` keystone + `complex_mul` /
`complex_sub`. No new lookup-table leaf, no host branch, no scalar
extraction — the `1/(2i)` factor is a complex constant `[0, −0.5]` applied
as a complex product, so the whole op stays in canonical-complex-vector
space. Same purity posture as `ccos`.

## Real-axis reduction (paper-cited real `sin` untouched)

For real `z = a` (imag 0):

```
iz  = [0, a]   → cexp(iz)  = [cos a,  sin a]
miz = [0, −a]  → cexp(miz) = [cos a, −sin a]
diff = [0, 2 sin a]
diff ⊗ [0, −0.5] = [ (0·0 − 2 sin a·(−0.5)), (0·(−0.5) + 2 sin a·0) ]
                 = [sin a, 0]
```

Exactly the real-angle `sin` eigenrotation, with zero imaginary leakage —
so the paper-cited real `sin` path is unaffected.

## Verification (ground-truth, measured)

`TestComplexArgumentSine.test_csin_vs_cmath` in
`sdk/sutra-compiler/tests/test_transcendentals.py` compares against Python
`cmath.sin` over five cases — real arg `0.5`, pure-imaginary
`sin(i) = i·sinh 1 ≈ 1.1752 i`, and two general points (`0.5+1i`,
`1+2i`) — both real and imag components, absolute tolerance `2e-2` (the
same float32 / table-precision class as the `ccos` and `pow` cases; not
tuned — the principled tightening is bigger tables / range reduction).
**6 passed, 43 subtests passed** for the whole transcendentals suite on
the torch backend.

## Framing note

Emma's 2026-05-28 `AskUserQuestion` answer ("make cos its own
transcendental, retire `cos = real(cexp(iθ))`") was, at the numerics
level, already satisfied: `_cos0` reads its own `_COS_VALUES` table, so
`cos` was never numerically derived from `exp` — the `real(cexp(iθ))`
phrasing described only the surface routing (corrected in the
open-question doc on 2026-05-17). The actionable work the answer pointed
at ("unblocks the csin follow-on") was `csin`. No real-`cos`/`sin`
numerics were changed.

## Not covered

- Literate *source spelling* of the complex transcendentals (`ccos` /
  `csin` are intrinsic + documented, same as `realExp` / `imaginaryExp`)
  remains pending — see the `math.su` header note. Not a math shortcut:
  the reduction is exact and substrate-pure; only the surface form is
  intrinsic rather than a `.su` body.
- Complex `clog` / `ctan` are not implemented (not faked).
