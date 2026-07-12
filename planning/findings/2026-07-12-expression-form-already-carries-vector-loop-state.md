# The loop EXPRESSION form already carries vector/String loop state (2026-07-12)

Follow-up to `2026-07-08-string-loop-state-crushed-by-scalar-slot-plane.md`. That finding
showed the **by-reference statement form** (`slot String acc; loop build(N, acc);`) crushes
String/vector loop state to a scalar and dies at runtime. This finding measures the **new
loop expression form** (shipped Stage 1, 2026-07-12) on the same workload and finds it
**already works** — no slot-plane change needed.

## Why the expression form is immune

The crush lives entirely in the CALLER's slot plane, at two points:
- `slot_store(_slot_state, i, value)` → projects any value to its 0-d real-axis reading
  (`_slot_cell`/`_re`) — a String's 868-d vector becomes one scalar.
- `slot_load(_slot_state, i)` → reads that scalar back (`state[i]`, 0-d).

The **expression form never touches the slot plane.** `loop NAME(cond, state_expr)` lowers to
`_loop_NAME(<state_expr>)[0]` — the state argument is passed straight into the driver as a
plain Python local (`x = _init_x`), threaded tick-to-tick by the step function, and returned
whole. A full d-dim vector survives because nothing ever projects it to a scalar.

## Measured (runtime_dim default, PyTorch backend)

```sutra
iterative_loop build(3, String acc) { pass string_concat(acc, make_string("x")); }
function string main() { return loop build(3, make_string("")); }
```
- **Expression form** `return loop build(3, make_string(""))` → decodes to `"xxx"`. CORRECT.
- **Statement form** `slot String acc = ...; loop build(3, acc); return acc;` →
  `RuntimeError: index_select(): Index to scalar can have only 1 value, got 97 value(s)`
  (exactly the 2026-07-08 crush).

Second workload — the finding's FizzBuzz-shape String accumulator (5 iterations, `fizzbuzz`
stubbed to return `"n"`), expression form → decodes to `"n n n n n "`. CORRECT
(ground-truth compared via `string_to_python`, not "it ran").

## Consequence for the "vector-valued loop state" design question

The open design question (should loop-state slots be sized `d` instead of 1?) was premised on
the by-reference form being the only surface. It is not. **Single-state vector/String loop
state is already available today via the expression form.** So the remaining decision narrows:

- **Path A — expression form is the vector path.** Keep the by-reference slot form scalar-only
  (add a diagnostic steering String/vector state to the expression form), and extend the
  expression form to the multi-state tuple-return surface `(a, b) = loop f(...)`. No slot-plane
  redesign. Smallest, leverages Stage 1, and the value-returning form becomes the modern path
  (vectors + multi-state) while the by-reference form stays the scalar back-compat surface.
- **Path B — vector-sized slots.** Redesign the slot plane so `slot String acc; loop
  build(N, acc);` also works by reference. Bigger substrate change; preserves by-reference
  symmetry for vector state.

Emma's first pick (before this measurement) was vector-sized slots (Path B). Shown this finding,
she chose **Both, expression-first (2026-07-12)**: ship the expression-form path now — steer the
by-reference statement form to it + extend the expression form to multi-state tuple-return — then
build vector-sized slots for the by-reference form afterward. Staged plan lives at the top of the
ACTIVE queue. Rung 1 (this finding + SUT0206 steer + String-state test + docs) shipped same day.
