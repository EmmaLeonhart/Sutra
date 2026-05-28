# 2026-05-28 — Daily substrate-honesty audit (clean modulo two already-tracked PARTIAL items)

Prepended-task fulfillment per `.github/workflows/daily-audit.yml`. Audits every commit landed since the previous daily audit (`e783e4e0`, 2026-05-26) against CLAUDE.md §"Subtler substrate breaches — measurement-required": dimension audit, state-locus audit, signal-separation audit.

## .su files added since previous audit

| commit | file | dim audit | state-locus | signal-sep |
|---|---|---|---|---|
| `e12e1ebd` | `demos/font/font.su` | PASS (dim=8, 0 basis_vector) | **PARTIAL** (inline comment in .su still says "Emma's recurrent step" — already tracked) | N/A (not a classifier — indexed lookup) |
| `e12e1ebd` | `demos/font/font_bound.su` | PASS (dim=384, 63 binds — within VSA tolerance) | N/A (encoding, not recurrent) | PASS (`test_font_bound.py:124` ships measured gap test) |
| `e12e1ebd` | `demos/font/font_bound_smoke.su` | PASS | N/A | N/A (smoke test) |
| `ff5183ef` | `demos/gui/count.su` | PASS (dim=8, 0 basis_vector) | **PARTIAL** (counter_demo.py:3 + test_gui_counter.py:3 still call it "Emma's recurrent-loop demo" — already tracked) | N/A |
| `ff5183ef` | `demos/gui/frame.su` | PASS | N/A (radial-glow stateless) | N/A |
| `ff5183ef` | `demos/gui/toggle.su` | PASS | PARTIAL (same as count.su) | N/A |
| `40ec9624` | `demos/font/font_bound_antipodal.su` | PASS (dim=256, antipodal-filler) | N/A (encoding) | PASS (commit msg ships the dim×encoding gap table; antipodal first non-overlapping at dim=256) |
| `9b156c26` → `11209429` | `examples/gui_window.su` | REMOVED (Emma's invented-toy rule — `feedback-never-invent-thing-emma-implies-exists`) | n/a | n/a |
| `22d785db` | `examples/parse_int2.su` | PASS (substrate-pure parser) | N/A | N/A — covered in `planning/findings/2026-05-27-arbitrary-precision-parser.md` |

## Findings

**No new breach surfaced.** The two PARTIAL items above were both surfaced in their dedicated audits (`planning/findings/2026-05-28-demos-font-substrate-audit.md`, `planning/findings/2026-05-28-demos-gui-substrate-audit.md`) and are tracked in `queue.md` State Inventory B item 5 (demos/gui substrate-RNN rewrite needs Emma's design intent) and the demos/font audit's recommended tightening for `font.su` inline comment.

The daily audit's "fix items BEFORE other queue work" gate is not tripped — the items are already in the queue and need Emma input, not autonomous work.

## Cross-refs

- `planning/findings/2026-05-28-demos-font-substrate-audit.md` (companion: font phase-1 audit)
- `planning/findings/2026-05-28-demos-gui-substrate-audit.md` (companion: gui phase-2 audit)
- `planning/findings/2026-05-27-arbitrary-precision-parser.md` (parse_int2.su)
- CLAUDE.md §"Subtler substrate breaches — measurement-required" (`f8beb415`)
- `paper/formal-verification/paper.md` §4.4 — the three checks are now named in the FV paper (`3edbe2a7`)
