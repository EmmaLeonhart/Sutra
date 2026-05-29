# 2026-05-28 — Documentation & directory scan (what's running vs stale)

Emma asked for a general scan of the directories and documentation — she had a
hunch the docs (especially `planning/`) were incomplete or stale relative to
what's actually running. This finding records the scan's conclusions and the
fixes applied. Four parallel audits covered `planning/`, `docs/` (website),
root docs (AGENTS.md/README/Audit/todo), cross-checking every status claim
against the actual compiler code.

## Headline: the docs are real and mostly accurate — staleness was concentrated, not pervasive

The hunch was right that staleness exists, but it was **localized**, not a
systemic gap. The structural/conceptual docs (vision, paradigms, ontology,
memory, logical-operations, primitive-classes, the open-questions VERDICT-banner
triage, the substrate-leak Audit.md, the README "what runs today" prose) are
accurate and well-maintained. The staleness clustered in a few predictable
places: **features that shipped recently and were never back-propagated into
older status lines.**

## What was stale, and was fixed this session (23 files, 3 commits)

**planning/** (commit on f787…/cc12…):
- `sutra-spec/non-halting-loop.md` said "Implementation pending" — `recur` is
  fully shipped (count/toggle/font demos use it). → SHIPPED. *This was the
  single most misleading doc — exactly the "don't know what's running" failure.*
- `issues/…k5-rank-k-sweep…` read as an open decision; Emma closed it. → CLOSED.
- `open-questions/cosine…` and `…arbitrary-precision-digit-array` said open;
  both resolved (csin shipped, BigInt shipped). → RESOLVED.
- Two findings got forward-pointers to the work that closed them.
- `exploratory/README.md` contents list had drifted from disk. → regenerated.

**docs/ website**:
- Transcendentals (`exp/log/sin/cos/tan/pow/sqrt`) + `complex_sub`/`complex_div`
  were documented as "disabled/pending" in `numeric-math.md` and `operators.md`
  but are **shipped** — and `tutorials/04` already showed them working, so the
  live site openly contradicted itself. → flipped to live.
- TS `Math.*` flipped to working (verified wired in `sdk/sutra-from-ts`).
- Stripped website-rule violations: a numpy-backend row, `Audit.md`/`experiments/`
  path leaks, a clawRxiv CI-mechanics paragraph, "honest" register, and stale
  `tree/master` links (default branch is `main`). Fixed stale pass-order +
  deleted-`_VSA.defuzzify` descriptions. Site rebuilds clean.

**root docs**:
- `AGENTS.md` file-map hid real surfaces (`demos/`, both `sdk/sutra-from-*`
  transpilers, `web/`, the live `paper/formal-verification/`). → added.
- `README.md`: docs/ described as "two pages" (it's ~20) + CI table missing 4
  workflows incl. the main `compiler-ci.yml`. → fixed.
- `Audit.md`: smoke count 11→10 (leak statuses verified correct, untouched).
- `todo.md`: removed confirmed-shipped items (csin, matrix_literal, implicit-loop
  desugar, select-T, BigInt) + the obsolete "burn down Audit.md leaks" block
  (all leaks now fixed). Conservative — unconfirmed items left with verify notes.

## Remaining gaps / follow-ons (NOT fixed — flagged for decision)

1. **open-questions/ pruning pass is a standing, never-run TODO.** The dir's own
   README rule 3 says RESOLVED docs get deleted once their rationale lives in a
   spec file. 8+ resolved docs have accumulated against that rule
   (`binding-kind-surface-syntax`, the `loop-*` set, `axon-bind-needs-permutation`,
   `equality-cosine-T-placement`, `non-halting-loop-recur-primitive`,
   `cosine-as-its-own-transcendental`, `arbitrary-precision-digit-array`). These
   are deletion candidates — left for Emma to greenlight a bulk prune (deletion
   is less reversible; rationale is already preserved in spec, so it's safe when
   she's ready). Same for the struck-through-but-present DECIDED lines in
   `sutra-spec/open-questions.md` (the doc prescribes its own pruning).
2. **Recently-shipped features have findings but no canonical spec home.**
   `csin`/`ccos`, `matrix_literal`, `select`-temperature trainable, BigInt class
   are shipped + have findings, but aren't folded into `operations.md`/`types.md`.
   The findings exist; the spec lags. Worth a "fold findings into spec" pass.
3. **font.su full compile is >300s** (PRE-EXISTING) — egglog post-pass on the 36
   `bit_<C>` + `glyph_pixel` selects, masked by an on-disk cache. The
   literal-constructor egglog skip shipped for `vector_literal`/`matrix_literal`
   would likely help the `select([…],[make_real…])` glyph case; needs a measured
   pass (queue follow-on).
4. **Dark code:** `planning/exploratory/{object,subject_object}_matrix_probe.py`
   are loose scripts with no writeup and zero references — unclear if they ran.
5. **findings/ (81 docs) is a healthy dated archive by design** — non-reference
   is not a defect there — but a few stale point-in-time audits exist; left as
   dated snapshots.

## The meta-pattern (the real answer to "what's going on")

The docs aren't broken — the failure mode is **back-propagation lag**: a feature
ships, its finding gets written, but the older status line in a spec/website page
that says "pending" never gets flipped. The fix is the discipline already in
CLAUDE.md (FV paper "live artifact" rule, capabilities-exhaustive rule) applied
more widely: when a feature ships, sweep the docs that claimed it was pending in
the same session. This scan did that sweep for the 2026-05 backlog.
