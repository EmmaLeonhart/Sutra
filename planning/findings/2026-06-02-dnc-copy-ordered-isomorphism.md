# DNC↔code isomorphism — the ordered case (copy): first run + a metric correction (2026-06-02)

The content-read rung is cleared (`2026-06-02-dnc-content-read-code-isomorphism.md`).
This is the **ordered** test: does a DNC trained on **copy** defuzz to a
clean sequential pointer-walk program? Design:
`differentiable-neural-computer.md` § "The correct full version".
Experiment: `experiments/dnc/dnc_copy.py` (faithful DNC — LSTM controller,
usage/allocation write, temporal-link matrix `L`, content/forward/backward
read — host-PyTorch prototype, NOT substrate-pure).

## First run (seed 0, 20000 steps, T-curriculum 1→6) — measured

```
copy bit-accuracy             : 1.000     <- learned copy perfectly
write weighting peak (one-hot): 0.997     <- clean one-hot writes
read  weighting peak (one-hot): 0.938     <- near one-hot reads
read rows all-distinct        : 100.0%    <- clean pointer walk over T rows
example read-row sequences    : [[11,1,13,14,9,5], [11,1,13,14,9,0], ...]
```

## A metric correction (don't mislabel a success)

The script's first pass/fail criterion checked whether read rows
*ascend* (0,1,2,…) and so reported "NOT a clean sequential walk" (advance
42.8%). **That criterion is wrong.** A DNC writes via **allocation** —
rows chosen by usage, e.g. 11,1,13,14,9,5 — and reads back via the
**temporal links** in *written order*. So the read sequence
`[11,1,13,14,9,5]` is exactly the write order, recovered by `next(p)`;
the physical indices are an allocation permutation, not 0..T-1. With copy
accuracy 1.000, near-one-hot reads (0.938), and 100% all-distinct rows,
the read **must** be recovering the written sequence in order — that is a
clean pointer walk, the correct program. The ascending-row check
conflated "sequential pointer walk" with "ascending physical index". (Same
class of metric error as the content-read finding's first cut — corrected
there too.)

The correct metric is **read-row[t] == write-row[t]** (does the read
recover the t-th written row, following the temporal link). Added that
metric + a model checkpoint to `dnc_copy.py`; **re-running to measure it
rigorously** before claiming confirmation.

## Status: strong evidence, rigorous confirmation pending

acc=1.0 + one-hot writes/reads + 100% all-distinct is strong evidence the
ordered isomorphism holds (the trained copy DNC reads off as
`write: loop t: p=alloc(); ramWrite(p,x_t)` / `read: p=first; loop t:
emit(ramRead(p)); p=next(p)`), but the direct `read==write order` metric
has not yet been measured. **This finding will be updated** with that
number from the corrected re-run. Not claiming "confirmed" until measured.

## Caveats

- Host-PyTorch prototype, not substrate-pure; single seed so far; one
  task (copy) at T=6, N=16.
- The β/sharpness is the controller's learned read/write strengths (not an
  explicit anneal); reads at peak 0.938 are near- but not perfectly
  one-hot — the ~6% residual is the open-Q-7 fidelity tail.

## Repro / cross-refs

- `python experiments/dnc/dnc_copy.py --seq 6 --steps 20000`
- `differentiable-neural-computer.md` § "The correct full version".
- `2026-06-02-dnc-content-read-code-isomorphism.md` — the content-read rung.
