# Vector-sized loop slots — SHIPPED (rung 3, Option B). Pointer only.

**This design question is closed; the build is done.** This doc previously carried the staged
B1..B5 plan for making the by-reference loop-call statement form carry vector state — the full
design reasoning stays in git history
(`git log -- planning/open-questions/vector-sized-loop-slots.md`).

Where the record lives now:

- **The shipped mechanism**: unified d-dim slot store — every slot holds a d-vector; scalars
  ride AXIS_REAL. Emma's calls: "Both, expression-first" (2026-07-12), then Option B
  (unify all slots d-dim).
- **Completion declaration**: `DEVLOG.md` 2026-07-13 — "The vector-valued-loop-state EPIC is
  COMPLETE: expression form (rung 1), multi-state destructure (rung 2), unified d-dim slots
  (rung 3 Option B), SUT0206 retired (B5)."
- **SUT0206 retirement** (the crush-to-scalar warning this doc existed to eliminate):
  `sdk/sutra-compiler/sutra_compiler/validator.py:492`.
- **Blast-radius analysis for Option B**:
  `planning/findings/2026-07-12-option-b-slot-unification-blast-radius.md`.
- **User-facing shape**: `docs/loops.md` (three call forms incl. by-reference vector state).
