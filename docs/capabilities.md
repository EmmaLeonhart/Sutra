# What Sutra implements

This page is the exhaustive inventory of every implemented thing in the Sutra language. Every keyword, every operator, every runtime primitive, every stdlib class, every control-flow form. For each item there's a **Training** note: whether training (in the constrain-train sense — train a parameter, bake it back into source as a literal, recompile) is implemented today on that item.

Training status legend used throughout:

- **shipped** — a training experiment exists, was run, measured, baked back into source, round-trip-clean.
- **mechanism** — a training harness exists and passes a smoke test, but no publication-quality measurement yet.
- **vision** — the item has a trainable surface in principle, but no harness exists yet.
- **n/a** — not a trainable surface (compiler infrastructure, syntax, lexical forms, etc.).

There is **one shipped** training instance in the whole language today (the equality `==` cosine scaling scalar) and **two mechanism** instances (rank-k `is_X` classification, defuzz gain). The bulk of trainable surfaces are **vision** — capable in principle, not yet built.

---

## 1. Keywords (reserved)

`function`, `method`, `static`, `public`, `private`, `var`, `const`, `return`, `if`, `else`, `while`, `for`, `foreach`, `in`, `do`, `loop`, `do_while`, `while_loop`, `iterative_loop`, `foreach_loop`, `pass`, `recur`, `recurring`, `replace`, `as`, `try`, `catch`, `this`, `operator`, `new`, `implicit`, `intrinsic`, `class`, `extends`, `slot`, `field`, `true`, `false`, `unknown`, `wait`, `async`, `await`.

**Training: n/a** — keywords are syntax.

## 2. Contextual keywords (lex as identifier; parser/codegen recognize)

`role`, `element`, `iterator`, `defuzzy`, `embed`, `unsafeCast`, `unsafeOverride`; logical-connective names `not`, `and`, `or`, `nand`, `xor`, `xnor`.

**Training: n/a** for the syntax. See §13 for the per-operator training notes on the connectives this maps to.

## 3. Comment forms

`//` line, `#` line, `/* */` block (not nested), `///` doc line.

**Training: n/a.**

## 4. String escape characters

`\n`, `\t`, `\r`, `\\`, `\"`, `\'`, `\0`, `\{`, `\}`, `\$`; unknown escapes pass through unchanged.

**Training: n/a.**

---

## 5. Literal forms

| Form | Example | Training |
|---|---|---|
| Integer | `42`, `0`, `1234567` | n/a (compile-time constant) |
| Float | `1.5`, `0.001` | n/a, **but** any source-level float that names a tunable threshold is a trainable surface — train as a parameter, bake back as the same literal form. Currently shipped on **equality `==` cosine scale T** (see §13). |
| Scientific notation | `1e10`, `1.5e-3`, `2E+5` | n/a (same surface as Float) |
| Imaginary | `5i`, `3.14i` | vision — a learned imaginary coefficient on the complex axis |
| Complex (folded) | `2 + 3i` → `ComplexLiteral(2,3)` | vision — both real and imaginary parts |
| String | `"hello"` | n/a (compile-time text) |
| Interpolated string | `$"hello {s}!"`, `$"n={n}"` | n/a — desugars to a substrate `make_string` / `string_concat` chain. **String- and int-typed interpolants**: `int` values format via `int_to_string`; a fractional `number`/fuzzy interpolant is rejected at codegen (decimal rendering is not built — declare integer interpolants `int`) |
| Char | `'a'`, `'\n'`, `'\''` | n/a |
| Bool | `true`, `false` | n/a |
| `unknown` | `unknown` | n/a — the truth-axis neutral; no parameter |
| `wait` | `var v : T = wait;` | n/a — deferred-initializer marker |
| Array literal | `[a, b, c]` | n/a (compile-time aggregate) |
| Map literal | `{k1: v1, k2: v2}` | vision — a learned key-value mapping |
| Vector literal (constructed) | `vector_literal(0.1, -0.2, ...)` | **shipped** on **rank-k prototype vectors** (see §13 — bake-back format for trained vectors) |
| Matrix literal (constructed) | `matrix_literal(vector_literal(...), vector_literal(...), ...)` | **shipped** — variadic row-vectors stacked into a 2-D substrate tensor; the source form for frozen lookup / permutation / cached matrices, consumed by `Tensor.MatrixMul` |
| Matrix from file (CSV) | `load_matrix("weights.su.csv")` | **shipped** — file-backed matrix constant: reads a CSV (comma floats, one row per line) at the path (absolute or CWD-relative) into a frozen 2-D substrate tensor, cached by path. The large-matrix counterpart to `matrix_literal` — trained weights live in a file (a weights store), not a giant inline literal |

No hex literals yet.

---

## 6. Primitive type names

`number` (the general numeric type; the old `scalar` alias was removed 2026-06-23), `vector`, `matrix`, `tuple`, `string`, `bool`, `fuzzy`, `void`, `permutation`, `map`, `char`, `int`, `trit` (three-valued: `true`/`false`/`unknown`), `complex`, `Promise<T>`, `function` (function-typed parameter). Generic syntax: `Type<args>` (e.g. `map<K, V>`, `Promise<T>`).

