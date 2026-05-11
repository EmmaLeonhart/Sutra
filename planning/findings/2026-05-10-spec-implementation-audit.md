# Spec / implementation consistency audit

**Date:** 2026-05-10
**Trigger:** Emma 2026-05-10 — "do a comprehensive look through of all of
the specs and everything to ensure that the stuff we're doing is generally
consistent." Specifically prompted by the host-Python-string bug being
caused by spec drift.
**Method:** Cross-grep of `planning/sutra-spec/`, `planning/open-questions/`,
`sdk/sutra-compiler/sutra_compiler/`, `examples/`, `docs/`, `paper/`, and
`tests/corpus/`. Findings classified as CRITICAL / CLEANUP / DOC-FIX /
INTENTIONAL.

## Loops (Emma's hunch confirmed)

- **F1 — CRITICAL:** `planning/sutra-spec/control-flow.md` §"Loops"
  (lines 46–149) describes C-style `while (cond)`, `for (init; cond; step)`,
  `do { } while (cond)`, and `loop (cond)` as parsed and compiled to
  eigenrotation. All four are now **rejected at codegen** (raise
  `CodegenNotSupported`) in favor of the function-decl form (`do_while`,
  `while_loop`, `iterative_loop`, `foreach_loop` + `pass` for tail-yield +
  `loop NAME(args);` at call sites). The canonical spec describes a
  surface that no longer compiles.
- **F2 — CLEANUP:** three dead loop-translation helpers in `BaseCodegen`:
  `_translate_eigenrotation_loop`, `_translate_while_as_geometric_loop`,
  `_translate_for_as_geometric_loop` plus the `_extract_loop_*` helpers.
  All unreachable now that `_translate_stmt` rejects the old shapes.
- **F3 — DOC-FIX:** `inliner.py`, `simplify.py`, and `validator.py` still
  walk `WhileStmt` / `ForStmt` / `DoWhileStmt` AST nodes. They never fire
  (codegen rejects before runtime) but the dead paths complicate searches.
- **F4 — CRITICAL:** `sdk/sutra-compiler/tests/corpus/valid/do_while.su`
  uses retired C-style `do { } while ()`. `test_corpus.py` only asserts
  parse+validate, so the file passes; `control-flow.md:149` cites it as
  proof. `examples/uncertain/04-control-flow-and-errors.su` and
  `06-executable-file.su` similarly use the retired syntax.
- **F5 — DOC-FIX:** `planning/open-questions/README.md` does not index the
  four loop-redesign docs (`loop-function-declarations.md`,
  `loop-surface-redesign.md`, `loop-tail-call-surface.md`,
  `loop-body-semantics.md`). `loop-tail-call-surface.md` is marked
  "shipped" — per the open-questions index's own rule, it should be moved
  out.

## Strings / char-vs-string

- **F6 — CRITICAL:** `planning/sutra-spec/strings.md` § "Current
  implementation state" (lines 143–163) explicitly says the codegen
  emits string literals as raw Python `str` everywhere. The 2026-05-10
  host-Python-string fix (commit `895e7a78`) made this stale —
  destination-type-driven coercion is now wired at return / var-decl /
  call-arg sites.
- **F7 — CRITICAL:** `planning/sutra-spec/types.md` lines 46–49 say
  `string` is "a Python str at runtime." Direct contradiction with
  `strings.md` substrate-encoded codepoint-array model.
- **F8 — DOC-FIX:** `types.md` doesn't mention `char` or `Character` at
  all. Lexer still keeps `char` as a TYPE_NAME; `make_char` / `is_char`
  exist as backward-compat shims; `examples/tutorial.su` still uses
  `char letter = 'a';`.
- **F9 — CLEANUP:** `stdlib/numbers.su` lines 48–58 document `make_char`
  with the old `AXIS_CHAR_FLAG` int-on-real-axis encoding. Today
  `make_char` is `make_string(chr(codepoint))` — a 1-length String.
- **F10 — INTENTIONAL:** `AXIS_CHAR_FLAG` references in non-compat code
  are load-bearing per `strings.md:96–100` as the documented backward-
  compat alias. The deprecated numpy backend (`codegen.py`) actually
  lacks `AXIS_STRING_FLAG` entirely, defining only `AXIS_CHAR_FLAG` —
  if numpy stays around, it should grow both names.

## Transcendentals

- **F11 — DOC-FIX:** `todo.md` and `queue.md` still describe the disabled
  set as `{sin, cos, tan}`. `_TRANSCENDENTALS_DISABLED = frozenset()`
  (empty) since 2026-05-10. Tests assert empty set + end-to-end Math.sin/
  cos/tan correctness.
- **F12 — CLEANUP:** `test_transcendentals_disabled.py` filename is now
  misleading — the file's own docstring says "delete this file when the
  math-precision test suite lands."

## Retired backends

- **F13 — CRITICAL:** `planning/sutra-spec/control-flow.md:139` and
  `types.md:126` reference deleted `codegen_flybrain.py`. The file does
  not exist (retired 2026-04-26).
- **F14 — CLEANUP:** Fly-brain residue in IntelliJ plugin
  (`SutraFlyBrainToolWindowFactory.kt` + registration in `plugin.xml`)
  and a mention in `examples/todo.md`.
- **F15 — DOC-FIX:** `README.md` presents `codegen.py` (numpy backend) and
  `codegen_pytorch.py` as equal first-class targets. `CLAUDE.md` and
  `docs/compilation.md` say numpy is deprecated.

## JavaScriptObject

- **F16 — DOC-FIX:** `stdlib/javascript_object.su` references nonexistent
  `planning/sutra-spec/javascript-object.md`. File is TBD; two intrinsics
  (`wrap`, `js_add`) shipped.

## Other

- **F17 — INTENTIONAL (open question):** `_translate_bounded_loop` emits
  host-side `for _ in range(N)` for non-literal-N bounded loops. Tracked
  in `open-questions.md`.

## Items checked and consistent

- Axons spec (second cut 2026-05-07) vs implementation: aligned.
- `CLAUDE.md` § "🔒 NeurIPS submission is FROZEN" correctly distinguishes
  frozen `paper/neurips/` from live `paper/paper.md`.
- Paper-code durability rule references current syntax.
- Loop tail-call surface (`return NAME(args)`) shipped and tested.

## Fix plan

Batch 1 (spec doc updates, CRITICAL): F1, F4, F6, F7, F13.
Batch 2 (code cleanups): F2, F9, F12.
Batch 3 (tracker updates): F11, F15, F8.
Batch 4 (smaller doc-fixes): F3, F5, F14, F16. Lower priority; can defer.

INTENTIONAL items (F10, F17) need no action; document only.
