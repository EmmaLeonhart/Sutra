# Branchless RNN-style `loop(cond)` — architecture, rationale, open directions

**Date:** 2026-04-30
**Author:** Claude (Sonnet) under Emma's direction
**Implementation commit:** `e612598`
**Spec section:** `planning/sutra-spec/control-flow.md` § "loop(cond)"
**Companion finding:** `planning/findings/2026-04-29-bound-table-capacity-limit.md`
**Related design:** `todo.md` § "Transcendental functions —
design absorbed from voice chat" (the chat that originally
sat in `chats/` was inlined into todo.md 2026-05-02).

This is a captured-design doc, not a spec. The implementation
landed and the spec got the user-facing summary; this writeup is
for the *why*, the alternatives, and the open directions — so a
future session (Claude or human) can revisit the design without
re-deriving the reasoning.

## The design intent in one sentence

**Non-looping Sutra programs are MLPs, looping Sutra programs are
RNNs, both branchless on the substrate.** That symmetry is the
load-bearing principle.

## Why the old `loop(cond)` was wrong

`_VSA.loop()` (codegen.py prior to `e612598`) ran:

```python
for iters in range(1, max_iters + 1):     # host Python for
    state = rotation @ state               # substrate matmul ✓
    if n > 0: state = state / n            # host conditional ✗
    best_name, best_score = None, -1.0     # host argmax setup
    for nm, proto in compiled_prototypes.items():
        s = self.similarity(state, proto)
        if s > best_score:                 # host argmax ✗
            best_score = s; best_name = nm
    if target_name is not None and best_name == target_name and best_score >= threshold:
        return best_name, state, iters     # host conditional exit ✗
```

The matmul ran on the substrate. *Nothing else did.* The whole
architectural point — Sutra programs as forward passes through
tensor ops on CUDA — collapsed at the loop boundary into vanilla
imperative Python. Per CLAUDE.md, spec-vs-impl divergence is the
load-bearing failure mode for the biomedical pipeline; this was a
textbook instance.

## The new architecture: three shells

