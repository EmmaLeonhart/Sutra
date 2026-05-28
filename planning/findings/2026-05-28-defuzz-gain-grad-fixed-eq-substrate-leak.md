# 2026-05-28 — Defuzz β grad-broken FIXED — `eq()` `float(cos.item())` was a hidden substrate leak

Follow-up to `2026-05-28-defuzz-gain-training-grad-broken.md`. The codegen fix landed in commit `e2b8ee7a` (SutraBarrel session, 23:22 PDT 2026-05-27). This finding documents the full investigation + independent verification + audit-trail catch-up (Audit.md #9 was not yet added).

## Root cause

`sdk/sutra-compiler/sutra_compiler/codegen_pytorch.py` line 2414, inside the emitted `_TorchVSA.eq` runtime method:

```python
def eq(self, a, b):
    av = self._as_any_vector(a)
    bv = self._as_any_vector(b)
    na = _torch.sqrt((av * av).sum())
    nb = _torch.sqrt((bv * bv).sum())
    cos = (av * bv).sum() / (na * nb + _torch.finfo(self.dtype).tiny)
    return self.make_truth(float(cos.item()))   # <— BOTH bugs in one line
```

`cos` is a 0-d tensor with a `grad_fn` chaining back to the inputs (and through them to any trainable parameter). The `.item()` extracts a Python scalar — **detaching autograd** — and `float(...)` re-wraps it as a host float. `make_truth(host_float)` then builds a fresh zero vector and writes the scalar into the truth axis. The numerical value is identical, but the gradient chain is severed.

This is also a substrate leak by the standard CLAUDE.md / Audit.md rule: a host-scalar extraction inside a runtime op. The exact pattern Audit.md REAL LEAK #2 fixed for `defuzzify_trit` was still alive here. Same disease, separate site.

`eq_synthetic` at line 2429 had the same shape (`return self.make_truth(float(truth.item()))`); fixed the same way.

The hypothesis labelled #2 in the prior finding was correct ("`==` operator's lowering may go through a `.detach()` or comparison-then-rebind path"). Hypotheses #1 (loop unroll) and #3 (loop + == interaction) were wrong — the count-form `loop (10)` unrolls correctly to 10 straight-line `v = _VSA.eq((gain * v), _VSA.make_truth(1.0))` calls; each call individually breaks autograd inside `eq`, so the chain dies on the first iteration.

## Fix (shipped as `e2b8ee7a`)

Replaced the `float(cos.item())` / `float(truth.item())` round-trip with a **substrate-pure scatter** that keeps `cos` (or `truth`) as a 0-d tensor:

```python
def eq(self, a, b):
    # ... cosine + eps-guarded divide identical ...
    cos = (av * bv).sum() / (na * nb + _torch.finfo(self.dtype).tiny)
    out = _torch.zeros(self.dim, dtype=self.dtype, device=self.device)
    out[self.semantic_dim + self.AXIS_TRUTH] = cos   # scatter 0-d tensor
    return out
```

Index assignment on a fresh zero tensor with a 0-d source tensor is autograd-tracked via `index_put_` — the resulting `out` has `requires_grad=True` and `grad_fn=<IndexPutBackward>` if `cos` has a grad chain.

Same shape applied to `eq_synthetic` (which had used `float(truth.item())` for the `1 - 2*tanh(||a-b||)` value).

## Verified

1. **Semantic identity preserved.** `experiments/defuzz_gain_adjustment.py --smoke`: param-form vs baked(gain=1.0) max|Δ| = 0.00e+00 < 1e-4. The numerics are exactly the same.

2. **Autograd connects.** Direct test (runtime_dim=64, input v with truth=0.05, gain=0.5):
   - `out.requires_grad = True` (was False before the fix)
   - `out.grad_fn = <MulBackward0>` (chain present)
   - `gain.grad is not None: True` (was None / RuntimeError before)
   - `loss.backward()` succeeds without "element 0 of tensors does not require grad and does not have a grad_fn"

3. **No regression in the test suite.** `pytest sdk/sutra-compiler/tests/` (minus the slow substrate-leak-sweep and the egglog hang on Windows): 402 passed, 7 skipped, 116 subtests passed.

4. **Substrate-leak sweep passes.** `pytest tests/test_substrate_leak_sweep.py`: 1 passed in 1288s. 67 user `.su` programs swept; 0 operator leaks. The fix removed an in-runtime-prelude leak, not a user-program leak, so the sweep CI gate continues green and the prelude is now cleaner.

## Separately: the defuzz task is locally saturated at gain=1.0

Direct autograd test reported `gain.grad = 0.0` — the gradient channel works, but the chosen task (10 iterations of `v == true` on truth-axis inputs in [0.1, 0.9]) saturates `v` to ±1 in 2-3 iterations. By the time the 10th iteration backpropagates, the chain has passed through multiple saturated tanh-like steps and the gradient w.r.t. `gain` is mathematically near-zero, not broken.

This is a **task design** issue, not a codegen issue. The defuzz β SHIP item now needs either:
- A less-iterated form (`loop (2)` or `loop (3)`), or
- Non-saturated inputs, or
- A task that doesn't go through the saturating polarizer

Tracking this in queue.md / `experiments/defuzz_gain_adjustment.py` as a follow-up — separate from the codegen fix.

## Why this leak survived the broader Audit

Audit.md REAL LEAK #2 fixed `defuzzify_trit` specifically by name. The `eq` / `eq_synthetic` methods carry the *same* pattern but were not listed in the audit's REAL LEAK section. The substrate-leak-sweep CI gate (`experiments/substrate_leak_sweep.py`) checks **user .su programs' emitted Python** for `float(...)`/`.item()` patterns — it does not check the runtime-prelude `_TorchVSA` class itself for the same patterns. Both gates have blind spots that overlapped here.

**Recommended follow-on (NOT this commit):** extend the substrate-leak-sweep to also grep `_TorchVSA` definitions, OR add a unit test that exercises the differentiability of every runtime method exposed via the user-facing surface. Either would have caught this.

## Cross-refs

- `planning/findings/2026-05-28-defuzz-gain-training-grad-broken.md` (the diagnosis)
- `experiments/defuzz_gain_adjustment.py` (the harness; unblocks now)
- `sdk/sutra-compiler/sutra_compiler/codegen_pytorch.py` lines 2406–2440 (the fix)
- `Audit.md` REAL LEAK #2 (defuzzify_trit's `float(v[..].item())` fix; the same shape applied here)
- CLAUDE.md "NO MATH SHORTCUTS" / "Forbidden: Scalar extraction inside an operation"
