# Sutra — Work Queue

**This file is a queue, not a state snapshot.** It is the
**stuff being worked on right at this moment**. Finished work
lives in `git log` and `planning/findings/`; longer-horizon
work lives in `todo.md`.

See CLAUDE.md §"Workflow Rules" for how queue.md and the task
tool stay in sync.

## Active

**Sprint:** systematic pass through `todo.md` from top to
bottom, treating it as a queue. Implement → commit → push →
remove from `todo.md` in the same commit. Repeat.

### Next up

1. **Website audit** (Emma 2026-05-01). Audit `docs/` for
   stale / irrelevant content; the Sutra docs site
   (`sutralang.dev`) needs to reflect the actual current
   state of the language. Delete what doesn't belong.
2. Then start barreling through `todo.md` from top.

The Claw4S clawRxiv submission cycle is closed (2026-05-01,
v51/post-2216 Accept locked in). All paper-submission CI
infrastructure has been removed.

## Pointers

- Longer-horizon agenda: `todo.md`.
- Pinned semantic corrections: `planning/semantic-corrections.md`.
- Deprecated spec (read-only reference): `planning/sutra-spec-deprecated/`.
- New spec dir + meta-failure note: `planning/sutra-spec/README.md`.
- Findings (dated): `planning/findings/`.
- Open design questions: `planning/open-questions/`.
- Hardwired assumptions in the demo path: `examples/todo.md`.
- Devlog (full history): `DEVLOG.md`.
