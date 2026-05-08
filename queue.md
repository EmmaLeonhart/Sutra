# Sutra — Work Queue

**This file is a queue, not a state snapshot.** It lists what is
being worked on right at this moment. Finished work lives in
`git log` and `planning/findings/`; longer-horizon work lives in
`todo.md`.

See CLAUDE.md §"Workflow Rules" for how queue.md and the task tool
stay in sync.

## Active

In strategic order. Top item is the current focus.

1. **Make the website / repo split explicit and agent-friendly.**
   The website (`docs/`, → `sutralang.dev`) is for a less technical
   human audience. The Markdown elsewhere in the repo (`planning/`,
   `queue.md`, `todo.md`, `DEVLOG.md`, root `CLAUDE.md`,
   `paper/supplementary/`) is for AI agents and contributors. The
   2026-05-07 sweep (commit `b98b795`) stripped scratchpad/internal
   paths out of `docs/`; the next step is to **document the split
   itself**: add a §"Audiences" section to `CLAUDE.md` saying the
   repo Markdown is the agent-facing surface and `docs/` is the
   human-facing one, and make the repo Markdown structurally
   pleasant for an agent to navigate (a top-level index of which
   files exist for what purpose).

2. **Publish the Sutra compiler to PyPI.** Today `sutra-compiler`
   only runs from a checkout of the repo. Move it to a state where
   `pip install sutra-compiler` works and the `sutra` / `sutrac`
   entrypoint is on PATH. Includes: package metadata, version
   pinning, Ollama-as-optional-extra, smoke test against a built
   wheel, GitHub Actions release workflow, and a tutorial pass to
   replace `cd sdk/sutra-compiler && python -m sutra_compiler` with
   the `pip`-installed surface.

3. **Expand the axon model.** `Yantra/planning/02-axon-model.md` is
   the current spec but is thinner than what the transpilers need.
   The axon is the essential currency of a Sutra-based OS — closer
   to a hardware-linked monad than to a Haskell monad — and both
   transpilers need it nailed down before they can target sensible
   Sutra. Expand: codebook lifecycle, hardware-link semantics
   (which roles are tied to which physical resources / IO surfaces
   / device handles), error-as-axon convention, and the type-of-
   axon vs value-of-axon distinction. This work happens in the
   Yantra repo; commits here only when the Sutra side needs to
   move with it.

4. **C → Sutra transpiler.** Strategic dependency for Yantra
   (lets existing C code participate in a Sutra-based OS). Hard.
   Blocked on (3). Initial scope: a translation-unit-at-a-time
   pass that lowers a restricted C subset (no preprocessor
   weirdness, no inline asm, structs-as-axons, function-pointers-
   as-axons) into `.su` source that compiles cleanly. Yantra's
   `planning/07-transpilers.md` is the design starting point.

5. **TypeScript → Sutra transpiler.** Same shape as (4) but for
   TS/JS. Treats JavaScript as TypeScript with the type
   annotations stripped, so the transpiler reads `.ts` and `.js`
   uniformly. Strategic dependency for Yantra. Hard. Blocked on
   (3). Initial scope: a single `.ts` file → single `.su` file
   pass that handles the typed core (interfaces, classes,
   functions, narrowing) and rejects the dynamic edges (eval,
   prototype mutation, untyped `any` chains).

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
