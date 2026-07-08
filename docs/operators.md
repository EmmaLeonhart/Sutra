---
title: Operators
description: Every Sutra operator and the function-expansion form it beta-reduces to. Operators are sugar over composed primitive functions; this page shows the chain.
---

# Operators

Sutra's operators are not primitive runtime instructions. They are syntactic sugar over composed function calls, and every one has a **root definition** — the chain of more-primitive functions it beta-reduces to. The compiler's function-expansion pass inlines each operator down to a tensor-op leaf (`+`, `*`, `@` matmul, polynomial, axis-projector). Once inlined, the simplifier and (future) fusion pass can fold long operator chains into single cached matrices.

The principle: **basically all functions beta-reduce to their components, except recursive ones.** Each operator below has a function-expansion form that names what it actually computes. If that form references another non-primitive function, that function in turn has its own expansion, and the chain bottoms out at the substrate primitives the runtime exposes (`dot`, `tanh`, `@`, axis-indexed read/write, Haar rotation, LLM embedding).

Status legend:

- **In Sutra** — the body is written in Sutra's standard library and gets inlined into user code.
- **Intrinsic** — declared in the standard library without a body; the codegen routes the call to a runtime method.
- **Blocked** — the Sutra-level body is sketched but a primitive surface (matrix literals, `@` matmul as an operator, indexed axis write, etc.) needs to land before the body can replace the runtime method. The runtime method works today; only the compile-time inlining is blocked.
- **Live** — declared, and the codegen routes calls to a substrate-pure runtime method that runs at runtime.

---

## Logical operators

Sutra's logic is fuzzy — every value lives on the truth axis as a number in `[-1, +1]` (Kleene K₃: `+1` true, `0` unknown, `-1` false). Logical operators are Lagrange polynomials over this scheme: exact on the three-valued grid, smooth everywhere, differentiable for gradient flow.

Each connective accepts one or more spellings; all forms produce identical AST and lower to the same stdlib polynomial body. The keyword forms (`not`, `and`, `or`, `nand`, `xor`, `xnor`) are case-insensitive AND contextual — they only become operators in expression positions, so user identifiers like `Xnor`, `Nand`, or `XorTable` keep parsing as plain names.

| Connective | Symbolic | Keyword (case-insensitive) | Stdlib body |
|---|---|---|---|
| NOT  | `!a`, `~a`           | `not a`                | `0 - a` |
| AND  | `a && b`, `a & b`    | `a and b`              | `(a + b + ab − a² − b² + a²b²) / 2` |
| NAND | —                    | `a nand b`             | `!(a && b)` |
| OR   | `a \|\| b`, `a \| b` | `a or b`               | `(a + b − ab + a² + b² − a²b²) / 2` |
| XOR  | —                    | `a xor b`              | `0 - a * b` |
| XNOR | —                    | `a xnor b`             | `a * b` |
| EQ   | `a == b`             | —                      | cosine similarity on truth axis (intrinsic) |
| NEQ  | `a != b`             | —                      | `!(a == b)` |
| LT   | `a < b`              | —                      | `b > a` |
| GT   | `a > b`              | —                      | smooth-tanh on real-axis difference (intrinsic) |
| LE   | `a <= b`             | —                      | `a < b` (collapses to LT under tanh-scheme) |
| GE   | `a >= b`             | —                      | `a > b` (same collapse) |

### `!a` — negation

```sutra
function fuzzy logical_not(fuzzy v) {
    return 0 - v;
}
```

Polynomial form: `NOT(v) = -v`. Exact on `{-1, 0, +1}`, fixed point at `0` (unknown stays unknown). Spellings: `!a`, `~a`, `not a` / `NOT a`. **Status: in Sutra** (`stdlib/logic.su`).

### `a && b` — conjunction (Kleene K₃ AND)

```sutra
function fuzzy logical_and(fuzzy a, fuzzy b) {
    return (a + b + a * b - a * a - b * b + a * a * b * b) * 0.5;
}
```

Lagrange polynomial: `a ∧ b = (a + b + ab − a² − b² + a²b²) / 2`. Spellings: `a && b`, `a & b`, `a and b` / `AND` / `And`. **Status: in Sutra** (`stdlib/logic.su`).

### `a nand b` — NAND

