# Sutra — Work Queue

**This file is a queue, not a state snapshot.** It lists what is
being worked on right at this moment. Finished work lives in
`git log` and `planning/findings/`; longer-horizon work lives in
`todo.md`.

See CLAUDE.md §"Workflow Rules" for how queue.md and the task tool
stay in sync.

## Active

In strategic order. Top item is the current focus.

1. **TypeScript → Sutra transpiler implementation.** Substantially
   complete as of 2026-05-08: 12 fixtures land cleanly, all of which
   both string-match the lowering output AND compile through the
   Sutra pipeline to runnable Python. Coverage:
   - Functions (incl. arrow-as-const), interfaces, type aliases,
     classes (fields + methods + static + constructors + `new`),
     discriminated unions, `this.field`, void instance methods.
   - Loops: while / for / do-while hoist into declared `while_loop`
     decls with auto-detected state vars + slot copies + writeback.
   - String concat (`s + t` → `String.string_concat`), primitive
     arrays (`T[]`, `arr[i]`, `arr.length`, `[1, 2, 3]`).
   - JavaScriptObject runtime (`wrap`, `js_add`) for the untyped JS
     fallback path.
   - Sutra-side enabling work also landed today: class fields,
     constructor sugar (`new`), value-returning instance methods,
     non-static class loops, operator overloading via inheritance-
     chain dispatch, synthetic-axis equality (Euclidean+tanh).
   Postponed: `Math.*` shims (gated on Sutra transcendentals),
   async/Promise, module imports — explicitly deferred per user
   2026-05-08.

No active items. The TS transpiler shipped 2026-05-08 with 12
fixtures green end-to-end. Postponed dimensions (Math.* shims,
async/Promise, module imports, multi-program axon passing) are
listed at the top of `todo.md` under "TS transpiler / Sutra
postponed pieces."

The C → Sutra transpiler skeleton at `sdk/sutra-from-c/` is parked
(decision 2026-05-08): user no longer views transpiling Linux as a
useful path to OS-level Sutra work. Skeleton stays in tree; do not
delete. See `todo.md` for the parked entry.

Yantra (the OS) is downstream of the TS transpiler — both the
core transpiler (shipped) and the multi-program axon demo
(postponed) are Yantra prerequisites for any real IPC story.
Yantra is its own repo (`../Yantra/`) with its own queue; Sutra's
queue ends at the transpiler.

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
