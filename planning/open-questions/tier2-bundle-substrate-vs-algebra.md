# Open question: does `bundle(...)` run on the substrate, or stay algebraic?

> **Status (2026-04-26):** moot for the current implementation —
> the only substrate that routed `bundle` through a circuit was the
> retired fly-brain backend. On the current PyTorch backend
> `bundle(...)` is normalized vector addition. The question would
> reopen if a circuit-routed substrate is reintroduced; preserved
> as the design-space map for that future. Doc title also referred
> to "tier-2," a framing rejected per CLAUDE.md.

## The question

When a Sutra program writes `bundle(a, b, c)`, should that:

- **(A)** compile to numpy `a + b + c` — pure algebra on the host, tier-2 per `planning/sutra-spec/02-operations.md`; or
- **(B)** compile to a call that encodes each input as PN currents, runs the spiking MB, and reads back the superposed KC pattern (`bundle_on_brain` in `fly-brain/vsa_operations.py`) — i.e. the bundle actually happens on neurons?

The spec currently says (A). The implementation currently does (B). One concrete computation (`fuzzy_conditional.su`) breaks under (B) and passes under (A). That mismatch is the question — not which individual test passes.

## What we currently do

- The `.su` codegen emits `_VSA.bundle(...)` for a source-level `bundle(...)` call.
- `FlyBrainVSA.bundle` routes to `SpikeVSABridge.bundle_on_brain`, which re-encodes each input as centered rate-coded PN currents, sums the currents, fires Brian2 LIF KCs through APL, and decodes the result via the learned MBON readout.
- In `fly-brain/fuzzy_conditional.su` we write `w_PH * beh_PH + w_PF * beh_PF + ...` instead of `bundle(...)`. That compiles to numpy addition and passes 16/16. Using `bundle(...)` fails 11/16 because the centered rate coding + APL sparsity squash the relative scalar weights.

## Why (A) has force

- `planning/sutra-spec/02-operations.md` explicitly puts bundle in tier-2 ("algebraic / VSA... O(1), pure math, no infrastructure").
- `CLAUDE.md` restates: "Running these on numpy is correct and spec-compliant. Routing them through a spiking simulation is *more* than the spec requires and doesn't strengthen anything."
- The reference `fly-brain/fuzzy_conditional.py` that achieves 16/16 and 80/80 σ=0 on hemibrain uses numpy addition for the weighted sum, not `bundle_on_brain`.

## Why (B) has force

- The whole point of Sutra is programming the substrate. If `bundle` is the VSA superposition op, and the substrate has a native superposition mechanism (convergent PN→KC currents), then running it on neurons is the thing we are trying to demonstrate, not a thing to avoid.
- The user's direct framing: "The point of the bundling and the binding is supposed to be that we're actively using this stuff to be an actual representation of neurons."
- If the demonstrated mode of bundle is "we bypass it", that reads as a benchmark-rigging shortcut even when the spec permits it.

## What's really going on underneath

The spiking-bundle implementation is lossy in a specific way: centered rate coding clips + normalizes the input magnitudes before encoding, so `2.0 * v` and `0.1 * v` present with similar firing rates. The op therefore computes a weight-free superposition, not a weighted one. Spec 02-operations.md gives bundle as `Σ vᵢ` (unweighted), so the spiking implementation is faithful to the spec's bundle — it's the *weighted* sum `Σ wᵢ · vᵢ` the spec doesn't explicitly cover.

Our current weighted-sum use case sits in between: scalar-multiply is tier-2, bundle is tier-2, so the composition is tier-2 by the spec — host math. But the user wants more of the computation to physically execute on neurons.

## What we'd need to decide

1. **Is the algebraic tier-2 bundle a first-class primitive, or a convenience?** If first-class, (A) is correct and we cite the spec. If convenience, we need a substrate-side weighted-superposition primitive (e.g. scale PN currents by the weight before summing, *without* the rate-coding clip) and (B) becomes viable.
2. **If we want (B), what's the substrate contract?** `bundle_on_brain` currently destroys the weights. A "weighted bundle on brain" means reaching into the encoding layer — either remove the magnitude clip for small values, or scale by presenting each weighted vector for `wᵢ · T` integration time, or something else. That's a real redesign of the encoder, not a one-line change.
3. **How do we keep the demo honest either way?** If we ship (A), the paper needs to say bundle is algebraic on purpose, not by accident. If we ship (B), we need a test that measurably distinguishes weighted-bundle output from unweighted, on-circuit.

## Concrete next steps (when picked up)

- Read `fly-brain/spike_vsa_bridge.py` `_encode` / `bundle_on_brain` to confirm exactly where the weights die.
- Try encoding `w · v` as presentation duration (integrate-on-longer) or as an unclipped current scalar, see whether a weighted bundle on-circuit can give the fuzzy_conditional pipeline 16/16.
- If yes, swap `fuzzy_conditional.su`'s `+` chain back to `bundle(...)` and keep the win. If no, update `planning/sutra-spec/02-operations.md` to explicitly mark weighted superposition as algebraic-only, and keep the `+` form.

## Status

Unresolved. Currently pinned by `fuzzy_conditional.su` needing numpy `+` to pass. Not urgent for the Claw4S paper — the reference `.py` version is what the paper cites, and it is honest about being algebra over substrate calls. Urgent before any claim of "the full program runs on neurons."
