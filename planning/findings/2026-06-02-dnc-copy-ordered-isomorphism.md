# DNC↔code isomorphism — the ordered case (copy): CONFIRMED (2026-06-02)

**Headline:** a DNC trained on copy defuzzes to a clean sequential
pointer-walk program — measured. Copy acc 1.000; reads one-hot (peak
0.937), 100% all-distinct rows; and an exhaustive shift-search shows the
read row sequence **equals the write row sequence at shift s=+1, 100%**
(s=0 and s=−1 both 0%) — i.e. the read recovers the written order exactly
via the temporal links, pipelined one step ahead of the emit. It reads
off as `write: loop t: p=alloc(); ramWrite(p,x_t)` /
`read: p=first; loop t: emit(ramRead(p)); p=next(p)`. This is the hard
(ordered) case of the DNC↔code isomorphism, confirmed on the substrate-op
family (host prototype).

---


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

## Two metric corrections (don't mislabel — but don't rationalize either)

The read rows are an **allocation permutation** (e.g. `[11,1,13,14,9,5]`),
not ascending `0..T-1` — because a DNC writes via allocation (rows by
usage) and reads via temporal links in *written order*. Two successive
pass/fail criteria were wrong before I measured the right thing:

1. *Ascending-row check* (first cut): reported "not sequential" (advance
   42.8%) — wrong, conflated "pointer walk" with "ascending index".
2. *`read==write[t]` (s=0)*: reported 0% — also wrong, because the read is
   **pipelined one step ahead** of the emit.

Rather than assert "it's fine" a third time, I ran an **exhaustive
shift-search** `read[t]==write[t+s]` for s∈{−1,0,+1} (the checkpoint makes
re-analysis seconds). Result: **s=−1 → 0%, s=0 → 0%, s=+1 → 100%.** The
read follows the written order *exactly* at shift +1 — measured, not
assumed (if no shift matched, the script reports failure). The +1 is a
real read-ahead pipeline: the controller emits item t from the previously
fetched read (correctly aligned, delivered via its `st["r"]` input) while
the read head I capture is already fetching item t+1's row.

## Status: CONFIRMED (measured)

| metric | value |
|---|---|
| copy bit-accuracy | 1.000 |
| write weighting peak (one-hot) | 0.997 |
| read weighting peak (one-hot) | 0.937 |
| read==write order, best shift | **100% at s=+1** (s=0/−1: 0%) |
| read rows all-distinct | 100% |

The trained differentiable copy DNC defuzzes to a clean sequential
pointer-walk over the written rows — the ordered DNC↔code isomorphism.

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
