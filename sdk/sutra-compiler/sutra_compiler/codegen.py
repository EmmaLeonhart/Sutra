"""AST -> Python source translator — DEPRECATED numpy backend.

**STATUS: DEPRECATED.** PyTorch is the canonical codegen target.
This file emits a `_NumpyVSA` runtime class and is retained only
as an emit-shape reference for the tests; new code should use
`codegen_pytorch.PyTorchCodegen`.

It still provides:

- The literal-lowering hooks (`_char_literal_src`, `_embed_expr_src`,
  `_bool_literal_src`, `_equality_src`, `_complex_mul_src`, etc.)
  that `PyTorchCodegen` inherits from. These are backend-agnostic
  (they emit `_VSA.X(...)` calls; both runtime classes implement
  the same method names).
- The `_emit_prelude` numpy runtime emit, which a few tests
  (`test_codegen.py`, `test_inliner.py`) still assert against for
  emit-shape verification.
- (Previously: `_translate_eigenrotation_loop` numpy-specific
  override; removed 2026-05-10 along with the dead base-class
  helpers — the C-style `loop(cond)` / `while` / `for` surface
  no longer reaches codegen.)

**Migration path** (queue item 6): move literal hooks into
`BaseCodegen`, make `PyTorchCodegen` extend `BaseCodegen` directly,
then delete this file. Tests that assert on numpy-specific emit
shapes either move to PyTorch-equivalent assertions or get retired.

**For new test code:** import `PyTorchCodegen` from
`codegen_pytorch` and use `cg.translate(module)`. The runtime
emit (the `_TorchVSA` class) is the same shape as `_NumpyVSA`
with torch tensors instead of numpy ndarrays.

`snap` is not supported here (this substrate has no cleanup circuit).
"""

from __future__ import annotations

from typing import List

from . import ast_nodes as ast
from .codegen_base import BaseCodegen, CodegenNotSupported


