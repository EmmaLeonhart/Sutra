# Pre-evaluation depth cap: measured default (Phase 5.5 tier 3, step 3b)

**Date:** 2026-06-17
**What:** picking the default `max_preeval_depth` for the opt-in compile-time pre-evaluation pass
(`sutra_compiler/preeval.py`, `--preeval`). Result: **default 128**, exposed as a CLI arg
(`--max-preeval-depth`) and an `atman.toml` field (`[project.compile] max_preeval_depth`).

## Measurement (compile-time fold cost vs recursion depth, memoized)

Folding a constant-arg call to a bounded pure recursive function, on the AST, with compile-time
memoization (so distinct subproblems are evaluated once):

| call       | cap | fold time | folded? |
|------------|-----|-----------|---------|
| `fib(20)`  | 128 | 0.24 ms   | yes     |
| `fib(30)`  | 128 | 0.15 ms   | yes     |
| `fib(60)`  | 128 | 0.26 ms   | yes     |
| `fac(50)`  | 128 | 0.22 ms   | yes     |
| `fac(120)` | 128 | 0.53 ms   | yes     |
| `fac(500)` | 128 | 3.35 ms   | **no** (500 > cap → cleanly declines) |

Memoization makes the cost ~linear in the number of distinct `(fn, args)` subproblems, so even
`fib(60)` folds sub-millisecond (it would be exponential without memo). Over-cap recursion
(`fac(500)` under cap 128) cleanly declines and is left for the runtime path — it does not fold and
does not error.

## Why 128 (the binding constraint is the host stack, not fold time)

The fold-time cost is negligible at any reasonable cap, so the cap is NOT chosen for speed. It is
chosen to keep the **host evaluator's own recursion within CPython's stack limit**: the evaluator
recurses on the host stack ~`depth` levels deep (several Python frames per logical level), and
CPython's default `recursionlimit` is ~1000. A cap of 128 → ~640 host frames, comfortably within
1000 with headroom. A cap set far above the host limit (e.g. 4096) overflows the host stack on deep
recursion; the pass catches that `RecursionError` and treats the site as not-foldable (clean
fallthrough), but the right default avoids relying on that recovery. **128 folds essentially all
practical bounded recursion while never risking a host-stack overflow.** Programs that genuinely
need deeper compile-time recursion can raise `max_preeval_depth` (and, if needed, the host
`recursionlimit`); deeper-than-cap sites simply fall through to tier 4/5 at runtime.

## Status

- `DEFAULT_MAX_PREEVAL_DEPTH = 128` in `preeval.py`.
- `--preeval` (opt-in) + `--max-preeval-depth N` CLI args; `[project.compile] max_preeval_depth` in
  `atman.toml` (read by `_read_atman_max_preeval_depth`, mirroring `loop_max_iterations`).
- Resolution order: CLI arg → atman.toml → `DEFAULT_MAX_PREEVAL_DEPTH`.
- Tests: `test_preeval.py` (11) incl. CLI-wiring (`--preeval` folds + compiles; `--run --preeval`
  prints 21; the atman.toml field is read).
- The *automatic-default policy* (when to pre-evaluate without `--preeval`, i.e. "when NOT to
  pre-evaluate") remains the open tier-3c Emma decision — this finding only sets the depth cap for
  the opt-in path.
