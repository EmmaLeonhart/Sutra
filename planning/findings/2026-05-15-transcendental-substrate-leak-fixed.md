# The transcendental/modulus substrate leak — found and fixed

**Date:** 2026-05-15
**Author:** Claude (Opus 4.7) under Emma's direction (Yantra-driven session)
**Touches:** `sdk/sutra-compiler/sutra_compiler/codegen_pytorch.py`,
`stdlib/math.su`, `stdlib/modulus.su`
**Supersedes the purity claim of:**
`planning/findings/2026-05-13-modulus-rotation-vs-sawtooth.md`

## What was wrong

Every transcendental and modulus intrinsic emitted by
`codegen_pytorch.py` leaked the substrate. The shape, in `exp`:

```python
def exp(self, x):
    xv = float(x)                                  # substrate → host
    if xv < self._EXP_LO or xv > self._EXP_HI:     # host control flow
        raise SutraMathOverflow(...)               # host raise on a scalar
    xt = _torch.as_tensor(xv, ...)
    d = (self._EXP_XS - xt).abs() / self._EXP_DX
    w = (1.0 - d).clamp(min=0.0)
    return float(_torch.dot(w, self._EXP_VALUES))  # host scalar return
```

The interpolated-table dot product in the middle *is* a tensor op,
but it was bracketed by host-Python scalar boundaries. Same pattern
in `log`, `pow` (`float(y)`), `sqrt`, `sin`/`cos` (`float(x)` return),
`tan` (`if c == 0.0`), `sinh`/`cosh`/`tanh` (`float(x)`), and the
whole modulus family — `fmod`/`rotation_mod`/`sawtooth_mod` did
`float(x)`, `float(m)`, `if float(m) == 0.0: raise`, `float(...)`
return, and `sawtooth_mod` ran a Python `for k in range(...)` over
scalars. The codegen comment at line 1137 claimed *"substrate-pure
... no Python control flow on x"* — the opposite of the code beneath
it. The 2026-05-13 finding's "substrate-pure / production path
measured" claim was fabricated against this code (see its correction
header).

This is the precise failure class the safety preamble of CLAUDE.md
forbids: host wrappers around substrate ops, plus prose asserting
purity that the code does not have.

## Root cause

These were never the eigenrotation / complex-exponential design the
language is built around (todo.md "Transcendental functions — design
absorbed from voice chat"). They were a 1-D interpolated table with
host scalar I/O — the 2026-04-29 "host scalar arithmetic" mistake
that was supposedly withdrawn, silently reintroduced 2026-05-10 and
then mis-described as pure.

## The fix

Authoritative design (Emma, voice direction; overrides the spec
where they disagree): two lookup primitives `exp`/`log`, complex
`cexp(a,b) = exp(a)·(cos b + i·sin b)`, real `exp` = `cexp(x,0)`
beta-reduced, `sin`/`cos` = imag/real of the unit eigenrotation
(sin is cos with the signs flipped), everything else a substitution
onto those.

Substrate-pure contract now enforced for every method:

- One host→substrate boundary, `self._st(x) = _torch.as_tensor(x,
  dtype, device)` — the same class of boundary as `embed()` turning
  a string into a vector. Nothing past it touches a host scalar.
- `_lerp(xt, xs, values, dx)` — the crosstalk-weighted continuous
  readout (triangular soft-index `matmul`), the rotational-binding
  kernel that makes a discrete codebook a continuous function.
- `cexp(re, im)` returns `[exp(re)·cos im, exp(re)·sin im]`;
  `exp(x) = cexp(x, 0)[0]`, so the complex-exp beta reduction
  executes on the substrate, not just in a comment.
- 0-d tensor return everywhere. No `float()`, no host `if`/`raise`,
  no Python `for` over scalars (`sawtooth_mod`'s k-sum is now a
  single `(K,N)` matmul against the sin table).

### Behavior change: saturate, not raise

`SutraMathOverflow` is **no longer raised**. Out-of-range input
saturates at the table edge via a tensor `clamp`. The old raise was
*both* a host-control-flow leak *and* a violation of the core
"no runtime errors by mechanism" rule (CLAUDE.md / Core Design).
Saturation is a mathematically-valid output (ln near `LN_LO` → a
large negative number; exp beyond `EXP_HI` → the edge value;
`tanh` → ±1 for large |x|, the correct limit). The exception class
is retained, never thrown, so existing `except SutraMathOverflow`
sites still import. Tests asserting the raise will now fail by
design — that is the corrected behavior, not a regression to paper
over.

## Measurements (honest, post-fix)

`sdk/sutra-compiler/tests/test_transcendentals.py`: **3 passed,
20 subtests passed** on both numpy and torch backends.
`examples/_smoke_test.py`: **PASS** (all retrieval / sequence
checks). `experiments/modulus_comparison.py`:

| m | rotation_mod max err | rotation_mod mean | sawtooth_mod max | latency rot µs/call (was) |
|---|---|---|---|---|
| 3.0 | 4.44e-7 | 1.10e-7 | 1.40e+0 | 3137 (was ~1131) |
| 7.0 | 1.00e-6 | 2.54e-7 | 3.27e+0 | 3333 (was ~1021) |

Accuracy is unchanged (still float32 precision; the rotation maps
cleanly onto the sin/cos tables). **Latency rose ≈3×.** That is the
honest, expected cost: the call now runs on the substrate (an
`as_tensor` boundary, the eigenrotation through `cexp`, per-call
CUDA kernel launches) instead of leaking to host float math. This
is the "global not local efficiency" tradeoff CLAUDE.md describes
and Emma explicitly endorsed — local waste is the point; uniform
substrate ops are what the compile-time fusion pass needs.

## What is still open (tracked in the substrate-leak audit)

- **Source-level beta reduction.** The ideal `math.su`/`modulus.su`
  form is Sutra method bodies (`static method scalar pow(...) {
  return Math.exp(y * Math.log(x)); }`) so the substitution is the
  source itself. The stdlib inliner does not yet resolve intra-
  `Math` member calls inside a class-bodied static method body
  (`NameError: name 'Math' is not defined` at codegen). Surfaced
  honestly: the files keep the reduction in heavy docstrings + the
  runtime, and the inliner work is the top audit item. The methods
  are `intrinsic` for now, routing to the substrate-pure `_VSA.*`.
- **`atan2` in `rotation_mod`.** Still `torch.atan2` (a tensor op,
  but libm-shaped). Its own eigenrotation lookup is the follow-on.
- **`Math.round` ties-to-even vs JS half-up.** Semantic, not a
  purity issue. Unchanged.
