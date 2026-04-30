# 2026-04-30 — Boundary leak enumeration for substrate-purity claim

**What this is.** A complete enumeration of the places where the
emitted Sutra runtime crosses the substrate↔Python boundary, paired
with what it would take to remove each. Companion to
`2026-04-30-runtime-substrate-purity-audit.md` (which audited the
runtime methods themselves) and queue.md items 4 + 5. Written so the
paper can scope its substrate-purity claim accurately rather than
overclaiming.

## Headline

The runtime is **substrate-pure on every Sutra operation, with five
specific scalar-arithmetic boundary leaks at the edges of operations
that cross into Python control-flow primitives**. The leaks are
small in count, documented here, and have a known fix path. None of
them lie about what the substrate computed; they just touch a Python
scalar at the seam where a tensor result is consumed by a control
construct (loop halt check, slot read, etc.).

The paper claim should read approximately: *"every Sutra operation
runs as a tensor operation on the substrate; the emitted module
crosses into Python only at five enumerated boundary points (loop
halt check, slot load/store, array indexing, rotation cache lookup,
loop tick counter), each of which can be fused away when
`torch.compile` traces the module end-to-end."*

NOT: *"no Python ever runs in the runtime."* That would be wrong
today.

## The five leaks, by location and severity

### Leak 1 — Loop halt check (`bool`/`float`/Python ternary)

**Location:** `sutra_compiler/codegen_base.py:633-642`,
`:670` (the per-tick body of every emitted loop function).

**What it emits:**
```python
_cond_truth = (float(_cond[_VSA.semantic_dim + _VSA.AXIS_TRUTH])
               if hasattr(_cond, '__len__') else float(_cond))
_keep = 1.0 if _cond_truth > 0 else 0.0
_halt_term = 1.0 - _keep
_halt_cum = min(_halt_cum + _halt_term, 1.0)
```

**Why it's a leak:** `float()` casts a numpy/torch scalar to a
Python float. The `1.0 if x > 0 else 0.0` ternary is a Python
branch on a Python bool. `min(...)` is Python's builtin. All four
of these execute on the host, not the substrate.

**Severity:** medium. Runs T=50 times per loop call, but the work
is genuinely tiny (a single comparison + add per tick). The leak is
*architectural*, not performance-relevant; the substrate-purity
story is the issue.

**Fix path:** Add three new runtime methods to `_VSA`:

```python
# In codegen.py / codegen_pytorch.py
def heaviside(self, x):
    """Step function: returns 1.0 where x > 0, else 0.0. Substrate scalar."""
    return _np.float64(x > 0.0)  # or torch.heaviside(x, ...)

def saturating_add_one(self, accum, term):
    """element-wise min(accum + term, 1.0). Substrate scalar."""
    return _np.minimum(accum + term, 1.0)

def truth_of(self, vec_or_scalar):
    """Read AXIS_TRUTH from a vector, or pass through a scalar.
    Returns a substrate-scalar (numpy/torch 0-dim), not a Python float."""
    if hasattr(vec_or_scalar, '__len__') and len(vec_or_scalar) > 1:
        return vec_or_scalar[self.semantic_dim + self.AXIS_TRUTH]
    return vec_or_scalar
```

Then the emitted body becomes:
```python
_cond_truth = _VSA.truth_of(_cond)
_keep = _VSA.heaviside(_cond_truth)
_halt_cum = _VSA.saturating_add_one(_halt_cum, 1.0 - _keep)
```

Three substrate operations, no Python branches. `_halt_cum` becomes
a substrate scalar (numpy/torch 0-dim) instead of a Python float.

The downstream soft-mux already does substrate arithmetic, so the
fix is local to the per-tick halt block.

### Leak 2 — Slot load/store (returns Python float)

**Location:** `sutra_compiler/codegen.py` and `codegen_pytorch.py`
in the `slot_load` runtime method.

**What it emits:** runtime call returns `float(state[i])` —
specifically, slot reads come back as Python floats.

**Why it's a leak:** Every slot read crosses the boundary. If the
next operation is a tensor op the value re-enters the substrate;
if it's an arithmetic expression in the source, the work happens
in Python.

**Severity:** small. Slot reads are infrequent in real programs
(once per slot var per scope), but each crossing is a leak.

**Fix path:** Have `slot_load` return a 0-dim numpy/torch scalar
instead of a Python float. Downstream arithmetic on that scalar
stays in substrate land.

### Leak 3 — Rotation cache lookup (`if key not in self._rot_cache`)

**Location:** `sutra_compiler/codegen.py:676`,
`codegen_pytorch.py:350`.

**What it emits:**
```python
key = self._role_hash(role_vec)
if key not in self._rot_cache:
    # construct a fresh rotation matrix
    ...
return self._rot_cache[key]
```

**Why it's a leak:** Runtime conditional + dict lookup, both Python.
On cache miss, additionally numpy QR + Givens construction runs on
the host before the substrate sees the result.

**Severity:** medium. Cache hits dominate after the first call per
role. The miss path is what the queue item 3 (pre-warm) eliminates:
scan the program at compile time, emit a pre-warm block at module
init that constructs all role rotations up front. After that,
runtime only ever hits the cached matmul.

