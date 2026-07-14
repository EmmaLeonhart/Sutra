# Backprop through a runtime loop HARD-FAILS: aten::heaviside has no derivative (2026-07-14)

Triggered by the v9 clawRxiv review's Heaviside criticism (review = signal; this measurement
is the verdict). MEASURED: building a leaf tensor with `requires_grad=True`, feeding it as
loop state through the emitted `_loop_addNumber` driver, and calling `backward()` on the
real-axis readout raises

    RuntimeError: derivative for aten::heaviside is not implemented

— i.e. programs containing runtime loops are not merely zero-gradient through halt timing,
they are **not backpropable at all** (autograd raises). The paper's conclusion claimed
"differentiable end-to-end through the compiled graph" unscoped; the §3.6 measured result
(gradients verified through connectives/similarity) is on loop-free graphs and stands.

## Paper fix (same day)

Two sites scoped to measured truth: the conclusion now states the straight-line graph is
differentiable end-to-end (verified §3.6) while loop termination is forward-only with a hard
step, surrogate as future work; the §3.4 loops-method section carries the same caveat where
the reviewer pointed. The reviewer's "2026 citations are hallucinated" con is reviewer error
(it is 2026); the toy-scale con is fair and already acknowledged.

## The design question (Emma's call — do NOT build unilaterally)

Making loops trainable needs a **surrogate gradient for the halt step** — options:
(a) straight-through estimator on `heaviside` (identity or clipped backward);
(b) replace the halt read with a steep sigmoid `tanh(k·x)`-style soft step (changes forward
    semantics slightly — halt saturation behavior must be re-measured);
(c) leave forward-only (loops as inference-time control, training on loop-free subgraphs).
Each changes training semantics on the substrate — a language-design call, not a bug fix.
Filed to the queue; the repro above becomes the test when a direction is chosen.
