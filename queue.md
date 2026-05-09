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

2. **Demonstrate multi-program axon passing with lazy evaluation.**
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
must be in working shape before Yantra is implementable. Item (2)
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
