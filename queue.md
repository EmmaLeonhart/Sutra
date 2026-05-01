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

### Done in this sprint

- **Claw4S close-out.** Auto-submit infra removed; paper artifact
  preserved; CLAUDE.md trimmed; queue/todo cleaned (commits
  `80f8c41`, `6540acf`).
- **Y Combinator references cleared** from todo.md (commit
  `0f4a89a`).
- **Operators page** added (`docs/operators.md`, commit `b2dda77`)
  — root-definition / function-expansion form for every Sutra
  operator. Wired into Theory-and-Paper nav.
- **Website audit** of the docs/ pages for stale content (loops,
  demo count, retired surfaces, broken links). Commits `02c3d1f`,
  `2a6654c`, `333f670`, `e1eed83`, `b69e313`, `473f5b1`,
  `ca421fe`, `ff81d09`, `6a07a75`.

### Next up

Now barreling through `todo.md` from the top. First section is
"[This year] Object encapsulation with file-scope rule for free
functions" — but most of those checkbox items are blocked on
class-system surfaces that don't exist yet, so the substantive
todo work starts a few sections down. Actual approach: scan
top-to-bottom, take the first item where the work is concrete
and shippable today.

## Pointers

- Longer-horizon agenda: `todo.md`.
- Pinned semantic corrections: `planning/semantic-corrections.md`.
- Deprecated spec (read-only reference): `planning/sutra-spec-deprecated/`.
- New spec dir + meta-failure note: `planning/sutra-spec/README.md`.
- Findings (dated): `planning/findings/`.
- Open design questions: `planning/open-questions/`.
- Hardwired assumptions in the demo path: `examples/todo.md`.
- Devlog (full history): `DEVLOG.md`.
