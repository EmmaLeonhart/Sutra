# 2026-05-28 — Defuzz β training: backward() fails — gradient does not reach `gain`

Emma greenlit (sweep Q4) running `experiments/defuzz_gain_adjustment.py` end-to-end. Launched `python experiments/defuzz_gain_adjustment.py --seeds 3 --epochs 20 --N 16`. The script crashes at `loss.backward()`:

```
RuntimeError: element 0 of tensors does not require grad and does not have a grad_fn
```

Runlog: `experiments/runlogs/2026-05-28-defuzz-gain-adjustment-3seed.txt`.

## Diagnosis

`gain = torch.tensor(1.0, dtype=dtype, device=device, requires_grad=True)` (line 240) — set up correctly. The optimizer wraps it `torch.optim.Adam([gain], lr=a.lr)`. The forward call is `mod.gated_polarize(v, gain)[truth_idx]`. So the input tensor IS a leaf with requires_grad; the loss tensor must be losing the connection somewhere inside the compiled .su's `gated_polarize`.

The .su is:

```
function fuzzy gated_polarize(fuzzy v, number gain) {
    loop (10) {
        v = (gain * v) == true;
    }
    return v;
}
```

The `loop (10)` is a count-based loop (NOT the `loop (cond)` rotation form) — per Audit.md REAL LEAK #2's fix, count-based loops are **codegen-time unrolled** into a straight-line tensor-op chain. So the emitted code should be 10 sequential `v = ...` reassignments, each differentiable.

## Why this isn't the same as equality_cosine_adjustment (which trains successfully)

`equality_cosine_adjustment.py` uses the same `T = torch.tensor(1.0, requires_grad=True)` pattern, also passes T as a `number` parameter. It works (it shipped in 2026-05-26 commit `21778648`). The difference between the two harnesses:

| | equality_cosine | defuzz_gain |
|---|---|---|
| Trainable param shape | scalar `number T` | scalar `number gain` |
| Loss path | cosine-similarity logits → cross-entropy | output truth-axis → MSE |
| `loop` in the .su | no | YES — `loop (10)` |
| `==` in the .su | no (sim() directly) | yes (`== true`) |

The two non-shared elements are the `loop (10)` count-form AND the `==` operator inside the loop body. One of them is detaching the gradient.

## Hypotheses (NOT verified — investigation needed)

1. **The `loop (10)` count-form's codegen unroll may not be threading the trainable parameter through.** Audit.md REAL LEAK #2's fix says "straight-line tensor-op chain" but the rebinding inside the unroll might be losing the connection.
2. **The `==` operator's lowering (defuzz polarize / equality_cosine) may go through a `.detach()` or comparison-then-rebind path.** The `defuzzify_trit` fix (Audit.md REAL LEAK #2) is "spec-fixed 10-step β-sharpening unrolled at codegen time into a straight-line tensor-op chain, each step three substrate-pure self.exp readouts; scatter back out[idx] = x (0-d tensor, no float())." The scatter-back via `out[idx] = x` *might* not be autograd-tracked if `out` is created fresh each iteration via `state.clone()` or similar.
3. **The two combined (loop + ==) interact in a way that detaches.** E.g., the loop's rebinding of `v` to the equality result might consume v in a way that strips the gradient.

## Not done in this tick

Per CLAUDE.md HARD RAILS "Don't implement what you don't 100% understand — write the spec/queue item instead." The fix requires tracing the compiled Python module's emitted code for `gated_polarize` and identifying where the gradient connection breaks. That's an investigation task, not a guess fix.

Per Emma's "every operation trainable" vision: **this experiment is the canonical test of whether `loop` + `==` compose with autograd**. If they don't, that's a real gap in the constrain-train surface that needs fixing — not a small bug.

## Next action

1. Add a fresh queue item: investigate why `gain` gradient does not reach `loss` in the defuzz harness. Trace the emitted Python; locate the autograd-breaking site.
2. The defuzz β SHIP item stays in queue until this is unblocked.
3. The arbitrary-precision and contract-key-soundness items proceed independently.

## Cross-refs

- `experiments/defuzz_gain_adjustment.py` (the broken harness)
- `experiments/equality_cosine_adjustment.py` (working precedent, no `loop`/`==`)
- `experiments/rank_k_is_x.py` (the matrix-valued working precedent, also no `loop`/`==` in the trainable surface)
- `Audit.md` REAL LEAK #2 (defuzzify_trit codegen-unroll fix)
- `sdk/sutra-compiler/sutra_compiler/codegen_pytorch.py` (the lowering)
