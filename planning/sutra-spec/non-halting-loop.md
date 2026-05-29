# Non-halting loop — `recur` + `return` primitive

**Status:** SHIPPED (all 5 sub-decisions locked Emma 2026-05-28; implemented in commits `6757863d` + `6fc64c15` — see non-halting-loop-recur-primitive (pruned 2026-05-28; in git history), whose banner confirms "v1 shipped"). `recur` / `recurring` codegen lives in `codegen_base.py` (`is_non_halting`); parsing in `parser.py` / `ast_nodes.py`. Live consumers: `tests/corpus/valid/non_halting_count.su`, `demos/gui/count.su`, `demos/gui/toggle.su`, and `demos/font/font.su` (whose `cycle_step` now uses it as a substrate-RNN). Supersedes non-halting-loop-recur-primitive (pruned 2026-05-28; in git history) (which preserves Emma's verbatim design intent).

## What this is

A second loop type in Sutra. The existing `loop` keyword is **halting** — bounded recurrence with a soft-halt signal, terminates by mechanism. This new construct is **non-halting** — takes an external input per tick, advances a recurring state on the substrate, emits a per-tick output, never terminates by mechanism.

> **Scope note from Emma's design (2026-05-28):** the halting/non-halting distinction is currently more an *ergonomic Python-host thing* than a deep runtime distinction. The downstream OS built on Sutra (Yantra) will not necessarily have halting as a runtime distinction. The `recur` keyword is what distinguishes them at the language level; the runtime difference is "host calls this function repeatedly to drive ticks" vs "function returns and terminates."

## Surface syntax

```sutra
function vector tick(scalar input) {
    recurring vector state = make_real(0.0);
    // ... computation using `state` and `input` ...
    vector new_state = step(state, input);
    vector pixels = render(new_state);
    recur(new_state);   // feeds back into next tick's `state`
    return(pixels);     // emits to host this tick
}
```

For cycle_step / counter-shaped functions with no explicit input:

```sutra
function vector cycle_step() {
    recurring scalar char_code = 0;   // override zero-default
    scalar next = (char_code + 1) % 36;
    vector pixels = glyph_pixel_array(next);
    recur(next);
    return(pixels);
}
```

### `recurring TYPE NAME = INITIAL;`

Declared INSIDE the function body, NOT in the parameter list. Each one names a piece of recurring state with its initial value. Multiple `recurring` declarations per function are allowed (a function can carry several state slots).

- **Default initialization:** if you write `recurring TYPE NAME;` without `= EXPR;`, the state is zero-initialized (per type: scalar → 0.0, vector → make_real(0.0), etc.).
- **Override:** `recurring TYPE NAME = EXPR;` sets the first-tick value.

On the first call, `NAME` holds the initial value. On subsequent calls, `NAME` holds whatever the previous tick's `recur(NEW_VALUE)` set.

### `recur(EXPR);`

Inside a non-halting function body. Sets the value of the recurring state for the next tick. Multiple `recurring` declarations need multiple `recur` calls (or a `recur(slot, EXPR)` shape — pending; v1 supports one recurring slot per function for now).

### `return(EXPR);`

Inside a non-halting function body. Emits the per-tick output to the host. Distinct from the halting-function `return EXPR;` (no parens) because non-halting functions return *every tick*; the parens are the syntactic marker.

> Compatibility note: `return EXPR;` (no parens) inside a non-halting function is a parse error. Inside a halting function, both `return EXPR;` and `return(EXPR);` parse the same way (since the latter is just `return (EXPR);` with grouping parens). The shape distinction only matters in non-halting contexts.

### A function is non-halting iff its body contains `recur(...)`

No new keyword on the function signature. The presence of `recur(...)` anywhere in the body marks the function as non-halting. The parser/validator detects this and switches codegen mode.

## Caller surface (Python host)

```python
mod = compile_su("count.su")
mod.tick(input=0)   # first tick: state at initial value
mod.tick(input=0)   # second tick: state at previous recur(...) value
mod.tick(input=5)   # third tick: state at previous recur(...) value
```

Each `mod.tick(input)` call is one tick. The recurring state is held in a hidden module-scoped slot; subsequent calls find it where the previous `recur(...)` left it. The host receives the per-tick `return(...)` value as the call's return.

**State scope:** one substrate state slot per non-halting function per module instance. Compiling the same .su twice gives two independent state slots. The slot lives for the lifetime of the module object.

## Codegen target (PyTorch)

The compiled module exposes the non-halting function as a method:

```python
class _Module:
    def __init__(self, vsa):
        self._vsa = vsa
        # one slot per `recurring` declaration in the source
        self._tick_state = _torch.zeros(vsa.dim, dtype=vsa.dtype, device=vsa.device)
        # ... or initialized with the override value if provided

    def tick(self, input):
        state = self._tick_state                         # load
        # ... user code, all substrate-pure ...
        new_state = ...
        pixels = ...
        self._tick_state = new_state                     # store via recur(...)
        return pixels                                    # return(...)
```

The state is a substrate vector held in the module instance. Per CLAUDE.md "Subtler substrate breaches" #2, this satisfies "state survives across calls without host `real()` extraction" — the state is a tensor in `self._tick_state`, never reduced to a host scalar between ticks.

## FV-paper implications

Non-halting functions do not have a termination obligation (they are non-halting by design). They DO have:

- **Substrate-purity of `recur` update:** the value passed to `recur(...)` is a substrate vector, and the path from the prior state to it is all tensor ops.
- **Substrate-purity of `return` output:** same condition for the emitted output.
- **State-locus invariant:** the state never round-trips through a host scalar between ticks. The codegen enforces this by storing the state as a tensor field.

These slot into the FV paper's §3 obligation framework as a new family parallel to §3.3 (termination — which non-halting functions are exempt from by construction).

## What's NOT in v1 (scoped for later)

- Multiple `recurring` slots per function with named `recur(slot, EXPR)` — v1 supports one slot per function. (If a function has two `recurring` declarations and one `recur(...)`, the validator picks the right slot by type-matching; if ambiguous, parse error.)
- Cross-program axon wiring of recurring outputs (this is the "axon-only alternative" from the dossier — left for the Yantra-OS-shaped future).
- `recur` as an expression (instead of statement) — v1 is statement-only.
- **`recurring TYPE NAME = INITIAL;` with non-vector types auto-lifted to substrate vectors.** v1 requires `recurring vector NAME = make_real(N)` for scalar-shaped state; Emma's example `recurring int x = 50` is not yet supported. Codegen would need to wrap the initializer in `_VSA.make_real(...)` when the declared type is `int` / `scalar` / `number`.
- **Sutra source-level `real()` / `imag()` / `truth()` accessor functions.** Currently `_VSA.real(v)` is a host accessor (returns a Python float; in the Audit.md LEGITIMATE list) but is not callable from .su source. This blocks rewrites that legitimately need one in-function extraction — see `planning/findings/2026-05-28-cycle-step-rewrite-blocked.md`. Without these, any function whose body's arithmetic was previously written for a `scalar` argument cannot trivially be lifted to a `recurring vector` slot, because there is no Sutra-level way to bridge the vector slot to scalar arithmetic. Two unblock paths: (A) expose `real()` etc. at the source level (small surface change), or (B) rework the body to do matrix-style tensor-only scoring (larger but fully substrate-pure).

## Cross-refs

- non-halting-loop-recur-primitive (pruned 2026-05-28; in git history) — Emma's verbatim design intent (preserved per chats-triage rule).
- `CLAUDE.md` §"Subtler substrate breaches" #2 — the state-locus rule this primitive satisfies.
- `paper/formal-verification/paper.md` §3.3 — the existing (halting) loop's termination obligation.
- `planning/sutra-spec/control-flow.md` — the halting `loop` primitive.
- `demos/gui/count.su`, `demos/gui/toggle.su` — the first targets of the rewrite.

## Implementation (shipped — commits `6757863d` + `6fc64c15`)

1. **Parser** — [DONE] accepts `recurring TYPE NAME (= EXPR)?;` declarations in function bodies; accepts `recur(EXPR);` and `return(EXPR);` statements (`parser.py`, `ast_nodes.py`).
2. **Validator** — [DONE] detects non-halting functions (presence of `recur`); requires return-with-parens for them; verifies single `recurring` slot in v1.
3. **Codegen** — [DONE] emits a non-halting-state holder + a `tick(input)` method; stores the recurring state as a substrate tensor field (`codegen_base.py`, gated on `is_non_halting`).
4. **Test** — [DONE] `tests/corpus/valid/non_halting_count.su` exercises the new shape; state survives across calls without host extraction.
5. **Rewrite** — [DONE] `demos/gui/count.su`, `demos/gui/toggle.su`, and `demos/font/font.su` use the new shape. Notably `font.su`'s `cycle_step` now carries a 36-dim one-hot glyph cursor in a `recurring vector`, advancing it on the substrate each tick — a real substrate-RNN, not a host-state shuttle.
