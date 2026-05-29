# Bundle-decoding regression in `examples/multi_program_axon`

> **FIXED — see `2026-05-15-axon-key-make-string-coercion-regression.md`.**

**Date:** 2026-05-14
**Status:** **Regression confirmed and bisected. FIXED — see `2026-05-15-axon-key-make-string-coercion-regression.md`.**
**Surfaced by:** Yantra-driven testing of `MultiProcessRuntime` cross-program axon-passing (Yantra commit `64b77e1` and surrounding work).

## Summary

The canonical `examples/multi_program_axon/_run.py` demo's bundle-decoding margins regressed by ~10× between commits `39ccacfd` (good) and `895e7a78` (bad). On master today (and at v0.3.2 / v0.3.3 / v0.3.4 / v0.3.5 / v0.4.0) the demo prints:

```
animal_2: cos(recovered, 'dog') = +0.0428   margin = +0.0204
color_1:  cos(recovered, 'red') = -0.0695   margin = -0.0408
user_1:   cos(recovered, 'alice') = -0.0266  margin = -0.0445
RESULT: FAIL
```

At `39ccacfd` and earlier (back through `872a8c1a`, when the demo was added):

```
animal_2: cos(recovered, 'dog') = +0.4001   margin = +0.1997
color_1:  cos(recovered, 'red') = +0.4031   margin = +0.1979
user_1:   cos(recovered, 'alice') = +0.4498  margin = +0.2639
RESULT: PASS
```

## Bisect

| commit | margin (animal_2) | result |
|---|---|---|
| `872a8c1a` (demo first added) | +0.1997 | PASS |
| `6d25f232` (per-key permutation in axon_add/item) | +0.1997 | PASS |
| `39ccacfd` (spec/strings literal-coercion doc) | +0.1997 | PASS |
| **`895e7a78` (FIX: destination-type-driven string-literal coercion)** | **+0.0204** | **FAIL** |
| `9dfa80ee`, `4202916f`, `2582cd46`, `2690051d`, all subsequent | +0.0204 | FAIL |

The Yantra-side work I did (axon-keys static analysis, axon_project, MultiProcessRuntime, device-coherence fix) **did not introduce this regression** — it was already present at v0.3.2 (pre-axon-keys).

## Root cause hypothesis

Commit `895e7a78` ("FIX: destination-type-driven string-literal coercion — no more host Python at Sutra boundaries") added compile-time coercion of string literals at function-call boundaries: a `StringLiteral` landing in a parameter typed `string` / `String` / `Character` is wrapped via `_VSA.make_string(...)` so the value crosses as a substrate-encoded codepoint vector instead of a host Python string.

The intended target was user-level string handling. The unintended impact: calls like `a.add("animal_1", v_cat)` (in `producer.su`) and `axon_item(state, "animal_2")` (in `consumer.su`) now pass a `make_string`-encoded vector as the `key` argument to the runtime methods `_TorchVSA.axon_add` and `_TorchVSA.axon_item`. Those methods have:

```python
key_vec = self.embed(key) if isinstance(key, str) else key
```

When `key` arrives as a Python string (pre-FIX): `key_vec = embed("animal_1")` — a semantic LLM-embedded vector that drives a useful rotation. When `key` arrives as a `make_string` vector (post-FIX): `isinstance(key, str)` is False, the else branch runs, and `key_vec` is the raw codepoint-encoded vector. Its content lives almost entirely in the synthetic block, so the rotation `_rotation_for(key_vec)` derived from it has very little semantic-block content — bind/unbind round-trips lose the per-role uniqueness that bundle decoding depends on.

Both producer and consumer apply the same coercion, so the rotation key matches on both sides — that's why the demo doesn't error or produce nonsense; it just produces *very weak* recovery.

## Suggested fix directions (not done)

Three possible directions, in order of how invasive they are:

1. **`axon_add` / `axon_item` decode-then-embed when key is a make_string vector.** Detect the substrate-encoded-string shape (probably `_VSA.AXIS_CHAR_FLAG` set in the synthetic block) and decode back to a Python string, then `embed()` as before. Smallest fix; preserves the "no host Python strings at substrate boundaries" rule for the user-facing path while making the runtime methods tolerant.
2. **Codegen: special-case axon_add / axon_item to NOT apply string-literal coercion to their `key` arg.** Their `key` parameter is semantically a "role identifier," not a "string value." Treat them as host-side helper signatures (similar carve-out to the existing JavaScriptObject + `make_char` interop carve-out documented in CLAUDE.md). Slightly more surgical than #1.
3. **Type the `key` parameter as something other than `string`.** A `name` / `role` / `identifier` type that the coercion rule doesn't trigger on. Cleanest at the spec level but requires a new type with no other users yet.

## Reproduce

```bash
cd external/Sutra
python examples/multi_program_axon/_run.py
# Compare output against the README's expected margins.

# Bisect:
git checkout 39ccacfd && python examples/multi_program_axon/_run.py  # PASS
git checkout 895e7a78 && python examples/multi_program_axon/_run.py  # FAIL
```

## Yantra-side impact

Bandwidth: none. Yantra's tests don't depend on the high-recovery numbers — the kernel tests use trivial pass-through `.su` bodies and the lazy-router tests use stand-in projectors (not the real `axon_project` recovery margin). The MultiProcessRuntime test that tries cross-program axon-passing was relaxed to verify mechanism (no crash, right shape, non-zero output) rather than recovery quality, exactly because of this regression.

The regression matters for *real* connectomes — once Yantra runs programs that actually depend on bundle-decoding accuracy across program boundaries (e.g. a sensor-fusion process publishing K labelled values for downstream consumers), the ~10× margin loss may push some valid configurations across the recovery threshold. Tracked for follow-up.
