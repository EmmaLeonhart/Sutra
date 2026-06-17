# 27 — Substrate-honesty audit, 2026-05-27

Triggered by Emma's pushback during the font-demo session: the demo was
running at `runtime_dim=768` for a 2-d-state task (one input scalar, one
displayed-char scalar). 766 dims of dead weight per substrate op, 96×
the work needed. Emma's broader hypothesis — "every other Yantra
programme that creates a graphical user interface that you wrote is
also fake" — pointed at the rest of the apps having the same bug.

**Survey result: yes, the same bug is everywhere.** Every Yantra `.su`
checked uses `runtime_dim=768` while none of them call `basis_vector`,
meaning every one is paying 96× more per-op tensor work than the task
needs. This is bloat masquerading as substrate work.

## What I measured (read-only audit, not yet fixed)

| App | `runtime_dim` | `basis_vector` calls | Right-sized dim | Notes |
|---|---|---|---|---|
| `apps/font/` | 8 (fixed today) | 0 | **8 measured exact** at 80 tests | DONE, commit `e22c80a` |
| `apps/calc/digits.su` | 8 (fixed today via `AXON_WIDTH=8`) | 0 | **8 measured exact** | DONE, 64 calc tests + 3 parse tests green |
| `apps/calc/parse_int2.su` | 8 | 0 | **8 measured exact** | DONE |
| `apps/calc/parse_op.su` | 8 | 0 | **8 measured exact** | DONE |
| `apps/calc/switch.su` | 8 | 0 | **8 measured exact** (2+3=5, 7*8=56, etc.) | DONE |
| `apps/gui/count.su` | 8 (fixed today) | 0 | **8 measured exact** at step+pixel | DONE, commit `4ac0421` |
| `apps/gui/frame.su` | 8 (fixed today) | 0 | **8 measured exact** at pixel | DONE, commit `4ac0421` |
| `apps/gui/toggle.su` | 8 (fixed today) | 0 | **8 measured exact** at flip | DONE, commit `4ac0421` |
| `apps/echo/echo.su` | 16 (fixed today) | 0 | **16 measured exact** — uses Axon.add/axon_item (rotation-binding), 1 bound key, dim=16 above noise floor | DONE, 5 echo tests green |
| `apps/terminal/` | host-only Python wrapper at `AXON_WIDTH=768`; no compiled .su | n/a | n/a until terminal gets a .su component | UNFIXED |
| `kernel/services.py` | **default removed** — `runtime_dim` now required keyword | manifest-dependent | each caller explicit | DONE — 5 test callers updated to `runtime_dim=16`, 295/295 + 1 xfail green |

(`echo.su` not yet read — included for completeness.)

## What "right-sized" means here

The `runtime_dim` parameter to `compile_su` is the width of every
substrate vector at runtime. Sutra's codegen layout is
`[semantic (semantic_dim) | zeros (synthetic_dim)]`. The semantic block
is where `basis_vector` embeddings land (LLM-derived). When a .su has
no `basis_vector` calls, **the semantic block is unused**, the
synthetic block is unused at module load, and the only thing using
the 768 dims is the math op (e.g. `make_real(66.0)` writes the scalar
to the real-axis dim, all others stay zero).

Concretely: a `make_real(66.0)` at `runtime_dim=768` is a 768-element
float64 tensor with element[0] = 66.0 and elements[1..767] = 0.0. The
substrate ops (multiply, add, dot) then process all 768 elements every
call. At `runtime_dim=8` the same operation is 8 elements. At
`runtime_dim=2` it's 2 elements. Speedup is linear in the dim.

The minimum useful dim per app is determined by how many distinct
real-axis-encoded scalars the .su needs to manipulate at once and
whether any rotation-binding is in play. For the apps surveyed: zero
rotation-binding (no `basis_vector`), at most one or two real-axis
scalars per op, so any dim ≥ 2 should work. `runtime_dim=8` gives
headroom without bloat.

## What I'm NOT claiming yet

I did NOT empirically verify that each app still gives correct output
at the smaller dim. The font app I verified (80 tests pass at dim=8);
the others are queued for verification, not yet measured. So this
audit is a *measured survey* of bloat presence + a *predicted* dim for
each — not a measured-correct fix.

## The separate failure this audit also exposes

The font demo wasn't only dim-bloated — the recurrence pattern was
also host-shaped (state lived on the host between substrate ticks via
`vsa.real()` extraction, not on the substrate). The dim fix did NOT
fix that; it just made each individual substrate op cheaper. **Other
apps almost certainly have the same host-state-shuttle pattern**
(`count.su`'s `step(scalar n) = make_real(n + 1.0)` is structurally
the same — host shuttles the scalar across ticks). Pure dim-fix on
those apps will make them run faster without making them more
substrate-pure. Both fixes need to happen, separately.

## Action items (queued)

Each app gets:
1. A measured-at-small-dim correctness check (compile + run + compare
   to the existing 768-d output).
2. If correct, a commit lowering the dim.
3. A separate check of "is the state shuttle host-shaped, and if so,
   is that the right shape for this task or fake-substrate framing."
4. A README / .su-header update saying plainly what the .su does and
   does NOT do on the substrate.

Tracked in `queue.md` § "Substrate-honesty audit across every Yantra
app". Item-by-item progress goes in this file as a running log.
