# Sutra — Work Queue

**This file is a queue, not a state snapshot.** It lists what is
being worked on right at this moment. Finished work lives in
`git log` and `planning/findings/`; longer-horizon work lives in
`todo.md`.

See CLAUDE.md §"Workflow Rules" for how queue.md and the task tool
stay in sync.

---

## Active

### 1. Promises and async/await — partially shipped, two pieces still open

Un-postponed 2026-05-09. Per the user, every TypeScript construct
should be expressible in Sutra (modulo architectural violations);
`async`, `await`, and `Promise<T>` are essential to that goal. They
are **first-class Sutra vocabulary** — not stdlib helpers, not TS
imports — with a **two-stage beta-reduction** at compile time:

```
async function    (sugar over)
   ↓
Promise<T>        (sugar over)
   ↓
while_loop with two-channel halt vector  (substrate primitive)
```

Spec: `planning/sutra-spec/promises.md` (canonical) +
`docs/promises.md` (website with three-box visualisation). Original
voice-conversation that drove the design:
`planning/exploratory/promises-design-conversation.md`.

#### What works today

- **Surface syntax fully reserved.** `async function`, `await expr`,
  and `Promise<T>` parse cleanly and validate without errors. Lexer
  has `KW_ASYNC` / `KW_AWAIT`; `Promise` is a contextual primitive
  type name like `vector` or `dict`.
- **Stage-1 desugar — two simple shapes compile + run end-to-end:**
  - *Pure return*: `async function Promise<T> f() { return e; }` →
    `function Promise<T> f() { return Promise.resolve(e); }`
  - *Thin wrapper*: `async function Promise<T> f() { return await e; }`
    → `function Promise<T> f() { return e; }`
  Implemented in `sdk/sutra-compiler/sutra_compiler/promise_desugar.py`.
  Corpus fixture: `tests/corpus/valid/async_promise_desugar.su`.
- **Stdlib `Promise<T>` class** — declared in
  `sdk/sutra-compiler/sutra_compiler/stdlib/promises.su` with
  `resolve`, `reject`, `isFulfilled`, `isRejected`, `isPending`,
  `value`, `reason` as static intrinsics. Loader sees them.
- **TS transpiler integration** — `async function`,
  `await expr`, and `: Promise<T>` annotations pass through verbatim
  from TypeScript into Sutra. TS fixture
  `sdk/sutra-from-ts/tests/fixtures/async_promise_basic/` lowering
  test green.
- **Codegen rejection on the unsupported shapes** — anything Stage-1
  desugar can't simplify (var-then-return, post-await code,
  try/catch) errors with a helpful pointer at
  `planning/sutra-spec/promises.md`. No silent failures.

Three-box mental model rendered at `docs/promises.md` (live at
`sutralang.dev/promises/` after the next pages-CI run).

#### What's still pending

**Active in this session:** Stage-2 lowering pass — `Promise<T>` →
`while_loop` with two-channel halt vector. The axon-based external-
I/O question (how does the loop body query "did the awaited input
arrive?") was resolved 2026-05-09 by the user: the input slot is
the zero vector until it arrives, then becomes non-zero;
`norm(slot) > eps` is the on-substrate "arrived?" check. Spec at
`planning/sutra-spec/axon-io.md`. Implementation now unblocked.

Concrete substrate work for Phase 6:
- Reserve `synthetic[AXIS_PROMISE_FULFILLED]` and
  `synthetic[AXIS_PROMISE_REJECTED]` in the canonical synthetic-
  axis allocation (currently 0..4: real, imag, truth,
  string-flag, loop-done).
- Implement `_VSA.resolve(v)` / `_VSA.reject(r)` /
  `_VSA.isFulfilled(p)` / `_VSA.isRejected(p)` /
  `_VSA.isPending(p)` / `_VSA.value(p)` / `_VSA.reason(p)` runtime
  methods in both numpy and pytorch backends. These are pure axis
  reads / writes — substrate-pure, no loop yet.
- For programs that just construct + inspect promises (no await),
  the runtime methods alone are sufficient. The `while_loop`
  generation kicks in only when an `await` actually gates on an
  external axon arrival.

**Deferred to `todo.md`:** First-class function values for
`.then(callback)`. The trivial Stage-1 desugar shapes (pure
return, thin wrapper) shipped. Anything richer — `vector v = await
x; return g(v);`, multi-await chains, `try { await ... } catch
{ ... }` — needs functions-as-values to express the post-await
continuation as a `.then(v -> body)` callback. Tracked at the top
of `todo.md` as its own focused work-stream; pick it up when the
first-class-function-value pass lands.

#### Phase tracker

| # | Phase | Status |
|---|---|---|
| 1 | Spec — `promises.md` two-stage layering | ✅ |
| 2 | Lexer + parser + AST + codegen rejection | ✅ |
| 3 | Stage-1 desugar — two simple shapes | ✅ first cut |
| 3+ | Stage-1 — full coverage (needs first-class fns) | 🚧 blocked |
| 4 | TS transpiler pass-through | ✅ |
| 5 | Stdlib `Promise<T>` class declaration | ✅ |
| 6 | Stage-2 lowering — `Promise<T>` → `while_loop` | 🚧 in progress (axon-io spec landed) |
| 7 | Fixtures — try/catch, multi-await, propagation | partial (2 corpus + 1 TS) |

---

### 2. TypeScript → Sutra transpiler implementation

Substantially complete as of 2026-05-08: 12 fixtures land cleanly,
all of which both string-match the lowering output AND compile
through the Sutra pipeline to runnable Python. Coverage:

- Functions (incl. arrow-as-const), interfaces, type aliases,
  classes (fields + methods + static + constructors + `new`),
  discriminated unions, `this.field`, void instance methods.
- Loops: while / for / do-while hoist into declared `while_loop`
  decls with auto-detected state vars + slot copies + writeback.
- String concat (`s + t` → `String.string_concat`), primitive
  arrays (`T[]`, `arr[i]`, `arr.length`, `[1, 2, 3]`).
- JavaScriptObject runtime (`wrap`, `js_add`) for the untyped JS
  fallback path.
- `async function`, `await`, `Promise<T>` pass-through (added
  2026-05-09 with item 1).
- Sutra-side enabling work that landed alongside: class fields,
  constructor sugar (`new`), value-returning instance methods,
  non-static class loops, operator overloading via inheritance-
  chain dispatch, synthetic-axis equality (Euclidean+tanh).

Postponed: `Math.*` shims (gated on Sutra transcendentals) and
module imports.

---

## Parked

The C → Sutra transpiler skeleton at `sdk/sutra-from-c/` is parked
(decision 2026-05-08): user no longer views transpiling Linux as a
useful path to OS-level Sutra work. Skeleton stays in tree; do not
delete. See `todo.md` for the parked entry.

Yantra (the OS) is downstream of the TS transpiler — both the
core transpiler (shipped) and the multi-program axon demo
(postponed) are Yantra prerequisites for any real IPC story.
Yantra is its own repo (`../Yantra/`) with its own queue; Sutra's
queue ends at the transpiler.

---

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