```sutra
function fuzzy logical_nand(fuzzy a, fuzzy b) {
    return !logical_and(a, b);
}
```

Composition over AND and NOT. Functionally complete on its own (`{NAND}` alone can express any Boolean function). **Status: in Sutra** (`stdlib/logic.su`).

### `a || b` — disjunction (Kleene K₃ OR)

```sutra
function fuzzy logical_or(fuzzy a, fuzzy b) {
    return (a + b - a * b + a * a + b * b - a * a * b * b) * 0.5;
}
```

Dual polynomial to AND: `a ∨ b = (a + b − ab + a² + b² − a²b²) / 2`. Spellings: `a || b`, `a | b`, `a or b` / `OR` / `Or`. **Status: in Sutra** (`stdlib/logic.su`).

### `a xor b` — exclusive OR

```sutra
function fuzzy logical_xor(fuzzy a, fuzzy b) {
    return 0 - a * b;
}
```

Closed form: `XOR(a, b) = -a·b`. Equivalent to `(a && !b) || (!a && b)` after polynomial folding. The simplifier discovers this collapse on its own when XOR is written compositionally; shipping the closed form here saves the simplifier the work. **Status: in Sutra** (`stdlib/logic.su`).

### `a xnor b` — biconditional / IFF

```sutra
function fuzzy logical_xnor(fuzzy a, fuzzy b) {
    return a * b;
}
```

NOT(XOR), which simplifies to the bare product. Spelling: `a xnor b`. **Status: in Sutra** (`stdlib/logic.su`).

### `a == b` — fuzzy equality (cosine on truth axis)

```sutra
// Target Sutra body (currently intrinsic):
function fuzzy eq(vector a, vector b) {
    number na  = sqrt(dot(a, a));
    number nb  = sqrt(dot(b, b));
    number cos = dot(a, b) / (na * nb + finfo_tiny);
    return make_truth(cos);
}
```

Cosine similarity placed on the truth axis. **Status: intrinsic** (blocked on `dot`, `sqrt`, `make_truth`, `finfo_tiny` having Sutra-level surfaces).

### `a != b` — fuzzy inequality

```sutra
function fuzzy neq(vector a, vector b) {
    return !(a == b);
}
```

Pure composition over `==` and `!`. **Status: in Sutra** (`stdlib/similarity.su`).

### `a > b` — strict greater-than (smooth sign)

```sutra
// Target Sutra body (currently intrinsic):
function fuzzy gt(complex a, complex b) {
    vector diff   = a - b;
    vector diff_r = real_projector @ diff;
    vector signed = tanh(100.0 * diff_r);
    return truth_from_real @ signed;
}
```

Differentiable smooth-sign on real-axis difference. **Status: intrinsic** (blocked on axis-projector matrix literals, `tanh` as a Sutra surface, `@` matmul as an operator).

### `a < b` — strict less-than

```sutra
function fuzzy lt(complex a, complex b) {
    return b > a;
}
```

`>` with sides swapped. **Status: in Sutra**.

### `a >= b` and `a <= b` — non-strict comparison

```sutra
function fuzzy ge(number a, number b) { return (a > b) || (a == b); }
function fuzzy le(number a, number b) { return (a < b) || (a == b); }
```

Non-strict comparison is `or(strict, ==)`: exact ties read **+1** (true), the true direction reads +1, and the false direction reads −1 — so the standard loop guard `i <= n` behaves correctly at the boundary. The `==` component is the exact number-equality indicator, keeping every reading crisp at integer spacing. The strict forms `<` / `>` still give `tanh(0) = 0` at a tie. **Status: in Sutra**.

### Chained comparisons (Python-style)

Sutra recognizes Python-style comparison chains and reduces them to named operations at parse time. Each pattern lowers through a dedicated codegen path so the user's intent is visible in the AST and the emitted polynomial form stays clean.

| Source | Reduction |
|---|---|
| `a == b == c` | `Equals(a, b, c)` |
| `a < b < c` | `hasOrder(a, b, c)` |
| `a > b > c` | `hasOrder(c, b, a)` *(args reversed — reduction is always-ascending)* |
| `a <= b <= c` | `hasOrderOrEqual(a, b, c)` |
| `a >= b >= c` | `hasOrderOrEqual(c, b, a)` |
| `a == b > c == d > e` | `hasOrder(e, Equals(c, d), Equals(a, b))` *(equality groups inlined as nested `Equals(...)` args; codegen rejects nested form for now, but the parser-level shape is locked in)* |
| `a != b == c > d` | `(a != b) && (b == c) && (c > d)` *(any chain with `!=`, or otherwise mixed → AND-chain fallback)* |

