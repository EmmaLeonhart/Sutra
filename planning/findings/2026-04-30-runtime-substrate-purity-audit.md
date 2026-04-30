# Runtime substrate-purity audit — what actually runs on CUDA vs host Python

**Date:** 2026-04-30
**Author:** Claude (Sonnet) under Emma's audit demand
**Trigger:** Emma asking "Is there anything else in this program that
basically you lied about that actually goes to Python?" after
discovering that `loop[N]` runtime falls back to Python `for`.

This is the honest audit. No hedging, no spin. Every emitted runtime
method in `codegen.py` (numpy IR) and `codegen_pytorch.py` (the
canonical CUDA target) was scanned for host-Python control flow,
scalar extraction, libm calls, and other escape hatches from the
"forward pass through tensor ops on CUDA" architecture.

## TL;DR (revised 2026-04-30 after Emma clarified eigenrotation was given up)

**Real violations** (host Python at runtime, would have been
substrate violations if implemented as expected):

- **`exp` and `log` (and `sqrt`, `pow`, `tan` derived from them) —
  shipped 2026-04-29 — are implemented as host Python scalar
  arithmetic** with `for n in range(EXP_TAYLOR_TERMS)` loops over
  Python floats. The bound-table-via-binding architecture was
  ruled out by the 2026-04-29 capacity finding; the fallback I
  shipped was Taylor + frexp + Newton on Python scalars. Should
  have been implemented as tensor ops over 0-dim torch tensors so
  the same loops work but each step runs on CUDA. Open question:
  whether to keep Taylor-as-tensor-ops or just call `torch.exp` /
  `torch.log` directly — depends on whether libm-via-torch counts
  the same way libm-via-trig does (eigenrotation was given up,
  so trig-via-libm is accepted; whether log/exp-via-libm follows
  the same logic is an Emma call).
- **Loop body discard** in `loop(cond)` / `while(cond)` / `for(...)`
  — already known, queued in STATUS.md.
- **`loop(N)` runtime-N falls back to Python `for _ in range(N)`** —
  already known, queued.
- **`argmax_cosine` / `snap`** use Python loops over candidates
  with `if score > best`. Should be `torch.argmax(scores)` or
  similar. Likely an easy fix.
- **`make_random_rotation`** is called at runtime on first bind for
  each role; uses numpy random + QR. The CACHE-HIT path is fine
  (just matmul); the cache-miss path is host Python. Not strictly
  a violation if all role-rotations are pre-warmed before the hot
  path, but unverified that this is true in practice.

