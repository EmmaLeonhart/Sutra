# Sutra — Work Queue

**This file is a queue, not a state snapshot.** It lists what is
being worked on right at this moment. Finished work lives in
`git log` and `planning/findings/`; longer-horizon work lives in
`todo.md`.

See CLAUDE.md §"Workflow Rules" for how queue.md and the task tool
stay in sync.

## Active

In strategic order. Top item is the current focus.

1. **Stabilize the axon spec.** `planning/sutra-spec/axons.md` is in
   as a first cut (commit `2227d06`) but has many open questions —
   the user has explicitly said they have not done much work on the
   axon. Both transpilers (items 4 and 5 in the just-finished queue)
   are blocked on this stabilizing. Outstanding axon questions are
   indexed in `planning/sutra-spec/open-questions.md` under §Axons.
   The most load-bearing for the transpilers: role surface syntax
   (`R_x` vs bare identifier in `.su`), function-pointer / higher-
   order-axon story, axon width specification.

2. **Configure PyPI Trusted Publishing for `sutra-compiler`.** The
   package, license, and release workflow are in (commits `3f74234`
   and `9a1bd59`); `pip install -e` works locally and the wheel
   smoke-tests cleanly. To actually publish: set up Trusted
   Publishing on pypi.org for project `sutra-compiler` pointing at
   `EmmaLeonhart/Sutra` + workflow `publish-sutra-compiler.yml`,
   verify the name `sutra-compiler` is available (rename
   `pyproject.toml` if not), then tag `sutra-compiler-v0.2.0`. This
   is user-side action — the workflow is inert until pypi.org is
   configured.

3. **C → Sutra transpiler implementation.** Skeleton landed at
   `sdk/sutra-from-c/` (commit `6970c52`). `c2su` CLI exits 2 with a
   pointer at `DESIGN.md`. Implementation is blocked on (1).

4. **TypeScript → Sutra transpiler implementation.** Skeleton landed
   at `sdk/sutra-from-ts/` (commit `6d8de7c`). `ts2su` CLI exits 2
   with a pointer at `DESIGN.md`. Implementation is blocked on (1).

Yantra (the OS) is downstream of (3) and (4) — both transpilers
must be in working shape before Yantra is implementable. Yantra is
its own repo (`../Yantra/`) with its own queue; Sutra's queue ends
at the transpilers.

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
