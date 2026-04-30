# Repo audit — 2026-04-25

**Status:** Per queue.md "Repo audit due soon" queue item. Walked
every top-level directory after the chats / scripts / HTMLs sweep
of 2026-04-25 closed. Replaces the stale `audit.md` / `AUDIT.md`
duplicates that were removed earlier in the day (those were written
when the repo still hosted Claw4S-2026 papers and `scripts/`).

## Summary

- **Git tree is clean.** No tracked bloat; the largest tracked
  blob is a 214 KB sutraDB benchmark history file. Nothing in
  HEAD breaks GitHub's 50 MB recommended file size.
- **Local working-tree bloat is real but gitignored.** ~1.2 GB of
  build/cache material lives on disk, none of it tracked. A
  `./gradlew clean` in `sdk/intellij-sutra/` recovers ~1.1 GB
  immediately.
- **One outright orphan: `many-to-many/`** — empty directory at
  repo root, referenced only by stale chats / deprecated spec /
  one finding doc. Safe to delete.
- **Four root-level files predate current organization** —
  candidates for either moving into `planning/` / `docs/` or
  deleting if redundant.

## Walked top-level directories

### `sdk/` — 1.2 GB on disk, ~3 MB tracked

| Subdir | On-disk | Tracked | Status |
|---|---|---|---|
| `intellij-sutra/build/` | 1.1 GB | — | Gitignored. `./gradlew clean` clears it. |
| `intellij-sutra/src/` | 289 KB | tracked | The actual plugin source. Load-bearing. |
| `sutra-compiler/` | 2.0 MB | tracked | The compiler. Load-bearing. |
| `vscode-sutra/` | 74 KB | tracked | The VSCode extension. Load-bearing. |

**Recommendation:** suggest the user run `./gradlew clean` in
`sdk/intellij-sutra/` to recover ~1.1 GB of local disk. The
build output is rebuildable; nothing is lost.

### `fly-brain/` — 101 MB on disk, ~250 KB tracked