class Codegen(BaseCodegen):
    """Emits a self-contained Sutra module against the default runtime.

    Overrides the prelude and rejects `snap()` at codegen time. Everything
    else (function bodies, bind/bundle/unbind/similarity/argmax_cosine,
    map lookup, loop unrolling) is inherited unchanged.
    """

    # Frozen-LLM substrate. The numpy backend runs on frozen LLM
    # embeddings via Ollama — no random-vector fallback. If Ollama is
    # unavailable or the model is missing, compiled programs raise.
    # Default model: nomic-embed-text (768-dim). mxbai-embed-large
    # has a documented attention-sink defect on diacritics and is
    # used in the paper as a known-broken baseline rather than a
    # default substrate.
    DEFAULT_LLM_MODEL = "nomic-embed-text"
    DEFAULT_LLM_DIM = 768
    DEFAULT_SYNTHETIC_DIM = 100

    def __init__(self, *, runtime_dim: int | None = None,
                 runtime_seed: int = 42,
                 llm_model: str | None = None,
                 synthetic_dim: int | None = None,
                 loop_max_iterations: int = 50) -> None:
        self._llm_model = llm_model if llm_model is not None else self.DEFAULT_LLM_MODEL
        # `runtime_dim` now names the SEMANTIC subspace size (the block
        # the LLM fills). Synthetic dims are appended on top. Total
        # runtime vector size = semantic + synthetic, stored on the
        # parent as `runtime_dim` so downstream plumbing (the prelude's
        # `dim=...` literal) sees the full extended state.
        if runtime_dim is None:
            runtime_dim = self.DEFAULT_LLM_DIM
        self._semantic_dim = runtime_dim
        self._synthetic_dim = (synthetic_dim if synthetic_dim is not None
                               else self.DEFAULT_SYNTHETIC_DIM)
        # List of strings that appear in `basis_vector("...")` calls,
        # populated by translate_module() between simplify and codegen.
        # The codegen emits a batched Ollama pre-fetch at module init
        # to replace N sequential HTTP round-trips with one call.
        self._prefetch_strings: list[str] = []
        super().__init__(
            runtime_dim=self._semantic_dim + self._synthetic_dim,
            runtime_seed=runtime_seed,
            loop_max_iterations=loop_max_iterations,
        )

    # Ops not supported by the pure-numpy substrate. `snap` requires a
    # cleanup circuit (MB spiking model or equivalent); rotation-based
    # loop primitives need the same. These are spec'd ops without a
    # runtime implementation here; programs that use them are rejected
    # at codegen time.
    _UNSUPPORTED_BUILTINS = frozenset({
        "snap",
        "make_rotation",
        "compile_prototypes",
        "geometric_loop",
    })

    def _char_literal_src(self, expr: ast.CharLiteral) -> str:
        """Lower `'a'` to a runtime make_char call with the code point."""
        return f"_VSA.make_char({int(expr.value)})"

    def _embed_expr_src(self, expr: ast.EmbedExpr) -> str:
        """Lower `embed(<inner>)` to a _VSA.embed runtime call.

        Covers both explicit `embed("foo")` source-level calls and
        implicit wrappings inserted by `_auto_embed_var_decl_init`
        (`vector v = "foo"` → `vector v = embed("foo")`).
        """
        inner_src = self._translate_expr(expr.expr)
        return f"_VSA.embed({inner_src})"

    def _defuzzy_expr_src(self, expr: ast.DefuzzyExpr) -> str:
        """Lower `defuzzy(<inner>)` by compile-time expansion of the
        stdlib `defuzzy` body.

        The canonical stdlib definition (stdlib/logic.su) is:

            function fuzzy defuzzy(fuzzy v) {
                loop (10) {
                    v = v == true;
                }
                return v;
            }

        We emit that unrolled inline as a nested expression: ten
        `_VSA.eq(_, make_truth(1.0))` calls wrapping the truth-axis
        projection of the input. Expressing it as one compound
        expression lets the downstream fusion pass see the whole
        chain — a runtime `for _ in range(10)` loop hides the
        iteration from the compiler. When the fusion pass lands it
        collapses this nested chain into a single cached matrix
        applied in one matmul; until then it's ten eq calls
        straight-line in the emitted Python.
        """
        DEFUZZ_ITERS = 10
        inner_src = self._translate_expr(expr.expr)
        acc = (f"_VSA._truth_projector() @ "
               f"_VSA._as_any_vector({inner_src})")
        for _ in range(DEFUZZ_ITERS):
            acc = f"_VSA.eq({acc}, _VSA.make_truth(1.0))"
        return acc

    def _unknown_literal_src(self, expr: ast.UnknownLiteral) -> str:
        """Lower `unknown` to the truth-axis neutral vector.

        `unknown` is the explicit-neutrality literal — identical
        runtime to `make_truth(0.0)` but named semantically. In a
        trit-typed context the fold in _fuzzy_literal_init_src will
        redirect through `make_trit(0.0)` for emitted-source
        readability; in any other context this direct lowering is
        used.
        """
        return "_VSA.make_truth(0.0)"

    def _imaginary_literal_src(self, expr: ast.ImaginaryLiteral) -> str:
        """Lower `5i` to `_VSA.make_complex(0.0, 5.0)`."""
        return f"_VSA.make_complex(0.0, {float(expr.value)!r})"

    def _bool_literal_src(self, expr: ast.BoolLiteral) -> str:
        """Lower `true` / `false` to truth-axis vectors unconditionally.

        The base class emits Python `True` / `False`; numpy overrides
        so the entire demo-path runtime operates on vectors, not on
        Python bools. This is the prerequisite for the logical
        operators being pure vector arithmetic — if `true` is a
        Python bool there's no vector to operate on.

        `true`  → _VSA.make_truth( 1.0)
        `false` → _VSA.make_truth(-1.0)
        """
        return f"_VSA.make_truth({1.0 if expr.value else -1.0!r})"

    def _logical_op_src(self, expr: ast.BinaryOp, op: str,
                        left_src: str, right_src: str) -> str:
        """Unreachable under the v0.3 pipeline. `&&` / `||` are lowered
        to stdlib `logical_and` / `logical_or` Call nodes by the
        operator-lowering pass in `inliner.py`, then inlined to the
        Lagrange-polynomial expression form. If this hook fires,
        operator lowering didn't run and the inlined polynomial is
        missing — loud failure is better than silently emitting a
        call to a runtime method that no longer exists."""
        raise CodegenNotSupported(
            expr,
            f"codegen saw a `{expr.op}` BinaryOp that the stdlib "
            f"operator-lowering pass should have replaced with a "
            f"Call(logical_{'and' if op == 'and' else 'or'}, ...). "
            f"Check that `inline_stdlib_calls` ran before codegen.",
        )

    def _logical_not_src(self, expr: ast.UnaryOp, operand_src: str) -> str:
        """Unreachable under the v0.3 pipeline — see _logical_op_src."""
        raise CodegenNotSupported(
            expr,
            "codegen saw a `!` UnaryOp that the stdlib operator-"
            "lowering pass should have replaced with a Call("
            "logical_not, ...). Check that `inline_stdlib_calls` ran "
            "before codegen.",
        )

    def _equality_src(self, expr: ast.BinaryOp, op: str,
                      left_src: str, right_src: str) -> str:
        """Lower `==` / `!=` to _VSA.eq / _VSA.neq.

        Synthetic-axis-encoded operands (int / float / complex / char /
        string) route through `eq_synthetic` / `neq_synthetic` per the
        2026-05-08 user directive: Euclidean distance + tanh rather
        than cosine similarity, since cosine doesn't distinguish well
        between values that share direction but differ in magnitude.
        Embedding-vector operands keep cosine — direction is the
        meaningful signal there.
        """
        assert op in ("eq", "neq")
        if (self._is_synthetic_axis_expr(expr.left)
                and self._is_synthetic_axis_expr(expr.right)):
            return f"_VSA.{op}_synthetic({left_src}, {right_src})"
        return f"_VSA.{op}({left_src}, {right_src})"

    def _complex_mul_src(self, expr: ast.BinaryOp,
                        left_src: str, right_src: str) -> str:
        """Lower `complex * *` to _VSA.complex_mul.

        The runtime reads the two relevant (real, imag) scalar pairs,
        computes the complex product in 2D, and returns a fresh
        make_complex vector. Scalar operands get auto-promoted via
        make_real inside complex_mul, so `int_literal * complex_var`
        and similar mixed forms work without additional codegen.
        """
        return f"_VSA.complex_mul({left_src}, {right_src})"

    def _complex_add_src(self, expr: ast.BinaryOp,
                        left_src: str, right_src: str) -> str:
        """Lower `complex + *` to _VSA.complex_add. Both operands get
        coerced to complex tensors first (`_as_complex_vector`), so a
        scalar `1.0` becomes `1 + 0i` rather than broadcasting across
        the imag axis and corrupting it."""
        return f"_VSA.complex_add({left_src}, {right_src})"

    def _complex_sub_src(self, expr: ast.BinaryOp,
                        left_src: str, right_src: str) -> str:
        """Lower `complex - *` to _VSA.complex_sub. Same coercion
        pattern as complex_add — scalar second operand is wrapped via
        `make_real` so subtraction only touches the real axis."""
        return f"_VSA.complex_sub({left_src}, {right_src})"

    def _complex_div_src(self, expr: ast.BinaryOp,
                        left_src: str, right_src: str) -> str:
        """Lower `complex / *` to _VSA.complex_div. Element-wise
        division is wrong for complex: `(a+bi)/(c+di) = ((ac+bd) +
        (bc-ad)i)/(c²+d²)`. The runtime computes the proper closed
        form on the real/imag axes."""
        return f"_VSA.complex_div({left_src}, {right_src})"

    def _comparison_src(self, expr: ast.BinaryOp, op: str,
                        left_src: str, right_src: str) -> str:
        """Lower `>` / `<` / `>=` / `<=` to _VSA.gt / _VSA.lt / _VSA.ge / _VSA.le.

        All four runtime methods project both sides onto the real
        axis, subtract, and map the sign componentwise onto the
        truth axis. Strict (gt / lt) give -1 on ties, non-strict
        (ge / le) give +1 on ties.
        """
        assert op in ("gt", "lt", "ge", "le")
        return f"_VSA.{op}({left_src}, {right_src})"

    def _complex_literal_src(self, expr: ast.ComplexLiteral) -> str:
        """Lower the folded `N + Mi` form to `_VSA.make_complex(N, M)`."""
        return f"_VSA.make_complex({float(expr.re)!r}, {float(expr.im)!r})"

    # Three-valued primitive class — same truth-axis storage as
    # `fuzzy`, but defuzzification polarizes toward {-1, 0, +1}
    # instead of just {-1, +1}. The distinguishing runtime op is
    # defuzzify_trit, not the storage layout.
    _TRIT_TYPE_NAMES = frozenset({"trit"})

    def _fuzzy_literal_init_src(self, decl: ast.VarDecl) -> str | None:
        """Compile-time fold of `fuzzy x = <literal>` to make_truth(value).

        `fuzzy x = 0.7` is the 2026-04-23 design's implicit form for
        `fuzzy x = true * 0.7` — a truth-axis vector scaled by 0.7. Since
        `true` lives at +1 on the truth axis, this reduces at compile
        time to a direct `_VSA.make_truth(0.7)` allocation with no
        runtime scalar multiplication.

        Bool literals use the truth-axis polarity: `true` → +1.0,
        `false` → -1.0. Unary `-` on a numeric literal is folded too
        so `fuzzy x = -0.3` works. Only triggers for literal initializers
        — non-literal RHS expressions (e.g. `fuzzy x = compute()`) fall
        through to normal codegen.

        `trit x = 0.7` uses the same fold but emits `make_trit` —
        same storage, different compile-time tag. The three-valued
        distinguishing behavior lives in defuzzify_trit, not here.
        """
        if decl.initializer is None:
            return None
        if decl.type_ref is None:
            return None
        type_name = decl.type_ref.name
        # Complex-typed slot with a literal initializer: lift the
        # real/imag scalar into a single make_complex call. Per user
        # direction ("every number is on the complex plane"), a plain
        # int or float in a `complex` slot coerces to (value, 0);
        # `5i` → (0, 5), `5 + 5i` → (5, 5) via the simplify fold.
        if type_name == "complex":
            return self._complex_init_src(decl.initializer)
        if type_name == "fuzzy":
            ctor = "make_truth"
        elif type_name in self._TRIT_TYPE_NAMES:
            ctor = "make_trit"
        else:
            return None
        scalar = self._fuzzy_constant_scalar(decl.initializer)
        if scalar is None:
            return None
        return f"_VSA.{ctor}({scalar!r})"

    def _complex_init_src(self, expr: ast.Expr) -> str | None:
        """Fold a literal initializer for a `complex`-typed slot.

        Covers: IntLiteral / FloatLiteral (real-only), ImaginaryLiteral
        (imag-only), ComplexLiteral (both), unary ± on same,
        Parenthesized wrappers. Returns None to fall through to normal
        codegen for non-literal RHS.
        """
        if isinstance(expr, ast.ComplexLiteral):
            return f"_VSA.make_complex({float(expr.re)!r}, {float(expr.im)!r})"
        if isinstance(expr, ast.ImaginaryLiteral):
            return f"_VSA.make_complex(0.0, {float(expr.value)!r})"
        if isinstance(expr, (ast.IntLiteral, ast.FloatLiteral)):
            return f"_VSA.make_complex({float(expr.value)!r}, 0.0)"
        if isinstance(expr, ast.UnaryOp) and expr.op in ("-", "+"):
            inner = self._complex_init_src(expr.operand)
            if inner is None:
                return None
            if expr.op == "+":
                return inner
            # Unary minus — re-parse the inner to flip sign. Cheapest
            # path: recompute from the operand shape directly.
            if isinstance(expr.operand, ast.ComplexLiteral):
                return (
                    f"_VSA.make_complex({(-float(expr.operand.re))!r}, "
                    f"{(-float(expr.operand.im))!r})"
                )
            if isinstance(expr.operand, ast.ImaginaryLiteral):
                return (
                    f"_VSA.make_complex(0.0, "
                    f"{(-float(expr.operand.value))!r})"
                )
            if isinstance(expr.operand, (ast.IntLiteral, ast.FloatLiteral)):
                return (
                    f"_VSA.make_complex({(-float(expr.operand.value))!r}, "
                    "0.0)"
                )
        if isinstance(expr, ast.Parenthesized):
            return self._complex_init_src(expr.inner)
        return None

    def _fuzzy_constant_scalar(self, expr: ast.Expr) -> float | None:
        """Fold a literal expression to a single fuzzy-axis scalar.

        Accepts int/float/bool literals, the `unknown` neutral
        literal, and unary `-` on same. Returns None for anything
        that needs runtime evaluation.
        """
        if isinstance(expr, ast.FloatLiteral):
            return float(expr.value)
        if isinstance(expr, ast.IntLiteral):
            return float(expr.value)
        if isinstance(expr, ast.BoolLiteral):
            return 1.0 if expr.value else -1.0
        if isinstance(expr, ast.UnknownLiteral):
            return 0.0
        if isinstance(expr, ast.UnaryOp) and expr.op == "-":
            inner = self._fuzzy_constant_scalar(expr.operand)
            if inner is not None:
                return -inner
        if isinstance(expr, ast.UnaryOp) and expr.op == "+":
            return self._fuzzy_constant_scalar(expr.operand)
        if isinstance(expr, ast.Parenthesized):
            return self._fuzzy_constant_scalar(expr.inner)
        return None

    # _translate_eigenrotation_loop and the related _extract_loop_*
    # helpers were removed 2026-05-10 — the C-style `loop(cond)` /
    # `while` / `for` surface is rejected at codegen now in favor of
    # the function-decl loop forms (do_while/while_loop/...). See
    # planning/sutra-spec/control-flow.md §"Loops" and the audit
    # finding 2026-05-10-spec-implementation-audit.md (F2).

    _VECTOR_ACCESSORS = frozenset({
        "component", "semantic", "synthetic",
        "real", "imag", "truth",
    })

    def _translate_call(self, call: ast.Call) -> str:
        callee = call.callee
        if isinstance(callee, ast.Identifier):
            if callee.name in self._UNSUPPORTED_BUILTINS:
                raise CodegenNotSupported(
                    call,
                    f"`{callee.name}` is not supported on the pure-numpy "
                    f"substrate (no cleanup circuit at runtime)",
                )
        if (isinstance(callee, ast.MemberAccess)
                and callee.member in self._VECTOR_ACCESSORS):
            obj_src = self._translate_expr(callee.obj)
            arg_srcs = [self._translate_expr(a) for a in call.args]
            joined = ", ".join([obj_src, *arg_srcs])
            return f"_VSA.{callee.member}({joined})"
        return super()._translate_call(call)

    def _emit_prelude(self) -> None:
        self._emit('"""Generated by sutra_compiler.codegen. Do not edit by hand."""')
        self._emit("from __future__ import annotations")
        self._emit()
        self._emit("import numpy as _np")
        self._emit()
        self._emit()
        self._emit("class SutraMathOverflow(Exception):")
        self._indent += 1
        self._emit('"""Raised when a Sutra transcendental (Math.exp, Math.log,')
        self._emit('Math.sqrt, Math.pow) is called with an input outside the')
        self._emit('precomputed lookup-table range. See the same class on the')
        self._emit('PyTorch backend; numpy and torch backends raise the same')
        self._emit('exception type for caller-side uniformity.')
        self._emit('"""')
        self._emit("pass")
        self._indent -= 1
        self._emit()
        self._emit()
        self._emit("class _NumpyVSA:")
        self._indent += 1
        self._emit('"""Frozen-LLM-backed VSA runtime. Rotation binding, normalized bundle.')
        self._emit('')
        self._emit('State vectors carry an extended layout: each vector is')
        self._emit('`[semantic (semantic_dim) | synthetic (synthetic_dim)]`. The')
        self._emit('semantic block is filled by `embed()` from the frozen LLM; the')
        self._emit('synthetic block is reserved computational/symbolic space that')
        self._emit('starts zero and is touched only by operations that explicitly')
        self._emit('write to it. See')
        self._emit('planning/findings/2026-04-21-extended-state-and-rotation-binding.md.')
        self._emit('')
        self._emit('Bind is role-seeded Haar-random orthogonal rotation applied to')
        self._emit('filler: bind(filler, role) = Q_role @ filler, with Q_role cached')
        self._emit('by role-vector hash. The rotation is block-diagonal — Haar in')
        self._emit('the semantic block, identity in the synthetic block — so rotation')
        self._emit('acts only on semantic content and the synthetic block is')
        self._emit('preserved through bind/unbind. Unbind is the transpose.')
        self._emit('"""')
        self._emit()
        self._emit("def __init__(self, semantic_dim, synthetic_dim, seed, llm_model):")
        self._indent += 1
        self._emit("self.semantic_dim = semantic_dim")
        self._emit("self.synthetic_dim = synthetic_dim")
        self._emit("self.dim = semantic_dim + synthetic_dim")
        self._emit("self.seed = seed")
        self._emit("self.llm_model = llm_model")
        self._emit("self._codebook = {}")
        self._emit("# Rotation matrix cache: role-vector-hash -> orthogonal matrix.")
        self._emit("# Generating a 768x768 Haar rotation is O(d^3); caching makes")
        self._emit("# repeated bind/unbind with the same role O(d^2) lookup + matmul.")
        self._emit("self._rot_cache = {}")
        self._emit("# On-disk embedding cache. Second-and-later runs load every")
        self._emit("# previously-seen basis_vector(...) string from disk instead of")
        self._emit("# hitting Ollama. Cache is keyed by (model, dim) so changing")
        self._emit("# either invalidates cleanly (different cache file).")
        self._emit("import os as _os")
        self._emit("self._cache_dir = _os.path.join(")
        self._indent += 1
        self._emit("_os.environ.get('XDG_CACHE_HOME', _os.path.expanduser('~/.cache')),")
        self._emit("'sutra', 'embeddings')")
        self._indent -= 1
        self._emit("_os.makedirs(self._cache_dir, exist_ok=True)")
        self._emit("# Sanitize model name for use as filename.")
        self._emit("_safe_model = llm_model.replace('/', '_').replace(':', '_')")
        self._emit("self._cache_path = _os.path.join(")
        self._indent += 1
        self._emit("self._cache_dir, f'{_safe_model}-d{self.dim}.npz')")
        self._indent -= 1
        self._emit("self._load_disk_cache()")
        self._emit("# Transcendental lookup tables — substrate-pure interpolation per")
        self._emit("# planning/findings/2026-05-10-interpolated-lookup-table-works.md.")
        self._emit("# Same shape as the PyTorch backend; out-of-range inputs raise")
        self._emit("# SutraMathOverflow.")
        self._emit("self._EXP_LO, self._EXP_HI, self._EXP_N = -10.0, 10.0, 16384")
        self._emit("self._EXP_XS = _np.linspace(self._EXP_LO, self._EXP_HI, self._EXP_N, dtype=_np.float64)")
        self._emit("self._EXP_VALUES = _np.exp(self._EXP_XS)")
        self._emit("self._EXP_DX = (self._EXP_HI - self._EXP_LO) / (self._EXP_N - 1)")
        self._emit("self._LN_LO, self._LN_HI, self._LN_N = 1e-3, 1e3, 16384")
        self._emit("self._LN_XS = _np.linspace(self._LN_LO, self._LN_HI, self._LN_N, dtype=_np.float64)")
        self._emit("self._LN_VALUES = _np.log(self._LN_XS)")
        self._emit("self._LN_DX = (self._LN_HI - self._LN_LO) / (self._LN_N - 1)")
        self._emit("# Trig tables — periodic so modulo-reduce input to [-π, π].")
        self._emit("import math as _math")
        self._emit("self._TRIG_LO, self._TRIG_HI, self._TRIG_N = -_math.pi, _math.pi, 4096")
        self._emit("self._TRIG_XS = _np.linspace(self._TRIG_LO, self._TRIG_HI, self._TRIG_N, dtype=_np.float64)")
        self._emit("self._SIN_VALUES = _np.sin(self._TRIG_XS)")
        self._emit("self._COS_VALUES = _np.cos(self._TRIG_XS)")
        self._emit("self._TRIG_DX = (self._TRIG_HI - self._TRIG_LO) / (self._TRIG_N - 1)")
        self._emit("self._TWO_PI = 2.0 * _math.pi")
        self._emit("# Math namespace constants — PI and TAU = 2*PI as scalars; E")
        self._emit("# beta-reduces live to _VSA.exp(1.0) at the call site.")
        self._emit("self.PI = float(_math.pi)")
        self._emit("self.TAU = 2.0 * float(_math.pi)")
        self._indent -= 1
        self._emit()
        self._emit("def _load_disk_cache(self):")
        self._indent += 1
        self._emit('"""Populate self._codebook from the on-disk embedding cache.')
        self._emit('')
        self._emit("Tolerant of a missing or corrupt cache file — a failed load")
        self._emit("leaves self._codebook empty and lets Ollama fetches repopulate")
        self._emit("it. The cache is performance, not correctness.")
        self._emit('"""')
        self._emit("import os as _os")
        self._emit("if not _os.path.exists(self._cache_path):")
        self._indent += 1
        self._emit("return")
        self._indent -= 1
        self._emit("try:")
        self._indent += 1
        self._emit("with _np.load(self._cache_path, allow_pickle=False) as data:")
        self._indent += 1
        self._emit("for key in data.files:")
        self._indent += 1
        self._emit("self._codebook[key] = data[key].astype(_np.float64)")
        self._indent -= 1
        self._indent -= 1
        self._indent -= 1
        self._emit("except Exception:")
        self._indent += 1
        self._emit("# Corrupt cache: ignore and let Ollama repopulate.")
        self._emit("self._codebook = {}")
        self._indent -= 1
        self._indent -= 1
        self._emit()
        self._emit("def _write_disk_cache(self):")
        self._indent += 1
        self._emit('"""Persist self._codebook atomically to disk.')
        self._emit('')
        self._emit("Writes to a tempfile then renames, so a partial write (crash,")
        self._emit("SIGKILL) leaves the old cache intact rather than corrupted.")
        self._emit("Called whenever embed / embed_batch fetches new vectors so")
        self._emit("subsequent runs hit the cache on module init.")
        self._emit('"""')
        self._emit("import os as _os, tempfile as _tempfile")
        self._emit("if not self._codebook:")
        self._indent += 1
        self._emit("return")
        self._indent -= 1
        self._emit("fd, tmp = _tempfile.mkstemp(")
        self._indent += 1
        self._emit("dir=self._cache_dir, prefix='.tmp-', suffix='.npz')")
        self._indent -= 1
        self._emit("_os.close(fd)")
        self._emit("try:")
        self._indent += 1
        self._emit("_np.savez(tmp, **self._codebook)")
        self._emit("# _np.savez writes tmp.npz, but tempfile handed us tmp ending")
        self._emit("# in .npz already — reconcile: savez appends .npz only if the")
        self._emit("# path does not already end in .npz. Python tempfile gives us")
        self._emit("# a .npz path, so savez leaves it as-is.")
        self._emit("_os.replace(tmp, self._cache_path)")
        self._indent -= 1
        self._emit("except Exception:")
        self._indent += 1
        self._emit("# Cache-write failure is non-fatal. Remove the tmp and continue.")
        self._emit("try:")
        self._indent += 1
        self._emit("_os.unlink(tmp)")
        self._indent -= 1
        self._emit("except OSError:")
        self._indent += 1
        self._emit("pass")
        self._indent -= 1
        self._indent -= 1
        self._indent -= 1
        self._emit()
        self._emit("def embed(self, name):")
        self._indent += 1
        self._emit('"""Frozen-LLM embedding via Ollama. No random fallback.')
        self._emit("If Ollama is unavailable or the model is missing, this raises.")
        self._emit("The numpy backend is defined as running on frozen LLM embeddings;")
        self._emit("a random-vector fallback is not Sutra.")
        self._emit("")
        self._emit("Output is the extended-state-vector layout:")
        self._emit("`[semantic (semantic_dim) | zeros (synthetic_dim)]`. The semantic")
        self._emit("block is the LLM embedding (truncated or zero-padded to")
        self._emit("semantic_dim as needed); the synthetic block is reserved and")
        self._emit('starts at zero."""')
        self._emit("if name not in self._codebook:")
        self._indent += 1
        self._emit("import ollama")
        self._emit("r = ollama.embed(model=self.llm_model, input=name)")
        self._emit("v = _np.array(r['embeddings'][0], dtype=_np.float64)")
        self._emit("# Mean-center. Raw LLM embeddings cluster in a cone (all-")
        self._emit("# positive-ish); centering keeps rotation/bind algebra")
        self._emit("# well-behaved.")
        self._emit("v = v - _np.mean(v)")
        self._emit("n = _np.linalg.norm(v)")
        self._emit("if n > 0: v = v / n")
        self._emit("# Fit the LLM output to the semantic block. Truncate if the")
        self._emit("# LLM is wider than semantic_dim, zero-pad if narrower.")
        self._emit("if v.shape[0] > self.semantic_dim:")
        self._indent += 1
        self._emit("v = v[:self.semantic_dim]")
        self._indent -= 1
        self._emit("elif v.shape[0] < self.semantic_dim:")
        self._indent += 1
        self._emit("v = _np.concatenate([v, _np.zeros(self.semantic_dim - v.shape[0])])")
        self._indent -= 1
        self._emit("# Append the synthetic block — reserved, starts zero.")
        self._emit("v = _np.concatenate([v, _np.zeros(self.synthetic_dim)])")
        self._emit("n = _np.linalg.norm(v)")
        self._emit("if n > 0: v = v / n")
        self._emit("self._codebook[name] = v")
        self._emit("self._write_disk_cache()")
        self._indent -= 1
        self._emit("return self._codebook[name].copy()")
        self._indent -= 1
        self._emit()
        self._emit("def embed_batch(self, names):")
        self._indent += 1
        self._emit('"""Batched Ollama embed: one HTTP round-trip for many names.')
        self._emit('')
        self._emit("Populates self._codebook for every name in `names` that isn't")
        self._emit("already cached. Subsequent embed(name) calls hit the cache in")
        self._emit("memory with no network round-trip. Replaces N sequential")
        self._emit("embed() calls at module init with one batched call; real")
        self._emit("wall-clock win on programs with many basis_vector strings.")
        self._emit('"""')
        self._emit("missing = [n for n in names if n not in self._codebook]")
        self._emit("if not missing:")
        self._indent += 1
        self._emit("return")
        self._indent -= 1
        self._emit("import ollama")
        self._emit("r = ollama.embed(model=self.llm_model, input=missing)")
        self._emit("for i, name in enumerate(missing):")
        self._indent += 1
        self._emit("v = _np.array(r['embeddings'][i], dtype=_np.float64)")
        self._emit("v = v - _np.mean(v)")
        self._emit("n = _np.linalg.norm(v)")
        self._emit("if n > 0: v = v / n")
        self._emit("# Fit to the semantic block, then append the zero-initialized")
        self._emit("# synthetic block. Same layout as embed().")
        self._emit("if v.shape[0] > self.semantic_dim:")
        self._indent += 1
        self._emit("v = v[:self.semantic_dim]")
        self._indent -= 1
        self._emit("elif v.shape[0] < self.semantic_dim:")
        self._indent += 1
        self._emit("v = _np.concatenate([v, _np.zeros(self.semantic_dim - v.shape[0])])")
        self._indent -= 1
        self._emit("v = _np.concatenate([v, _np.zeros(self.synthetic_dim)])")
        self._emit("n = _np.linalg.norm(v)")
        self._emit("if n > 0: v = v / n")
        self._emit("self._codebook[name] = v")
        self._indent -= 1
        self._emit("# One batched write after all fetches in this call.")
        self._emit("self._write_disk_cache()")
        self._indent -= 1
        self._emit()
        self._emit("def _role_hash(self, role_vec):")
        self._indent += 1
        self._emit('"""Deterministic uint32 seed from a role vector.')
        self._emit('')
        self._emit("Uses the float64 bytes of the vector, so tiny numerical noise")
        self._emit("produces the same seed as long as the vector is bit-identical.")
        self._emit("Bit-level determinism is what we want here — callers should")
        self._emit("not retrieve via a different-but-similar role; that's what")
        self._emit("hashmap_get's continuous-projection path is for.")
        self._emit('"""')
        self._emit("import hashlib")
        self._emit("h = hashlib.blake2b(role_vec.tobytes(), digest_size=8).digest()")
        self._emit("return int.from_bytes(h, 'little') & 0xFFFFFFFF")
        self._indent -= 1
        self._emit()
        self._emit("def _rotation_for(self, role_vec):")
        self._indent += 1
        self._emit('"""Block-diagonal Haar-random orthogonal matrix seeded by the role.')
        self._emit('')
        self._emit("Haar-uniform in the semantic block (top-left semantic_dim x")
        self._emit("semantic_dim), identity in the synthetic block (bottom-right")
        self._emit("synthetic_dim x synthetic_dim). Bind and unbind therefore rotate")
        self._emit("only the semantic content and leave the synthetic block fixed —")
        self._emit("which is what the extended-state-vector design requires: the")
        self._emit("synthetic block is reserved for computational/symbolic state and")
        self._emit("rotation bind must not mix semantic content into it.")
        self._emit('')
        self._emit("Cached per role-hash so the same role always produces the same")
        self._emit("rotation — required for bind/unbind round-trip.")
        self._emit('"""')
        self._emit("key = self._role_hash(role_vec)")
        self._emit("if key not in self._rot_cache:")
        self._indent += 1
        self._emit("rng = _np.random.RandomState(key)")
        self._emit("A = rng.randn(self.semantic_dim, self.semantic_dim)")
        self._emit("Q_sem, _R = _np.linalg.qr(A)")
        self._emit("# Flip sign of rows where R's diagonal was negative, so the QR")
        self._emit("# output is Haar-uniform rather than biased by the QR sign.")
        self._emit("d = _np.sign(_np.diag(_R))")
        self._emit("d[d == 0] = 1.0")
        self._emit("Q_sem = Q_sem * d")
        self._emit("# Block-diagonal: Q_sem on the semantic block, identity elsewhere.")
        self._emit("Q = _np.eye(self.dim, dtype=_np.float64)")
        self._emit("Q[:self.semantic_dim, :self.semantic_dim] = Q_sem")
        self._emit("self._rot_cache[key] = Q")
        self._indent -= 1
        self._emit("return self._rot_cache[key]")
        self._indent -= 1
        self._emit()
        self._emit("def bind(self, role, filler):")
        self._indent += 1
        self._emit("# Rotation binding. Role-first convention matches the majority")
        self._emit("# of .su demos (analogy, fuzzy_dispatch, knowledge_graph, etc.):")
        self._emit("#   bind(role, filler) = Q_role @ filler")
        self._emit("# Q_role is the Haar-random rotation seeded by the role vector.")
        self._emit("Q = self._rotation_for(role)")
        self._emit("return Q @ filler")
        self._indent -= 1
        self._emit()
        self._emit("def unbind(self, role, record):")
        self._indent += 1
        self._emit("# Role-first, matching bind. Q is orthogonal so inverse = transpose:")
        self._emit("#   unbind(role, record) = Q_role^T @ record")
        self._emit("# For the matched-pair term in the bundle,")
        self._emit("#   Q_role^T @ Q_role @ filler = filler exactly.")
        self._emit("# Other bundled terms appear as Q_role^T @ Q_other @ ... which")
        self._emit("# is random-ish noise with ~1/sqrt(d) magnitude per term.")
        self._emit("Q = self._rotation_for(role)")
        self._emit("return Q.T @ record")
        self._indent -= 1
        self._emit()
        self._emit("def bundle(self, *vectors):")
        self._indent += 1
        self._emit("s = _np.sum(vectors, axis=0)")
        self._emit("n = _np.linalg.norm(s)")
        self._emit("return s / n if n > 0 else s")
        self._indent -= 1
        self._emit()
        self._emit("def zero_vector(self):")
        self._indent += 1
        self._emit('"""Zero vector in the runtime dim.')
        self._emit('')
        self._emit("Emitted by the simplifier for identities that resolve to zero")
        self._emit("(e.g. displacement(a, a) → zero, bundle(zero_vector()) absorbed).")
        self._emit("Also the starting accumulator for hashmap_new; kept as its own")
        self._emit("method so future substrates can override (e.g. a connectome")
        self._emit("backend's no-spike state instead of numeric zero).")
        self._emit('"""')
        self._emit("return _np.zeros(self.dim, dtype=_np.float64)")
        self._indent -= 1
        self._emit()
        self._emit("def bundle_of_binds(self, *role_filler_pairs):")
        self._indent += 1
        self._emit('"""Fused bind+sum+normalize over N role-filler pairs.')
        self._emit('')
        self._emit("Emitted by the compiler when every arg to bundle() is itself")
        self._emit("a bind() call. The N binds are independent (no shared state),")
        self._emit("so executing them as a batch instead of sequentially is")
        self._emit("correct and ~Nx faster on GPU-class hardware.")
        self._emit("")
        self._emit("numpy implementation: stack the per-role rotation matrices")
        self._emit("into (N, d, d), stack fillers into (N, d), batched einsum")
        self._emit("for the bind, sum over N, normalize. Same result as sequential")
        self._emit("bind+sum+normalize, in a single einsum + reduce.")
        self._emit("")
        self._emit("This is the independence-structure case that justified")
        self._emit("the PyTorch/GPU backend: the fused form collapses N small")
        self._emit("kernel launches into O(1) big ones.")
        self._emit('"""')
        self._emit("if not role_filler_pairs:")
        self._indent += 1
        self._emit("return self.zero_vector()")
        self._indent -= 1
        self._emit("roles = [rf[0] for rf in role_filler_pairs]")
        self._emit("fillers = [rf[1] for rf in role_filler_pairs]")
        self._emit("Q_stack = _np.stack([self._rotation_for(r) for r in roles])  # (N, d, d)")
        self._emit("F_stack = _np.stack([_np.asarray(f, dtype=_np.float64) for f in fillers])  # (N, d)")
        self._emit("# Batched bind: element-i is Q_i @ f_i; shape (N, d).")
        self._emit("bound = _np.einsum('nij,nj->ni', Q_stack, F_stack)")
        self._emit("s = bound.sum(axis=0)")
        self._emit("n = _np.linalg.norm(s)")
        self._emit("return s / n if n > 0 else s")
        self._indent -= 1
        self._emit()
        self._emit("# ---- Rotation-hashmap (library pattern per open question) ----")
        self._emit("#")
        self._emit("# Prototype of the rotation-hashmap described in")
        self._emit("# planning/open-questions/rotation-hashmap-as-language-feature.md.")
        self._emit("# Implemented as runtime methods — accessed by test scripts, not")
        self._emit("# wired into the .su surface syntax yet. If the mechanism works,")
        self._emit("# this is evidence for Candidate A (first-class map<K,V>); if")
        self._emit("# capacity is poor, evidence for Candidate B (library-only).")
        self._emit()
        self._emit("def hashmap_new(self):")
        self._indent += 1
        self._emit('"""Empty accumulator — a zero vector in the runtime dim."""')
        self._emit("return _np.zeros(self.dim, dtype=_np.float64)")
        self._indent -= 1
        self._emit()
        self._emit("def hashmap_set(self, acc, key_vec, val_vec):")
        self._indent += 1
        self._emit('"""Store val under key: acc + bind(key, val).')
        self._emit('')
        self._emit("Reuses the same role-seeded Haar rotation as bind itself, so")
        self._emit("the hashmap has identical capacity / cross-talk behavior as a")
        self._emit("bundle of role-filler pairs. The only difference from bind + ")
        self._emit("bundle is the API — the caller doesn't have to construct the")
        self._emit("bundle themselves; set() just accumulates additively.")
        self._emit("")
        self._emit("Storage is additive WITHOUT normalization. Normalizing after")
        self._emit("every set would destroy the magnitude information downstream")
        self._emit("retrieval depends on. Normalize at retrieval time if needed.")
        self._emit("")
        self._emit("LIMITATION: key lookup is by bit-identical hash of key_vec, so")
        self._emit("soft lookup (noisy query key -> approximate recovery) does NOT")
        self._emit("work with this prototype. A continuous-hash variant using")
        self._emit("Householder reflections or learned projections would enable")
        self._emit("soft lookup; future work per the open question.")
        self._emit('"""')
        self._emit("return acc + self.bind(key_vec, val_vec)")
        self._indent -= 1
        self._emit()
        self._emit("def hashmap_get(self, acc, key_vec):")
        self._indent += 1
        self._emit('"""Retrieve val associated with key: unbind(key, acc).')
        self._emit('')
        self._emit("Returns the raw recovered vector; caller applies cleanup")
        self._emit("(argmax_cosine against a codebook) or uses it directly.")
        self._emit("Cross-talk from other stored entries appears as noise with")
        self._emit("~1/sqrt(d) magnitude per other entry. For N stored entries")
        self._emit("and a d-dim substrate, recovered signal-to-noise is ~1/sqrt(N).")
        self._emit('"""')
        self._emit("return self.unbind(key_vec, acc)")
        self._indent -= 1
        self._emit()
        self._emit("# ---- Promise runtime methods ----")
        self._emit("# Promise<T> is a vector wearing one of two synthetic-axis flags.")
        self._emit("# See planning/sutra-spec/promises.md §'The three states'.")
        self._emit()
        self._emit("def resolve(self, value):")
        self._indent += 1
        self._emit('"""Promise.resolve(value) — already-fulfilled promise."""')
        self._emit("v = _np.asarray(value, dtype=_np.float64).copy()")
        self._emit("v[self.semantic_dim + self.AXIS_PROMISE_FULFILLED] = 1.0")
        self._emit("v[self.semantic_dim + self.AXIS_PROMISE_REJECTED] = 0.0")
        self._emit("return v")
        self._indent -= 1
        self._emit()
        self._emit("def reject(self, reason):")
        self._indent += 1
        self._emit('"""Promise.reject(reason) — already-rejected promise."""')
        self._emit("v = _np.asarray(reason, dtype=_np.float64).copy()")
        self._emit("v[self.semantic_dim + self.AXIS_PROMISE_FULFILLED] = 0.0")
        self._emit("v[self.semantic_dim + self.AXIS_PROMISE_REJECTED] = 1.0")
        self._emit("return v")
        self._indent -= 1
        self._emit()
        self._emit("def isFulfilled(self, p):")
        self._indent += 1
        self._emit("return float(p[self.semantic_dim + self.AXIS_PROMISE_FULFILLED])")
        self._indent -= 1
        self._emit()
        self._emit("def isRejected(self, p):")
        self._indent += 1
        self._emit("return float(p[self.semantic_dim + self.AXIS_PROMISE_REJECTED])")
        self._indent -= 1
        self._emit()
        self._emit("def isPending(self, p):")
        self._indent += 1
        self._emit("f = float(p[self.semantic_dim + self.AXIS_PROMISE_FULFILLED])")
        self._emit("r = float(p[self.semantic_dim + self.AXIS_PROMISE_REJECTED])")
        self._emit("return 1.0 - max(f, r)")
        self._indent -= 1
        self._emit()
        self._emit("def value(self, p):")
        self._indent += 1
        self._emit('"""Read the resolved value with channel flags zeroed out."""')
        self._emit("v = p.copy()")
        self._emit("v[self.semantic_dim + self.AXIS_PROMISE_FULFILLED] = 0.0")
        self._emit("v[self.semantic_dim + self.AXIS_PROMISE_REJECTED] = 0.0")
        self._emit("return v")
        self._indent -= 1
        self._emit()
        self._emit("def reason(self, p):")
        self._indent += 1
        self._emit('"""Read the rejection reason with channel flags zeroed out."""')
        self._emit("v = p.copy()")
        self._emit("v[self.semantic_dim + self.AXIS_PROMISE_FULFILLED] = 0.0")
        self._emit("v[self.semantic_dim + self.AXIS_PROMISE_REJECTED] = 0.0")
        self._emit("return v")
        self._indent -= 1
        self._emit()
        self._emit("def await_value(self, p):")
        self._indent += 1
        self._emit('"""await — exact reduction of the spec-2 while_loop')
        self._emit("(no external axon producer mutates p mid-spin, so the")
        self._emit("spin's empty body yields p unchanged and the loop's")
        self._emit("terminal read is exactly value(p)). Audit REAL LEAK #3")
        self._emit("removed: prior body was a host bounded poll loop with a")
        self._emit("host branch on the pending predicate. See the pytorch")
        self._emit("backend for the full spec-justification docstring.")
        self._emit('"""')
        self._emit("return self.value(p)")
        self._indent -= 1
        self._emit()
        self._emit("# ---- Binding-array (substrate-stored ordered list) ----")
        self._emit("#")
        self._emit("# An array stores N scalar values in a single substrate vector,")
        self._emit("# with a length prefix at index 0. Layout:")
        self._emit("#   arr[0] = length (number of valid elements)")
        self._emit("#   arr[1..length] = the elements (in order)")
        self._emit("# Capacity is fixed at allocation time (the vector's full length")
        self._emit("# minus 1). foreach_loop walks 0..length-1 and binds each element")
        self._emit("# to the `element` keyword in the body.")
        self._emit("#")
        self._emit("# Used by foreach_loop. Pure tensor reads/writes; no Python list,")
        self._emit("# no heap allocation beyond the initial vector.")
        self._emit()
        self._emit("def array_from_literal(self, *values):")
        self._indent += 1
        self._emit('"""Build an array from compile-time-known scalar values."""')
        self._emit("arr = _np.zeros(len(values) + 1, dtype=_np.float64)")
        self._emit("arr[0] = float(len(values))")
        self._emit("for i, v in enumerate(values):")
        self._indent += 1
        self._emit("arr[1 + i] = float(v)")
        self._indent -= 1
        self._emit("return arr")
        self._indent -= 1
        self._emit()
        self._emit("def array_length(self, arr):")
        self._indent += 1
        self._emit('"""Read the length prefix as an int."""')
        self._emit("return int(arr[0])")
        self._indent -= 1
        self._emit()
        self._emit("def array_get(self, arr, i):")
        self._indent += 1
        self._emit('"""Read element at index i (0-based). Returns substrate scalar.')
        self._emit('')
        self._emit("Returns the underlying numpy scalar rather than a Python float so")
        self._emit("downstream arithmetic stays in substrate land. Indexing arithmetic")
        self._emit("(`int(i)`) is the only Python crossing remaining; that's the loop")
        self._emit("tick counter, removable only by full unroll (queue item 5).")
        self._emit('"""')
        self._emit("return arr[1 + int(i)]")
        self._indent -= 1
        self._emit()
        self._emit("# ---- Substrate scalar primitives (boundary-leak reductions) ----")
        self._emit("# Added 2026-04-30 to remove the Python-bool / Python-min crossings")
        self._emit("# in the loop halt check. See planning/findings/")
        self._emit("# 2026-04-30-substrate-purity-leak-enumeration.md.")
        self._emit()
        self._emit("def truth_axis(self, vec_or_scalar):")
        self._indent += 1
        self._emit('"""Read AXIS_TRUTH from a fuzzy-vector result, or pass scalars through.')
        self._emit('')
        self._emit("Returns a substrate scalar (numpy 0-dim) rather than a Python float;")
        self._emit("substrate-pure loop halt checks consume the result without crossing")
        self._emit("the Python boundary.")
        self._emit('"""')
        self._emit("if hasattr(vec_or_scalar, '__len__') and len(vec_or_scalar) > 1:")
        self._indent += 1
        self._emit("return vec_or_scalar[self.semantic_dim + self.AXIS_TRUTH]")
        self._indent -= 1
        self._emit("return _np.asarray(vec_or_scalar)")
        self._indent -= 1
        self._emit()
        self._emit("def heaviside(self, x):")
        self._indent += 1
        self._emit('"""Step function: 1.0 where x > 0, else 0.0. Substrate scalar.')
        self._emit('')
        self._emit("Used by the loop halt check to convert a substrate truth scalar to")
        self._emit("a substrate-resident keep-mask, without Python's `1.0 if x > 0 else")
        self._emit("0.0` ternary.")
        self._emit('"""')
        self._emit("return (_np.asarray(x) > 0.0).astype(_np.float64)")
        self._indent -= 1
        self._emit()
        self._emit("def saturate_unit(self, x):")
        self._indent += 1
        self._emit('"""min(x, 1.0) implemented as a substrate op rather than Python\'s min().')
        self._emit('')
        self._emit("Used by the halt accumulator: halted = saturate_unit(halted +")
        self._emit("halt_term). Numpy minimum() preserves the substrate-scalar dtype")
        self._emit("rather than coercing to Python float.")
        self._emit('"""')
        self._emit("return _np.minimum(_np.asarray(x), 1.0)")
        self._indent -= 1
        self._emit()
        self._emit("# ---- 2D-Givens-per-slot rotation binding (synthetic subspace) ----")
        self._emit("#")
        self._emit("# Design:")
        self._emit("# planning/findings/2026-04-21-extended-state-and-rotation-binding.md")
        self._emit("# Validation:")
        self._emit("# planning/findings/2026-04-24-synthetic-subspace-validation.md")
        self._emit("#")
        self._emit("# Each positional / variable slot gets one disjoint 2D plane in the")
        self._emit("# synthetic subspace, starting after the canonical axes. Slot s uses")
        self._emit("# plane (SLOT_BASE + 2*s, SLOT_BASE + 2*s + 1). A slot-rotation is a")
        self._emit("# 2D Givens rotation in that plane; slots do not overlap (until")
        self._emit("# capacity runs out at synthetic_dim - SLOT_BASE pairs), so retrieval")
        self._emit("# from slot i is orthogonal to content at slot j by construction.")
        self._emit("#")
        self._emit("# Storage / retrieval convention (reversible imperative state):")
        self._emit("#   slot_store(state, s, scalar) = state + scalar * e_{SLOT_BASE+2s}")
        self._emit("#                                  (after zeroing the slot's plane)")
        self._emit("#   slot_load(state, s) = state[SLOT_BASE+2s]   (cosine component)")
        self._emit("#")
        self._emit("# An explicit rotation angle `theta` applied via rotate_slot(s, theta)")
        self._emit("# rotates the scalar by theta into the imaginary leg of the plane,")
        self._emit("# which is what makes assignments reversible as exact inverses.")
        self._emit()
        self._emit("# First synthetic axis used for slot planes. Reserves the canonical")
        self._emit("# axes 0..7 for int/complex/truth/char/loop-flag/promise-fulfilled/")
        self._emit("# promise-rejected/axon-populated.")
        self._emit("SLOT_BASE = 8")
        self._emit()
        self._emit("def _slot_plane(self, slot_idx):")
        self._indent += 1
        self._emit('"""Return (i, j) — the two synthetic-block indices for slot.')
        self._emit('')
        self._emit("Slot 0 -> (SLOT_BASE, SLOT_BASE+1); slot 1 -> (SLOT_BASE+2,")
        self._emit("SLOT_BASE+3); etc. Wraps modulo (synthetic_dim - SLOT_BASE) // 2")
        self._emit("so out-of-capacity slots share planes (capacity-experiment finding:")
        self._emit("sharing beyond N/2 degrades accuracy past ~65% at k=N/2+8).")
        self._emit('"""')
        self._emit("n_planes = (self.synthetic_dim - self.SLOT_BASE) // 2")
        self._emit("if n_planes <= 0:")
        self._indent += 1
        self._emit("raise RuntimeError(")
        self._indent += 1
        self._emit('"synthetic subspace has no room for slot planes; "')
        self._emit('"increase synthetic_dim or SLOT_BASE budget")')
        self._indent -= 1
        self._indent -= 1
        self._emit("s = int(slot_idx) % n_planes")
        self._emit("base = self.semantic_dim + self.SLOT_BASE + 2 * s")
        self._emit("return (base, base + 1)")
        self._indent -= 1
        self._emit()
        self._emit("def slot_store(self, state, slot_idx, scalar):")
        self._indent += 1
        self._emit('"""Write scalar to slot slot_idx. Overwrites the slot\'s plane.')
        self._emit('')
        self._emit("The scalar lives on the real leg of the slot\'s 2D plane; the")
        self._emit("imaginary leg is zeroed. A subsequent slot_load returns the scalar")
        self._emit("exactly. This is the reversible-imperative-state primitive: a")
        self._emit("variable assignment = one slot_store; the inverse is slot_store of")
        self._emit("the previous value. State outside the slot\'s plane is unchanged.")
        self._emit('"""')
        self._emit("i, j = self._slot_plane(slot_idx)")
        self._emit("new = state.copy() if hasattr(state, 'copy') else _np.asarray(state).copy()")
        self._emit("new[i] = float(scalar)")
        self._emit("new[j] = 0.0")
        self._emit("return new")
        self._indent -= 1
        self._emit()
        self._emit("def slot_load(self, state, slot_idx):")
        self._indent += 1
        self._emit('"""Read the scalar stored at slot slot_idx (the real leg).')
        self._emit('')
        self._emit("Returns a substrate scalar (numpy 0-dim from state[i]) rather than a")
        self._emit("Python float — downstream arithmetic stays in substrate land. Other")
        self._emit("slots and semantic content do not contribute; the disjoint-plane")
        self._emit("allocation makes this a projection, not a noisy readout.")
        self._emit('"""')
        self._emit("i, _j = self._slot_plane(slot_idx)")
        self._emit("return state[i]")
        self._indent -= 1
        self._emit()
        self._emit("def rotate_slot(self, state, slot_idx, angle):")
        self._indent += 1
        self._emit('"""Apply a 2D Givens rotation by `angle` in slot slot_idx\'s plane.')
        self._emit('')
        self._emit("Pure rotation in the slot\'s 2D plane; content in other slots, in")
        self._emit("canonical axes, and in the semantic block is untouched. The")
        self._emit("inverse is rotate_slot(state, slot_idx, -angle); applying rotate")
        self._emit("forward and backward on any sequence returns to the starting state")
        self._emit("within floating-point roundoff (validated empirically 2026-04-24,")
        self._emit("100-op sequence: 6e-16 roundtrip error).")
        self._emit('"""')
        self._emit("i, j = self._slot_plane(slot_idx)")
        self._emit("c, s = _np.cos(float(angle)), _np.sin(float(angle))")
        self._emit("new = state.copy() if hasattr(state, 'copy') else _np.asarray(state).copy()")
        self._emit("xi, xj = state[i], state[j]")
        self._emit("new[i] = c * xi - s * xj")
        self._emit("new[j] = s * xi + c * xj")
        self._emit("return new")
        self._indent -= 1
        self._emit()
        self._emit("def similarity(self, a, b):")
        self._indent += 1
        self._emit("na = _np.linalg.norm(a)")
        self._emit("nb = _np.linalg.norm(b)")
        self._emit("# eps-guarded divide — zero-norm case evaluates to 0 without branch.")
        self._emit("return float(_np.dot(a, b) / (na * nb + _np.finfo(_np.float64).tiny))")
        self._indent -= 1
        self._emit()
        # General-purpose tensor operations on vectors and matrices.
        # The Sutra language exposes these via the `Tensor` namespace
        # (stdlib/tensor.su):
        #   Tensor.MatrixMul(A, B)     -> _VSA.matmul
        #   Tensor.TensorProduct(a, b) -> _VSA.tensor_product
        #   Tensor.Outer(a, b)         -> _VSA.outer
        #   Tensor.Dot(a, b)           -> _VSA.dot (scalar)
        #   Tensor.Transpose(M)        -> _VSA.transpose
        # Each is a thin wrapper over numpy; the linear-algebra
        # behavior is whatever numpy does. These are general
        # tensor-algebra primitives, not VSA primitives — bind /
        # unbind / bundle remain the canonical VSA operations.
        self._emit("def matmul(self, a, b):")
        self._indent += 1
        self._emit('"""Matrix multiplication (numpy `a @ b`). Works on 1-D, 2-D, or higher-rank arrays per numpy semantics."""')
        self._emit("return _np.matmul(a, b)")
        self._indent -= 1
        self._emit()
        self._emit("def tensor_product(self, a, b):")
        self._indent += 1
        self._emit('"""Tensor / Kronecker product (numpy `kron`)."""')
        self._emit("return _np.kron(a, b)")
        self._indent -= 1
        self._emit()
        self._emit("def outer(self, a, b):")
        self._indent += 1
        self._emit('"""Vector outer product → rank-2 array."""')
        self._emit("return _np.outer(a, b)")
        self._indent -= 1
        self._emit()
        self._emit("def dot(self, a, b):")
        self._indent += 1
        self._emit('"""Inner / dot product → scalar."""')
        self._emit("return float(_np.dot(a, b))")
        self._indent -= 1
        self._emit()
        # ---- Transcendental intrinsics (numpy backend) — same architecture
        # as the PyTorch backend, see codegen_pytorch.py for the reasoning.
        self._emit("def exp(self, x):")
        self._indent += 1
        self._emit('"""exp(x) on [-10, 10] via interpolated lookup."""')
        self._emit("xv = float(x)")
        self._emit("if xv < self._EXP_LO or xv > self._EXP_HI:")
        self._indent += 1
        self._emit('raise SutraMathOverflow(')
        self._indent += 1
        self._emit('f"Math.exp({xv}) outside table range [{self._EXP_LO}, {self._EXP_HI}]."')
        self._indent -= 1
        self._emit(")")
        self._indent -= 1
        self._emit("d = _np.abs(self._EXP_XS - xv) / self._EXP_DX")
        self._emit("w = _np.maximum(0.0, 1.0 - d)")
        self._emit("return float(_np.dot(w, self._EXP_VALUES))")
        self._indent -= 1
        self._emit()
        self._emit("def log(self, x):")
        self._indent += 1
        self._emit('"""Natural log on [1e-3, 1e3] via interpolated lookup."""')
        self._emit("xv = float(x)")
        self._emit("if xv < self._LN_LO or xv > self._LN_HI:")
        self._indent += 1
        self._emit('raise SutraMathOverflow(')
        self._indent += 1
        self._emit('f"Math.log({xv}) outside table range [{self._LN_LO}, {self._LN_HI}]."')
        self._indent -= 1
        self._emit(")")
        self._indent -= 1
        self._emit("d = _np.abs(self._LN_XS - xv) / self._LN_DX")
        self._emit("w = _np.maximum(0.0, 1.0 - d)")
        self._emit("return float(_np.dot(w, self._LN_VALUES))")
        self._indent -= 1
        self._emit()
        self._emit("def pow(self, x, y):")
        self._indent += 1
        self._emit('"""x ** y via beta-reduction to exp/log: pow(x,y) = exp(y * log(x)). x > 0."""')
        self._emit("return self.exp(float(y) * self.log(x))")
        self._indent -= 1
        self._emit()
        self._emit("def sqrt(self, x):")
        self._indent += 1
        self._emit('"""sqrt(x) = exp(0.5 * log(x)). x > 0."""')
        self._emit("return self.exp(0.5 * self.log(x))")
        self._indent -= 1
        self._emit()
        self._emit("def _trig_reduce(self, x):")
        self._indent += 1
        self._emit('"""Reduce x to (-π, π] via x - 2π * round(x / 2π)."""')
        self._emit("return float(x) - self._TWO_PI * _np.round(float(x) / self._TWO_PI)")
        self._indent -= 1
        self._emit()
        self._emit("def sin(self, x):")
        self._indent += 1
        self._emit('"""sin(x) via interpolated lookup on [-π, π]."""')
        self._emit("xr = self._trig_reduce(x)")
        self._emit("d = _np.abs(self._TRIG_XS - xr) / self._TRIG_DX")
        self._emit("w = _np.maximum(0.0, 1.0 - d)")
        self._emit("return float(_np.dot(w, self._SIN_VALUES))")
        self._indent -= 1
        self._emit()
        self._emit("def cos(self, x):")
        self._indent += 1
        self._emit('"""cos(x) via interpolated lookup on [-π, π]."""')
        self._emit("xr = self._trig_reduce(x)")
        self._emit("d = _np.abs(self._TRIG_XS - xr) / self._TRIG_DX")
        self._emit("w = _np.maximum(0.0, 1.0 - d)")
        self._emit("return float(_np.dot(w, self._COS_VALUES))")
        self._indent -= 1
        self._emit()
        self._emit("def tan(self, x):")
        self._indent += 1
        self._emit('"""tan(x) = sin(x) / cos(x)."""')
        self._emit("c = self.cos(x)")
        self._emit("if c == 0.0:")
        self._indent += 1
        self._emit('return float("inf") if self.sin(x) >= 0 else float("-inf")')
        self._indent -= 1
        self._emit("return self.sin(x) / c")
        self._indent -= 1
        self._emit()
        self._emit("def sinh(self, x):")
        self._indent += 1
        self._emit('"""sinh(x) = (exp(x) - exp(-x)) / 2."""')
        self._emit("return (self.exp(x) - self.exp(-float(x))) * 0.5")
        self._indent -= 1
        self._emit()
        self._emit("def cosh(self, x):")
        self._indent += 1
        self._emit('"""cosh(x) = (exp(x) + exp(-x)) / 2."""')
        self._emit("return (self.exp(x) + self.exp(-float(x))) * 0.5")
        self._indent -= 1
        self._emit()
        self._emit("def tanh(self, x):")
        self._indent += 1
        self._emit('"""tanh(x) = (exp(2x) - 1) / (exp(2x) + 1) — numerically stable form."""')
        self._emit("e2x = self.exp(2.0 * float(x))")
        self._emit("return (e2x - 1.0) / (e2x + 1.0)")
        self._indent -= 1
        self._emit()
        self._emit("def transpose(self, m):")
        self._indent += 1
        self._emit('"""Transpose. For 1-D inputs, returns the input unchanged (numpy convention)."""')
        self._emit("return _np.transpose(m)")
        self._indent -= 1
        self._emit()
        self._emit("def norm(self, v):")
        self._indent += 1
        self._emit('"""L2 norm. Scalar result."""')
        self._emit("return float(_np.linalg.norm(v))")
        self._indent -= 1
        self._emit()
        self._emit("def normalize(self, v):")
        self._indent += 1
        self._emit('"""L2-normalize with an eps-guard so zero-norm input returns zero."""')
        self._emit("n = _np.linalg.norm(v)")
        self._emit("return v / (n + _np.finfo(_np.float64).tiny)")
        self._indent -= 1
        self._emit()
        self._emit("def rotation_for(self, role):")
        self._indent += 1
        self._emit('"""Cached Haar-random orthogonal rotation matrix for the role vector."""')
        self._emit("return self._rotation_for(role)")
        self._indent -= 1
        self._emit()
        # PascalCase aliases — the preferred Sutra-side spelling.
        # Bound at the class level so `_VSA.MatrixMul(a, b)` resolves
        # via Python's descriptor protocol and binds self correctly.
        self._emit("MatrixMul = matmul")
        self._emit("TensorProduct = tensor_product")
        self._emit("Outer = outer")
        self._emit("Dot = dot")
        self._emit("Transpose = transpose")
        self._emit("Norm = norm")
        self._emit("Normalize = normalize")
        self._emit("RotationFor = rotation_for")
        self._emit()
        self._emit("# ---- Vector component accessors (debugging / teaching) ----")
        self._emit("#")
        self._emit("# Lowered from the surface-level method calls `v.component(i)`,")
        self._emit("# `v.semantic(i)`, `v.synthetic(i)`. Zero-indexed. Return a Python")
        self._emit("# float so the value can be printed, compared, or fed back into")
        self._emit("# Sutra as a scalar. Not part of the substrate's algebra — these")
        self._emit("# only exist to make the [semantic | synthetic] layout legible.")
        self._emit()
        self._emit("def component(self, v, i):")
        self._indent += 1
        self._emit('"""Return element i of v over the full extended state vector."""')
        self._emit("return float(v[int(i)])")
        self._indent -= 1
        self._emit()
        self._emit("def semantic(self, v, i):")
        self._indent += 1
        self._emit('"""Return element i of v within the semantic block (0..semantic_dim).')
        self._emit('')
        self._emit("Equivalent to `v.component(i)` while i < semantic_dim, but named")
        self._emit("so the reader can see which subspace is being addressed.")
        self._emit('"""')
        self._emit("idx = int(i)")
        self._emit("if idx < 0 or idx >= self.semantic_dim:")
        self._indent += 1
        self._emit("raise IndexError(")
        self._indent += 1
        self._emit('f"semantic index {idx} out of range [0, {self.semantic_dim})")')
        self._indent -= 1
        self._indent -= 1
        self._emit("return float(v[idx])")
        self._indent -= 1
        self._emit()
        self._emit("def synthetic(self, v, i):")
        self._indent += 1
        self._emit('"""Return element i of v within the synthetic block (0..synthetic_dim).')
        self._emit('')
        self._emit("Equivalent to `v.component(semantic_dim + i)` — the synthetic block")
        self._emit("starts right after the semantic block in the extended state vector.")
        self._emit("Iterating `i` from 0 to synthetic_dim-1 walks the reserved")
        self._emit("computational-state slots.")
        self._emit('"""')
        self._emit("idx = int(i)")
        self._emit("if idx < 0 or idx >= self.synthetic_dim:")
        self._indent += 1
        self._emit("raise IndexError(")
        self._indent += 1
        self._emit('f"synthetic index {idx} out of range [0, {self.synthetic_dim})")')
        self._indent -= 1
        self._indent -= 1
        self._emit("return float(v[self.semantic_dim + idx])")
        self._indent -= 1
        self._emit()
        self._emit("# ---- Canonical synthetic-axis allocation ----")
        self._emit("#")
        self._emit("# First five synthetic axes have designated semantics (per")
        self._emit("# 2026-04-23 + 2026-04-30 design; see")
        self._emit("# planning/findings/2026-04-21-extended-state-and-rotation-binding.md):")
        self._emit("#")
        self._emit("#   synthetic[0] = real component of a number")
        self._emit("#   synthetic[1] = imaginary component of a number")
        self._emit("#   synthetic[2] = truth axis (higher = more true)")
        self._emit("#   synthetic[3] = char-vs-int discriminator flag")
        self._emit("#   synthetic[4] = loop-completion flag (0 = not done, 1 = converged)")
        self._emit("#")
        self._emit("# Pinning the allocation to named class attributes so the layout")
        self._emit("# is legible at runtime and from the REPL.")
        self._emit("#")
        self._emit("# AXIS_LOOP_DONE is the substrate-side completion flag set by the")
        self._emit("# RNN-style branchless loop. It carries the cumulative soft-halt")
        self._emit("# value (in [0, 1]); programs that read this can detect non-")
        self._emit("# convergence without host-side conditionals. Output-gating multiplies")
        self._emit("# value axes by this flag so an incomplete loop emits a zero-vector.")
        self._emit("# Same shape as the broader exception-channel pattern used for")
        self._emit("# divide-by-zero and NaN propagation elsewhere in the runtime.")
        self._emit("AXIS_REAL = 0")
        self._emit("AXIS_IMAG = 1")
        self._emit("AXIS_TRUTH = 2")
        self._emit("AXIS_CHAR_FLAG = 3")
        self._emit("AXIS_LOOP_DONE = 4")
        self._emit("# Promise channel axes — see planning/sutra-spec/promises.md")
        self._emit("# §'The three states' and planning/sutra-spec/axon-io.md.")
        self._emit("AXIS_PROMISE_FULFILLED = 5")
        self._emit("AXIS_PROMISE_REJECTED = 6")
        self._emit("# Axon populated flag — for genuinely-zero values.")
        self._emit("# See planning/sutra-spec/axon-io.md §'all-zeros edge case'.")
        self._emit("AXIS_AXON_POPULATED = 7")
        self._emit()
        self._emit("def real(self, v):")
        self._indent += 1
        self._emit('"""Real component of v — synthetic[AXIS_REAL]."""')
        self._emit("return float(v[self.semantic_dim + self.AXIS_REAL])")
        self._indent -= 1
        self._emit()
        self._emit("def imag(self, v):")
        self._indent += 1
        self._emit('"""Imaginary component of v — synthetic[AXIS_IMAG].')
        self._emit('')
        self._emit("Zero for a purely real number; nonzero for complex. Sutra's")
        self._emit("commitment is first-class complex numbers sharing the allocator")
        self._emit("with int/float — a complex number is just a vector with both")
        self._emit("the real and imaginary synthetic axes populated.")
        self._emit('"""')
        self._emit("return float(v[self.semantic_dim + self.AXIS_IMAG])")
        self._indent -= 1
        self._emit()
        self._emit("def truth(self, v):")
        self._indent += 1
        self._emit('"""Truth value carried by v — synthetic[AXIS_TRUTH].')
        self._emit('')
        self._emit("Higher scalar → more true; lower (including negative) → more")
        self._emit("false. Orthogonal to semantic content and to the real/imag")
        self._emit("axes by construction, so a number's value does not bleed into")
        self._emit("its truth and vice versa.")
        self._emit('"""')
        self._emit("return float(v[self.semantic_dim + self.AXIS_TRUTH])")
        self._indent -= 1
        self._emit()
        self._emit("def make_real(self, x):")
        self._indent += 1
        self._emit('"""Extended-state vector carrying x at synthetic[AXIS_REAL].')
        self._emit('')
        self._emit("The rest of the vector is zero — no semantic content, no")
        self._emit("imaginary component, no truth. Analog of a bare float or int")
        self._emit("literal in the Sutra runtime.")
        self._emit('"""')
        self._emit("v = _np.zeros(self.dim, dtype=_np.float64)")
        self._emit("v[self.semantic_dim + self.AXIS_REAL] = float(x)")
        self._emit("return v")
        self._indent -= 1
        self._emit()
        self._emit("def make_complex(self, re, im):")
        self._indent += 1
        self._emit('"""Extended-state vector carrying (re, im) on the real/imag axes.')
        self._emit('')
        self._emit("A complex number is a vector with synthetic[0] = Re(z) and")
        self._emit("synthetic[1] = Im(z). No separate wrapper type, no parallel")
        self._emit("storage — the extended state vector carries the whole number.")
        self._emit('"""')
        self._emit("v = _np.zeros(self.dim, dtype=_np.float64)")
        self._emit("v[self.semantic_dim + self.AXIS_REAL] = float(re)")
        self._emit("v[self.semantic_dim + self.AXIS_IMAG] = float(im)")
        self._emit("return v")
        self._indent -= 1
        self._emit()
        self._emit("# Three cached matrices for the pure-matmul complex-product form:")
        self._emit("#   _swap_ri    — swaps real and imag axes, zeroes elsewhere")
        self._emit("#   _cm_real    — picks (input.REAL − input.IMAG) into REAL slot")
        self._emit("#   _cm_imag    — picks (input.REAL + input.IMAG) into IMAG slot")
        self._emit("# Combined with one element-wise multiply, they compute the")
        self._emit("# complex product with no scalar extraction — preserving the")
        self._emit("# invariant that matrix operations stay matrix operations all")
        self._emit("# the way down, so chains of complex multiplications can be")
        self._emit("# compile-time-fused into a single matrix.")
        self._emit()
        self._emit("def _swap_ri_matrix(self):")
        self._indent += 1
        self._emit("if not hasattr(self, '_swap_ri_cache') or self._swap_ri_cache is None:")
        self._indent += 1
        self._emit("M = _np.zeros((self.dim, self.dim), dtype=_np.float64)")
        self._emit("r = self.semantic_dim + self.AXIS_REAL")
        self._emit("i = self.semantic_dim + self.AXIS_IMAG")
        self._emit("M[r, i] = 1.0; M[i, r] = 1.0")
        self._emit("self._swap_ri_cache = M")
        self._indent -= 1
        self._emit("return self._swap_ri_cache")
        self._indent -= 1
        self._emit()
        self._emit("def _cm_real_matrix(self):")
        self._indent += 1
        self._emit("if not hasattr(self, '_cm_real_cache') or self._cm_real_cache is None:")
        self._indent += 1
        self._emit("M = _np.zeros((self.dim, self.dim), dtype=_np.float64)")
        self._emit("r = self.semantic_dim + self.AXIS_REAL")
        self._emit("i = self.semantic_dim + self.AXIS_IMAG")
        self._emit("M[r, r] = 1.0; M[r, i] = -1.0")
        self._emit("self._cm_real_cache = M")
        self._indent -= 1
        self._emit("return self._cm_real_cache")
        self._indent -= 1
        self._emit()
        self._emit("def _cm_imag_matrix(self):")
        self._indent += 1
        self._emit("if not hasattr(self, '_cm_imag_cache') or self._cm_imag_cache is None:")
        self._indent += 1
        self._emit("M = _np.zeros((self.dim, self.dim), dtype=_np.float64)")
        self._emit("r = self.semantic_dim + self.AXIS_REAL")
        self._emit("i = self.semantic_dim + self.AXIS_IMAG")
        self._emit("M[i, r] = 1.0; M[i, i] = 1.0")
        self._emit("self._cm_imag_cache = M")
        self._indent -= 1
        self._emit("return self._cm_imag_cache")
        self._indent -= 1
        self._emit()
        self._emit("def complex_mul(self, a, b):")
        self._indent += 1
        self._emit('"""Complex multiplication via pure matmul + element-wise.')
        self._emit('')
        self._emit("Given a = (r1 + i1·i) and b = (r2 + i2·i) encoded as vectors")
        self._emit("with their scalar parts on the real/imag axes, the complex")
        self._emit("product is:")
        self._emit("")
        self._emit("    c = _cm_real @ (a ⊙ b)  +  _cm_imag @ ((_swap_ri @ a) ⊙ b)")
        self._emit("")
        self._emit("where ⊙ is element-wise multiply. No scalar extraction; the")
        self._emit("operation stays in vector space throughout, so a compile-time")
        self._emit("simplifier can fuse chains of complex multiplications (by")
        self._emit("constants) into a single cached matrix.")
        self._emit('"""')
        self._emit("av = self._as_complex_vector(a)")
        self._emit("bv = self._as_complex_vector(b)")
        self._emit("ab = av * bv")
        self._emit("swapped_ab = (self._swap_ri_matrix() @ av) * bv")
        self._emit("return self._cm_real_matrix() @ ab + self._cm_imag_matrix() @ swapped_ab")
        self._indent -= 1
        self._emit()
        self._emit("def complex_add(self, a, b):")
        self._indent += 1
        self._emit('"""Complex addition. Coerces both operands to complex vectors')
        self._emit('first so `complex + scalar` adds to the real axis only')
        self._emit('rather than broadcasting across imag too."""')
        self._emit("return self._as_complex_vector(a) + self._as_complex_vector(b)")
        self._indent -= 1
        self._emit()
        self._emit("def complex_sub(self, a, b):")
        self._indent += 1
        self._emit('"""Complex subtraction. Same coercion pattern as complex_add."""')
        self._emit("return self._as_complex_vector(a) - self._as_complex_vector(b)")
        self._indent -= 1
        self._emit()
        self._emit("def _conj_matrix(self):")
        self._indent += 1
        self._emit('"""Cached d×d matrix that conjugates a complex vector: identity')
        self._emit('on every axis except imag, where it negates."""')
        self._emit("if not hasattr(self, '_conj_cache') or self._conj_cache is None:")
        self._indent += 1
        self._emit("M = _np.eye(self.dim, dtype=_np.float64)")
        self._emit("i = self.semantic_dim + self.AXIS_IMAG")
        self._emit("M[i, i] = -1.0")
        self._emit("self._conj_cache = M")
        self._indent -= 1
        self._emit("return self._conj_cache")
        self._indent -= 1
        self._emit()
        self._emit("def _broadcast_real_matrix(self):")
        self._indent += 1
        self._emit('"""Cached d×d matrix that broadcasts the real-axis value to every')
        self._emit('axis: column real_axis is all-ones, everything else zero."""')
        self._emit("if not hasattr(self, '_br_real_cache') or self._br_real_cache is None:")
        self._indent += 1
        self._emit("M = _np.zeros((self.dim, self.dim), dtype=_np.float64)")
        self._emit("r = self.semantic_dim + self.AXIS_REAL")
        self._emit("M[:, r] = 1.0")
        self._emit("self._br_real_cache = M")
        self._indent -= 1
        self._emit("return self._br_real_cache")
        self._indent -= 1
        self._emit()
        self._emit("def complex_div(self, a, b):")
        self._indent += 1
        self._emit('"""Complex division: (a+bi)/(c+di) = ((ac+bd) + (bc-ad)i)/(c²+d²).')
        self._emit('Substrate-pure — no scalar extraction. conj(b) via _conj_matrix,')
        self._emit('numerator via complex_mul(a, conj_b), denominator c²+d² via')
        self._emit('complex_mul(b, conj_b) (imag part is exactly zero by algebra),')
        self._emit('broadcast across all axes and element-wise divide."""')
        self._emit("av = self._as_complex_vector(a)")
        self._emit("bv = self._as_complex_vector(b)")
        self._emit("conj_b = self._conj_matrix() @ bv")
        self._emit("num = self.complex_mul(av, conj_b)")
        self._emit("denom_complex = self.complex_mul(bv, conj_b)")
        self._emit("denom_vec = self._broadcast_real_matrix() @ denom_complex")
        self._emit("return num / denom_vec")
        self._indent -= 1
        self._emit()
        self._emit("def _as_complex_vector(self, x):")
        self._indent += 1
        self._emit('"""Coerce a Python scalar / vector to complex-plane form."""')
        self._emit("if isinstance(x, _np.ndarray):")
        self._indent += 1
        self._emit("return x")
        self._indent -= 1
        self._emit("if isinstance(x, bool):")
        self._indent += 1
        self._emit("return self.make_real(1.0 if x else 0.0)")
        self._indent -= 1
        self._emit("return self.make_real(float(x))")
        self._indent -= 1
        self._emit()
        self._emit("def make_truth(self, t):")
        self._indent += 1
        self._emit('"""Extended-state vector carrying truth value t at synthetic[AXIS_TRUTH]."""')
        self._emit("v = _np.zeros(self.dim, dtype=_np.float64)")
        self._emit("v[self.semantic_dim + self.AXIS_TRUTH] = float(t)")
        self._emit("return v")
        self._indent -= 1
        self._emit()
        self._emit("def make_char(self, codepoint):")
        self._indent += 1
        self._emit('"""Extended-state vector for a character literal.')
        self._emit('')
        self._emit("Unicode code point at synthetic[AXIS_REAL] (same slot as")
        self._emit("int/float); synthetic[AXIS_CHAR_FLAG] set to 1.0 to")
        self._emit("distinguish `'a'` (97 with flag) from `97` (97 without).")
        self._emit("Arithmetic on chars works the same as on ints — both")
        self._emit("live on the number axis. Downstream code that cares")
        self._emit("about the distinction can read the flag via `is_char`.")
        self._emit('"""')
        self._emit("v = _np.zeros(self.dim, dtype=_np.float64)")
        self._emit("v[self.semantic_dim + self.AXIS_REAL] = float(codepoint)")
        self._emit("v[self.semantic_dim + self.AXIS_CHAR_FLAG] = 1.0")
        self._emit("return v")
        self._indent -= 1
        self._emit()
        self._emit("def is_char(self, v):")
        self._indent += 1
        self._emit('"""True iff v was produced as a character literal."""')
        self._emit("return bool(v[self.semantic_dim + self.AXIS_CHAR_FLAG] >= 0.5)")
        self._indent -= 1
        self._emit()
        self._emit("def make_trit(self, t):")
        self._indent += 1
        self._emit('"""Three-valued primitive class allocated on the truth axis.')
        self._emit('')
        self._emit("Shares storage with `make_truth` — a trit is a truth-axis")
        self._emit("scalar, same as a fuzzy. The difference is compile-time: trit")
        self._emit("values polarize to {-1, 0, +1} under `defuzzify_trit`, whereas")
        self._emit("fuzzy values polarize to {-1, +1}. Use `trit` when the")
        self._emit('"explicitly neutral" case is a first-class meaning you want')
        self._emit("the defuzzifier to preserve, rather than collapse to a pole.")
        self._emit('"""')
        self._emit("return self.make_truth(t)")
        self._indent -= 1
        self._emit()
        self._emit("def defuzzify_trit(self, v, iters=10, beta=2.0):")
        self._indent += 1
        self._emit('"""Three-way differentiable polarizer toward {-1, 0, +1}.')
        self._emit('')
        self._emit("Softmax over exp(-β · (x - pole)²) with poles at -1, 0, +1;")
        self._emit("output is the weighted-mean position. As β grows the weight")
        self._emit("concentrates on the nearest pole, so iterating with β doubling")
        self._emit("each pass sharpens toward a pole without ever binarizing. The")
        self._emit("output stays in [-1, +1] and differentiable — no hard commit.")
        self._emit('')
        self._emit("Semantic mirror of the binary `defuzzify` but with the neutral")
        self._emit("point preserved as a first-class attractor. A trit near zero")
        self._emit("stays near zero; a trit biased toward one of the poles sharpens")
        self._emit("toward that pole.")
        self._emit('"""')
        self._emit("x = float(v[self.semantic_dim + self.AXIS_TRUTH])")
        self._emit("b = float(beta)")
        self._emit("for _ in range(int(iters)):")
        self._indent += 1
        self._emit("w_neg = _np.exp(-b * (x + 1.0) ** 2)")
        self._emit("w_zero = _np.exp(-b * x ** 2)")
        self._emit("w_pos = _np.exp(-b * (x - 1.0) ** 2)")
        self._emit("s = w_neg + w_zero + w_pos")
        self._emit("x = float((-w_neg + w_pos) / s)")
        self._emit("b *= 2.0")
        self._indent -= 1
        self._emit("out = v.copy()")
        self._emit("out[self.semantic_dim + self.AXIS_TRUTH] = x")
        self._emit("return out")
        self._indent -= 1
        self._emit()

        self._emit("# ---- Logical operators — smooth polynomial form ----")
        self._emit("#")
        self._emit("# min and max expressed as degree-4 polynomials derived by")
        self._emit("# Lagrange interpolation on the three-valued grid")
        self._emit("# {-1, 0, +1}². Exact on the grid (all 9 points match min /")
        self._emit("# max) and C^∞ everywhere — no |.|, no kink, no subgradient")
        self._emit("# dispatch. Compile-time simplification passes can apply")
        self._emit("# standard polynomial rewrites without special-casing the")
        self._emit("# absolute-value branches.")
        self._emit("#")
        self._emit("#   min(a, b) = (a + b + ab - a² - b² + a²b²) / 2    elem-wise")
        self._emit("#   max(a, b) = (a + b - ab + a² + b² - a²b²) / 2    elem-wise")
        self._emit("#   not(x)    = -x                                    elem-wise")
        self._emit("#")
        self._emit("# Identities on {-1, 0, +1}:")
        self._emit("#   min(1, 1) = 1     min(0, 0) = 0     min(-1, -1) = -1")
        self._emit("#   min(1, -1) = -1   min(1, 0) = 0     min(-1, 0) = -1")
        self._emit("# (max is the symmetric mirror — swap sign on the odd terms.)")
        self._emit("#")
        self._emit("# For continuous fuzzy values in (-1, +1) these are polynomial")
        self._emit("# approximations to true min / max rather than exact equals —")
        self._emit("# e.g. min(0.7, 0.3) → 0.342 vs true 0.3. Functional")
        self._emit("# completeness on the three-valued set holds regardless.")
        self._emit("#")
        self._emit("# `true` and `false` are vectors too — the _bool_literal_src")
        self._emit("# override emits make_truth(±1) for bool literals, so the")
        self._emit("# entire numpy demo path is vector-native.")
        self._emit("#")
        self._emit("# Unlike JavaScript / TypeScript / C#, these do NOT short-")
        self._emit("# circuit — both sides evaluate because min / max need both.")
        self._emit()
        self._emit("def _as_truth_vector(self, x):")
        self._indent += 1
        self._emit('"""Return x as a vector. Already-a-vector passes through;')
        self._emit("a Python scalar / bool is lifted to make_truth(scalar).")
        self._emit('"""')
        self._emit("if isinstance(x, _np.ndarray):")
        self._indent += 1
        self._emit("return x")
        self._indent -= 1
        self._emit("if isinstance(x, bool):")
        self._indent += 1
        self._emit("return self.make_truth(1.0 if x else -1.0)")
        self._indent -= 1
        self._emit("return self.make_truth(float(x))")
        self._indent -= 1
        self._emit()
        # logical_and / logical_or / logical_not runtime methods were
        # deleted in v0.3 step 4. The operator-lowering pass in
        # `inliner.py` rewrites `&&`, `||`, `!` as Call nodes targeting
        # the stdlib `logical_and` / `logical_or` / `logical_not`
        # functions defined in `stdlib/logic.su`, and the inliner
        # expands those to the inline polynomial forms before codegen
        # runs. No runtime method is needed.

        self._emit("# ---- Ordered comparison — differentiable, no predicate ----")
        self._emit("#")
        self._emit("# `>`, `<`, `>=`, `<=` operate on number-family values by")
        self._emit("# projecting onto the real axis and applying a steep tanh")
        self._emit("# to the difference. Pure tensor arithmetic — no componentwise")
        self._emit("# predicate, no branch, differentiable everywhere. The steep")
        self._emit("# slope at zero means integer differences saturate at ±1;")
        self._emit("# near-ties get a smoothly-varying truth value.")
        self._emit("#")
        self._emit("# Pipeline:")
        self._emit("#   diff      = a - b                      element-wise vec sub")
        self._emit("#   diff_r    = _real_projector @ diff     matmul projection")
        self._emit("#   signed    = tanh(CMP_SLOPE * diff_r)   componentwise smooth sign")
        self._emit("#   result    = _truth_from_real @ signed  matmul placement")
        self._emit("#")
        self._emit("# Strict (`>`, `<`) and non-strict (`>=`, `<=`) collapse on")
        self._emit("# this scheme — the tie case gives tanh(0) = 0 in all four.")
        self._emit("# Programs that need to distinguish strict from tie compose")
        self._emit("# with `==` (cosine similarity, crisp on identical operands).")
        self._emit("#")
        self._emit("# Truth-family operands (bool, fuzzy, trit) are rejected at")
        self._emit("# codegen time — ordered comparison has no natural meaning")
        self._emit("# on the truth axis. Custom classes can override.")
        self._emit()
        self._emit("def _real_projector(self):")
        self._indent += 1
        self._emit('"""Diagonal dim×dim projector onto the real axis. Cached."""')
        self._emit("if not hasattr(self, '_real_proj_cache') or self._real_proj_cache is None:")
        self._indent += 1
        self._emit("M = _np.zeros((self.dim, self.dim), dtype=_np.float64)")
        self._emit("idx = self.semantic_dim + self.AXIS_REAL")
        self._emit("M[idx, idx] = 1.0")
        self._emit("self._real_proj_cache = M")
        self._indent -= 1
        self._emit("return self._real_proj_cache")
        self._indent -= 1
        self._emit()
        self._emit("def _truth_from_real(self):")
        self._indent += 1
        self._emit('"""Matrix that moves the real-axis entry to the truth axis.')
        self._emit('')
        self._emit("Has a single nonzero entry: M[TRUTH, REAL] = 1. Applied to")
        self._emit("a vector with content only at the real axis (the post-sign")
        self._emit("result from a comparison), it places that content at the")
        self._emit("truth axis and zeros everywhere else.")
        self._emit('"""')
        self._emit("if not hasattr(self, '_t_from_r_cache') or self._t_from_r_cache is None:")
        self._indent += 1
        self._emit("M = _np.zeros((self.dim, self.dim), dtype=_np.float64)")
        self._emit("M[self.semantic_dim + self.AXIS_TRUTH,")
        self._indent += 1
        self._emit("self.semantic_dim + self.AXIS_REAL] = 1.0")
        self._indent -= 1
        self._emit("self._t_from_r_cache = M")
        self._indent -= 1
        self._emit("return self._t_from_r_cache")
        self._indent -= 1
        self._emit()
        self._emit("# Slope on the tanh — high enough that integer differences")
        self._emit("# saturate (tanh(100) ≈ 1 to double precision), near-zero")
        self._emit("# differences traverse the smooth region.")
        self._emit("CMP_SLOPE = 100.0")
        self._emit()
        self._emit("def gt(self, a, b):")
        self._indent += 1
        self._emit('"""a > b — differentiable smooth sign on the real-axis difference."""')
        self._emit("av = self._as_complex_vector(a)")
        self._emit("bv = self._as_complex_vector(b)")
        self._emit("diff_r = self._real_projector() @ (av - bv)")
        self._emit("signed = _np.tanh(self.CMP_SLOPE * diff_r)")
        self._emit("return self._truth_from_real() @ signed")
        self._indent -= 1
        self._emit()
        # lt / ge / le runtime methods were deleted in v0.3 step 4.
        # The operator-lowering pass rewrites `<`, `<=`, `>=` as
        # Call nodes targeting stdlib `lt` / `ge` / `le`, and the
        # inliner expands them to `b > a`, `a > b`, `b > a` before
        # codegen — `gt` stays as the single runtime method for the
        # comparison family until gt's own stdlib body unblocks.

        self._emit("# ---- Equality and inequality — vector cosine similarity ----")
        self._emit("#")
        self._emit("# a == b produces a truth-axis vector whose truth coordinate")
        self._emit("# is cos(a, b). Identical vectors → truth +1 (true); opposite")
        self._emit("# vectors → truth -1 (false); orthogonal vectors → truth 0")
        self._emit("# (unknown). Differentiable almost everywhere — the only")
        self._emit("# singularity is at a zero input vector, which we guard with")
        self._emit("# an explicit fallback to truth 0.")
        self._emit("#")
        self._emit("# The reduction (dot product + norms) is the natural shape of")
        self._emit("# the semantic question — 'how similar are these two vectors'")
        self._emit("# — not a scalar-extraction cheat on top of what should have")
        self._emit("# been a vector op. The math lives in vector arithmetic up to")
        self._emit("# the reduction, then places the answer on the truth axis.")
        self._emit()
        self._emit("def eq(self, a, b):")
        self._indent += 1
        self._emit('"""Vector equality — cosine similarity projected onto truth axis.')
        self._emit('')
        self._emit("Pure tensor ops: dot products (matmul), sqrt (tensor), add,")
        self._emit("divide. An eps is added to the denominator so the zero-norm")
        self._emit("case evaluates to 0/eps = 0 (the neutral) without a predicate.")
        self._emit('"""')
        self._emit("av = self._as_any_vector(a)")
        self._emit("bv = self._as_any_vector(b)")
        self._emit("na = _np.sqrt(_np.dot(av, av))")
        self._emit("nb = _np.sqrt(_np.dot(bv, bv))")
        self._emit("# tiny eps (~2.2e-308) guards the divide without branching;")
        self._emit("# at normal norms it's lost in roundoff, at zero norms it")
        self._emit("# makes the result exactly 0 (neutral).")
        self._emit("return self.make_truth(float(_np.dot(av, bv) / (na * nb + _np.finfo(_np.float64).tiny)))")
        self._indent -= 1
        self._emit()
        # Synthetic-axis equality — Euclidean distance + tanh shape
        # (2026-05-08 user directive). Used for int / float / complex /
        # char / string operands where magnitude matters; cosine
        # collapses information for these. Same truth-axis output
        # contract as `eq`.
        self._emit("def eq_synthetic(self, a, b):")
        self._indent += 1
        self._emit('"""Equality for synthetic-axis-encoded values.')
        self._emit('')
        self._emit('Distance d = ||a - b||₂; truth = 1 - 2*tanh(d).')
        self._emit('At d=0 truth=+1 (equal). As d→∞, truth→-1 (not equal).')
        self._emit('Same tanh squash as the truth-axis machinery, just')
        self._emit('routed through Euclidean distance instead of cosine.')
        self._emit('"""')
        self._emit("av = self._as_any_vector(a)")
        self._emit("bv = self._as_any_vector(b)")
        self._emit("diff = av - bv")
        self._emit("dist = _np.sqrt(_np.dot(diff, diff))")
        self._emit("truth = 1.0 - 2.0 * _np.tanh(dist)")
        self._emit("return self.make_truth(float(truth))")
        self._indent -= 1
        self._emit()
        self._emit("def neq_synthetic(self, a, b):")
        self._indent += 1
        self._emit('"""!= for synthetic-axis values — negation of eq_synthetic."""')
        self._emit("return -self.eq_synthetic(a, b)")
        self._indent -= 1
        self._emit()
        # neq runtime method was deleted in v0.3 step 4. `!=` lowers
        # to Call(neq, ...) which inlines to `!(a == b)`; the `!` then
        # lowers to Call(logical_not, ...) and inlines to `0 - _`.
        # Final form: `0 - _VSA.eq(a, b)`. No runtime method needed.

        self._emit("def _as_any_vector(self, x):")
        self._indent += 1
        self._emit('"""Coerce any runtime value to a d-dim vector for comparison.')
        self._emit('')
        self._emit("Vectors pass through. Bool → make_truth(±1). Other scalars →")
        self._emit("make_real(x) (on the number axis, not the truth axis — the")
        self._emit("semantic question 'is 3 == 3.0' is about the number, not the")
        self._emit("truth value). A string falls back to embed() so `s == embed`")
        self._emit("works consistently.")
        self._emit('"""')
        self._emit("if isinstance(x, _np.ndarray):")
        self._indent += 1
        self._emit("return x")
        self._indent -= 1
        self._emit("if isinstance(x, bool):")
        self._indent += 1
        self._emit("return self.make_truth(1.0 if x else -1.0)")
        self._indent -= 1
        self._emit("if isinstance(x, (int, float)):")
        self._indent += 1
        self._emit("return self.make_real(float(x))")
        self._indent -= 1
        self._emit("if isinstance(x, str):")
        self._indent += 1
        self._emit("return self.embed(x)")
        self._indent -= 1
        self._emit("raise TypeError(f'cannot coerce {type(x).__name__} to a vector for comparison')")
        self._indent -= 1
        self._emit()
        self._emit("# ---- Defuzzification — matrix projection + iterated eq ----")
        self._emit("#")
        self._emit("# defuzzify(x, iters=10):")
        self._emit("#   1. Matrix-multiply by the truth-axis projector — a dim×dim")
        self._emit("#      diagonal matrix with a single 1 at the truth axis.")
        self._emit("#      Zeroes every other coordinate, including real/imag/")
        self._emit("#      semantic. Non-truth-axis inputs (int, semantic")
        self._emit("#      vector, char, etc.) go to truth=0 → unknown.")
        self._emit("#   2. Iterate `f = f == true` N times. Under cosine equality")
        self._emit("#      on a truth-axis vector this snaps to ±1 in one pass if")
        self._emit("#      truth≠0, or stays at 0 (the zero-norm guard in eq)")
        self._emit("#      if truth==0. The iteration is kept at 10 for the")
        self._emit("#      user-specified semantics — even though one pass is")
        self._emit("#      enough mathematically, the loop is the definition.")
        self._emit("#")
        self._emit("# Output is a truth-axis vector — a three-valued bool. Identical")
        self._emit("# inputs of type bool/fuzzy/trit will defuzzify to true, false,")
        self._emit("# or unknown depending on the sign of their truth coordinate.")
        self._emit()
        self._emit("def _truth_projector(self):")
        self._indent += 1
        self._emit('"""Diagonal dim×dim projector onto the truth axis. Cached."""')
        self._emit("if not hasattr(self, '_truth_proj_cache') or self._truth_proj_cache is None:")
        self._indent += 1
        self._emit("M = _np.zeros((self.dim, self.dim), dtype=_np.float64)")
        self._emit("idx = self.semantic_dim + self.AXIS_TRUTH")
        self._emit("M[idx, idx] = 1.0")
        self._emit("self._truth_proj_cache = M")
        self._indent -= 1
        self._emit("return self._truth_proj_cache")
        self._indent -= 1
        self._emit()
        # defuzzify runtime method was deleted in v0.3 step 4. The
        # `defuzzy(x)` source form is expanded inline by
        # `_defuzzy_expr_src` above into ten nested `_VSA.eq(...)`
        # calls wrapping the truth-axis projection of the input —
        # matching the stdlib definition in `stdlib/logic.su`.

        self._emit("def make_random_rotation(self, angle, n_planes=1, seed=None):")
        self._indent += 1
        self._emit('"""Block-diagonal Haar rotation, scaled so its largest eigenphase ~= angle.')
        self._emit('')
        self._emit('Haar-uniform in the semantic block, identity in the synthetic')
        self._emit('block — matches the binding-rotation layout so eigenrotation')
        self._emit('loops walk the semantic subspace while the synthetic subspace')
        self._emit('stays untouched.')
        self._emit('')
        self._emit('Uniform-angle Givens composition makes every plane orbit at the')
        self._emit('same frequency, so any trajectory is near-periodic and never')
        self._emit('explores the hypersphere. A Haar-random orthogonal matrix has a')
        self._emit('spectrum of eigenphases and produces quasi-periodic trajectories')
        self._emit('that actually sample the sphere. `angle` and `n_planes` are kept')
        self._emit('in the signature for cross-backend API compatibility.')
        self._emit('"""')
        self._emit("rng = _np.random.RandomState(seed if seed is not None else self.seed)")
        self._emit("A = rng.randn(self.semantic_dim, self.semantic_dim)")
        self._emit("Q_sem, _ = _np.linalg.qr(A)")
        self._emit("# Fractional matrix power via eigendecomposition so the caller")
        self._emit("# can still dial rotation magnitude via `angle`. Q^(angle/pi)")
        self._emit("# interpolates between identity (angle=0) and full Q (angle=pi).")
        self._emit("w, V = _np.linalg.eig(Q_sem)")
        self._emit("phases = _np.angle(w) * (angle / _np.pi)")
        self._emit("R_sem = _np.real((V * _np.exp(1j * phases)) @ _np.linalg.inv(V))")
        self._emit("R = _np.eye(self.dim, dtype=_np.float64)")
        self._emit("R[:self.semantic_dim, :self.semantic_dim] = R_sem")
        self._emit("return R")
        self._indent -= 1
        self._emit()
        self._emit("def compile_prototypes(self, prototype_vectors, frame_seed=None):")
        self._indent += 1
        self._emit('"""Pass-through on the numpy substrate: no KC sparsification here."""')
        self._emit("return dict(prototype_vectors)")
        self._indent -= 1
        self._emit()
        self._emit("def _step(self, state, R, target, halted, k, threshold, eps=1e-12):")
        self._indent += 1
        self._emit('"""RNN cell: one branchless eigenrotation step with soft halt.')
        self._emit('')
        self._emit("Pure tensor ops — multiply, add, divide, exp, minimum. No `if`, no")
        self._emit("control flow. The soft halt indicator (sigmoid) plus monotone")
        self._emit("cumulative halt (clamped at 1) freezes state once convergence is")
        self._emit("reached, without any host-side branch.")
        self._emit('"""')
        self._emit("cand = R @ state")
        self._emit("cand = cand / (_np.linalg.norm(cand) + eps)")
        self._emit("sim = _np.dot(cand, target) / (_np.linalg.norm(target) + eps)")
        self._emit("halt = 1.0 / (1.0 + _np.exp(-k * (sim - threshold)))")
        self._emit("halted = _np.minimum(halted + halt, 1.0)")
        self._emit("state = (1.0 - halted) * cand + halted * state")
        self._emit("return state, halted")
        self._indent -= 1
        self._emit()
        self._emit("def loop(self, initial_state, rotation, compiled_prototypes,")
        self._indent += 1
        self._emit("target_name=None, threshold=0.5, max_iters=50, k=20.0, frame_seed=None):")
        self._emit('"""Branchless RNN-style eigenrotation loop.')
        self._emit('')
        self._emit("Runs `max_iters` cell steps unconditionally — no early exit, no")
        self._emit("host-side `for iters` count, no `if best_score >= threshold`. Soft")
        self._emit("halt freezes state once convergence; output gating zeroes value")
        self._emit("axes if convergence never fires (incomplete output → exception")
        self._emit('channel via AXIS_LOOP_DONE).')
        self._emit('')
        self._emit("Returns (target_name, state, iters_est) where iters_est is a tensor")
        self._emit("scalar approximating the step at which convergence happened.")
        self._emit('"""')
        self._emit("state = initial_state.copy()")
        self._emit("halted = 0.0")
        self._emit("# iters_active accumulates (1 - halted) each step — counts the steps")
        self._emit("# the cell was 'active' (not yet saturated). Approximates the step at")
        self._emit("# which convergence happened, as a tensor scalar (no Python int counter).")
        self._emit("iters_active = 0.0")
        self._emit("# Pick the target: named target if provided, else the single proto.")
        self._emit("if target_name is not None:")
        self._indent += 1
        self._emit("target = compiled_prototypes[target_name]")
        self._indent -= 1
        self._emit("else:")
        self._indent += 1
        self._emit("target = next(iter(compiled_prototypes.values()))")
        self._indent -= 1
        self._emit("# T-step unroll. The Python `for` is meta-iteration over compile-")
        self._emit("# time-fixed steps; each iteration is a tensor-op cell with no")
        self._emit("# data-dependent branches.")
        self._emit("for _t in range(max_iters):")
        self._indent += 1
        self._emit("iters_active = iters_active + (1.0 - float(halted))")
        self._emit("state, halted = self._step(state, rotation, target, halted, k, threshold)")
        self._indent -= 1
        self._emit("# Output gating: multiply value-bearing axes by halted so an")
        self._emit("# incomplete loop emits a near-zero output. AXIS_LOOP_DONE itself")
        self._emit("# carries the cumulative halt as a tensor scalar for downstream")
        self._emit("# code that wants to read the convergence confidence.")
        self._emit("gated = state * float(halted)")
        self._emit("gated[self.semantic_dim + self.AXIS_LOOP_DONE] = float(halted)")
        self._emit("return target_name, gated, iters_active")
        self._indent -= 1
        self._indent -= 1
        self._emit()
        self._emit()
        self._emit(
            f"_VSA = _NumpyVSA("
            f"semantic_dim={self._semantic_dim}, "
            f"synthetic_dim={self._synthetic_dim}, "
            f"seed={self.runtime_seed}, "
            f"llm_model={self._llm_model!r})"
        )
        # Batched pre-fetch of every basis_vector("...") string argument
        # the program uses. One Ollama round-trip instead of N sequential
        # ones. Collected by the simplify pass (see translate_module).
        if self._prefetch_strings:
            self._emit(f"_VSA.embed_batch({self._prefetch_strings!r})")
        # Module-level constants exposing the static axon-key analysis
        # results. Downstream tooling (Yantra's kernel router for lazy
        # axon evaluation; possibly future per-receiver projection)
        # reads these instead of re-parsing the .su source. Always
        # emit the constants — even when empty — so consumers can rely
        # on the symbol being present. See sutra_compiler.axon_keys.
        bound = getattr(self, "_axon_keys_bound", frozenset())
        read = getattr(self, "_axon_keys_read", frozenset())
        self._emit(f"AXON_KEYS_BOUND = frozenset({sorted(bound)!r})")
        self._emit(f"AXON_KEYS_READ = frozenset({sorted(read)!r})")
        self._emit()
        self._emit()
        self._emit("def _argmax_cosine(query, candidates):")
        self._indent += 1
        self._emit('"""Candidate with the largest cosine similarity to query.')
        self._emit('')
        self._emit("Vectorized: stacks `candidates` into a (N, d) matrix and")
        self._emit("computes all N cosines in a single matmul. Equivalent to the")
        self._emit("old Python for-loop over _VSA.similarity, but ~Nx faster on")
        self._emit("CPU and the shape the PyTorch/GPU backend will reuse without")
        self._emit("any further rewriting. N small-kernel launches becomes 1 big one.")
        self._emit('"""')
        self._emit("if not candidates:")
        self._indent += 1
        self._emit("return None")
        self._indent -= 1
        self._emit("M = _np.stack([_np.asarray(c, dtype=_np.float64) for c in candidates])")
        self._emit("q = _np.asarray(query, dtype=_np.float64)")
        self._emit("row_norms = _np.linalg.norm(M, axis=1)")
        self._emit("q_norm = _np.linalg.norm(q)")
        self._emit("if q_norm == 0:")
        self._indent += 1
        self._emit("return candidates[0]")
        self._indent -= 1
        self._emit("safe_rn = _np.where(row_norms > 0, row_norms, 1.0)")
        self._emit("scores = (M @ q) / (safe_rn * q_norm)")
        self._emit("scores = _np.where(row_norms > 0, scores, -_np.inf)")
        self._emit("return candidates[int(_np.argmax(scores))]")
        self._indent -= 1
        self._emit()
        self._emit()
        self._emit_select_helper()
        self._emit()
        self._emit("def _vector_map_lookup(pairs, key):")
        self._indent += 1
        self._emit('"""Identity-first lookup for vector-keyed maps, cosine fallback.')
        self._emit('')
        self._emit("Identity-hit short-circuits before any matmul (the common case")
        self._emit("for literal vector keys). The cosine fallback stacks and matmuls.")
        self._emit('"""')
        self._emit("for k, v in pairs:")
        self._indent += 1
        self._emit("if k is key:")
        self._indent += 1
        self._emit("return v")
        self._indent -= 1
        self._indent -= 1
        self._emit("if not pairs:")
        self._indent += 1
        self._emit("return None")
        self._indent -= 1
        self._emit("keys = _np.stack([_np.asarray(k, dtype=_np.float64) for k, _ in pairs])")
        self._emit("q = _np.asarray(key, dtype=_np.float64)")
        self._emit("row_norms = _np.linalg.norm(keys, axis=1)")
        self._emit("q_norm = _np.linalg.norm(q)")
        self._emit("if q_norm == 0:")
        self._indent += 1
        self._emit("return pairs[0][1]")
        self._indent -= 1
        self._emit("safe_rn = _np.where(row_norms > 0, row_norms, 1.0)")
        self._emit("scores = (keys @ q) / (safe_rn * q_norm)")
        self._emit("scores = _np.where(row_norms > 0, scores, -_np.inf)")
        self._emit("return pairs[int(_np.argmax(scores))][1]")
        self._indent -= 1


