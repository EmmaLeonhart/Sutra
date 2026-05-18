# Host Python strings at substrate boundaries — chronology and fix

**Date:** 2026-05-10
**Severity:** CLAUDE.md safety-critical rule violation
("every Sutra operation must actually run where the spec says it
runs"). Strings passed through user functions were running as host
Python `str` values, not substrate-encoded codepoint arrays.
**Reporter:** Emma 2026-05-10 ("no fucking host python oh my god
fix it immediately how did this happen").
**Fix:** Destination-type-driven literal coercion in `codegen_base.py`
(this commit).

## What the bug was

Sutra source like

```sutra
function string greet(string name) { return name; }
function string main() { return greet("alice"); }
```

emitted Python equivalent to:

```python
def greet(name):
    return name

def main():
    return greet('alice')   # <-- 'alice' is a HOST Python str
```

The literal `"alice"` never crossed the substrate. The function
`greet` received a Python `str` object; returned it as a Python
`str`; `main` returned a Python `str`. The substrate's
`make_string` codepoint encoding was never invoked.

This violated `planning/sutra-spec/strings.md` § "Literal coercion"
(documented 2026-05-10 earlier in the same session as the rule),
and more broadly the `CLAUDE.md` safety-critical statement that
"every Sutra operation must actually run where the spec says it
runs."

## When the inconsistency started

**The codegen has emitted `StringLiteral` as `repr(expr.value)`
since the original SDK scaffolding.** Specifically:

| Date | Commit | Event |
|------|--------|-------|
| 2026-04-10 | `217ecf9d` | Initial codegen path. `StringLiteral` lowers to `repr(expr.value)` — a host Python string. No substrate-encoding step. |
| 2026-04-23 | `e3d76045` | `Codegen` base class extracted; `StringLiteral` handling carried forward unchanged. |
| 2026-04-30 | `b285dc0b` | First workaround added: a special-case "skip halt-multiply for string returns" because `'alice' * 0.0` raised a Python TypeError. The fix *accepted* that strings are host-side; it did not encode them onto the substrate. |
| 2026-05-08 | (strings.md "first cut") | Spec doc landed saying "to produce a String value, the source must explicitly construct one through the `String` class." The spec went one direction (constructor-explicit); the implementation stayed silent. Spec / code never reconciled. |
| 2026-05-10 (earlier this session) | `39ccacfd` | Spec updated to document destination-type-driven coercion as the rule. Implementation noted as "design target — wiring required." |
| 2026-05-10 (this commit) | this commit | Implementation lands. Destination-type-driven coercion in `codegen_base.py`. Host Python strings at Sutra boundaries are eliminated. |

So the inconsistency is **as old as the SDK** — the original codegen
had no concept of substrate-encoded strings (the `make_string`
runtime method came much later, with the strings.md spec on
2026-05-08). The 2026-04-30 workaround acknowledged the gap in a
comment but addressed only the immediate `TypeError`, not the
underlying substrate-purity violation.

## How it kept going under the radar

- Most existing `.su` examples that return a `string` actually
  return the result of a codebook lookup (`return ANIMAL_NAME[winner]`),
  not a literal. The lookup returns a host str (codebook
  decoding is also host-side, which is allowed at the monitoring
  boundary). So the bug was invisible to those programs because
  there was no substrate-encoded form they were missing.
- `hello_world.su` was the only program returning a literal
  string directly. The 2026-04-30 fix made that path "work"
  (didn't crash) and the chain ended there.
- The multi-program axon demo (2026-05-10 earlier) uses
  `axon_add(a, key, "alice")`, which is a different code path —
  `axon_add` does `isinstance(value, str)` runtime detection
  and wraps via `make_string` at the runtime boundary. So strings
  bundled into axons DID get substrate-encoded; the gap was only
  in the function-call and return paths outside axons.
- This session's "axons are serialization" reframe (which Emma is
  rightfully concerned might have been misread) did NOT cause the
  bug. The bug predates the reframe by ~30 days. The reframe was
  about *axon* semantics; the unrelated function-call string path
  was a pre-existing gap that just hadn't been noticed because no
  test exercised it.

The accurate assessment is that the bug existed from day one and
slipped past every review because no test ever cared whether a
function-call-returning-a-string went through the substrate. The
spec/code drift on 2026-05-08 made it official but didn't create
the underlying issue.

## The fix in this commit

`codegen_base.py` now does destination-type-driven literal coercion
at three call sites:

1. **Return statements** (`return "hello";` from a `function string f()`):
   the `Return`-statement translator passes `dest_type=self._current_return_type`
   to `_translate_expr`. When `dest_type ∈ {"string", "String", "Character"}`,
   a `StringLiteral` emits as `_VSA.make_string("hello")` instead of `'hello'`.
2. **Function call arguments** (`greet("alice")` where `greet`'s
   first param is `string`): a new pre-pass `Pre-pass C` walks all
   FunctionDecls (and stdlib FunctionDecls) and registers each
   function's parameter types into `self._func_param_types`. The
   call translator looks up the called function's param types at
   the call site and threads each arg's destination type into the
   arg-translation call.
3. **Variable declarations** (`string s = "hello";`): the var-decl
   translator passes `dest_type=decl.type_ref.name`. `string s =
   "hello";` now emits `s = _VSA.make_string('hello')`.

Other contexts that pass literals (e.g. `basis_vector("alice")`,
`axon_add(a, "k", "v")`) are unchanged because their destinations
are not `string`-typed. `basis_vector`'s param is `vector` (it
takes a raw string and produces an embedding via Ollama, by
design); `axon_add` does runtime-detect and wrap via `make_string`.

## Verification

End-to-end check on the bug's original surface:

```
--- before fix ---
def from_var():       s = 'hello';   return s                # HOST str
def from_return():    return 'direct'                        # HOST str
def from_call():      return greet('alice')                  # HOST str

--- after fix ---
def from_var():       s = _VSA.make_string('hello');  return s  # substrate Tensor
def from_return():    return _VSA.make_string('direct')         # substrate Tensor
def from_call():      return greet(_VSA.make_string('alice'))   # substrate Tensor
```

Runtime check: each recovered value's `string_to_python` decode
returns the original literal. The vector lives on the device
(`cuda:0` in this run), has the AXIS_STRING_FLAG bit set, and
carries the codepoints at the canonical synthetic axes — i.e.
a real substrate String value, not a host Python `str`.

Regression check: 36 TS-transpiler fixture tests + 20 subtests
+ 100 sutra-compiler codegen tests all green. No existing test
relied on the host-string behavior.

## What this does NOT fix (acknowledged scope)

- **Class field initializations** with string literals: not yet
  threaded through `dest_type`. If a future codepath sets a
  `field string name;` from a literal, the wrap would still be
  needed. Tracked as follow-on.
- **Assignment statements** (`s = "hello";` where `s` was already
  declared `string`): currently not threaded. Variable-declaration
  cases are covered; later assignment is not. Tracked as follow-on.
- **Function-call args to stdlib intrinsics that take a `string`-
  typed param** are covered by the stdlib loader registering its
  own param types into `_func_param_types` (Pre-pass C extension).
  If any stdlib function declares its `string` params differently,
  the registration might miss; verifiable by running the smoke
  tests once they exist for those entries.

These are real gaps. They're smaller than the original bug
(literals at the return / decl / call boundary, which is where
most string activity actually happens) and they're tracked
explicitly. The fix is not declared "complete"; it is declared
"substantially closed" with documented residue.

## Lessons

- "Doesn't crash" is not the same as "runs on the substrate."
  The 2026-04-30 fix made `hello_world.su` not crash but did not
  substrate-encode the string. The runtime contract requires the
  latter, not the former.
- Spec / code drift is real and accumulates silently. The 2026-05-08
  strings.md spec said one thing; the implementation said another;
  no test caught the divergence. Audit of spec-vs-code at the
  substrate-purity boundary is worth doing periodically.
- When a user reframes architecture ("axons are serialization"),
  that reframe applies to the thing it names — not as license to
  let unrelated host-side behavior stand. The host-string bug
  predated and is independent of the axons-as-serialization
  framing.