| Subdir | On-disk | Tracked | Status |
|---|---|---|---|
| `flywire_data/` | 100 MB | — | Gitignored per CLAUDE.md. External authoritative copy lives at `C:\Users\Immanuelle\flybrain\`. |
| `__pycache__/` | 252 KB | — | Gitignored. |
| Python `.py` files | ~250 KB | tracked | Per CLAUDE.md "Avoiding fly-brain Python sprawl" the 2026-04-13 cleanup pass got this from 33 files to 15. Current count is consistent with that target — no regression visible from a quick `ls`. |
| `hemibrain_pn_kc.npz` | 84 KB | tracked | Small enough to keep. |

**Recommendation:** none. The flywire_data layout matches the
CLAUDE.md spec (external copy authoritative; in-repo mirror
gitignored). Python file count is in budget.

### `experiments/` — 80 KB, 6 files

```
egglog_matrix_chain_fusion.py
egglog_smoke_test.py
rotation_binding_capacity.py
rotation_hashmap_capacity.py
slot_rotation_reversibility.py
synthetic_subspace_validation.py
```

All produced by recent (2026-04-22 onward) work that landed
findings docs. None are stale.

**Recommendation:** none.

### `examples/` — 480 KB, 30 .su + 5 .py files

The `.su` files include the demos, the wait-keyword demo, the
classes demo, the rotation-hashmap demo. The 5 `_*.py` files are
test harnesses (smoke test, su harness, king-queen attractor
search, etc.) — purpose audited during the chats triage and
documented in the chats triage commit messages.

A handful of `*_viz.html` outputs from `--run-viz` are sitting in
the working tree (gitignored, but cluttering the directory).

**Recommendation:** optionally `rm examples/*_viz.html` to clean
the working tree. Pure local-disk cosmetic cleanup; no impact.

### `planning/` — 1.2 MB

Three sub-trees: `findings/` (dated experimental writeups),
`exploratory/` (parking-lot ideas with READMEs governing
discipline), `open-questions/` (live design gaps). Plus the new
`prior-art-vsa-turing-completeness.md` and the deprecated spec
under `sutra-spec-deprecated/`.

**Recommendation:** none. `planning/sutra-spec-deprecated/` is
explicitly retained as a read-only reference.

### `chats/` — 144 KB

Three files: `README.md` plus two deferred chats from the 2026-04-25
triage round (`vsa-operations-explained.md`,
`vsa-programming-languages.md`). Status in queue.md.

**Recommendation:** none until those two are triaged.

### `docs/` — 249 KB

mkdocs source. The `_site/` build output is gitignored.

**Recommendation:** none.

### `sutraDB/` — 3.6 MB

Subtree of the sibling project. Per CLAUDE.md it lives here
intentionally — shares the Sutra name and is the planned execution
backend for compiled-Sutra HNSW codebook ops.

**Recommendation:** none.

### `_site/` — 3.7 MB

mkdocs build output. Gitignored.

**Recommendation:** none.

### `many-to-many/` — empty directory

Empty at root. Referenced by stale chats / deprecated spec / one
finding (`planning/findings/2026-04-18-many-to-many-cold-
replication.md`). The finding mentions the directory but the
directory itself contains no files.

**Recommendation:** delete the directory. The finding's references
remain valid as historical context.

## Root-level files

| File | Status | Recommendation |
|---|---|---|
| `CHANGELOG.md` | Current. | Keep. |
| `CLAUDE.md` | Current; updated 2026-04-25. | Keep. |
| `DEVLOG.md` | Active. | Keep. |
| `README.md` | Current; framing updated this round. | Keep. |
| `queue.md` | Active queue. | Keep. |
| `todo.md` | Active. | Keep. |
| `mkdocs.yml` | Build config. | Keep. |
| `sutrac.py` | Compiler CLI wrapper. | Keep. |
| `!editor.bat` | Local launcher. CLAUDE.md references it. | Keep, but note it's user-specific. |
| `!runClaude.bat` | Local launcher. | Keep — same as above. |
| `.gitattributes`, `.gitignore` | Standard. | Keep. |
| `fly-brain-program-plan.md` | Referenced by DEVLOG + one 2026-04-18 finding. Predates current organization. | **Audit and either move to `planning/` or merge into DEVLOG.** |
| `sutra-demo-program.su` | Root-level `.su`. Predates the `examples/` directory; demo content overlaps with what's now in `examples/`. | **Move to `examples/` or delete if redundant.** |
| `sutra-syntax-decisions.md` | Referenced by deprecated spec + SDK READMEs. The "rolling document for syntax and surface-language decisions" — but the current spec lives in `planning/sutra-spec/` now. | **Audit: most "decisions" likely landed in `planning/sutra-spec/`. Move stale ones to deprecated or delete.** |
| `sutra-language-comparisons.md` | Comparison content; speculative. Referenced by deprecated spec + SDK READMEs. | **Audit: likely move to `planning/exploratory/` or `docs/`.** |

## Action items

Concrete, ordered by impact:

1. **Delete the empty `many-to-many/` directory** (no risk, removes
   a confusing stub).
2. **Suggest user run `./gradlew clean` in `sdk/intellij-sutra/`** —
   recovers ~1.1 GB of local disk. Optional; doesn't affect repo.
3. **Optionally `rm examples/*_viz.html`** to clean local
   working-tree cosmetics.
4. **Audit the four root-level Markdown files** —
   `fly-brain-program-plan.md`, `sutra-demo-program.su`,
   `sutra-syntax-decisions.md`, `sutra-language-comparisons.md` —
   for whether their content is duplicated in `planning/sutra-spec/`
   or `docs/`. Move or delete accordingly. This is a separate
   queue.md follow-up because it requires careful read-through;
   the audit itself doesn't make the call.

Items 1 and 2 are quick wins. Items 3 and 4 are optional/scoped
follow-ups.

## What this audit deliberately did NOT do

- **Did not run a section-by-section read of the deferred VSA
  chats** (`chats/vsa-operations-explained.md`,
  `chats/vsa-programming-languages.md`). Those are tracked
  separately as deferred chats triage work.
- **Did not audit the spec itself for staleness.** The spec is its
  own active-development surface; staleness audits happen
  per-section during the spec rewrite, not as part of a repo-wide
  audit pass.
- **Did not investigate `sutraDB/` internally.** It's a subtree of
  a sibling project with its own audit cycle.
