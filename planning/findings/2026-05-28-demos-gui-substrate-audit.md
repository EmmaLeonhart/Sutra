# 2026-05-28 — demos/gui/ substrate-breach audit (per CLAUDE.md "Subtler substrate breaches")

Applies the three audit rules from CLAUDE.md commit `f8beb415` to the `demos/gui/` migration that landed from Yantra in commit `ff5183ef` (Yantra→Sutra phase 2). Same shape as the demos/font audit (`f02fc798`).

## Summary

| Check | Verdict | Detail |
|---|---|---|
| #1 Runtime-dim bloat | **PASS** | All three .su (count, frame, toggle) have 0 basis_vector calls; all .py drivers run at runtime_dim=8 with the `llm_model="unused-no-basis-vectors"` flag — explicit + correct. |
| #2 Host-state-shuttle dressed as recurrence | **PARTIAL** | `.su` files are honest: count.su + toggle.su headers explicitly say "recurrence is HOST-state-shuttle, not a substrate-state RNN" and name the queued refactor. But `counter_demo.py:3` and `test_gui_counter.py:3` still call it "Emma's recurrent-loop demo." Honest at the source layer; not at the driver/test layer. |
| #3 Signal-separation gap | **N/A** | None of count/frame/toggle is a classifier; they compute values (counter +1, radial glow, toggle 1−s). No positive/negative class boundary to measure. Rule doesn't apply. |

## Check #1 — runtime-dim bloat

`grep -c basis_vector|embed` in `demos/gui/*.su`:

| file | basis_vector / embed calls | runtime_dim used |
|---|---:|---:|
| `count.su` | 0 | 8 (per `counter_demo.py:67`) |
| `frame.su` | 0 | 8 (per `window.py:42`) |
| `toggle.su` | 0 | 8 (per `click_demo.py:50`) |

All three .py drivers use `llm_model="unused-no-basis-vectors", runtime_dim=8` explicitly. Documented + correct. PASS.

## Check #2 — host-state-shuttle dressed as recurrence

**The CLAUDE.md rule:** *"if you call something 'recurrent' / 'RNN' / 'state lives on the substrate,' the state MUST be a vector that survives across calls without host `real()` extraction."*

### count.su (stateful)

**What the .su says (honest):**
```
// count.su — a GUI counter. The +1 IS computed on the substrate, but the
// recurrence is HOST-state-shuttle, not a substrate-state RNN. Plainly:
//   step(n) = n + 1 — substrate computes one increment per call. The host
//                     extracts the scalar via real(), holds it in a Python
//                     variable, feeds it back as the next call's input.
//                     State lives on the host between ticks; the substrate
//                     function is stateless. Calling this a "recurrent
//                     loop" or "state lives on the substrate" was the same
//                     framing error font.su carried until 2026-05-27 —
//                     the audit flagged both. A real substrate-state RNN
//                     would keep n as a vector across ticks without the
//                     host extracting it; that refactor is queued for the
//                     Sutra migration.
```

Plain, accurate, names the queued refactor. PASS at the .su layer.

**What `counter_demo.py:3` says:** *"Emma's recurrent-loop demo. Two substrate computations drive it (count.su): step(n) = n + 1 — the recurrent step. The current count is the state; each ..."* — still calls it "Emma's recurrent-loop demo" and "the recurrent step." The driver doc has not been updated to match the .su's correction.

**What `test_gui_counter.py:3` says:** *"Emma's recurrent-loop demo: each click increments an integer ON THE SUBSTRATE in Emma's recurrent loop; the +1 is the substrate's, not a host n += 1."* — same misframing.

### toggle.su (stateful)

**What the .su says (honest):**
```
// toggle.su — a GUI toggle. The flip IS computed on the substrate,
// but the state-shuttle is host-resident, not a substrate-state RNN.
```

PASS at the .su layer.

### frame.su (stateless)

The header explicitly notes it's a stateless dispatch (no recurrence to misframe). PASS by construction.

**Verdict (PARTIAL):** Same pattern as font/ — the .su files have been corrected to honest framing; the .py drivers and tests still carry the older "recurrent loop" wording. Same recommendation as font/: tighten the driver/test docstrings to match the .su's framing. **NOT silent-fixed per HARD RAILS — surfaced for Emma's call.**

**Per the new memory `feedback-gui-stateful-must-be-substrate-rnn-not-host-shuttle`:** Emma's design intent is that the stateful GUI programs (count, toggle) SHOULD use a `loop` with the hidden state as a substrate vector across iterations — the current host-state-shuttle is a design failure, not just doc drift. The .su files already say this; the queued refactor is real. This audit confirms the gap but does not perform the rewrite (out of scope; needs Emma's design + sign-off).

## Check #3 — signal-separation gap

**The CLAUDE.md rule applies only to substrate classifiers** — functions that return numbers intended to distinguish classes (positive vs negative for the purpose of a decision).

- `count.su`: `step(n) = n + 1` is arithmetic, not classification.
- `frame.su`: `pixel(x, y) = 1 - x² - y²` is a continuous brightness field, not class assignment.
- `toggle.su`: `flip(s) = 1 - s` is a deterministic flip, not classification.

No classifier present; the rule doesn't apply. PASS by N/A.

## Tests in the migration

Three test files shipped:
- `test_gui_click.py` (toggle correctness — flip(0)=1, flip(1)=0, flip(flip(0))=0)
- `test_gui_counter.py` (count correctness over iterated calls)
- `test_gui_render.py` (frame brightness field)

All three call `vsa.real()` to extract scalar outputs for assertion — fine for tests (monitoring accessor). They are NOT load-bearing on the substrate-RNN claim (none of them assert "state stayed on the substrate across calls"; they just verify per-tick correctness).

## What this audit does NOT cover

- The substrate-RNN REWRITE (count.su + toggle.su rewritten to keep hidden state as a vector across loop iterations) — the design + implementation is queued; this audit only confirms the current code is host-state-shuttle, not the refactor target shape.
- The driver/test docstring tightening (counter_demo.py, test_gui_counter.py "recurrent loop" wording correction) — surfaced for Emma's call; not silent-fixed.
- End-to-end visual verification — `python demos/gui/counter_demo.py` / `window.py` / `click_demo.py` not run as part of this audit. Tests cover substrate-side correctness.

## Cross-refs

- CLAUDE.md "Subtler substrate breaches — measurement-required" (commit `f8beb415`)
- `planning/findings/2026-05-28-demos-font-substrate-audit.md` (companion audit, font/)
- queue.md § "Yantra → Sutra migration of GUI / I-O apps" tail item #3
- Memory `feedback-gui-stateful-must-be-substrate-rnn-not-host-shuttle` (Emma's design intent for stateful GUI)
- demos/gui/count.su lines 2-16 (the honest framing block)
- demos/gui/counter_demo.py line 3 + test_gui_counter.py line 3 (the still-misframed driver/test docs)
