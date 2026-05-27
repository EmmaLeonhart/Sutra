# Where does the trained equality-cosine `T` live in the language? — LEAN: per-rule literal

**Status:** Resolved 2026-05-26 by Emma (one-word call: "Lean"). Captured here per the open-questions convention so future sessions don't re-open it without re-asking.

## The question

The Stage-B finding (`planning/findings/2026-05-18-differentiable-training-is-a-proxy-not-compiled.md`) trained a scalar gain `w` *per rule*, then baked it as a numeric literal into the rule's `.su` source. The current `experiments/equality_cosine_adjustment.py` does the same, renamed `T` for the equality cosine context. Several long-term placements were possible:

1. **Per-rule literal (status quo).** Each compiled `.su` rule carries its own baked-in `T` literal at every `similarity` call site. No language change.
2. **Per-program constant.** A top-level `number T = 1.431431;` declaration that the rule references — one `T` per `.su` file, shared across all rules in that file.
3. **Language-level cosine policy.** `_VSA.similarity` itself gains a learned `T` factor (compile-time calibrated once for the runtime); all `similarity` calls in all programs share it.
4. **Compile-time calibration step.** A scripted pass that, given a probe set, calibrates `T*` and emits a fused `similarity_T` primitive — distinct from runtime training.

## Decision: option 1 (per-rule literal)

Emma's word, 2026-05-26: "Lean."

This means: do exactly what Stage-B's bake-back already does. `T` is a numeric literal at each call site inside the trained rule. No spec change. No new declaration form. No new `_VSA` primitive. Optimizer trains it, bake-back substitutes it, recompile round-trip confirms equivalence.

## Why each side had force

- **Per-rule literal (chosen).** Already works end-to-end (Stage-B + smoke-tested in `bu7o9mqxu`). Zero spec / compiler change. The trained model IS the rule's `.su` source — Stage-B's headline property. Substrate-pure: `T * _VSA.similarity(...)` is two substrate ops composed; nothing host.
- **Per-program constant.** Would let one trained `T` cover multiple rules in a file without keeping them in sync by hand. But requires (a) a `T` declaration grammar, (b) bake-back-into-declaration machinery, (c) the assumption that one program *wants* one `T` (not yet established). Defer until a use case actually needs cross-rule sharing.
- **Language-level cosine policy.** Architecturally cleanest in some sense — but it commits `_VSA.similarity`'s semantics to a single `T` that all programs inherit, which over-constrains. Different programs may want different `T`s; the lean per-rule option doesn't preclude this from being added later, but adding it now is over-design for the current evidence.
- **Compile-time calibration step.** Would skip the runtime training loop entirely — calibrate once at compile, bake. Strong if calibration generalizes across tasks; weak if it doesn't. Not enough evidence yet to know; the per-rule path keeps the question open for a separate experiment.

## What would re-open this question

- A constrain-train experiment where two rules in the same program need *consistent* `T`s for the program to behave correctly, and per-rule training drifts them apart. Would justify option 2 (per-program constant).
- Evidence that a *compile-time-calibrated* `T*` (no runtime training, just a probe-set pass at compile) generalizes to downstream tasks within ε. Would justify option 4.
- A language-wide audit showing `similarity` is too cosine-compressed everywhere by the same factor (anisotropy is uniform). Would justify option 3.

None of these triggers exists today.

## Cross-links

- The equality cosine adjustment experiment: `experiments/equality_cosine_adjustment.py`
- Stage-B precedent: `planning/findings/2026-05-18-differentiable-training-is-a-proxy-not-compiled.md` § "Cron fire 9"
- Constrain-train agenda the decision feeds: `todo.md` §"Agentic RAG for constrained-training design" → "similarity temperature (scalar)" target
