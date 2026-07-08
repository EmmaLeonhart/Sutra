# fuzzy_dispatch.su returns WRONG dispatches on the PyTorch backend — and the smoke test never sees it, because the examples harness still compiles via the deprecated numpy backend (2026-07-07)

> **RESOLVED same day — and the root cause was NOT a backend divergence.** Measurement showed
> the sims identical on both backends (winner 1.0 vs ~0.61–0.70) and the decode WRONG BY
> CONSTRUCTION at softmax T=1: the winning record got ~0.32 weight, while the action `start`
> appears in TWO records (music+timer, combined ~0.47) and out-votes the true action in the
> superposition. Backends only differed in which knife-edge cases tipped (decode gaps 0.01–
> 0.06). Worse: the smoke test printed per-case FAILs but PASSED anyway — a previous session
> had weakened the gate to `correct >= 2` with a "prototype separation" rationale the
> measurement disproves. FIXES (all shipped): (1) the example sharpens its scores (×10 gain =
> the spec's explicit select temperature) → 4/4 on BOTH backends, measured decode gaps action
> 0.20–0.30 / target 0.19–0.22; (2) smoke gate restored to `correct == total`; (3) harness
> flipped to the canonical pytorch backend; (4) `strings_and_formatting.su` added as smoke
> entry 11. Full smoke PASS on torch.

Found while adding the round-17 strings tutorial example (it needs the String runtime, which
only the torch backend has — that's what exposed the harness's backend choice).

## Measured

1. **`examples/_su_harness.py` compiles every example with the DEPRECATED numpy backend**
   (`from sutra_compiler.codegen import translate_module`). CLAUDE.md § Architecture names
   PyTorch as the canonical compile target, and `sutrac --run` (what a pip user actually
   executes) compiles via `codegen_pytorch`. So the smoke test — the paper-durability guard —
   verifies a backend users never run.
2. **On the pytorch backend, `fuzzy_dispatch.su` fails 3 of 4 dispatch cases** — weather,
   music, and cancel ALL collapse to `start:alarm`; only timer is right. Verified on TODAY's
   HEAD *and* on pre-today `656e888f` in a clean worktree: identical output, so this is a
   longstanding numpy↔pytorch semantic divergence, NOT a regression from the 2026-07-07
   cast/interp/concat work (whose `+`-concat dispatch provably does not fire here — the
   operands are subscripts, which the conservative `_is_text_expr` leaves False).
3. Every other smoke entry passes on pytorch (hello_world, fuzzy_branching 16/16, records,
   semantic FAQ 5/5, etc.) — the divergence is specific to whatever `fuzzy_dispatch.su`
   exercises (N-way dispatch over bound records; suspicion, unverified: the weighted
   superposition of record fields or the `map<vector,string>` readout ranks differently under
   the torch runtime's binding/normalization).

## Why this matters

- A pip user running the cited example gets silently wrong output TODAY — exactly the "wrong
  math propagates silently downstream" class the integrity rules exist for.
- The paper-durability guard (`examples/_smoke_test.py keeps passing`) is currently a guard on
  the wrong backend; switching the harness to the canonical backend flips it red, which is why
  the switch was reverted rather than shipped (a red smoke is not shippable, and the fix is an
  investigation, not a one-liner).

## Follow-ups (queued)

1. Investigate the fuzzy_dispatch divergence on pytorch — decode the intermediate record
   bindings/similarities on both backends, find the op that ranks differently, fix the torch
   runtime (or the example if the numpy behaviour was the accident). Measured gap table
   required per CLAUDE.md § signal-separation.
2. THEN switch `_su_harness.py` to `codegen_pytorch.translate_module` (canonical), re-run the
   full smoke, and add `strings_and_formatting.su` to the smoke entries (it needs the String
   runtime, so it can only join after the switch).