def translate_module(module: ast.Module, **kwargs) -> str:
    """Translate a parsed Sutra module to a self-contained Python module.

    Runs the simplification pass over the AST before handing to the
    codegen so identity rewrites (bundle(v) -> v, bundle flattening)
    happen in source-to-source form rather than in the emitted
    Python. Also collects every `basis_vector("...")` string literal
    so the codegen can emit a batched Ollama pre-fetch at module init
    (N HTTP round-trips collapse into one batched embed call).
    """
    from .simplify import simplify_module, collect_basis_vector_strings
    from .inliner import inline_stdlib_calls
    from .promise_desugar import desugar_promises
    from .loop_desugar import desugar_implicit_loops
    from .axon_keys import collect_axon_keys
    # Axon-keys static analysis runs BEFORE simplify/inline so that
    # the keys we collect match the user-visible source pattern (the
    # simplifier may rewrite things in ways that obscure the bind/
    # item shape — e.g. inlined helpers fusing across function
    # boundaries — even though the runtime semantics are unchanged).
    bound_keys, read_keys = collect_axon_keys(module)
    # Stage-1 promise desugar runs first (queue.md item 1 phase 3):
    # transforms `async function ... { return [await] e; }` into the
    # equivalent non-async form returning Promise.resolve(e) or e.
    # Anything more complex stays async; the codegen rejects it with
    # a planning/sutra-spec/promises.md pointer.
    desugar_promises(module)
    # Implicit tail-recursive loop desugar: loop(expr){body} ->
    # iterative_loop LoopFunctionDecl + LoopCallStmt (queue.md item
    # 0). Same pass as the torch backend, same position.
    desugar_implicit_loops(module)
    # Inline stdlib calls — the inlined polynomial bodies then go
    # through simplify's arithmetic constant folding / zero
    # absorption, which can fold parts of the inlined form.
    inline_stdlib_calls(module)
    simplify_module(module)
    strings = collect_basis_vector_strings(module)
    cg = Codegen(**kwargs)
    cg._prefetch_strings = strings
    cg._axon_keys_bound = bound_keys
    cg._axon_keys_read = read_keys
    return cg.translate(module)