**Training: n/a** (type names are syntax). Per-type trainable surfaces are listed under the operators and runtime methods that consume each type.

---

## 7. Top-level declaration forms

| Form | Surface | Training |
|---|---|---|
| `function ReturnType name<Tps>(params) { body }` | regular function | n/a for the declaration; trainable parameters inside the body get trained per-call-site |
| `async function ...` | async function | n/a |
| `intrinsic function ReturnType name(params);` | body-less, runtime-backed | n/a |
| `method ReturnType name(params) { body }` | class method | n/a |
| `static method ...`, `static intrinsic method ...` | class-scoped function | n/a |
| `public` / `private` modifiers | access modifier | n/a |
| `implicit` (for implicit conversions) | implicit-conversion method | n/a |
| `operator <op>(...)` | operator overload | n/a — but the lowered op's parameters are trainable surfaces |
| `class Name extends Parent { ... }` | class | n/a |
| `field TYPE name;` (inside class) | typed field | vision — a learned default value for a field |
| Loop function decls: `do_while`, `while_loop`, `iterative_loop`, `foreach_loop` | substrate-RNN cell | vision — a learned cell update matrix or learned `max_iters` |

---

## 8. Statement forms

| Form | Surface | Training |
|---|---|---|
| `{ ... }` | block | n/a |
| `if (cond) { ... } else { ... }` / `else if` | **parses + validates but NEVER compiles — by design** (control-flow: conditionals are weighted superpositions, not discrete branches). Write `select(scores, options)` instead; see the fuzzy-dispatch pattern | n/a |
| `while (cond) { ... }` | **RETIRED** — the C-style imperative loop was rejected at codegen in the 2026-04-30 substrate-purity audit. Use a `while_loop NAME(cond, ...state) { ...; pass ...; }` declaration + `loop NAME(cond, args);` call (see [loops.md](loops.md)). | n/a |
| `for (init; cond; step) { ... }` | **RETIRED** — same audit. Use `iterative_loop NAME(count, ...state) { ... }` for fixed-count iteration, or `while_loop` for data-dependent (see [loops.md](loops.md)). | n/a |
| `foreach (TYPE name in iterable) { ... }` | iterate over binding-array | n/a |
| `do { ... } while (cond);` | **RETIRED** — same audit. Use a `while_loop` / `iterative_loop` declaration (see [loops.md](loops.md)). | n/a |
| `loop (10) { ... }` | bounded count | vision — count is currently a literal; trainable count would discover the right unroll |
| `loop (10 as i) { ... }` | bounded with index variable | vision — same |
| `loop (expr) { ... }` | condition-based eigenrotation | vision — the halt threshold is a trainable surface |
| `loop NAME(cond, args, ...);` | invoke a loop function | n/a |
| `try { ... } catch { ... }` | exception barrier | n/a (no learned recovery policy yet) |
| `return expr;` | return | n/a |
| `pass v1, v2, ..., replace, ...;` | tail-recursive yield in loop functions; `replace` keeps prior value | n/a |
| `recurring TYPE name = INITIAL;` | non-halting-loop state slot declaration (substrate-resident tensor across calls) | n/a — slot lifetime is structural |
| `recur(expr);` | sets the recurring slot's value for the next tick | n/a — substrate write to the slot |
| `return(expr);` | non-halting per-tick output (parens distinguish from halting-`return expr;`) | n/a |
| `var x = ...;`, `const x = ...;`, `TYPE x = ...;`, `var x : TYPE;`, `var[N] x : TYPE;` | declarations | n/a |
| `slot ...` | slot declaration (compiler-allocated rotation slot) | vision — learned slot-index assignment |
| `role X = ...;` | role declaration (contextual) | vision — learned role-rotation matrix (the deferred learned-binding track) |

---

## 9. Special-call forms

