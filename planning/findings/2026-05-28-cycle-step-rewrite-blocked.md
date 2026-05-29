# 2026-05-28 — `cycle_step` substrate-RNN rewrite blocked

> **CLOSED 2026-05-28 — see `2026-05-28-font-cycle-step-substrate-rnn-shipped.md` (Option B shipped).** The block below is kept as the wall-analysis record.

Per Emma's "rewrite them" instruction (after count.su + toggle.su shipped substrate-RNN via `recur`), I attempted the same rewrite for `demos/font/font.su`'s `cycle_step`. Reverted; the file is at HEAD. Documenting the wall so the next attempt has the analysis in hand.

## The blocker

`cycle_step`'s body computes 36 squared-distance scores from `prev_code` (the current char_code) against the cycle's 36 supported char codes, then uses `select` to pick the next char via softmax saturation. The arithmetic is:

```sutra
scalar s_K = 0.0 - 1000.0 * (prev_code - K.0) * (prev_code - K.0);
```

In the original (host-state-shuttle) cycle_step, `prev_code` was a `scalar` function argument — the host called `cycle_step(prev_code_value, typed, has_typed)` with a Python float, so `prev_code - 65.0` was Python float arithmetic and `s_K` was a Python float. `_select_softmax` consumed a list of Python floats.

For the `recur` rewrite, `prev_code` becomes the value of a `recurring vector prev_state` slot. Two attempts:

1. **Vector arithmetic throughout** (`prev_state - 65.0` etc.): each `s_K` is now a vector of shape `(runtime_dim,)` with the squared-distance on the real axis AND non-zero values on every other axis (the `-65.0` broadcasts element-wise across all axes, so other axes hold `(0 - 65)^2 * -1000 = -4225000`). `_select_softmax` fails: `_torch.as_tensor(scores, ...)` errors with "only one element tensors can be converted to Python scalars" because each score is a 16-d tensor, not a scalar.

2. **One in-function extraction via Sutra-level `real(prev_state)`**: would give a Python float `prev_code`, then the rest of the body works as before. But Sutra source has **no `real()` free function** — `_VSA.real(v)` is a runtime accessor exposed as a Python-host helper, not callable from .su source. The codegen emits `NameError: name 'real' is not defined`.

## What's needed for the rewrite to land

One of:

- **Option A: Expose `real()` (and `imag()`, `truth()`) as Sutra source-level free functions** that compile to `_VSA.real(v)`. Smaller surface change. Per audit BORDERLINE, these are documented monitoring/extraction accessors — exposing them at the source level makes the "one extraction inside an op" pattern available without forcing a host round-trip. The rewrite would then look like `scalar prev_code = real(prev_state);` at the function top, body unchanged. This IS a documented purity gap (one extraction per call inside an op), but it satisfies the state-locus rule (the recurring slot stays a vector across calls — only the within-call computation extracts).

- **Option B: Rewrite the 36-way scoring as tensor-only.** Encode the 36 supported char codes as a `(36, runtime_dim)` matrix and the corresponding "next char" codes as another `(36, runtime_dim)` matrix; compute distances via tensor ops; do softmax over the distance vector; weighted-sum the next-char matrix. Substrate-pure end-to-end, but requires matrix primitives Sutra may not currently expose at the source level + a new substrate `_select_softmax_from_vectors` op or equivalent.

- **Option C: Status-quo + honest framing.** Leave `cycle_step` as host-state-shuttle (the host carries `prev_code` between calls); update the audit doc + docstring to explicitly acknowledge this case as the unresolved one in the post-`recur` cleanup. Honest about scope; not actually fixing the breach.

## Recommendation (subject to Emma)

Option A is the smallest unblock. The substrate-purity rule already allows host extraction at monitoring/output boundaries (`vsa.real(v)` is in Audit.md's LEGITIMATE list); exposing `real()` to .su source moves the boundary INSIDE the function without changing the breach calculus — the state-locus rule is what matters for "substrate-RNN" claim, and that one is satisfied as long as the recurring slot holds a vector across calls.

Option B is the purer fix but a much bigger ship. Defer until matrix primitives are more developed.

Option C is a placeholder, not a fix.

## Cross-refs

- `planning/sutra-spec/non-halting-loop.md` "Implementation plan" item — names the v2 follow-ons including this rewrite.
- `demos/font/font.su` `cycle_step` — current host-state-shuttle implementation (untouched).
- `planning/findings/2026-05-28-demos-font-substrate-audit.md` — the original audit that flagged cycle_step alongside count.su / toggle.su.
- count.su + toggle.su rewrites (`6757863d`, `6fc64c15`) — successful cases where the body's arithmetic was naturally vector-compatible.
- CLAUDE.md "Subtler substrate breaches" #2 — the state-locus rule.
