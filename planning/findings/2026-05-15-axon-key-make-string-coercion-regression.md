# Axon role-key string-literal coercion regression — root-caused + fixed

**Date:** 2026-05-15
**Author:** Claude (Opus 4.7), autonomous Yantra-driven queue run
**Touches:** `sdk/sutra-compiler/sutra_compiler/codegen_base.py`
**Repro:** `python examples/multi_program_axon/_run.py`
**Filed as:** the Yantra-side "bundle-decoding regression" (Yantra
`todo.md`, filed 2026-05-14: recovery margins ~10× below README).

## Symptom

`examples/multi_program_axon/_run.py` recovered fillers at
`cos(recovered,'dog') = +0.04` (two keys at *negative* margin →
`RESULT: FAIL`) versus the README/2026-05-10-finding expected
`+0.40` (`margin +0.20`, `PASS`). Same code path, ~10× worse — a
real regression, not the documented 12-key capacity wall
(`producer.su` is the 5-key case).

## Investigation (measured, not theorized)

A staged diagnostic probe (two separately-compiled module
instances, exactly like `_run.py`) ruled the suspects out and in:

| Test | Result |
|---|---|
| `embed("animal_2")` byte-identical across the two module instances | **identical** (max Δ 0.0) |
| `_role_hash` agreement producer vs consumer | **match** |
| same-instance `unbind(r, bind(r, dog))` | **cos +1.0000** |
| cross-instance `unbind_C(bind_P(dog))` | **cos +1.0000** |
| direct runtime `axon_add`/`axon_item`, N=1..5, cross-instance | **+0.40 at N=5 (== README), wire .npy byte-lossless** |
| compiled `producer.make_state()` vs direct embed-keyed axon | **cos +1.0000** (producer key = `embed`) |
| **direct `cv.axon_item(state,"animal_2")`** | **+0.4001** |
| **compiled `consumer.recover_animal(state)`** (same input) | **+0.0428** |

So bind/unbind, role-hash determinism, the bundle, and the `.npy`
wire are all correct. The divergence is **exactly** between the
*direct runtime* `axon_item` (correct) and the *compiled* consumer
`axon_item(state, "animal_2")` (broken) on identical input.

## Root cause

`stdlib/axons.su` declares `axon_item(Axon a, string key)`. The
free-call lowering in `codegen_base.py` (`_arg_dest`) uses the
declared param type as the `dest_type` for literal coercion, so the
string literal `"animal_2"` is translated under `dest_type="string"`
and `_translate_expr` wraps it as `_VSA.make_string('animal_2')`
(the 2026-05-08 parallel-string-model coercion). The runtime
`axon_item` then takes its `else` branch
(`key_vec = _torch.as_tensor(key, …)` — the codepoint vector)
instead of `isinstance(key, str) → key_vec = self.embed(key)`.

The producer side is unaffected: `producer.su`'s
`a.add("animal_2", v_dog)` lowers through the member-access
`_axon_declared` path, which translates the key arg **with no
`dest_type`** → host str → `embed("animal_2")`. So producer keyed
on `embed("animal_2")`, consumer keyed on
`make_string("animal_2")` — different vectors → different role
rotation → `unbind` returns a wrong orthogonal transform of the
bundle → recovered ≈ noise (cos ≈ 0 to the true filler).

This is the "vibe-coded spec drift" pattern CLAUDE.md warns about:
the 2026-04-10 "string literals stay host" decision was correct in
scope; the 2026-05-08 parallel string model silently made the
free-call axon-key path wrong, while the member-access path stayed
correct — invisible until a cross-module decode exercised both.

## Fix

`codegen_base.py` `_arg_dest`: exempt the axon role-key argument
(`axon_add` arg 1, `axon_item` arg 1) from string→`make_string`
coercion — force `dest_type=None` so the literal stays a host str
and the runtime's `isinstance(key,str) → embed(key)` branch fires,
consistently with the member-access path, the producer, and the
spec (`axons.su`: `axon_item(a,k) → unbind(basis_vector(k), a)` —
the key is a role *name* embedded into a basis vector, not string
*content*). One surgical change; the May-8 string model is
untouched for all real string *values*.

## Verification (honest, untuned)

`python examples/multi_program_axon/_run.py` →

```
animal_2: cos('dog')   =+0.4001  cos('octopus')=+0.2004  margin=+0.1997  [OK]
color_1 : cos('red')   =+0.4031  cos('violet') =+0.2052  margin=+0.1979  [OK]
user_1  : cos('alice') =+0.4498  cos('xavier') =+0.1859  margin=+0.2639  [OK]
RESULT: PASS
```

Exactly the README / 2026-05-10-finding numbers — restored by
correcting the key path, not by tuning. Full
`sdk/sutra-compiler/tests/` suite: see commit message for the
regression-check result.

## Note for the Yantra side

This closes the Yantra `todo.md` "bundle-decoding regression"
investigation. The VSA-capacity story the Sutra paper rests on was
**not** degraded — the mechanism was always correct; a compiler
key-coercion regression corrupted the cross-module demo only.
`_run.py`'s `[2/4] … building 12-key axon` print string is stale
(the source builds 5 keys) — cosmetic, flagged for a later tidy.
