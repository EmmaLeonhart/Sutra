# Neural Unix utilities — the big Unix tools on a completely neural computer

Emma's 2026-07-06 goal: **neural implementations of all the big Unix utilities**, running on a
**completely neural computer** — an NTM-style machine with external addressable RAM and a persistent disk,
not an RNN. Each utility's genuine work (scan, count, gate, translate, compare, match, field-split) runs
on the **Sutra substrate**; the host does only I/O (feeding bytes, moving the cursor, reading results at
the boundary), the same division `planning/sutra-spec/ram-pointers.md` draws for the RAM device.

**Status: COMPLETE — 15 rungs, every one verified against the real coreutils binary (or Python `re`).**
Regression guards: `sdk/sutra-compiler/tests/test_ntm_ram.py` (27 tests). Each `run_*.py` has a self-test
(`python experiments/ntm_ram/run_X.py`) that compares the neural output to the coreutils ground truth, and
most take a real pipe (`… | python run_X.py <args>`).

## The substrate keystones

- **Exact codepoint indicator** `is_cp(c, center) = relu(1 - |c - center|)` — exactly 1 at the center
  codepoint, a hard 0 everywhere else (measured gap 1.0, no saturation residual — the `exp`/`tanh` table
  clamps at e⁻¹⁰, so the relu-of-triangle form is used instead). This one primitive composes into every
  scalar rung: streaming accumulators, gated emits, codebook maps, comparators, substring products.
- **Vector-valued substrate state** for the regex NFA: the active-state SET is an N-dim buffer stepped by
  transition + epsilon-closure **matmuls** on the substrate (`s' = ge1(E · (T_c · s))`).

## The 15 rungs

Tier A — pure stream transforms (RAM buffer):
- `run_echo.py` — echo (passthrough scan/emit, the base case)
- `run_cat.py` — cat (streamed stdin axon; `--stdin`)
- `run_wc.py` — wc (first real transform: substrate streaming accumulators for lines/words/bytes)
- `run_head_tail.py` — head / tail -n (line-gated emit; substrate line count for tail)
- `run_tr.py` — tr (per-byte codebook map: weighted sum of exact indicators; translate + `-d` delete)
- `run_rev.py` — rev / tac (reverse permutation: `pointer = limit - cursor`)
- `run_cut.py` — cut -c (per-column gated emit; counter resets at newline)

Tier B — ordering / comparison:
- `run_uniq.py` — uniq (adjacent-dup removal via a substrate prev-vs-current mismatch accumulator)
- `run_sort.py` — sort (full-buffer comparison network; neural lexicographic comparator)

Tier C — pattern matching (on-substrate regex NFA, `neural_regex.py`; spec
`planning/sutra-spec/neural-regex-nfa.md`):
- `run_grep.py` — grep -F (fixed-string substring match: product of exact indicators)
- `neural_regex.py` — the NFA matcher itself (literals, `.`, classes, `* + ?`, `|`, `( )`, `^ $`; 29/29
  vs Python `re`)
- `run_grep_regex.py` — grep -E (regex, per line)
- `run_sed.py` — sed s/re/repl/[g] (regex substitute + match-span extraction)
- `run_awk.py` — awk common subset (`$N`/`NF`/`NR`/`$0`/`$NF`, `/re/` patterns, `-F`; substrate field
  splitting). Full-language awk (variables/arithmetic/BEGIN-END/printf) is out of scope.

Tier D — filesystem (persistent disk device, `disk_device.py`; spec `planning/sutra-spec/disk-device.md`):
- `run_fs.py` — cat FILE / ls / cp / mv / rm / find (`-name` via the NFA). Traversal is I/O; the byte
  processing and the `-name` match are substrate.

## The machine underneath

- `ram_device.py` — external addressable RAM (host memory the program addresses through VRAM pointers).
- `disk_device.py` — persistent named storage (P1): a path→region namespace over a host sandbox dir.
- `orchestrator.py` — drives a non-halting substrate module tick by tick, serving RAM at each emitted
  pointer (the first external `await` producer; the "who writes the slot" answer from `axon-io.md`).
- `text_scan.su` — the recurring-cursor read head that streams a region; the `*_head.su` / `*_heads.su`
  files are the per-utility substrate programs (accumulators, gates, comparators, field splitters).
