# Open question — Cosine as its own transcendental function?

> **VERDICT: FULLY RESOLVED.** Both complex-argument transcendentals
> have shipped, substrate-pure. (1) `Math.ccos(complex z) =
> (cexp(i·z) + cexp(-i·z))/2` shipped 2026-05-17 (`codegen_pytorch.py`
> `def ccos`); ground-truth vs `cmath.cos` ≤2e-4; real-arg case carries
> exactly zero imaginary leakage (paper-cited real `cos` untouched).
> See `planning/findings/2026-05-17-complex-argument-cosine-implemented.md`.
> (2) The `csin` follow-on — the only residue that was still open — also
> SHIPPED 2026-05-28 (`codegen_pytorch.py` `def csin`); see
> `planning/findings/2026-05-28-csin-complex-sine-shipped.md`. Built only
> from the verified-pure `cexp` keystone + `complex_mul`/`complex_add`;
> no new leaf, no host branch. Nothing in this doc remains open — it is
> now eligible for the next open-question pruning pass (README rule 3).

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

## Resolution — complex-argument `cos(z)` shipped as `ccos`

The sub-question this doc once posed as open — *"does Sutra grow a
substrate-pure complex-argument cosine `cos(z)` for complex `z`,
including its imaginary part, built geometrically?"* — **is resolved.**
It shipped 2026-05-17 as `ccos`:

- **Implementation:** `ccos` at
  `sdk/sutra-compiler/sutra_compiler/codegen_pytorch.py:1384` —
  `cos(z) = (e^(i·z) + e^(-i·z))/2`, built only from the verified-pure
  `cexp` keystone + `complex_mul`/`complex_add`, with the imaginary
  unit and `0.5` as `_mk` constants and `_cnum` as the entry boundary.
  No new leaf, no host branch, no scalar extraction. For real `z` it
  reduces to exactly the real-angle `cos` eigenrotation (zero imaginary
  leakage), so the paper-cited real `cos` path is untouched.
- **Verification:** ground-truth vs `cmath.cos` ≤2e-4. See
  `planning/findings/2026-05-17-complex-argument-cosine-implemented.md`.

The real-angle surface `cos(x)` is unchanged and was already
substrate-pure (its own `_COS_VALUES` table — see "Corrected framing"
above).

## Genuinely-open residue — CLOSED 2026-05-28

Complex sine — `csin(z)` — **shipped 2026-05-28**, the last residue this
doc left open. Same model as `ccos`: `sin(z) = (e^(i·z) − e^(−i·z))/(2i)`,
built only from the verified-pure `cexp` keystone + `complex_mul` /
`complex_sub`, with the `1/(2i)` factor as the complex constant
`−i/2 = [0, −0.5]`; no new leaf, no host branch, no scalar extraction.
For real `z = a` it reduces to exactly `[sin a, 0]` (zero imaginary
leakage — the paper-cited real `sin` path is untouched). Implementation:
`codegen_pytorch.py` `def csin`; declaration: `math.su`
`static intrinsic method complex csin(complex z)`. Ground-truth vs
`cmath.sin` < 2e-2 across 5 cases (real arg, pure-imaginary
`sin(i) = i·sinh 1`, two general points), regression guard
`TestComplexArgumentSine` in `test_transcendentals.py`. See
`planning/findings/2026-05-28-csin-complex-sine-shipped.md`.

**This doc is now fully resolved on both sub-questions** (cos already its
own table-backed transcendental; ccos + csin complex-argument forms
shipped) and is a candidate for the next open-question pruning pass.

### A note on the "make cos its own transcendental" framing

Emma's 2026-05-28 `AskUserQuestion` answer was "make cos its own
transcendental (retire `cos = real(cexp(iθ))`)." Reading the emitted code
showed this was **already true at the numerics level** before any change:
`_cos0` reads its own dedicated `_COS_VALUES` table (the real coordinate
of the eigenrotation), so `cos` is not numerically derived from `exp` —
the `real(cexp(iθ))` phrasing was only the *surface routing*, corrected in
the "Corrected framing" section above on 2026-05-17. So the actionable
work the answer pointed at ("unblocks the csin follow-on") was `csin`,
which is what shipped. No real-`cos` numerics were changed — doing so
would have been a no-op or a regression of the paper-cited path.
