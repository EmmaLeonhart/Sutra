# Stage A0 — emit substrate-pure tensor `similarity`/`dot`

**Created 2026-05-18.** Prerequisite for §3.6 real-compiled-graph
training (Stage A). Emma's call: full fix, test-gated, **hold
submission**. No harness monkeypatching (= faking, rejected).

## The defect (verified)

`codegen_pytorch.py` emits:
- L1133 `similarity` → `return float(_torch.dot(a,b)/(na*nb+tiny))`
- L1160 `dot`        → `return float(_torch.dot(a,b))`

`float()` mid-graph (a) detaches autograd → the compiled fuzzy-rule
returns a Python float, untrainable; (b) violates the runtime's own
doctrine ("exactly ONE host→substrate boundary `_st`"; accessors
`real`/`truth`/`component` are the monitoring-only collapse points —
NOT ops). `similarity`/`dot` are ops used *inside* composed
expressions, so their `float()` is a substrate-purity violation, not
a legitimate accessor boundary.

Already correct (tensor, no float, leave alone): loop `_step`
(L2368 raw `_torch.dot`), complex real/imag projections
(L1287/1293), `matmul`/`outer`/`kron`.

## The change

Drop the `float()` in `similarity` and `dot` so they return 0-d
tensors; keep the eps-guard. Verify `eq` (L2261, the `==` cosine)
returns a tensor when composed. Host collapse happens ONLY at the
true monitoring/decode boundary: `real()` (L1653), `truth()`
(L1663), `nearest_string` (L544), and the program-output/print
path — exactly where the runtime already intends it.

## Ripple inventory — verify program *values* unchanged, only
host/tensor *type* defers to the decode boundary

- numeric `main()` result printed by harness/corpus: 0-d tensor
  must render identically (e.g. collapse at the output boundary,
  not via `similarity`). Biggest regression surface — the corpus
  asserts printed outputs.
- `defuzzify`/`defuzzify_trit` (L2159), `eq`/`==` (L2261): operate
  on tensors — confirm unaffected.
- numeric comparisons / soft-mux conditionals / `is_true`: Sutra
  has no host branch on data → already tensor-shaped; confirm.
- `argmax_cosine` / `nearest_string`: confirm they don't depend on
  `similarity` returning a host float.
- test corpus programs that do arithmetic on `similarity`/`dot`.

## Test gate (must be green, zero regression)

Baseline FIRST (record pass counts), then re-run after the change:
- `python -m pytest sdk/sutra-compiler/tests -q`
- `python examples/_smoke_test.py`
- loop/transcendental suites if not covered by the pytest run.
Any corpus output diff (`tensor(0.83)` vs `0.83`) is fixed at the
decode/print boundary — **never** by re-adding `float()` to
`similarity`.

## Sequence

baseline → change emission → gate → fix ripple at decode boundary →
re-gate (zero regression) → Stage A (real compiled differentiable
classifier, 5-seed, measured numbers whatever they are) → rewrite
§3.6/abstract to the true claim → Stage B (weighted `Equals(a,b,w)`,
trained weights emitted back into `.su` source). Submission stays
held until Stage A is real and gated. Frozen `paper/neurips/`
untouched.
