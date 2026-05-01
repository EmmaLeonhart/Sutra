# Sutra — Work Queue

**This file is a queue, not a state snapshot.** It is the
**stuff being worked on right at this moment**. Finished work
lives in `git log` and `planning/findings/`; longer-horizon
work lives in `todo.md`.

See CLAUDE.md §"Workflow Rules" for how queue.md and the task
tool stay in sync.

## Active

**Sprint:** systematic pass through `todo.md`, treating it as a
queue. Implement → commit → push → remove from `todo.md` in the
same commit. Repeat.

### Done in this sprint (2026-05-01)

- **Claw4S close-out.** Auto-submit infra removed; paper artifact
  preserved; CLAUDE.md trimmed; queue/todo cleaned (commits
  `80f8c41`, `6540acf`).
- **Y Combinator references cleared.** `Pre-YC` and
  `Pre-Anthropic-grant-app` priority levels collapsed into `This
  year` (commit `0f4a89a`).
- **Operators page** added (`docs/operators.md`, commit `b2dda77`)
  — root-definition / function-expansion form for every Sutra
  operator. Wired into the Theory-and-Paper nav.
- **Website audit** of the docs/ pages: loops.md rewrite for the
  declared-function loop design, paradigms.md / index.md /
  what-is-sutra.md / demos.md / vision.md / README.md updated for
  retired loop syntax, demo count corrections, broken-link fixes,
  bind-unbind.js header clarified, agent-routing affordance on the
  landing page, noscript fallbacks on the JS widgets. Commits
  `02c3d1f`, `2a6654c`, `333f670`, `e1eed83`, `b69e313`, `473f5b1`,
  `ca421fe`, `ff81d09`, `6a07a75`, `a705e5d`, `dfd4b27`.
- **todo.md tidy-up.** Smoke-test-failures section closed (both
  items resolved); Concurrency description fixed to declared-function
  loop form; Formula-simplification section dropped (no remaining
  pieces); Integer-class section relabeled; Control-flow Dynamic-
  foreach question answered by `foreach_loop`; "after Claw4S"
  deferrals removed. Commits `4b2bebc`, `6eb350a`, `51c6c67`,
  `bab0b91`.

### Next up

Most remaining `todo.md` items need real engineering or design time
that won't fit in an autonomous sprint:

- **Object encapsulation** — gated on the class-system MVP gaining
  bodies / methods / instances. Premature today.
- **Compile-time math approximation** — needs a substrate-pure
  `log`/`exp(E)` design before implementation; lookup-table approach
  failed (see the 2026-04-29 finding).
- **Rotation-hashmap capacity / Monte-Carlo experiments** — need GPU
  time and a real evaluation harness.
- **MCP server for docs** — real infrastructure piece; not a doc
  edit.
- **Concurrency / learned-matrix binding / atman.toml backend config
  / transcendentals** — substantial parser+codegen work each.

Pick whichever of these you want to start on, or keep barreling for
small wins (e.g. the smaller IDE/tooling items further down `todo.md`).

## Pointers

- Longer-horizon agenda: `todo.md`.
- Pinned semantic corrections: `planning/semantic-corrections.md`.
- Deprecated spec (read-only reference): `planning/sutra-spec-deprecated/`.
- New spec dir + meta-failure note: `planning/sutra-spec/README.md`.
- Findings (dated): `planning/findings/`.
- Open design questions: `planning/open-questions/`.
- Hardwired assumptions in the demo path: `examples/todo.md`.
- Devlog (full history): `DEVLOG.md`.