**Fix path:** queue.md item 3 — pre-warm at compile time. The
*lookup* itself (the `if key not in cache`) is harder to remove
because Python dict membership has no substrate equivalent; but
once pre-warmed, the lookup is always a hit and can be replaced
with a direct attribute access (`self._rot_<role_name>`) emitted at
compile time.

### Leak 4 — `array_get` returns Python float

**Location:** `sutra_compiler/codegen.py` `_NumpyVSA.array_get`,
mirrored in `codegen_pytorch.py`.

**What it emits:** `return float(arr[index + 1])` (the +1 is for
the length-stored-at-arr[0] convention).

**Why it's a leak:** Same shape as Leak 2 (slot_load). Every array
read crosses to Python.

**Severity:** small. Used only in `foreach_loop` body's `element`
binding (one read per tick).

**Fix path:** Same as Leak 2 — return a 0-dim substrate scalar.

### Leak 5 — Loop tick counter (`for _t in range(50)`)

**Location:** every emitted loop function
(`codegen_base.py:619`).

**What it emits:** `for _t in range(50):` — a Python loop counter.

**Why it's a leak:** Python iteration drives substrate evaluation.
The substrate sees T=50 inline cell evaluations regardless, but the
*scheduling* is Python's responsibility.

**Severity:** smallest. The runtime model is "fixed-T meta-iteration
+ substrate cell," and `for _t in range(T)` is the meta-iteration.
Removing it means full unrolling at compile time — emit T copies of
the cell body inline, no Python loop.

**Fix path:** queue.md item 5 — full unroll. After this, the
emitted module has zero Python loops, just T inline tensor-op
calls. `torch.compile` can trace the whole module as one graph.

Worth noting: this leak is *cosmetic* in the substrate-purity sense
because the substrate sees the same T cell evaluations either way.
But it matters for the "Python wrapper is just IO" headline (queue
item 5) and for `torch.compile` fusion.

## What this means for the paper

Three places where overclaiming would be tempting and wrong:

1. **"No Python in the runtime."** False: the five leaks above run
   in Python. Correct claim: "every Sutra *operation* runs as a
   tensor operation on the substrate; control-flow primitives
   (loop halt, slot read, array index) cross into Python at the
   seams, with a known fix path."

2. **"The compiled module is one big tensor-op graph."** False
   today: the `for _t in range(50)` is Python iteration. Correct:
   "the compiled module emits substrate-pure tensor ops within
   each cell evaluation; the meta-iteration over T fixed steps is
   currently a Python `for` loop, with full unrolling as a known
   future direction (queue item 5)."

3. **"`torch.compile` fuses the whole module into a single
   kernel."** Aspirational, not true today. The Python boundary
   crossings break the trace. Correct: "after the boundary leaks
   are removed (queue items 4 + 5), the module becomes a pure
   tensor-op graph that `torch.compile` can trace; this work is
   known and queued."

## Why the leaks are small enough to defend

The boundary leaks are at the *control-flow seams*, not in the
operations themselves. Every `bind`, `unbind`, `bundle`,
`similarity`, `rotate`, `permute` runs as a tensor op on the
substrate today. Where Python touches the runtime is at the edges:

- Reading a scalar to decide halt
- Reading a scalar to consume a slot value
- Counting ticks
- Looking up a cache entry
- Indexing an array

In each case, the substrate did the work; Python just looked at the
result for a control decision. None of these leaks have the
substrate compute the wrong thing; they just touch a Python scalar
at the seam.

This is qualitatively different from the failure mode the
safety-critical preamble in CLAUDE.md is written against: an
operation that *claims* to run on the substrate but actually runs
on Python. None of the five leaks fit that description.

## What's been fixed already (for completeness)

- **Transcendentals (sin/cos/exp/log/sqrt/tan/pow):** disabled at
  compile time as of 2026-04-30 because the prior implementations
  were Python scalar arithmetic in disguise. Compile-time error
  with a pointer to `stdlib/math.su`'s "NOT IMPLEMENTED" status
  block. See commit `2515fca`.
- **Loop body discard (the prior C-style loop forms):** parser-
  rejected as of 2026-04-30. The function-declaration loop forms
  (`do_while NAME(...)` etc.) replaced them and run the body on
  every tick via the substrate cell. See commit `29733a4`.
- **Program-level halt propagation:** `_program_halt` accumulator
  multiplies through every function's return value, so a loop that
  doesn't converge wipes the program output to ~0. Shipped
  2026-04-30. See commit `06c8498`.

These were *real* substrate-purity bugs. They're fixed. The five
leaks above are smaller — they touch scalars at seams, not whole
operations.

## Fix priority

If picked up later, fix in this order:

1. **Leak 1 (loop halt)** — runs every tick, biggest semantic
   surface area. Three new `_VSA` methods, ~20 lines of codegen
   change.
2. **Leak 2 (slot load) + Leak 4 (array get)** — simultaneous
   one-line returns of substrate scalars instead of Python floats.
3. **Leak 5 (tick counter)** — full unroll. Cosmetic but enables
   `torch.compile` fusion.
4. **Leak 3 (rotation cache)** — covered by queue item 3
   (pre-warm). After pre-warm, the lookup is always a hit and can
   be replaced with a direct attribute access at compile time.
