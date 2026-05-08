# Sutra — Work Queue

**This file is a queue, not a state snapshot.** It lists what is
being worked on right at this moment. Finished work lives in
`git log` and `planning/findings/`; longer-horizon work lives in
`todo.md`.

See CLAUDE.md §"Workflow Rules" for how queue.md and the task tool
stay in sync.

## Active

In strategic order. Top item is the current focus.

1. **TypeScript → Sutra transpiler implementation.** Skeleton at
   `sdk/sutra-from-ts/` (commit `6d8de7c`). Recent lowering work in
   flight (commits `f3d19ab` if/else + `JavaScriptObject` +
   `truth_axis` intrinsic; `99fcac7` minimal first-cut transpiler).
   Not blocked — the axon surface decisions the transpiler depends
   on (`add` / `item` / property-style access / no schema / four
   positions / lazy across boundaries) all landed in the 2026-05-07
   axon-spec second cut. Remaining open axon questions (per-entry
   tag mechanics, missing-key behavior, error propagation, dynamic-
   key lowering) are calibration items the transpiler can pick a
   default for and revisit.

2. **Configure PyPI Trusted Publishing for `sutra-dev`.** The
   package, license, and release workflow are in; `pip install -e`
   works locally and the wheel smoke-tests cleanly. The PyPI name
   `sutra-compiler` was rejected as too similar to an existing
   project (2026-05-08); rerolled to `sutra-dev`. The PyPI trusted-
   publisher form was filled in with: project `sutra-dev`, owner
   `EmmaLeonhart`, repo `Sutra`, workflow `publish-sutra-compiler.yml`,
   environment `pypi`. Remaining user-side steps: (a) submit the
   trusted-publisher form on pypi.org, (b) create a GitHub Actions
   environment named `pypi` in repo settings (the workflow now
   declares `environment: pypi`, which means GH will fail the run
   if the env doesn't exist), (c) tag `sutra-dev-v0.2.0` and push.

3. **Demonstrate multi-program axon passing with lazy evaluation.**
   `axons.md` claims that only the keys the receiver references
   actually cross a program boundary. We have never demonstrated
   this end-to-end: every `.su` example is a single program, and
   `program-structure.md` is explicit that there is no module /
   import system. The user (2026-05-08) flagged this as the actual
   open axon question — within a program the loop's recurrent
   state already *is* an implicit axon, but between-program axon
   passing is unbuilt. Concrete shape of the demo: two `.su`
   programs, one publishes a wide axon (10+ keys), the other reads
   a small slice; verify in the compiled artifact that only the
   referenced slice materializes on the wire. Spec-validation
   task, not a transpiler blocker.

The C → Sutra transpiler skeleton at `sdk/sutra-from-c/` is parked
(decision 2026-05-08): user no longer views transpiling Linux as a
useful path to OS-level Sutra work, so the focus is solely on
TypeScript. Skeleton stays in tree; do not delete. See `todo.md`
for the parked entry.

Yantra (the OS) is downstream of (1) — the TypeScript transpiler
must be in working shape before Yantra is implementable. Item (3)
is also Yantra-relevant: Yantra leans on inter-program axon passing
as the IPC currency, so a working multi-program demo is the
prerequisite for any real Yantra IPC story. Yantra is its own repo
(`../Yantra/`) with its own queue; Sutra's queue ends at the
transpiler and the multi-program demo.

## Pointers

- Longer-horizon agenda: `todo.md`.
- Pinned semantic corrections: `planning/semantic-corrections.md`.
- Deprecated spec (read-only reference): `planning/sutra-spec-deprecated/`.
- New spec dir + meta-failure note: `planning/sutra-spec/README.md`.
- Findings (dated): `planning/findings/`.
- Open design questions: `planning/open-questions/`.
- Hardwired assumptions in the demo path: `examples/todo.md`.
- Devlog (full history): `DEVLOG.md`.
- Yantra (the OS Sutra is being built for): `../Yantra/`.