```
┌──────────────────────────────────────────────────────────────┐
│  Outer shell: output gating ("exception handler")            │
│    gated = state * halted                                  │
│    gated[AXIS_LOOP_DONE] = halted                          │
│    return gated                                              │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  Middle shell: T-step compile-time unroll              │  │
│  │    for _t in range(max_iters):    ← meta-iter, not data│  │
│  │      state, halted = _step(...)                      │  │
│  │                                                         │  │
│  │  ┌──────────────────────────────────────────────────┐  │  │
│  │  │  Inner shell: the RNN cell (_step)               │  │  │
│  │  │    cand     = R · state                          │  │  │
│  │  │    cand    /= ||cand||                           │  │  │
│  │  │    sim      = cos(cand, target)                  │  │  │
│  │  │    halt     = sigmoid(k · (sim − threshold))     │  │  │
│  │  │    halted = min(halted + halt, 1)            │  │  │
│  │  │    state    = (1 − halted)·cand                │  │  │
│  │  │             + halted·state                     │  │  │
│  │  └──────────────────────────────────────────────────┘  │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

### Inner shell: the cell

One timestep of the recurrence. Pure tensor ops: matmul, divide,
sigmoid (one exp), minimum, weighted sum. No data-dependent
control flow — `min(halted + halt, 1)` uses `np.minimum`/
`torch.minimum` which are tensor ops, not branches.

The soft halt (sigmoid of `sim − threshold`, with sharpness `k`)
is the key trick: it produces a continuous "are we there yet?"
indicator in `(0, 1)` instead of a hard boolean. Once `halted`
saturates at 1, the soft mux `(1 − halted)·cand + halted·state`
freezes state at its current value — branchlessly.

### Middle shell: T-step unroll

The Python `for _t in range(max_iters):` is meta-iteration over
a compile-time-fixed count. The substrate sees T inline cell
evaluations regardless of when convergence happens. *No data-
dependent iteration count exists at runtime.*

Default T = 50 (matches the prior `max_iters`). Cost: T cell
evaluations every loop, vs ~10 average in the old early-exit
behavior. At dim=512 this is ~50·(d² + d) ≈ 13M FLOPs per loop
site — negligible on CPU, trivial on GPU. Worth it for the
substrate-purity gain.

### Outer shell: output gating

After T steps, `halted ∈ [0, 1]` is a tensor scalar:
- `halted ≈ 1` → loop converged at some step t* ≤ T → output valid.
- `halted < 1` → loop did not converge within T → output
  "incomplete."

Two layers of gating:
1. **Marker**: `state[AXIS_LOOP_DONE] = halted`. Downstream code
   reads this synthetic axis as a tensor scalar — no host
   conditional needed to detect non-convergence.
2. **Wipe**: `state = state * halted`. The value-bearing axes
   get scaled toward zero on non-convergence, so a downstream
   consumer that ignores the flag still sees a near-zero
   (detectably wrong) result rather than a misleading partial
   state.

This is the first instance of the broader **exception channel**
pattern Emma described — a reserved synthetic axis that flags a
"this output is suspect" condition without breaking the constant
flow of tensor information through the program. Future work:
unify with divide-by-zero (`log(0)`, `1/0`) and NaN propagation.

## The hidden state

Same extended-state vector every Sutra value uses:

```
[ semantic block (semantic_dim) | synthetic block (synthetic_dim) ]
```

Synthetic block layout (post-2026-04-30):

| Index | Constant | Role |
|---|---|---|
| 0 | `AXIS_REAL` | real component of a number |
| 1 | `AXIS_IMAG` | imaginary component |
| 2 | `AXIS_TRUTH` | fuzzy truth value |
| 3 | `AXIS_CHAR_FLAG` | char-vs-int discriminator |
| 4 | `AXIS_LOOP_DONE` | **NEW** — cumulative halt; loop completion flag |
| 5+ | `SLOT_BASE..` | disjoint 2D Givens slots for variable assignments |

`SLOT_BASE` bumped from 4 → 5 to make room for `AXIS_LOOP_DONE`.
Slot capacity at default `synthetic_dim=100` drops from 48 to 47
planes — negligible.

## What was considered and rejected

### Bound-table-via-binding (the original chat's design)

Emma originally sketched a bundled-bound-table architecture for
exp/ln (and by extension would have applied to loop convergence
too): N samples bound at unique angles in a 2D plane, summed into
one substrate vector, queried by inverse rotation. Falsified
empirically — see
`planning/findings/2026-04-29-bound-table-capacity-limit.md`. The
2D bundle has only 2 scalars of capacity, which is hopelessly
inadequate for representing arbitrary functions. Worked exactly
for cos/sin (because rotation IS the trig primitive), failed
hard (~85% rel error) for non-periodic functions.

The trig-via-rotation half of that design IS what cos/sin/
imaginaryExp use today. The bundle half didn't survive. For the
loop primitive specifically, a bound-table approach to convergence
would have hit the same capacity wall — the soft-halt approach
sidesteps it by using a *scalar* convergence signal (cosine to
target) directly rather than trying to encode the whole
prototype-match table as a bundled vector.

### Hard-exit replacement (just push down the original `for/if`)

Could have kept the prototype-match argmax + `>= threshold` exit,
just pushed the branching down into the substrate via masking.
Rejected because it doesn't change the conceptual story — it'd
still be "imperative loop with early exit, dressed in tensor
syntax." The soft-halt formulation is a genuine architectural
shift: the loop *is* an RNN cell, not a substrate-flavored
imperative loop.

### Side-by-side gating (keep both old and new behind a flag)

Tempting for safety, rejected per Plan agent's recommendation.
The old path *is* the bug; keeping it as default preserves the
violation. Tests catch regressions, and CLAUDE.md's "spec-vs-impl
must agree" stance argues against a long dual-path window.
Replace-in-place was the call. Worked.

## What's still open / where this could go

These aren't queued; they're the natural follow-ups if/when the
loop work resumes.

### 1. Per-loop-site `T`, `k`, `threshold` configuration

Currently hardcoded defaults (`T=50, k=20.0, threshold=0.5`).
Surface syntax: `loop[T=20](cond)` for explicit step cap;
`atman.toml` `[loops]` section for project-level defaults. The
`threshold` extraction from the source condition (`similarity(...)
< 0.9` literally drops the `0.9` today — that's a separate
oversight from the RNN refactor, but the new code path is the
right time to wire it up).

### 2. Stabilization-based termination

The existing target-based termination (cosine to a known target)
is one shape. The general shape is "halt source = any sigmoid-able
scalar." Stabilization (`||state_n − state_{n−1}|| < eps`) is
natural for attractor-style iteration where no target is supplied
— track the previous state via a one-step delay buffer, feed the
difference norm into the sigmoid. Surface syntax for selecting
between target / stabilization / custom is open.

### 3. Learned R (instead of Haar-random)

Today `R = make_random_rotation(angle=π/4, n_planes=20)` — a
fixed Haar-uniform rotation seeded by the runtime seed. A
"semantic" loop where R is learned from data (e.g. via
backpropagation through the unrolled cell, since the whole thing
is autograd-friendly on the torch backend) is the natural next
step toward looping programs whose recurrence is *meaningful*
rather than random. Connects to the deferred learned-matrix
binding work in `todo.md`.

### 4. Adaptive Computation Time (ACT)

Graves 2016. Instead of fixed T, learn a halting probability per
step that the network can dial up or down. Compatible with the
current architecture — replace the `sigmoid` halt with a
learned-MLP halt prediction. Useful if some loops should stop
early and others should run longer.

### 5. Higher-dim cell (Transformer-shaped instead of vanilla RNN)

Today the cell is `state ← R · state` (one matrix). A
Transformer-shaped cell `state ← state + Attention(state, target)`
would let the loop attend to *multiple* targets simultaneously —
relevant if Sutra grows multi-target loop conditions. Speculative
but worth flagging.

### 6. Unify with the broader exception channel

`AXIS_LOOP_DONE` is one reserved axis for one kind of exception
(loop didn't converge). The same pattern wants to extend to:
- `log(0)` → `-inf` flag on a `AXIS_DIVZERO` axis
- `1/0` → same
- `NaN` propagation through arithmetic
- User-defined `try/catch` (currently parser-only, codegen-rejected)

The right design probably has *one* shared exception-flags
sub-block in synthetic space, with one axis per exception kind,
and a uniform "if any flag is set, propagate it" pattern at every
operation boundary. Not designed yet. Belongs in
`planning/exploratory/exception-channel.md` when someone gets to
it.

### 7. Cost vs the old early-exit path

The old code averaged ~10 iterations before terminating; the new
code always runs T=50. For loops that converged fast, this is a
5× cost increase per loop site. At current Sutra program sizes
this is invisible (single-digit ms on CPU); for tight inner
loops on GPU at scale it could matter. If it ever does:
- Per-site `T` tuning gets the average back down.
- True ACT (above) makes the run-length learnable.
- The fundamental answer is "if you needed early exit you
  weren't running on the substrate" — and the soft-halt freeze
  IS the substrate version of early exit.

## Verification

Tests in `sdk/sutra-compiler/tests/test_branchless_loop.py` (7
PASS):

- `TestNoHostControlFlow` (3 tests): grep the emitted runtime
  source (with docstrings/comments stripped) for `for iters in
  range`, `best_score`, `>= threshold`, `while ` — all forbidden
  patterns. Both backends checked.
- `TestSoftHaltFreeze`: state at unroll step T equals state at
  step T/2 within 1e-6 when convergence happens early.
- `TestOutputGatingOnNonConvergence`: orthogonal target → halted
  stays low → value axes scale toward zero → AXIS_LOOP_DONE < 0.5.
- `TestConvergenceMarksDoneAxis`: converged loop → AXIS_LOOP_DONE
  near 1.
- `TestPyTorchBackend`: same shape on torch backend, autograd-
  friendly.

Broader 80-test codegen suite still green after the axis bump.

## What to read first if revisiting

- `sdk/sutra-compiler/sutra_compiler/codegen.py` — `_step()` and
  `loop()` methods (search for `_step(self,`).
- `sdk/sutra-compiler/sutra_compiler/codegen_pytorch.py` — torch
  mirror of the same.
- `planning/sutra-spec/control-flow.md` — user-facing spec.
- This file — the why and the alternatives.
- `planning/findings/2026-04-29-bound-table-capacity-limit.md` —
  the empirical falsification of the original bound-table design.