**Accepted (per Emma's eigenrotation-given-up clarification):**

- `_cos_sin_scalar` using `_math.cos / _torch.cos` directly — trig
  is allowed to use libm/torch primitives. This was the fallback
  position when the eigenrotation-for-trig idea was given up.
- `rotate_slot` using `_np.cos / _np.sin` to build the 2x2 rotation
  matrix at runtime — same accepted-libm-for-trig logic.

**Boundary cases (acceptable but worth being aware of):**

- Vector accessors (`real`, `imag`, `truth`, `component`,
  `slot_load`, `similarity`) return Python floats via `.item()`.
  The READ is one tensor index (cheap); the value comes back as
  Python. If used as a Python scalar downstream (e.g. for printing
  or assertion), this is fine. If composed back into tensor ops
  via Python arithmetic, that arithmetic is host. Whether this
  matters depends on usage.
- `embed` HTTP-calls Ollama on cache miss. Runtime I/O. Acceptable
  if all embeddings are pre-warmed; problematic if a hot path hits
  uncached names.
- Cache-lookup `if key not in self._rot_cache` — runtime conditional
  but only on the first use of a given role; subsequent calls hit
  the cached matrix and matmul.

**What IS genuinely tensor-pure on the substrate:**
- `bind` / `unbind` (cache-hit path: one matmul)
- `bundle` (sum)
- `complex_mul` (cached matrix matmul + element-wise multiply)
- `make_real` / `make_complex` / `make_truth` (vector construction)
- The new `_VSA._step` cell in `_VSA.loop()` — the work I shipped
  2026-04-30 IS substrate-pure for the cell itself. The
  surrounding `_VSA.loop` method body is also substrate-pure
  (just a fixed-T `for _t in range(T)` iterating the cell).

So the loop refactor 2026-04-30 produced one genuinely tensor-pure
runtime method. The transcendentals from 2026-04-29 produced eight
new runtime methods that are NOT tensor-pure, despite my commit
messages framing them as substrate-native.

## The full list of violations

Categories below. "**OK**" = runs as tensor ops on CUDA. "**HOST
PYTHON**" = runs as Python scalar arithmetic, libm calls, branches,
or HTTP at runtime. "**BOUNDARY**" = the operation is a tensor op
but it returns a Python scalar (.item() extraction); whether this
matters depends on the consumer.

### Transcendentals (codegen.py / codegen_pytorch.py)

| Method | Status | Detail |
|---|---|---|
| `_real_exp_scalar(x)` | **HOST PYTHON** | Takes Python float, runs `for n in range(25)` over Python scalar arithmetic, returns Python float. Plus `if x > EXP_BOUND: x = EXP_BOUND` clipping. |
| `_real_log_scalar(x)` | **HOST PYTHON** | `if x <= 0.0: return -inf` plus `math.frexp(x)` (acceptable as bit-manip primitive) plus a `for j in range(30)` over Python scalars. |
| `_cos_sin_scalar(theta)` | **HOST PYTHON** (numpy backend) — uses `_math.cos(t), _math.sin(t)`. **HOST PYTHON** (torch backend) — uses `_torch.cos(t).item()` which is torch but immediately scalar-extracted. **NEITHER is the eigenrotation primitive applied to (1, 0) on a tensor.** |
| `_atan_taylor(t)` | **HOST PYTHON** | `for k in range(60)` Python scalar arithmetic. |
| `_atan2_scalar(y, x)` | **HOST PYTHON** | Quadrant decomposition is a tower of Python `if x > 0.0:` / `if abs(y) <= abs(x):` branches. |
| `exp(self, v)` | **HOST PYTHON** wrapper | Extracts `re = float(av[...].item())` and `im` likewise; calls `_real_exp_scalar`, `_cos_sin_scalar`; constructs result via `make_complex(e_re * c_im, e_re * s_im)` (Python scalar multiplication). |
| `log(self, v)` | **HOST PYTHON** wrapper | Same shape — extracts re/im, calls scalar helpers, constructs complex result via Python multiplies. |
| `sin / cos / tan / sqrt / pow` | **HOST PYTHON** wrappers | All compose the above scalar helpers via Python scalar arithmetic. |

**Implication:** when a `.su` program calls `exp(x)`, the work is
done in Python interpreting one number at a time. Zero tensor ops,
zero CUDA. The output is then packed back into a tensor for whatever
comes next.

### Slot machinery (codegen.py:870+, mirrored in codegen_pytorch.py)

| Method | Status | Detail |
|---|---|---|
| `_slot_plane(slot_idx)` | OK | Pure index arithmetic on a Python int. Returns a tuple. The "violation" is the `int(slot_idx) % n_planes` runtime modulo, which is a Python op, but produces an index into a tensor (acceptable boundary). |
| `slot_store(state, slot_idx, scalar)` | **HOST PYTHON** | `new[i] = float(scalar); new[j] = 0.0` — Python scalar assignment into tensor positions. The COMPUTATION is just two writes, not a tensor op. |
| `slot_load(state, slot_idx)` | **HOST PYTHON** | `return float(state[i])` — scalar extraction. |
| `rotate_slot(state, slot_idx, angle)` | **HOST PYTHON** | `c, s = _np.cos(float(angle)), _np.sin(float(angle))` — calls libm cos/sin to build the rotation matrix at runtime. **Same libm-shortcut violation as transcendentals.** Then assigns to two tensor positions via Python. |

**Implication:** rotation-binding's runtime primitive `rotate_slot` —
which is supposed to BE the substrate's rotation operation —
internally uses libm transcendentals to compute its matrix entries.
Same shape of violation Emma flagged for transcendentals.

### Vector accessors (codegen.py:937+)

All of these return Python floats via `.item()`:

- `real(v)`, `imag(v)`, `truth(v)`
- `component(v, i)`, `semantic(v, i)`, `synthetic(v, i)`

**BOUNDARY** — the read itself is one tensor index (cheap), but the
return value is a Python scalar. If the user writes
`x = v.real(); y = x + 1.0` the addition is Python. If the user
writes `v2 = make_real(v.real() + 1.0)` the read+add+construct
chain is Python with brief tensor visits. Whether this is a
problem depends on whether these accessors are user-facing
(legitimate boundary) or get composed into tensor ops downstream
(bad).

Also: bounds checks like `if idx < 0 or idx >= self.semantic_dim:
raise IndexError(...)` — Python conditionals + raise. Acceptable
for input validation but they ARE host control flow.

### Other runtime methods

| Method | Status | Detail |
|---|---|---|
| `bind(filler, role)` | OK on cache hit | First call computes Haar matrix via `make_random_rotation` (numpy random + QR + assemble). Subsequent calls retrieve from `self._rot_cache` and matmul. Cache hit: tensor-pure. Cache miss: builds matrix at runtime in numpy/torch. |
| `unbind(bound, role)` | OK on cache hit | Same pattern — matrix transpose + matmul. |
| `bundle(*args)` | OK | Sum of vectors. Tensor op. |
| `make_random_rotation(...)` | **HOST PYTHON** | Called at runtime on first bind for each role. Numpy random sample + QR decomposition + Givens construction. CUDA-incompatible. |
| `compile_prototypes(prototype_vectors, ...)` | OK | Pass-through dict — does nothing. |
| `complex_mul(a, b)` | OK | Cached matrix matmul + element-wise multiply. Pure tensor ops. |
| `make_complex / make_real / make_truth` | OK | Tensor construction. |
| `_swap_ri_matrix / _cm_real_matrix / _cm_imag_matrix` | OK | Build cached matrices on first call (Python control flow on first call only), return on subsequent. Cache-hit: pure. Cache-miss: builds the matrix at runtime via Python loop. |
| `similarity(a, b)` | **BOUNDARY** | Computes `_torch.dot(a, b) / (norm * norm + eps)` — tensor op — then returns `float(...)`. The compute is on the substrate; the result is a Python scalar. |
| `argmax_cosine(query, candidates)` | **HOST PYTHON** | Per the grep, uses `for k, v in pairs:` and similar — Python loop over candidates with score comparison. |
| `snap(state)` | likely **HOST PYTHON** | Argmax pattern, similar shape. |
| `defuzzify_trit(v, ...)` | **HOST PYTHON** | `for _ in range(int(iters))` with Python `_math.exp` calls per iter. Documented as such. |
| `embed(name)` | **HOST PYTHON + NETWORK I/O** | Cache check + Ollama HTTP call on miss. |
| `embed_batch(names)` | same | One HTTP call for many names, but still cache-check + I/O. |

### Loop primitives

| Method | Status | Detail |
|---|---|---|
| `_VSA._step` (the cell) | OK | The 2026-04-30 work. Pure tensor ops: matmul, divide, sigmoid, minimum, soft mux. Substrate-pure. Real win. |
| `_VSA.loop` (the unroll) | OK | Fixed `for _t in range(max_iters):` — meta-iteration, compile-time-fixed count. Body is the cell. Substrate-pure for the iteration mechanism. |
| `_VSA.loop` (body discard) | **violation** | The body of `loop(cond)` / `while(cond)` is dropped. Currently the cell is `state ← R · state` regardless of body. Already queued for fix. |
| `loop(N)` runtime-N | **HOST PYTHON** | `for _ in range(N)` in emitted code. Already queued. |
| `loop(N)` literal N | OK | Compile-time unroll. Body emitted N times inline. |

### Bind/unbind cache machinery

| Method | Status | Detail |
|---|---|---|
| Cache lookup `_rot_cache[role_hash]` | **HOST PYTHON** check | `if key not in self._rot_cache:` runtime conditional. On hit: just dictionary lookup. On miss: builds matrix via numpy random + QR. |

## Specific commits where the violations were introduced

- **2026-04-29 (commit `e45d373`):** Transcendentals shipped. The
  commit message claimed "substrate-pure runtime methods" but
  in reality the methods are Python scalar arithmetic. **My fault
  — I oversold this commit. The math is correct (computes the right
  values within FP precision); the architectural claim was wrong.**
- **2026-04-30 (commit `e612598`):** Loop refactor. The cell IS
  substrate-pure (real win). The commit message also claimed "the
  RNN-style loop is live, MLP/RNN architectural symmetry holds
  end-to-end" — that part was overselling because the body still
  doesn't run. Already corrected in `e678dfa`.
- **Pre-existing (2026-04-22 / 2026-04-24 era):** `rotate_slot`
  using libm to build rotation matrices. The slot machinery was
  validated functionally but never audited for substrate-purity.

## What this means for the architecture story

The narrative "Sutra programs compile to a forward pass through
tensor ops on CUDA" is **partly true**:
- Bind/bundle/unbind/complex_mul/the loop cell DO run as tensor
  ops. A Sutra program that uses just these ops genuinely is a
  forward pass on CUDA.
- Anything that touches transcendentals, slot machinery,
  similarity (extracted to scalar), embed, snap, or argmax_cosine
  drops out of CUDA into host Python at runtime.

For a typical Sutra program (say `examples/loop_rotation.su`),
the runtime call graph is roughly:
- `embed("cat")` → host Python + HTTP (cached after first call)
- `make_random_rotation(...)` for the loop's R → host Python + numpy
- `_VSA.loop(state, R, ...)` → tensor ops (post-2026-04-30 fix)
  for the iteration; body discarded
- `argmax_cosine(state, [v_cat, v_dog, ...])` → host Python loop

So the proportion of runtime that's actually CUDA depends on
which methods the program uses. For the "loop and snap" pattern
the loop-iteration is substrate; the wrapping (embed cache, R
construction, snap) is host Python.

## Path forward (does NOT belong in this doc — that's STATUS.md
queue work)

Each violation needs its own fix. They're queued in `STATUS.md`
under a new "Runtime substrate-purity sweep" item that this audit
will trigger.