Reductions:

- `Equals(a, b, c, ...)` → fuzzy AND of `_VSA.eq(a, b)` between each adjacent pair.
- `hasOrder(a, b, c, ...)` → fuzzy AND of `_VSA.gt(b, a)` between each adjacent pair (since `a < b` is `b > a` on the runtime).
- `hasOrderOrEqual(...)` → currently identical to `hasOrder` because the K3-tanh `<=` collapses to `<` (both produce `tanh(0) = 0` on exact ties); when a real non-strict semantics lands the body switches.
- For chains mixing `==` with uniform-direction ordering (e.g. `a == b > c == d > e`), the parser builds `hasOrder` (or `hasOrderOrEqual`) with each equality group inlined as a nested `Equals(...)` call. The example reduces to `hasOrder(e, Equals(c, d), Equals(a, b))`. Note the "weird programming concept" this introduces: `Equals` returns a fuzzy truth value at top level, but as a positional arg inside `hasOrder` it represents the equality group itself — same call name, different role by context. The codegen rejects the nested form today (the group-expansion semantics — chain-AND with cross-group ordering plus internal group equality — isn't wired yet). The parser-level reduction is locked in so a future codegen pass can implement it without breaking source.

This is parser-level sugar — the `+`, `-`, `*`, etc. arithmetic operators continue to bind tighter than comparisons (so `a + 1 == b + 2 == c` works as expected).

---

## Arithmetic operators

Arithmetic on Sutra's number axis (real / imag / char-flag in `synthetic[]`). The primitive operations `+`, `-`, `*`, `/` are runtime substrate operations; `^` and the transcendentals decompose to them.

### `a + b`, `a - b`, `a * b`, `a / b`

Element-wise vector arithmetic on the substrate. These are **runtime primitives** — tensor-op leaves the rest of the language is built on. The codegen lowers them directly to `torch.add` / `torch.mul` / etc.

Augmented assignment forms (`+=`, `-=`, `*=`, `/=`) desugar to `x = x op y`. Per Sutra's no-memory-points principle, the assignment is just naming the right-hand side; there's no cell being mutated.

**`+` on strings concatenates.** When both operands are strings (literals, `string`/`String`-typed variables, interpolated strings, or string-returning calls), `a + b` dispatches to the substrate string concatenation — `"ab" + "cd"` is `"abcd"`, a permutation-shift-and-add over the codepoint axes, not element-wise numeric addition. Mixed string/number operands stay on the numeric paths.

### `a ^ b` — exponent (planned)

The `^` operator is reserved as exponentiation on the number axis (not bitwise XOR — Sutra has no bits to flip). Surface declared 2026-04-29 from the transcendentals chat. Target expansion:

```sutra
function Number operator ^(Number a, Number b) {
    return Math.Pow(a, b);
}

function Number Pow(Number a, Number b) {
    return exp(a * log(b));
}
```

Each step of the chain is a function-expansion: `^` reduces to `Pow`, `Pow` reduces to `exp` and `log`. The chain bottoms out at `exp` and `log`, both of which are live and substrate-pure (see Transcendental functions below).

**Status: operator surface not yet wired.** The underlying `Math.pow` / `exp` / `log` intrinsics run today, but the `^` infix operator itself is still pending: the lexer needs a `^` token and the parser needs an infix-binary production at the appropriate precedence (above `*`, right-associative is the math convention). Until then, call `Math.pow(a, b)` directly.

---

## The leaf VSA primitives — what everything beta-reduces to

The operations below are the **bottom of the function-expansion chain**. The rest of this page lists higher-level operations (`bind`, `unbind`, `bundle`, `similarity`, `argmax_cosine`, etc.) — those are convenience names for common compositions that ultimately reduce to calls into the `Tensor` namespace defined here. The point is **transparency**: when you ask "what does `bind` actually do at the lowest level?" the answer is `MatrixMul(RotationFor(role), filler)`, and you can read that chain in the stdlib source.

Both PascalCase and snake_case spellings are accepted; both bare-name and namespaced forms work:

```sutra
vector x = Tensor.MatrixMul(M, v);    // preferred
vector x = Tensor.matmul(M, v);       // also works
vector x = MatrixMul(M, v);           // bare-name shortcut via stdlib_loader
```

| Leaf primitive | Sutra form | Runtime |
|---|---|---|
| Matrix multiplication | `Tensor.MatrixMul(a, b)` / `matmul(a, b)` | `torch.matmul` |
| Tensor / Kronecker product | `Tensor.TensorProduct(a, b)` / `tensor_product(a, b)` | `torch.kron` |
| Outer product | `Tensor.Outer(a, b)` / `outer(a, b)` | `torch.outer` |
| Dot product (number result) | `Tensor.Dot(a, b)` / `dot(a, b)` | `torch.dot` |
| Transpose | `Tensor.Transpose(M)` / `transpose(M)` | `torch.transpose` |

How the higher-level VSA names reduce:

```
bind(role, filler)        -> MatrixMul(RotationFor(role), filler)
unbind(role, record)      -> MatrixMul(Transpose(RotationFor(role)), record)
bundle(a, b, c, ...)      -> Normalize(a + b + c + ...)
similarity(a, b)          -> Dot(a, b) / (Norm(a) * Norm(b))
argmax_cosine(q, [a, b, c]) -> a/b/c with the largest similarity(q, .)
```

There's nothing else underneath. Every Sutra program is some chain of these five leaf operations plus element-wise `+`, `-`, `*`, `/` and the polynomial logical-connective forms.

Worked example: `examples/tensor_ops.su` calls each of the five primitives directly.

---

## Vector / VSA primitives — what reduces to the leaves above

The hyperdimensional-computing core. Every operation is a tensor op on the substrate.

### `bind(role, filler)` — role-rotation binding

```sutra
// Target Sutra body (currently a runtime method):
function vector bind(vector role, vector filler) {
    matrix Q = rotation_for_role(role);
    return Q @ filler;
}
```

Role-seeded Haar-random orthogonal rotation applied to the filler. Block-diagonal: Haar in the semantic block, identity in the synthetic block — bind acts only on semantic content. The rotation is cached in `_VSA.prewarm_rotation_cache()` at module init, so repeat calls with the same role are one matmul. **Status: blocked** (target body in `stdlib/vectors.su`; runtime method works today).

### `unbind(role, bound)` — inverse of bind

```sutra
function vector unbind(vector role, vector bound) {
    matrix Q = rotation_for_role(role);
    return transpose(Q) @ bound;
}
```

Same cached rotation matrix, transposed. **Status: blocked**.

### `bundle(v1, v2, ...)` — normalized superposition

```sutra
function vector bundle(vector... args) {
    vector s = zero_vector();
    foreach (v in args) {
        s = s + v;
    }
    return s / (norm(s) + finfo_tiny);
}
```

Variadic sum + L2-normalize. The fused `bundle_of_binds((r1,f1), (r2,f2), ...)` codegen peephole is a compile-time optimization on top of this spec definition — it collapses N sequential binds + an N-arg bundle into one batched einsum. **Status: blocked** (variadic param surface needs work).

### `similarity(a, b)` — cosine similarity (number)

```sutra
function number similarity(vector a, vector b) {
    number na = sqrt(dot(a, a));
    number nb = sqrt(dot(b, b));
    return dot(a, b) / (na * nb + finfo_tiny);
}
```

Cosine without truth-axis placement. Same dot/norm pipeline as `==`, but returns the raw number. **Status: intrinsic**.

### `argmax_cosine(query, candidates)` — best-match retrieval

```sutra
function vector argmax_cosine(vector query, vector[] candidates) {
    matrix C       = stack(candidates);
    vector scores  = (C @ query) / (row_norms(C) * norm(query) + tiny);
    int    best    = argmax(scores);
    return candidates[best];
}
```

Stacked-candidate matmul + argmax. **Status: blocked**.

### `select(scores, options)` — softmax-weighted superposition

```sutra
function vector select(number[] scores, vector[] options) {
    number[] s = scores - max(scores);
    number[] w = exp(s);
    w          = w / sum(w);
    return sum(w[i] * options[i] for i);
}
```

Softmax over scores, weighted sum of options. The runtime never does a host-side branch — every option contributes weighted by its softmax score. **Status: blocked**.

### `permute(v, key)` and friends

```sutra
function vector permute(vector v, permutation key) {
    return v * sign_flip_mask(key);
}
```

Element-wise multiply with a deterministic ±1 mask. **Status: blocked** on `sign_flip_mask` primitive.

---

## Memory operators

### `zero_vector()`

The neutral vector — zero in semantic block, zero in synthetic block. **Status: intrinsic**.

### `hashmap_get(map, key)` and `hashmap_set(map, key, value)`

VSA-style associative memory: a hashmap is a bundle of bind(key, value) pairs; get is an unbind + cleanup. Target Sutra forms in `stdlib/memory.su`. **Status: blocked**.

---

## Embedding

### `embed(string)`

The LLM-substrate intrinsic: a string goes in, a (mean-centered, normalized) vector comes out. Cached at compile time via `_VSA.embed_batch` and `_VSA.populate_sutradb`. The runtime never pays a network round-trip on the hot path — every literal string is pre-embedded at module init.

```sutra
intrinsic function vector embed(string name);
```

`embed` is the canonical (and only) spelling. `basis_vector(name)` was a pure alias for it, **removed 2026-06-23** — use `embed`.

**Status: intrinsic** (`embed`).

---

## Defuzzification

### `defuzzy(v)` — polarize along the truth axis

```sutra
function fuzzy defuzzy(fuzzy v) {
    loop (10) {
        v = v == true;
    }
    return v;
}
```

Iterates cosine equality with `true` ten times. Inputs with `truth = 0` stay at `0` (unknown is a fixed point of equality-with-true under the eps-guarded `==`); inputs with `truth ≠ 0` sharpen toward `±1`. Ten iterations is the spec definition — one pass mathematically suffices for well-separated inputs, but the unrolled form is what the fusion pass targets. **Status: in Sutra**.

### `is_true(v)` and `defuzzify(v)`

`defuzzify` is the same operation as `defuzzy` — both names are accepted. `is_true(v)` is `defuzzify(v)` followed by a positive-axis projection. Both keep the value fuzzy and differentiable; neither binarizes.

---

## Transcendental functions (live, substrate-pure)

```sutra
intrinsic function number log(number x);
intrinsic function number sqrt(number x);
intrinsic function number exp(number x);
intrinsic function number sin(number x);
intrinsic function number cos(number x);
intrinsic function number tan(number x);
intrinsic function number pow(number x, number y);
```

**Status: live, substrate-pure.** Every call routes to a runtime method that runs on the substrate — `exp` and `log` via interpolated lookup tables on a bounded domain, the trig family via the unit-circle rotation primitive the language already uses for binding, and `pow` / `sqrt` beta-reducing onto those. No call reaches a host math library at runtime. The unlock was eigenrotation-as-modulus, which makes the unit-circle rotation naturally periodic without floor-based range reduction. (An earlier Taylor-with-frexp implementation was withdrawn because it ran as host Python scalar arithmetic, a substrate-purity violation.)

With substrate-pure `log` and `exp` in place, the rest of the chain composes: `Pow(a, b) = exp(b * log(a))`, and `sin` / `cos` come straight from eigenrotation.

---

## How to read the chain

Take `^` as the worked example:

```
a ^ b
  → Math.Pow(a, b)        // operator desugar
    → exp(a * log(b))     // Pow's expansion
      → exp(<number>)     // multiplication is primitive
        ...               // exp lowers to substrate ops
```

Each arrow is the inliner replacing a function call with its body. The chain stops at substrate primitives — operations the runtime exposes as torch tensor ops without further decomposition. For a long chain of operator applications, the inliner produces a long flat sequence of tensor ops; the simplifier and fusion pass then fold linear sub-chains into cached matrices. By the time the runtime executes, what was a stack of nested operators in the source is one matmul on CUDA.

---

## Related reading

- [Logical operations](logical-operations.md) — deeper coverage of the Kleene K₃ scheme and the polynomial gates.
- [Numeric math](numeric-math.md) — how integers, floats, complex numbers live on the substrate.
- [Memory](memory.md) — bind / unbind / bundle in detail.
- [Compilation](compilation.md) — the function-expansion / inlining / fusion pipeline.