| Name | Form | Training |
|---|---|---|
| `unsafeCast<Type>(value)` | type-system escape — the pure relabel: the value crosses unchanged, only the static type changes (never axis-moves; `unsafeCast<fuzzy>(n)` reinterprets, so a real-axis value reads truth 0) | n/a |
| `(Type) value` (C-style cast) | conversion cast — no-op relabel by default; numeric↔truth casts axis-move (`(fuzzy) 0.7` puts 0.7 on the truth axis, `(number) b` reads a bool back as 1/0) via cached matmuls; `(string) n` on an `int` formats via `int_to_string`; other text casts are rejected at codegen (fractional rendering is not built; string→vector is `embed()`'s job). Guard SUT0111 still steers `(vector) "literal"` to `embed(...)` | n/a |
| `unsafeOverride(value)` | type-system escape — suppresses the call-site type check; lowers as the pure passthrough (value unchanged) | n/a |
| `defuzzy(value)` | truth-axis polarizer | mechanism — the cosine `(v == true)` loop body is scale-invariant in any input gain (`cos(g*v, true) = sign(x)`), so a wrapper gain on top of `defuzzy` is degenerate. The shipped trainable polarizer is `defuzzify_trit` below |
| `defuzzify_trit(v, iters, beta)` | three-way β-sharpening polarizer (Sutra-source intrinsic since 2026-05-28) | **shipped** — β is the trainable scalar; a training run with `--body trit --iters 1` converges to β\* = 6.58 ± 0.17 across 3 seeds; baseline 0.2126 → trained 0.0146 (~15× loss reduction); bake-back round-trip max\|Δ\| = 1.19e-7 (bit-exact within float32 precision). Second shipped constrain-train instance after `==` cosine-scale T. Runtime iters became runtime-variable 2026-05-28; default iters=10 preserves prior behavior |
| `embed(string)` | LLM-embedding primitive | vision — per-string embedding fine-tunes (a tiny adaptation layer on the frozen substrate) |

---

## 10. Lexer/parser/validator diagnostic codes

*This is the canonical, complete `SUT####` reference — other pages that mention a specific code link here.*

`SUT0001` unterminated block comment; `SUT0002` unterminated string / interpolated string; `SUT0003` character literal errors; `SUT0100` generic "expected X, got Y" parse error; `SUT0101` modifiers misapplied; `SUT0102` non-overloadable operator passed to `operator` decl; `SUT0103` `var TYPE x` form (use `var x : TYPE`); `SUT0104` expression expected / `slot` misuse; `SUT0105` `unsafeCast` requires `<Type>`; `SUT0110` `|>` pipe-forward not supported; `SUT0111` `(vector) "string"` (use `embed(...)`); `SUT0112` `public` and `private` conflict; `SUT0113` class casing drift (warning); `SUT0120` fuzzy/trit literal outside `[-1, +1]` (warning); `SUT0130`-`SUT0133` `wait` keyword misuse; `SUT0140` deferred feature; `SUT0141` class already declared; `SUT0142` class extends unknown; `SUT0144` object method reads file-scope name (encapsulation rule); `SUT0145` duplicate field / operator-method `intrinsic`; `SUT0151` spec'd-but-unimplemented substrate builtin (`snap`, `make_rotation`, …) — warning, steers to `argmax_cosine`; `SUT0200` unknown type — a name that is not a primitive, container, declared class, or stdlib type (warning; e.g. `vec` → `vector`); `SUT0201` unknown function with a "did you mean" typo suggestion (warning; e.g. `argmaxcosine` → `argmax_cosine`); `SUT0202` wrong argument *count* to a declared function (warning); `SUT0203` wrong argument *type* — e.g. a `string` where a `vector` is expected (warning; steers to `embed(...)`); `SUT0204` calling a Python builtin (`print`, `str`, `len`) that is not a Sutra function — it would lower to a host call (warning); `SUT0205` unknown variable with a "did you mean" typo suggestion — a bare identifier within 2 edits of a declared local/param/file-scope name (warning; e.g. `totl` → `total`; deliberately silent on far-off undeclared names, which are legitimate runtime-bound identifiers); `SUT2002` atman/workspace TOML parse error; `SUT2007` atman project table errors.

**Training: n/a** — diagnostic checks are compiler infrastructure.

---

## 11. Compiler passes

Lexer → Parser → Validator → Lowering / desugar passes (`promise_desugar` then `loop_desugar`, with `loop_capture` as part of the loop lowering) → Inliner → Simplifier (hand-written `simplify.py`; optional egglog backend `simplify_egglog.py`) → Codegen → Runtime. The desugar passes run before inlining so the synthesized loop and promise bodies get the same stdlib inlining as hand-written code, and the simplifier runs last over the fully-inlined tree.

Additional surface: workspace + atman config, cached-compile, stdlib loader, axon-keys static analysis, trace, review (FV checker public API `fv` namespace exposing the polynomial-obligation checker).

**Training: n/a** — these are compiler infrastructure.

---

## 12. Codegen targets

| Target | Status | Training |
|---|---|---|
| PyTorch (canonical) | active | the runtime trainable parameters land as `nn.Parameter`-shaped tensors here; this is the codegen target trained programs use |
| base codegen | abstract base class the active target extends | n/a |

---

## 13. Operators

For each: the syntactic surface, what it lowers to on the substrate, and the training status of any parameter inside.

### Arithmetic (numeric axis)

| Op | Surface | Lowers to | Training |
|---|---|---|---|
| `+` | binary, also unary | tensor add; `complex_add` when complex | vision — a learned scale/bias around the add |
| `-` | binary, unary | tensor sub; `complex_sub` when complex | vision |
| `*` | binary | element-wise multiply; `complex_mul` (matmul) when complex | vision — a learned multiplier (this IS what equality cosine T trains, except inside the equality call rather than as a standalone op trainer) |
| `/` | binary | element-wise divide; `complex_div` (matmul) when complex | vision |
| `%` | binary | `_VSA.fmod` (truncation mod) | vision |
| `++`, `--` | postfix unary | desugars to `x = x + 1` / `x = x - 1` | n/a |
| `+=`, `-=`, `*=`, `/=` | binary augmented | desugars to `x = x <op> rhs` | n/a (defers to the op) |

### Equality and comparison (truth axis)

| Op | Surface | Lowers to | Training |
|---|---|---|---|
| `==` | binary | cosine similarity → truth-axis projection (`_VSA.eq`) | **shipped** — `equality_cosine_adjustment.py` trains a per-program scalar T scaling the cosine inside `is_X(x) = (T * similarity(x, own)) && !(T * similarity(x, others))`; T baked back as a numeric literal in the recompile; round-trip max\|Δ\| < 1e-4 (typical ≈ 2e-7). One of the **four shipped constrain-train instances** today (alongside `defuzzify_trit` β, rank-k is_X K=2, and `select` softmax temperature). |
| `!=` | binary | `!(a == b)` (composes through `==`) | vision (inherits the T from `==` indirectly) |
| `<`, `>`, `<=`, `>=` | binary | tanh-smooth comparison on the real axis (`_VSA.gt` + composition) | vision — a learned sharpness scalar inside the smooth-sign |

Python-style chained comparisons (`a < b < c`) supported.

### Logical (Kleene three-valued, smooth polynomial form)

The Kleene connectives lower to Lagrange-interpolated polynomials over the truth grid `{−1, 0, +1}`:

- `a && b = (a + b + ab − a² − b² + a²b²) / 2`
- `a || b = (a + b − ab + a² + b² − a²b²) / 2`
- `!a = −a`

| Op | Surface | Training |
|---|---|---|
| `&&` (also `and`, `&`) | binary | **vision** — the 6 polynomial coefficients per call site are a trainable surface (the connective polynomial would specialize per use, with the {-1, 0, +1} grid-exactness constraint as a regularizer) |
| `\|\|` (also `or`, `\|`) | binary | vision — same as `&&` |
| `!` (also `not`, `~`) | unary | vision — coefficients of the `−a` form are trivial today but a trainable shape would generalize |
| `nand` | binary | vision |
| `xor` | binary | vision |
| `xnor` | binary | vision |

### Assignment, member access, calls

| Op | Surface | Training |
|---|---|---|
| `=` | binary | n/a (binding) |
| `.` | binary | member access — n/a |
| `::` | binary | scope/namespace — n/a |
| `[ ]` | postfix | subscript — n/a |
| `( )` | postfix | call — n/a (callee's trainable parameters apply individually) |
| `->`, `=>` | function-arrow tokens | n/a |
| `\|>` | pipe-forward | **rejected by validator (SUT0110)** |
| `^` | reserved token (binary XOR not currently a stdlib op via `^`; XOR is via the `xor` keyword) | n/a |

### User-overloadable operators (stdlib)

Currently shipped overload: `method operator +(String a, String b)` in `strings.su` → `string_concat`. `_parse_operator_decl` accepts overloads for `+`, `-`, `*`, `/`, `%`, `==`, `!=`, `<`, `>`, `<=`, `>=`. JavaScript-flavored subclasses (`JavaScriptString`, `JavaScriptInt`, `JavaScriptFloat`, `JavaScriptBool`) inherit and may override.

**Training:** per-overload — same as the underlying op.

---

## 14. Runtime primitives (`_VSA` methods on the PyTorch backend)

This is the substrate's full operation set. Each row is one method emitted into the runtime class.

### VSA core (bind / unbind / bundle)

| Method | Description | Training |
|---|---|---|
| `bind(role, filler)` | rotation binding: `R_role @ filler` | **vision** — learned per-role rotation matrices (the deferred learned-binding track) |
| `unbind(role, record)` | inverse rotation | vision (inherits learned-binding) |
| `bundle(*vectors)` | sum and L2-normalize | vision — learned per-component bundle weights (`(w_a*a + w_b*b + w_c*c)` then normalize) |
| `bundle_of_binds(*role_filler_pairs)` | bundle + bind composition | vision |
| `zero_vector()` | additive identity | n/a (constant) |
| `vector_from_floats(values)` | substrate vector from float list | n/a (compile-time, used by `vector_literal`) |
| `matrix_from_rows(rows)` | substrate 2-D tensor from row tensors (stack) | n/a (compile-time, used by `matrix_literal`) |
| `load_matrix(path)` | frozen substrate matrix read from a CSV file (cached by path) | n/a — the file-backed weight store; the loaded matrix's *consumers* train |

### Rotation internals

| Method | Description | Training |
|---|---|---|
| `_role_hash(role_vec)` | derive a stable rotation seed from a role vector | n/a |
| `_rotation_for(role_vec)` | rotation matrix for a role | vision (learned-binding) |
| `rotation_for(role)` | public alias | vision |
| `make_random_rotation(angle, n_planes, seed)` | Haar-distributed orthogonal | vision |
| `compile_prototypes(prototype_vectors, frame_seed)` | precompute rotation frames | vision |

### Embedding lifecycle

| Method | Description | Training |
|---|---|---|
| `__init__(semantic_dim, synthetic_dim, seed, llm_model)` | runtime init | n/a |
| `embed(name)` / `embed_batch(names)` | LLM-embedding lookup | vision — per-string embedding fine-tunes |
| `_load_disk_cache` / `_write_disk_cache` | persist embeddings | n/a |
| `_ensure_sutradb` / `populate_sutradb` | triple-store integration | n/a |
| `prewarm_rotation_cache` | precompute rotations | n/a |
| `nearest_string(query)` | nearest codebook string | vision — learned codebook weights |

### Tensor primitives

| Method | Description | Training |
|---|---|---|
| `similarity(a, b)` | cosine similarity | **shipped indirectly** via the `==` op (T scales the cosine output); standalone op trainer would scale the cosine independently |
| `matmul(a, b)` | matrix multiply | vision |
| `tensor_product(a, b)` | tensor product | vision |
| `outer(a, b)` | outer product | vision |
| `dot(a, b)` | dot product | vision |
| `transpose(m)`, `norm(v)`, `normalize(v)` | linear algebra | n/a / vision |

### Retrieval / selection

| Method | Description | Training |
|---|---|---|
| `_select_softmax(scores, options)` | softmax-weighted superposition (the differentiable `switch`) | **shipped via T scaling the scores at the Sutra source level** (`select([s_i/T for i], [opt_i for i])`); a training run learns T at K=5 / 3-seeds for +1.77× margin gain, with substrate-pure autograd; also: learned firing threshold (vision) |
| `_vector_map_lookup(pairs, key)` | vector-keyed map lookup | vision — learned key matching weights |

### Hashmap (rotation-bound accumulator)

| Method | Description | Training |
|---|---|---|
| `hashmap_new()` | empty hashmap | n/a |
| `hashmap_set(acc, key_vec, val_vec)` | insert | vision — learned per-key angle assignment |
| `hashmap_get(acc, key_vec)` | retrieve | vision |

### Slot machinery (rotation-bound scalar storage)

| Method | Description | Training |
|---|---|---|
| `_slot_plane(slot_idx)` | rotation plane for a slot | n/a |
| `slot_store(state, slot_idx, scalar)` | write | vision — learned slot allocation |
| `slot_load(state, slot_idx)` | read | vision |
| `rotate_slot(state, slot_idx, angle)` | rotate slot's plane | vision — learned rotation angle |

### Array literal runtime

| Method | Description | Training |
|---|---|---|
| `array_from_literal(*values)` | construct array | n/a |
| `array_length(arr)` | length | n/a |
| `array_get(arr, i)` | indexed read | n/a |

### Truth-axis ops

| Method | Description | Training |
|---|---|---|
| `truth_axis(vec_or_scalar)` | project to truth axis | n/a |
| `heaviside(x)` | step function — runtime helper used to gate the halting loop forms; not a source-level construct | n/a (wrapper-internal) |
| `saturate_unit(x)` | clamp to [0, 1] | n/a |
| `_truth_projector()` / `_real_projector()` / `_truth_from_real()` | projection matrices | n/a |
| `make_truth(t)` / `make_trit(t)` | constructors | n/a |
| `_as_truth_vector(x)` / `_as_any_vector(x)` | coercions | n/a |
| `defuzzify_trit(v, iters=10, beta=2.0)` | three-way β-sharpening polarizer | **shipped** — runtime uses `for _t in range(int(iters))` over the structural iters parameter (substrate-pure per Audit #4); β is the trainable scalar, exposed at Sutra source via `intrinsic function fuzzy defuzzify_trit(fuzzy v, number iters, number beta);` in `stdlib/logic.su`. See the §9 Special-call entry for the harness measurement |

### Number constructors

| Method | Description | Training |
|---|---|---|
| `make_real(x)` | real-axis constructor | n/a |
| `make_complex(re, im)` | complex constructor | n/a |
| `make_char(codepoint)` | char (alias for `make_string` of length 1) | n/a |
| `is_string(v)` | flag check (`is_char` alias retired 2026-07-08) | n/a |

### Complex arithmetic (matmul-based, substrate-pure)

| Method | Description | Training |
|---|---|---|
| `_swap_ri_matrix`, `_cm_real_matrix`, `_cm_imag_matrix`, `_conj_matrix`, `_broadcast_real_matrix` | precomputed complex-mul matrices | n/a |
| `complex_mul(a, b)` | complex multiply | vision |
| `complex_add(a, b)` | complex add | vision |
| `complex_sub(a, b)` | complex subtract | vision |
| `complex_div(a, b)` | complex divide | vision |
| `_as_complex_vector(x)` | coerce to complex | n/a |

### String runtime (synthetic-axis codepoint array)

| Method | Description | Training |
|---|---|---|
| `_string_axis(char_index)` | axis index for a char position | n/a |
| `string_max_length()` / `_str_axes()` | capacity helpers | n/a |
| `make_string(s)` | construct String | n/a |
| `is_string(v)` | flag check | n/a |
| `string_length(v)` | length | n/a |
| `string_char_at(v, i)` | codepoint at index | n/a |
| `string_concat(a, b)` | concatenate | n/a |
| `int_to_string(n)` | integer → String formatter (mod-free two-floor digit extraction, sign slot, leading-zero gating; exact to 7 digits at float32 / 15 at float64) | n/a |
| `string_to_python(v)` | decode for monitoring | n/a (debug/monitor) |

### Transcendentals (substrate-pure: lookup + eigenrotation + matrix multiplication)

| Method | Description | Training |
|---|---|---|
| `_st(x)`, `_lerp(xt, xs, values, dx)` | scalar substrate primitives | n/a |
| `_e_real()`, `_e_imag()` | precomputed Euler constants | n/a |
| `_cnum(x)`, `_re(z)`, `_im(z)`, `_mk(r0, i0)` | complex helpers | n/a |
| `_exp_table(x)`, `_ln_table(x)` | lookup tables | **vision** — learned lookup-table contents |
| `_trig_reduce(x)`, `_cos0(theta)`, `_sin0(theta)` | trig helpers | n/a |
| `realExp(z)`, `imaginaryExp(z)`, `cexp(z)` | complex exponential | vision (via learned exp table) |
| `exp(x)` | real exponential | vision |
| `ccos(z)`, `cos(x)`, `sin(x)`, `tan(x)` | trig | vision |
| `log(x)` | natural log | vision |
| `pow(x, y)`, `sqrt(x)` | power / square root | vision |
| `sinh(x)`, `cosh(x)`, `tanh(x)` | hyperbolic | vision |

### Rounding (single-instruction substrate ops)

| Method | Description | Training |
|---|---|---|
| `floor(x)`, `ceil(x)`, `round(x)`, `trunc(x)` | rounding | n/a |
| `abs(x)`, `sign(x)` | sign | n/a |

### Modulus family

| Method | Description | Training |
|---|---|---|
| `fmod(x, m)` | truncation mod (`%`) | n/a |
| `rotation_mod(x, m)` | eigenrotation floor-mod (`Math.mod`) | vision — learned rotation seed |
| `sawtooth_mod(x, m, n_terms=16)` | Fourier-series smooth mod | vision — learned `n_terms` |

### Eigenrotation loop runner

| Method | Description | Training |
|---|---|---|
| `_step(state, R, target, halted, k, threshold, eps)` | one loop tick | vision — learned `threshold` and `k` (sharpening rate) |
| `loop(initial_state, rotation, compiled_prototypes, ...)` | full eigenrotation loop | vision — learned `max_iters`, halt operator, cell update |

### Comparison / equality

| Method | Description | Training |
|---|---|---|
| `gt(a, b)` | tanh-smooth greater-than | vision — learned smooth-sign sharpness |
| `eq(a, b)` | cosine equality on the truth axis | **shipped** (via the `==` operator's T scalar) |
| `eq_synthetic(a, b)` | equality on the synthetic block | vision |
| `neq_synthetic(a, b)` | inverse | vision |

### Introspection accessors — being removed (no readout by design)

Sutra has **no way to read a value off the substrate** — by design there is no
logging, monitoring, or debugging readout. The former accessors `component()`,
`semantic()`, `synthetic()`, `real()`, `imag()`, `truth()` (and `norm`)
compiled to a host read (`float(v[...].item())`), which ran the rest of the
computation on the CPU and **detached the autograd graph** — so any program
that touched them was neither substrate-pure nor end-to-end differentiable.
They are being removed from the parser, codegen, and runtime (decided
2026-06-07). A substrate program is verified substrate-to-substrate, not by
reading values out.

### Axons

| Method | Description | Training |
|---|---|---|
| `axon_new()` | empty axon | n/a |
| `axon_add(axon, key, value)` | append a key-value pair | vision — learned per-key binding rotation |
| `axon_project(axon, requested_keys)` | filter to requested keys (lazy delivery) | n/a |
| `axon_item(axon, key)` | retrieve by key | vision |
| `_axon_permutation_for(role_vec)` | per-key permutation | vision |
| `_axon_permute_synthetic(vec, perm)` / `_axon_unpermute_synthetic(vec, perm)` | permutation application | n/a |

### Promises (no-external-producer synchronous runtime)

| Method | Description | Training |
|---|---|---|
| `resolve(value)`, `reject(reason)` | constructors | n/a |
| `isFulfilled(p)`, `isRejected(p)`, `isPending(p)` | state check | n/a |
| `value(p)`, `reason(p)` | extract | n/a |
| `await_value(p)` | get value (substrate-pure) | n/a |

### JavaScript coercion (operates on JavaScriptObject and subclasses)

`wrap(value)`, `js_add(a, b)`, `js_strict_eq(a, b)`, `js_strict_neq(a, b)`, `js_loose_eq(a, b)`, `js_loose_neq(a, b)`, `js_lt(a, b)`, `js_gt(a, b)`, `js_le(a, b)`, `js_ge(a, b)`, `js_truthy(a)`, `js_typeof(a)`.

**Training:** vision — JS-coercion thresholds and string-vs-number coercion rules have trainable scalars.

---

## 15. Stdlib classes and their methods

| File | Class | Members | Training |
|---|---|---|---|
| `logic.su` | (free) | `defuzzy(fuzzy)`, `logical_not`, `logical_and`, `logical_or`, `logical_nand`, `logical_xor`, `logical_xnor`, `lt(complex,complex)`, `ge`, `le`, `intrinsic gt`, `intrinsic make_truth(number)`, `intrinsic truth_axis(vector)` | per-op (see §13) |
| `numbers.su` | `Numbers extends vector` | `make_real(number)`, `make_complex(number, number)`, `make_char(int)`, `complex_mul(complex, complex)` | n/a |
| `strings.su` | `String extends vector` | `make_string(string)`, `string_length(String)`, `string_char_at(String, int)`, `is_string(vector)`, `string_concat(String, String)`, `operator +(String, String)` | n/a |
| `strings.su` | `Character extends String` | (empty body — 1-length String) | n/a |
| `modulus.su` | `Math extends vector` | `floor`, `ceil`, `round`, `trunc`, `abs`, `sign`, `rotation_mod`, `sawtooth_mod`, `fmod`, `static method mod(x, m)` → `rotation_mod` | n/a / vision per row |
| `math.su` | `Math extends vector` | `realExp`, `imaginaryExp`, `ccos`, `cexp` (literate), `exp`, `log`, `ln`, `cos`, `sin`, `pow` (literate), `sqrt` (literate), `tan`, `sinh`, `cosh`, `tanh` (all literate) | vision (per the underlying lookup table) |
| `vectors.su` | — | spec/pseudocode for `bind`, `unbind`, `bundle`, `permute`, `permutation_key`, `identity_permutation`, `compose` — all blocked-on-intrinsics; runtime-implemented on `_VSA` | per-runtime-method |
| `memory.su` | (free + class) | `hashmap_new()`, `hashmap_set(acc, key, value)`, `hashmap_get(acc, key)`; `class Memory extends vector { static intrinsic method vector zero_vector(); }` | vision (per the hashmap entries above) |
| `similarity.su` | (free) | `neq(vector, vector)`, `intrinsic eq(vector, vector)`, `intrinsic similarity(vector, vector)` | **shipped** for `eq` via the `==` T |
| `tensor.su` | `Tensor extends vector` | `MatrixMul`/`matmul`, `TensorProduct`/`tensor_product`, `Outer`/`outer`, `Dot`/`dot`, `Transpose`/`transpose`, `Norm`/`norm`, `Normalize`/`normalize`, `RotationFor`/`rotation_for` (PascalCase + snake_case both available) | vision |
| `axons.su` | `Axon extends vector` | `axon_new()`, `axon_add(Axon, string, vector)`, `axon_item(Axon, string)` | vision |
| `embed.su` | `Embedding extends vector` | `embed(string)` | vision (per-string fine-tune) |
| `promises.su` | `Promise extends vector` | `resolve`, `reject`, `isFulfilled`, `isRejected`, `isPending`, `value`, `reason`, `await_value`; `then`/`catch`/`all`/`race` are spec-only (deferred — need lambdas) | n/a |
| `javascript_object.su` | `JavaScriptObject extends vector` | `wrap`, `js_add`, `js_strict_eq`, `js_strict_neq`, `js_loose_eq`, `js_loose_neq`, `js_lt`, `js_gt`, `js_le`, `js_ge`, `js_truthy`, `js_typeof` | vision per-op |
| `javascript_primitives.su` | `JavaScriptString extends String`, `JavaScriptInt extends int`, `JavaScriptFloat extends float`, `JavaScriptBool extends bool` | empty bodies — structural-only subclasses for dispatch | n/a |
| `rotation.su` | — | spec-only pseudocode for `make_random_rotation`, `compile_prototypes`, `eigenrotation_loop` (runtime backing lives on `_VSA`) | vision (per-runtime) |
| `bigint.su` | `BigInt extends vector` (+ free `bigint_add`) | `bigint_add(vector, vector)` literate wrapper over the `digit_array_add` substrate intrinsic (Hillis-Steele-style carry propagation, radix 10); class is a type-name wrapper for digit-array values | vision per `digit_array_add` |

---

## 16. AST node types (complete enumeration)

Every concrete `class` in the AST:

**Base:** `Node` (carries `span`). **Types:** `TypeRef`.

**Literals (Expr):** `IntLiteral`, `FloatLiteral`, `ImaginaryLiteral`, `ComplexLiteral`, `StringLiteral`, `CharLiteral`, `BoolLiteral`, `UnknownLiteral`, `WaitLiteral`, `InterpolatedString`, `Identifier`, `ThisExpr`.

**Composite expressions:** `MemberAccess`, `Call`, `NewExpr`, `CastExpr`, `UnsafeCastExpr`, `UnsafeOverrideExpr`, `DefuzzyExpr`, `EmbedExpr`, `BinaryOp`, `UnaryOp`, `AwaitExpr`, `PostfixOp`, `Assignment`, `Parenthesized`, `ArrayLiteral`, `Subscript`, `MapLiteral`.

**Statements (Stmt):** `Block`, `ExprStmt`, `ReturnStmt`, `IfStmt`, `WhileStmt`, `ForStmt`, `ForeachStmt`, `LoopStmt`, `DoWhileStmt`, `TryStmt`, `PassStmt`, `LoopCallStmt`, `VarDecl`.

**Loop function machinery:** `LoopStateParam`, `LoopFunctionDecl`, `ReplaceMarker`.

**Declarations:** `Modifiers`, `Param`, `FunctionDecl`, `MethodDecl`, `FieldDecl`, `ClassDecl`.

**Module:** `Module` (`items: List[TopLevel]`, `span`).

**Training: n/a** — AST nodes are compiler infrastructure.

---

## 17. SDK / tooling packages

| Package | Status | Surface |
|---|---|---|
| `sutra-compiler` | active (canonical) | parser, validator, codegen, runtime; CLI entry via `python -m sutra_compiler` |
| `sutra-from-ts` | active | TypeScript → Sutra transpiler |
| `sutra-from-c` | parked (back of todo) | skeleton only, two test fixtures, design doc |
| `intellij-sutra` | active | IntelliJ plugin — lexer, parser definition, external annotator, syntax highlighter, color settings, commenter, brace matcher, completion contributor, quote handler, file type, language, MCP surface, run configuration, embedding-space visualizer, workspace model, live templates |
| `vscode-sutra` | active | VS Code extension — `extension.ts`, tmLanguage grammar, snippets, language configuration, embedding visualizer HTML |

Top-level CLI front-end: `sutrac.py`.

**Training: n/a** — tooling.

---

## 18. Examples (`examples/*.su`)

`analogy.su`, `analogy_minilm.su`, `analogy_mxbai.su`, `axon_demo.su`, `axon_escape_demo.su`, `classes_demo.su`, `classifier.su`, `class_static_dispatch.su`, `class_with_fields.su`, `do_while_adder.su`, `fuzzy_branching.su`, `fuzzy_dispatch.su`, `hello_world.su`, `imperative_reversible.su`, `king_queen_naive.su`, `knowledge_graph.su`, `logical_connectives.su`, `nearest_phrase.su`, `parse_int2.su`, `predicate_lookup.su`, `protein_record.su`, `review_demo.su`, `role_filler_record.su`, `rotation_book_catalog.su`, `rotation_hashmap.su`, `rotation_record.su`, `sequence.su`, `string_demo.su`, `tensor_ops.su`, `tutorial.su`, `void_method_demo.su`, `wait_keyword_demo.su`.

**Training: n/a** for the example shape; some examples (`classifier.su`, `parse_int2.su`) are baseline source for training experiments referenced in §13–§14.

---

## What's not on this page (yet)

- **Test corpus fixtures.** The compiler's regression-test corpus is exhaustively numbered but not user-relevant; it's intentionally omitted from this user-facing inventory.
- **Internal compiler symbols not exposed to source.** Functions on the compiler side (CST → AST helpers, span trackers, etc.) are intentionally omitted.
- **Anything not listed here that you find in the code.** If you find an implemented thing in `.su` source or a runtime `_VSA` method that isn't on this page, that's a bug in this page; [open an issue](https://github.com/EmmaLeonhart/Sutra/issues).

---

## Summary of trainable status

- **Shipped (4):**
    1. **Equality `==` cosine scalar T** (2026-05-26): trains a per-program T scaling the cosine inside `is_X(x) = (T*sim(x,own)) && !(T*sim(x,others))`; ~1.08× margin gain on K=5 embed-protos.
    2. **Defuzz β** (2026-05-28): trains the sharpening rate inside `defuzzify_trit`; ~15× loss reduction; β\* = 6.58 ± 0.17 across 3 seeds; round-trip 1.19e-7.
    3. **Rank-k `is_X` K=2** (2026-05-27): trains K×k vector prototypes + K×k scalar gains per class; 3.01× margin improvement on K=2 smoke.
    4. **Select softmax temperature** (2026-05-28): trains T inside `select([s_i/T for i], [opt_i for i])`; +1.77× margin gain on K=5 orthogonal-protos; round-trip 3.58e-07. CE surface is bimodal in T (global min at small +T, spurious basin at T<0); lr=0.005 default stays in the correct basin.
- **Vision (many):** essentially every other surface listed above where "Training: vision" appears — each is a trainable surface in principle whose harness has not been written. Per the design vision, the long-arc goal is for every operation to have a shipped trainable form; today we have four. Each new shipped instance is a step toward the picture where the entire program is back-propagatable from a learned neural network into legible Sutra source.
