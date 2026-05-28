# 2026-05-28 — Daily substrate-honesty audit, pass 2

Second prepended-task fulfillment of the day (`f77a606d` re-prepended the daily audit after `planning/findings/2026-05-28-daily-substrate-honesty-audit.md` already discharged the first pass earlier in the session). Audits every commit since the first pass against CLAUDE.md §"Subtler substrate breaches — measurement-required".

## .su files added or modified since the first pass

| commit | file | dim audit | state-locus | signal-sep |
|---|---|---|---|---|
| `6757863d` | `demos/gui/count.su` | PASS (runtime_dim=8 per `_compile` call; 0 basis_vector — fits) | PASS — recurring vector state lives on substrate slot between calls, verified by `test_step_increments_on_substrate` walking 1..10 with no host extraction between calls | N/A (not a classifier; per-tick state advancer) |
| `6757863d` | `sdk/sutra-compiler/tests/corpus/valid/non_halting_count.su` | PASS (small, no basis_vector) | PASS (same shape as count.su) | N/A |
| `6fc64c15` | `demos/gui/toggle.su` | PASS (runtime_dim=8; 0 basis_vector) | PASS — recurring vector state lives on substrate slot, verified by `test_flip_toggles_state_on_substrate` walking 0→1→0→1→0 across 4 calls | N/A |
| (revert) | `demos/font/font.su` | n/a — reverted to HEAD; cycle_step still host-state-shuttle | UNCHANGED from previous state (host-state-shuttle); task #18 tracks the rewrite blocker | N/A |

## Findings

**No new breach surfaced.** The substrate-RNN rewrites that landed this session (count.su, toggle.su) closed the breach for those demos; the `recur` codegen verifies the state is a `torch.Tensor` held in a module-level slot between calls, with no host-scalar round-trip. The audit's three measurement-required checks (dim / state-locus / signal-separation) are all PASS or N/A for the new code paths.

The `cycle_step` rewrite was attempted and reverted (planning/findings/2026-05-28-cycle-step-rewrite-blocked.md). The host-state-shuttle pattern persists there as a documented v2 follow-on; this audit confirms the revert is clean (41 font_cycle tests pass on the reverted state).

The codegen `eq` / `eq_synthetic` substrate-leak fix (`e2b8ee7a`) was already audited as Audit.md REAL LEAK #9 in the first pass — clean.

The extended substrate-leak-sweep (`c270acc0`, includes runtime-prelude scan) reports **0 leaks** across 67 .su programs + runtime prelude.

## Closure

Daily audit pass 2 is **clean**. The prepended item (`f77a606d`) is discharged.

## Cross-refs

- `planning/findings/2026-05-28-daily-substrate-honesty-audit.md` — pass 1 (earlier in session)
- `planning/findings/2026-05-28-cycle-step-rewrite-blocked.md` — the one revert, with v2 unblock options
- `planning/findings/2026-05-28-defuzz-gain-grad-fixed-eq-substrate-leak.md` — the `eq` substrate leak that motivated the leak-sweep prelude extension
- `Audit.md` #9 — codegen `eq` / `eq_synthetic` host-extraction (CLOSED in `e2b8ee7a`)
- `planning/sutra-spec/non-halting-loop.md` — the spec doc that supersedes the open-question dossier
- CLAUDE.md §"Subtler substrate breaches — measurement-required"
