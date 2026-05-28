# 2026-05-28 — demos/font/ substrate-breach audit (per CLAUDE.md "Subtler substrate breaches")

Applies the three audit rules CLAUDE.md picked up in commit `f8beb415` (2026-05-27 20:40 PST) to the `demos/font/` migration that landed from Yantra in commit `e12e1ebd` (Yantra→Sutra phase 1). The audit is the obligation: Yantra→Sutra migration plan tail item #3 + the new CLAUDE.md rule that "every op runs on the substrate" is necessary, not sufficient.

## Summary

| Check | Verdict | Detail |
|---|---|---|
| #1 Runtime-dim bloat | **PASS** | font.su uses runtime_dim=8 (0 basis_vector calls); font_bound.su at 384 (uses bind); fixes already landed Yantra-side |
| #2 Host-state-shuttle dressed as recurrence | **PARTIAL** | Demo-layer doc-string correctly names "state lives on the host"; font.su itself still labels `step` as "Emma's recurrent step" in source comments — tighten |
| #3 Signal-separation gap | **PASS** (where applicable) | font_bound.py has measured `gap = lit_min - unlit_max` test (line 124); font.su isn't a classifier, so the rule doesn't apply |

No silent fix made — surfacing only.

## Check #1 — runtime-dim bloat (CLAUDE.md substrate breach #1)

`grep -c basis_vector|embed` in `demos/font/*.su`:

| file | basis_vector / embed calls | runtime_dim used | bloat ratio |
|---|---:|---:|---:|
| `font.su` | 0 | 8 (per `font_demo.py:runtime_dim=8`) | 1× (none) |
| `font_bound.su` | 63 | 384 (per `test_font_bound.py` header) | 2× (within tolerance for VSA bundle capacity) |
| `font_bound_smoke.su` | 8 | not measured here | not blocking |

`font_demo.py` explicitly documents the choice: "Uses `runtime_dim=8` (NOT 768). font.su contains no `basis_vector`. The previous runtime_dim=768 was 96x bigger than necessary." So the dim audit was already performed Yantra-side and the fix landed. PASS.

## Check #2 — host-state-shuttle dressed as recurrence (CLAUDE.md substrate breach #2)

**The CLAUDE.md rule:** *"if you call something 'recurrent' / 'RNN' / 'state lives on the substrate,' the state MUST be a vector that survives across calls without host `real()` extraction."*

**What font_demo.py actually does:** the host holds the pixel field as a numpy array `out[y,x]` (numpy float, NOT a substrate vector); on each render it calls `step(prev_pix, x, y, char_code)` per cell, extracts the scalar result via `vsa.real(new_pix)`, writes it back to `out`. State (the pixel field across renders) lives on the host as `out`. The `step` substrate function takes `vector prev_state`, multiplies by `0.0` to discard it, returns a fresh `vector new_pix`. The substrate function is **stateless** (the `prev_state` input is multiplied by zero — it's not used for anything).

**What font.su says about it (line 48):** `function vector step(vector prev_state, scalar x, scalar y, scalar char_code)` — and the immediately following comment block calls this *"Emma's recurrent step."*

**What font_demo.py says about it (lines 7-19):** acknowledges plainly — *"state lives on the host, not on the substrate"* — and lines 23-24 also honest-frame: not "substrate-pure end-to-end" — "those framings would require state to live as a substrate vector across calls."

**Verdict:** PARTIAL. The demo's docstring has the honest framing per Yantra-side correction commits `26a6acb` / `29551b1`. The `font.su` source itself still carries the older "recurrent step" wording in its inline comment, which is the breach-#2-shaped wording the new CLAUDE.md rule flags. Not a runtime-correctness issue; a doc/source-comment issue that propagates the older misframing if someone reads `font.su` in isolation.

**Recommended tightening (NOT done in this audit per HARD RAILS — surfaced for Emma's call):** rewrite the inline comment in `font.su` `step()` from "Emma's recurrent step: discard the previous pixel state (`* 0`)..." to something like "Stateless per-cell substrate dispatch. The `prev_state` input is multiplied by 0 (discarded); `step` returns the new pixel value for cell (x, y) under character `char_code`. The 'recurrence' (across renders) lives in the host's pixel array, not on the substrate." This matches the framing the demo docstring already uses.

## Check #3 — signal-separation gap (CLAUDE.md substrate breach #3)

**The CLAUDE.md rule:** *"A substrate function can return numbers via `make_real(some_op(...))` while the returned numbers fail to distinguish the classes the function is supposed to distinguish. Rule: ship a measured `gap = min(positive_class) - max(negative_class)` table with every substrate-classifier."*

**Where this applies in demos/font/:**
- `font.su`: returns a pixel value for cell (x,y,char_code) via softmax-saturated select over 36 chars × 25 positions. Not a classifier — it's a deterministic indexed lookup decided on the substrate. No "positive class / negative class" structure; signal-separation rule doesn't apply.
- `font_bound.su`: is a classifier — bundle-of-binds encoding asks "is this cell lit or unlit for the typed character?" Lit vs unlit IS the class boundary.

**font_bound test coverage:** `demos/font/test_font_bound.py` (line 124) computes `gap = lit_min - unlit_max` explicitly. Threshold `_THRESHOLD = 0.14` is named (line 37) and the test asserts every (char, x, y) cell crosses on the correct side. There's also a separate test (line 107+) that "reports the actual extremes" so a regression surfaces precise numbers, not a tolerance loosening.

**Verdict:** PASS. The bound-vector classifier ships with the measured gap test the rule requires; the table is in the test output rather than a static doc, which is acceptable (the test is the live source of truth).

## Bonus observation — font_data.py is host

`demos/font/font_data.py` is the source-of-truth glyph table; `tools/generate_font_su.py` codegens `font.su` from it. The font shape itself is host-Python-defined; the substrate's job is to evaluate "pixel (x,y) for char_code C" given the codegenned-in glyph table. This is fine — the font definition is compile-time, not runtime; analogous to a literal in source. Surfacing for completeness.

## What this audit does NOT cover

- `demos/gui/` (the phase-2 migration with count.su, frame.su, toggle.su) — those need their own audit. Same three checks; per the migration plan #3 they should each get a similar findings doc. Queue as task #20.
- Substrate-purity grep for raw operator leaks inside the migrated demos. `experiments/substrate_leak_sweep.py` is the existing tool; running it across `demos/` is the natural extension.
- End-to-end correctness — i.e., does `python demos/font/font_demo.py` actually open a window and render correctly? Not run as part of this audit (no tk session this tick). Tests in `demos/font/test_font*.py` cover the substrate-side correctness; the visual end-to-end is a separate gate.

## Cross-refs

- CLAUDE.md "Subtler substrate breaches — measurement-required" (commit `f8beb415`)
- DEVLOG.md 2026-05-28 "Yantra OS attempt paused" (commit `4c98d31a`)
- queue.md § "Yantra → Sutra migration of GUI / I-O apps" tail item #3
- `demos/font/font.su` lines 48-56 (the `step` function + flagged comment)
- `demos/font/font_demo.py` lines 7-19, 23-24 (honest framing at the demo layer)
- `demos/font/test_font_bound.py` lines 107-124 (the gap-measurement test)
