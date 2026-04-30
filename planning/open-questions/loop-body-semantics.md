# Open question: what should `loop(cond) { body }`'s body actually mean?

**Surfaced:** 2026-04-30
**Status:** Implementation has a quirk that hasn't been resolved at the design level.

## The current behavior

`_translate_eigenrotation_loop` (codegen_base.py) extracts exactly
two things from the body:
1. The state variable name (via `_extract_loop_state_var`)
2. The target vector from the condition (via `_extract_loop_target`)

It then **discards the body** and emits a call to `_VSA.loop()`
that applies a fixed Haar-random rotation R to the state for T
steps. The actual statements inside `{ }` are not executed.

So today:

```
loop (similarity(state, v_dog) < 0.9) { state = state; }
loop (similarity(state, v_dog) < 0.9) { state = embed("kitten"); }
loop (similarity(state, v_dog) < 0.9) {
    state = bind(state, v_dog);
    state = bundle(state, v_cat);
}
```

**all compile to the same code** — they all become `state ←
R · state` repeated T times. The body's actual statements are
decorative.

The 2026-04-30 RNN-style refactor made the *execution* of this
loop substrate-pure (T-step branchless unroll, soft halt, output
gating). It did not change the body-discarded semantics; that
was pre-existing.

## Why this has force

If the loop is meant to be a real RNN cell — a function that
takes the previous state and produces the next state, with the
function defined by the program text — then the body **should**
be the cell. Today it isn't. The recurrence is a Haar random
rotation, fixed per loop site, with no relationship to what the
programmer wrote.

If the loop is meant to be an *attractor search* primitive —
"find a state where similarity(state, target) ≥ threshold" — then
the random rotation makes some sense as a way to wander the
semantic space, and the body's role really is just to name the
state variable. But then the surface syntax is misleading: it
looks like a body that runs each iteration, when actually it's
just a slot for variable names.

Both readings are defensible. Sutra's spec doesn't currently
commit to either.

## Why the alternative has force

The 2026-04-30 RNN architecture writeup
(`planning/findings/2026-04-30-rnn-loop-architecture.md`) frames
the design intent as "non-looping Sutra programs are MLPs;
looping Sutra programs are RNNs, both branchless on the
substrate." For that to be a real claim about RNNs (and not
just "fixed recurrence applied N times"), the body of the loop
should be the cell function — what the user wrote should
determine what each tick computes.

The current "body discarded" behavior contradicts this framing
without anything in the spec saying so explicitly.

## What we'd need to decide

Three coherent options:

### Option A: body-as-cell
Translate the body literally as the cell function. Each tick
runs the user's statements once on the current state. The R
rotation goes away (or becomes one option among many cell
shapes). Programs like:
```
loop (similarity(state, v_dog) < 0.9) {
    state = bind(state, v_step);
}
```
would actually `bind(state, v_step)` on every tick.

Cost: substantial codegen rework — body statements need to
compose into a cell function that's called T times under the
existing soft-halt unroll. The "extract state var name" hack
becomes the natural state-passing.

### Option B: body-as-decoration, made explicit
Acknowledge in the spec and surface syntax that `loop(cond)`'s
body is just a slot for "tell me which variable is the state
and what's the target." Maybe drop the braces entirely:
```
loop similarity(state, v_dog) < 0.9 over state;
```
or use a different keyword (`search`, `wander`) to make clear
this isn't an imperative loop with a body. The current codegen
stays; the surface syntax stops lying.

### Option C: body-as-rotation-source
The body runs once at compile time and produces the R matrix.
e.g. `loop (...) { state = bind(state, v_step); }` would
compile to "R = the matrix that implements bind-with-v_step,
apply T times." This is closer to the current behavior but
makes the body genuinely meaningful — it determines R per
loop site instead of using a fixed Haar random rotation.

Cost: medium — need a static analysis pass that derives the
rotation matrix from the body's statements (which only works
for body shapes that ARE expressible as a single linear
operation; non-linear bodies would error or fall back).

## What the implementation work this week did and didn't do

The 2026-04-30 commit `e612598` ("codegen: rewire loop(cond) as
branchless RNN unroll") made the *execution* of `_VSA.loop()`
substrate-pure. That's a real correctness fix and the
fundamentals (T-step unroll, soft halt, output gating,
AXIS_LOOP_DONE) carry over to whichever option above gets
chosen later — they're orthogonal to the body-semantics
question.

Surfacing this question now so we don't accidentally treat
"branchless loop is shipped" as also resolving the body
question. They're separate.

## What to read

- `planning/findings/2026-04-30-rnn-loop-architecture.md` —
  the implementation writeup. Note that it says "the cell is
  `state ← R · state`" — the *cell* is fixed regardless of body.
- `sdk/sutra-compiler/sutra_compiler/codegen_base.py`
  `_translate_eigenrotation_loop` (lines ~734) and
  `_extract_loop_state_var` / `_extract_loop_target` — the
  body-extraction code that throws everything else away.
- `examples/loop_rotation.su` — the canonical demo. Body is
  `state = state;`. Try changing it; the program produces
  identical output.
