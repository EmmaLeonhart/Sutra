# Eigenrotation as exact sine, cosine, and modulus

**Date opened:** 2026-04-28.
**Status:** Exploratory — mathematical insight validated, cost
speculation refuted. See
`planning/findings/2026-04-28-eigenrotation-as-trig-validation.md`
for the empirical results. Summary: the identity holds (trivially);
the modulus-for-free claim is real but is a libm property, not
Sutra-specific; the "saves a trig call" cost claim is **wrong** —
rotation is strictly more work than direct trig on numpy CPU. The
architectural-uniformity argument survives and is the only
Sutra-specific value that's honestly defensible.

## The insight

Sutra already has eigenrotation as a substrate primitive: `loop(cond)`
compiles to `state ← R · state` and the angular position on the
helix `R^i · v_0` *is* the loop counter (see
`planning/sutra-spec/control-flow.md` and STATUS pinned correction
§2). The runtime knows how to apply Givens rotations on the
synthetic subspace.

Sine and cosine are *literally what 2D rotation matrices contain*:

    R(θ) = [ cos θ   -sin θ ]
           [ sin θ    cos θ ]

So computing `sin(x)` is "build R(x), apply it to the unit vector
`(1, 0)`, read off the y-coordinate." `cos(x)` is the x-coordinate
of the same operation. There is no approximation — it is the exact
trig identity, just written in matrix form.

The only thing the substrate has to know how to do is build R(θ)
from a scalar θ. That step *itself* is a sin/cos call somewhere —
which sounds circular, but it isn't: the rotation primitive in the
runtime takes θ and produces R(θ) using whatever the substrate's
native trig is (numpy's, torch's, hardware CORDIC). What we get is:
**every Sutra-source `sin(x)` / `cos(x)` call resolves to one
rotation-build + one matrix-vector multiply on the substrate, with
no Chebyshev approximation, no lookup table, no precision tradeoff.**

## Why this is interesting beyond "it's a trig identity"

Three reasons:

1. **Modulus comes for free.** Rotation is inherently periodic:
   `R(θ + 2π) = R(θ)` exactly. So `x mod 2π` is the identity
   operation when `x` is going into a rotation — no separate
   modulus call needed. For trig specifically, **`mod 2π` collapses
   into the rotation itself.** No Chebyshev approximation can give
   you that — Chebyshev approximations of sine drift outside their
   fitted interval and require explicit range reduction with its
   own precision budget.

2. **It looks like a loop, but it isn't iterative.** The user's
   framing: "it would theoretically be a loop, except for the fact
   that the number that we plug in has already done the rotation."
   The eigenrotation primitive's signature is the same as for a
   `loop(cond)` (apply R to state), but here the angle is supplied
   from the input scalar in one step rather than accumulated across
   iterations. The substrate machinery is the same; the use case
   is single-step rather than convergent. This means **trig
   compiles using the existing substrate primitive** — no new
   runtime mechanism needed.

3. **It slots cleanly into the math approximation tier hierarchy.**
   The current four tiers (Exact / Chebyshev / Lookup / CORDIC, see
   `sutra-paper-draft.md` § Novelty 1 and `todo.md` § Compile-time
   math function approximation) lump trig under Chebyshev or
   lookup. With this insight, **trig (sin, cos, tan via sin/cos,
   modulus when paired with trig) moves up to the Exact tier** for
   the rotation-substrate-bound case. That's not a marginal
   speedup — it removes the precision/speed tradeoff entirely for
   a whole family of functions.

## What to try

Minimum experiment to validate the insight:

1. **Pure-math version**: build R(θ) using torch's trig, apply to
   `(1, 0)`, compare against `torch.sin(θ)` / `torch.cos(θ)` over
   a range of θ including values outside `[-π, π]`. Should match to
   numerical precision and handle modulus implicitly.
2. **Compare against Chebyshev tier** for sine specifically. Pick
   a precision target (e.g. 1e-6); count operations / measure
   wall-clock for both paths on a batch of inputs. The rotation
   path should be at least as fast and exact.
3. **Tan, sec, csc, cot**: derivable from sin / cos via single
   division. The Exact tier handles them all once sin / cos do.

## How it would surface in Sutra

The user wouldn't write rotations by hand. The math intrinsic
mechanism (`stdlib/math.su`, see `todo.md`) routes `sin(x)` to
whichever tier the compiler picks. With this insight, the routing
adds a top tier:

- **Exact (rotation-substrate bound)** — sin, cos, tan and their
  reciprocals; modulus when feeding directly into sin/cos. Compile
  to one-step eigenrotation on the synthetic subspace.
- Exact (linear) — closed linear forms.
- Chebyshev — bounded-domain smooth approximations (log, sqrt,
  exp).
- Lookup + interpolation.
- CORDIC.

The compiler picks Exact (rotation-substrate bound) whenever the
input's domain type and the target function are compatible with the
rotation primitive — which is *always* for sin / cos / tan with
real-scalar inputs.

## Open questions

- ~~**Does the rotation primitive's existing build cost (computing
  cos θ / sin θ to assemble R(θ)) make this no better than just
  calling sin / cos directly?**~~ **Resolved 2026-04-28: yes, it
  makes it strictly worse on numpy CPU.** The rotation builder
  internally calls *both* `np.cos(θ)` and `np.sin(θ)` to fill R, so
  there's no "one trig call assembles both" saving — there's a 2×2
  matvec on top of the same two trig calls. Measured: rotation path
  is 1.41× the cost of scalar direct trig and 99× the cost of
  vectorized direct trig. The earlier speculation in this doc that
  "this pays for itself when both are needed" was wrong. See
  `planning/findings/2026-04-28-eigenrotation-as-trig-validation.md`
  test 3 for the measurements.

- **Does this play with the synthetic subspace's slot allocation?**
  The rotation primitive operates on 2D Givens slots. Trig
  operations would need a dedicated slot, or the slot allocator
  would need to spin one up per trig call. Cheap if it's
  per-compile-time-call (allocator just hands out a slot index);
  potentially expensive if it has to be a runtime allocation.

- **Modulus by other than 2π.** The free-modulus story only works
  for angles into trig. `x mod 7` doesn't get this treatment
  unless 7 is also a rotation period — which it can be, but for
  arbitrary moduli the construction is contrived. Worth noting
  the limit explicitly so we don't overclaim.

- **Argument range and dtype interaction.** A very large input
  angle (say 1e9 radians) feeding into the rotation builder has
  precision concerns of its own — float32 loses fractional radians
  at that magnitude, so the implicit modulus only works if the
  rotation builder itself doesn't lose precision before assembling
  R. This needs to be checked against the `[backend] dtype` setting
  before we can claim "Exact" without caveat.

## What this is not

A commitment to ship a new tier. A claim that this is novel
mathematics (it isn't — rotation matrices have always contained
sin/cos). The Sutra-specific claim is **architectural**: because
Sutra already has eigenrotation as a substrate primitive for an
unrelated reason (loops), routing trig through it costs *one
runtime code path instead of two* — but it does not cost less per
operation, on numpy CPU. The cost-win story would only materialize
on a substrate where rotation is a hardware primitive cheaper than
two libm calls (CORDIC on FPGA, or a future native instruction),
which is not where Sutra runs today.

The honest pitch: this is a "nice cleanup if/when we touch the
math-tier code" item, not a priority feature. It does not justify
prioritizing the work over the existing approximation tiers
(Chebyshev, lookup-table, CORDIC) that the math-approximation
todo entry tracks.
