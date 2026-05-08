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

3. **Add the axon to the Sutra spec.** Axons are a Sutra concept,
   not a Yantra concept — Yantra uses axons because Sutra has them.
   The canonical spec belongs in `planning/sutra-spec/axons.md`
   and not in the Yantra repo. The closest analogy is a hardware-
   linked monad: structured embeddings (rotation-bound role/filler
   bundles) that compose without parsing and are differentiable
   end-to-end. Initial doc covers: definition, codebook lifecycle,
   hardware-link semantics (which roles tie to physical resources /
   IO surfaces / device handles), error-as-axon convention,
   type-of-axon vs value-of-axon. The Yantra repo's existing
   `planning/02-axon-model.md` becomes a thin pointer to this spec
   plus Yantra-specific OS-context notes.

4. **C → Sutra transpiler.** Lowers a restricted C subset (no
   preprocessor weirdness, no inline asm, structs-as-axons,
   function-pointers-as-axons) into `.su` source that compiles
   cleanly through the existing Sutra compiler. Translation-unit-
   at-a-time pass to start. Hard. Wants the axon spec from (3)
   pinned down first so structs and function pointers have a
   stable lowering target.

5. **TypeScript → Sutra transpiler.** Same shape as (4) but for
   TS/JS. Reads `.ts` and `.js` uniformly (JavaScript is treated
   as TypeScript with annotations stripped). Initial scope: a
   single-file pass that handles the typed core (interfaces,
   classes, functions, narrowing) and rejects the dynamic edges
   (eval, prototype mutation, untyped `any` chains). Wants the
   axon spec from (3) pinned down first.

Yantra (the OS) is downstream of (4) and (5) — both transpilers
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
