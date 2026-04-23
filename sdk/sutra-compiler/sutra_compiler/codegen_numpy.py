"""AST -> pure-numpy Python source translator.

This is the demo-path backend. It emits self-contained Python modules
that depend only on numpy — no fly-brain imports, no spiking simulator,
no learned MBON readouts. VSA ops run as plain matrix operations on CPU.

Inherits the backend-agnostic AST walker from `BaseCodegen` in
`codegen_base.py` (so it shares expression / statement / call / loop
translators with the fly-brain backend WITHOUT depending on it). This
backend overrides the prelude, a handful of literal-lowering hooks
(`_char_literal_src`, `_embed_expr_src`, `_bool_literal_src`,
`_logical_op_src`, `_logical_not_src`, etc.), and the `_fuzzy_literal_init_src`
compile-time fold so truth-axis / complex / char literals resolve
against this backend's `_NumpyVSA` runtime.

`snap` is not supported here (the demo substrate has no cleanup
circuit; programs that need `snap` should target the fly-brain
backend).
"""

from __future__ import annotations

from typing import List

from . import ast_nodes as ast
from .codegen_base import BaseCodegen, CodegenNotSupported


class NumpyCodegen(BaseCodegen):
    """Emits a self-contained numpy-only module.

    Overrides the prelude and rejects `snap()` at codegen time. Everything
    else (function bodies, bind/bundle/unbind/similarity/argmax_cosine,
    map lookup, loop unrolling) is inherited unchanged.
    """

    # Frozen-LLM substrate. The numpy backend runs on frozen LLM
    # embeddings via Ollama — no random-vector fallback. If Ollama is
    # unavailable or the model is missing, compiled programs raise.
    # Default model: nomic-embed-text (768-dim). Avoid mxbai-embed-large
    # per CLAUDE.md — it has a documented attention-sink defect on
    # diacritics and is treated as a known-broken baseline.
    DEFAULT_LLM_MODEL = "nomic-embed-text"
    DEFAULT_LLM_DIM = 768
    # Extended-state-vector layout: runtime vectors are
    # `[semantic (n) | synthetic (SYNTHETIC_DIM)]`. The synthetic block
    # is reserved computational/symbolic space. Initial `embed()` output
    # has zeros in the synthetic block; rotation bind is block-diagonal
    # (Haar in the semantic block, identity in the synthetic block) so
    # the synthetic block stays zero-preserved until something explicitly
    # writes to it. Per user direction 2026-04-23 — spec finding at
    # planning/findings/2026-04-21-extended-state-and-rotation-binding.md.
    DEFAULT_SYNTHETIC_DIM = 100

    def __init__(self, *, runtime_dim: int | None = None,
                 runtime_seed: int = 42,
                 llm_model: str | None = None,
                 synthetic_dim: int | None = None) -> None:
        self._llm_model = llm_model if llm_model is not None else self.DEFAULT_LLM_MODEL
        # `runtime_dim` now names the SEMANTIC subspace size (the block
        # the LLM fills). Synthetic dims are appended on top. Total
        # runtime vector size = semantic + synthetic, stored on the
        # parent as `runtime_dim` so downstream plumbing (prelude's
        # `dim=...` literal, hemibrain wiring if ever re-enabled) sees
        # the full extended state.
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
            runtime_n_kc=0,
            runtime_use_hemibrain=False,
        )

    # Ops not supported by the pure-numpy substrate. `snap` requires a
    # cleanup circuit (MB spiking model or equivalent); rotation-based
    # loop primitives need the same. Programs that use these should
    # target `codegen_flybrain` instead.
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
        """Lower `defuzzy(<inner>)` to _VSA.defuzzify.

        Single-argument source form; the runtime method uses its
        default `iters=10`. If we later want to expose the iteration
        count at the surface level (e.g. `defuzzy(x, 5)`), this is
        the hook that grows a second arg.
        """
        inner_src = self._translate_expr(expr.expr)
        return f"_VSA.defuzzify({inner_src})"

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
        """Lower `&&` / `||` to _VSA.logical_and / logical_or.

        Runtime dispatches on operand types — pure-bool inputs return
        a Python bool, any truth-axis-vector input returns a
        truth-axis vector with the folded min / max. This keeps
        boolean-only code behaving like Python while giving fuzzy /
        trit / truth-vector code the Zadeh t-norm semantics.
        """
        method = "logical_and" if op == "and" else "logical_or"
        return f"_VSA.{method}({left_src}, {right_src})"

    def _logical_not_src(self, expr: ast.UnaryOp, operand_src: str) -> str:
        """Lower `!x` to `_VSA.logical_not(x)`.

        For bool: returns `not x`. For truth-axis vectors: flips just
        the truth coordinate (matches the user's "multiplication by
        -1 on the truth axis" framing without flipping other axes).
        """
        return f"_VSA.logical_not({operand_src})"

    def _equality_src(self, expr: ast.BinaryOp, op: str,
                      left_src: str, right_src: str) -> str:
        """Lower `==` / `!=` to _VSA.eq / _VSA.neq.

        Vector cosine similarity projected onto the truth axis. The
        runtime computes dot(a, b) / (||a|| · ||b||) via pure vector
        arithmetic (element-wise multiplies, sums, sqrt), then places
        the resulting scalar on the truth axis. Differentiable almost
        everywhere; the only singularity is at a zero-norm input
        which we guard with a truth=0 fallback.
        """
        assert op in ("eq", "neq")
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

    def _translate_eigenrotation_loop(self, stmt):
        """Eigenrotation on the numpy substrate.

        Differences from fly-brain:
        - Haar-random orthogonal matrix (fly-brain's uniform-angle
          Givens gives a tight periodic orbit that never explores).
        - Threshold is parsed from the condition (the numeric literal
          side of `similarity(state, target) < T`). Fly-brain uses a
          fixed 0.3 because matching is KC-pattern Jaccard; numpy
          matches on raw cosine, which has a very different scale.
        """
        from . import ast_nodes as ast
        lid = self._next_loop_id()
        state_var = self._extract_loop_state_var(stmt.body)
        target_expr = self._extract_loop_target(stmt.condition)

        threshold = 0.9
        cond = stmt.condition
        if isinstance(cond, ast.BinaryOp):
            for side in (cond.left, cond.right):
                if isinstance(side, ast.FloatLiteral):
                    threshold = side.value
                elif isinstance(side, ast.IntLiteral):
                    threshold = float(side.value)

        self._emit(f"{lid}_R = _VSA.make_random_rotation("
                   f"angle=1.0, n_planes=_VSA.dim // 2, seed=_VSA.seed)")
        self._emit(f"{lid}_target = {target_expr}")
        self._emit(f"{lid}_protos = _VSA.compile_prototypes("
                   f"{{\"target\": {lid}_target}})")
        self._emit(f"{lid}_name, {state_var}, {lid}_iters = _VSA.loop(")
        self._indent += 1
        self._emit(f"{state_var}, {lid}_R, {lid}_protos,")
        self._emit(f"target_name=\"target\", threshold={threshold}, max_iters=500)")
        self._indent -= 1

    # Vector-level accessor methods that the user can call as
    # `v.component(i)`, `v.semantic(i)`, `v.synthetic(i)` on any vector.
    # Parsed generically as a Call(MemberAccess(...), ...) by the parser;
    # intercepted here and lowered to `_VSA.component(v, i)` etc. because
    # runtime vectors are numpy arrays and arrays have no `.component()`
    # method. Purpose is introspection / debugging / teaching — see the
    # user direction 2026-04-23 when the extended state vector landed.
    # The shared set also includes the named canonical-axis shortcuts:
    # `.real()` == `.synthetic(0)`, `.imag()` == `.synthetic(1)`,
    # `.truth()` == `.synthetic(2)`. See the canonical-axis allocation in
    # planning/findings/2026-04-21-extended-state-and-rotation-binding.md.
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
                    f"substrate; use the fly-brain backend if you need it",
                )
        if (isinstance(callee, ast.MemberAccess)
                and callee.member in self._VECTOR_ACCESSORS):
            obj_src = self._translate_expr(callee.obj)
            arg_srcs = [self._translate_expr(a) for a in call.args]
            joined = ", ".join([obj_src, *arg_srcs])
            return f"_VSA.{callee.member}({joined})"
        return super()._translate_call(call)

    def _emit_prelude(self) -> None:
        self._emit('"""Generated by sutra_compiler.codegen_numpy. Do not edit by hand."""')
        self._emit("from __future__ import annotations")
        self._emit()
        self._emit("import numpy as _np")
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
        self._emit("# Replaces sign-flip (retired 2026-04-21). See spec binding.md.")
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
        self._emit("This is the independence-structure case the PyTorch/GPU")
        self._emit("backend was gated on per STATUS.md — the fused form collapses")
        self._emit("N small kernel launches into O(1) big ones.")
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
        self._emit("def similarity(self, a, b):")
        self._indent += 1
        self._emit("na = _np.linalg.norm(a)")
        self._emit("nb = _np.linalg.norm(b)")
        self._emit("if na == 0 or nb == 0:")
        self._indent += 1
        self._emit("return 0.0")
        self._indent -= 1
        self._emit("return float(_np.dot(a, b) / (na * nb))")
        self._indent -= 1
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
        self._emit("# First three synthetic axes have designated semantics (per")
        self._emit("# 2026-04-23 design; see")
        self._emit("# planning/findings/2026-04-21-extended-state-and-rotation-binding.md):")
        self._emit("#")
        self._emit("#   synthetic[0] = real component of a number")
        self._emit("#   synthetic[1] = imaginary component of a number")
        self._emit("#   synthetic[2] = truth axis (higher = more true)")
        self._emit("#")
        self._emit("# Pinning the allocation to named class attributes so the layout")
        self._emit("# is legible at runtime and from the REPL.")
        self._emit("#")
        self._emit("# synthetic[3] is the character-vs-int discriminator. A char")
        self._emit("# literal 'a' stores the code point at AXIS_REAL and sets this")
        self._emit("# flag to 1.0; a plain int leaves it at 0.0. Both types share")
        self._emit("# the number-axis representation — the flag is the only")
        self._emit("# runtime difference between `int 97` and `char 'a'`.")
        self._emit("AXIS_REAL = 0")
        self._emit("AXIS_IMAG = 1")
        self._emit("AXIS_TRUTH = 2")
        self._emit("AXIS_CHAR_FLAG = 3")
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
        self._emit("# ---- Logical operators — pure vector arithmetic ----")
        self._emit("#")
        self._emit("# Zadeh fuzzy logic implemented as element-wise vector math.")
        self._emit("# min / max expressed in pure arithmetic so there is NO")
        self._emit("# scalar extraction from the truth axis at runtime — the")
        self._emit("# operation is substrate-native vector algebra:")
        self._emit("#")
        self._emit("#   min(a, b) = (a + b - |a - b|) / 2     componentwise")
        self._emit("#   max(a, b) = (a + b + |a - b|) / 2     componentwise")
        self._emit("#   not(x)    = -x                         componentwise")
        self._emit("#")
        self._emit("# `true` and `false` are vectors too — the _bool_literal_src")
        self._emit("# override emits make_truth(±1) for bool literals, so the")
        self._emit("# entire numpy demo path is vector-native. There is no")
        self._emit("# Python-bool path masquerading as truth-axis logic.")
        self._emit("#")
        self._emit("# If a caller passes a Python scalar (int/float/bool) we")
        self._emit("# coerce via make_truth at the edge. That coercion is")
        self._emit("# compile-time-equivalent input construction, not runtime")
        self._emit("# scalar arithmetic hiding in the op.")
        self._emit("#")
        self._emit("# Unlike JavaScript / TypeScript / C#, these do NOT short-")
        self._emit("# circuit — min / max need both sides.")
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
        self._emit("def logical_and(self, a, b):")
        self._indent += 1
        self._emit('"""Zadeh t-norm as pure vector arithmetic: (a+b - |a-b|)/2."""')
        self._emit("av = self._as_truth_vector(a)")
        self._emit("bv = self._as_truth_vector(b)")
        self._emit("return (av + bv - _np.abs(av - bv)) * 0.5")
        self._indent -= 1
        self._emit()
        self._emit("def logical_or(self, a, b):")
        self._indent += 1
        self._emit('"""Zadeh t-conorm as pure vector arithmetic: (a+b + |a-b|)/2."""')
        self._emit("av = self._as_truth_vector(a)")
        self._emit("bv = self._as_truth_vector(b)")
        self._emit("return (av + bv + _np.abs(av - bv)) * 0.5")
        self._indent -= 1
        self._emit()
        self._emit("def logical_not(self, x):")
        self._indent += 1
        self._emit('"""Negation as pure scalar-by-vector multiplication: -x."""')
        self._emit("return -self._as_truth_vector(x)")
        self._indent -= 1
        self._emit()
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
        self._emit('"""Vector equality — cosine similarity projected onto truth axis."""')
        self._emit("av = self._as_any_vector(a)")
        self._emit("bv = self._as_any_vector(b)")
        self._emit("na = _np.sqrt(_np.dot(av, av))")
        self._emit("nb = _np.sqrt(_np.dot(bv, bv))")
        self._emit("if na == 0 or nb == 0:")
        self._indent += 1
        self._emit("# Equality with the zero vector is undefined; return")
        self._emit("# the neutral point rather than NaN.")
        self._emit("return self.make_truth(0.0)")
        self._indent -= 1
        self._emit("return self.make_truth(float(_np.dot(av, bv) / (na * nb)))")
        self._indent -= 1
        self._emit()
        self._emit("def neq(self, a, b):")
        self._indent += 1
        self._emit('"""Vector inequality — truth axis inverted cosine similarity."""')
        self._emit("eq_vec = self.eq(a, b)")
        self._emit("return self.logical_not(eq_vec)")
        self._indent -= 1
        self._emit()
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
        self._emit("def defuzzify(self, x, iters=10):")
        self._indent += 1
        self._emit('"""Project onto truth axis via matmul, then iterate eq(., true)."""')
        self._emit("av = self._as_any_vector(x)")
        self._emit("# Step 1: matmul projection onto truth axis (zero elsewhere).")
        self._emit("t = self._truth_projector() @ av")
        self._emit("# Step 2: iterate equality with true — cosine similarity snaps")
        self._emit("# to ±1 for non-neutral inputs, stays 0 for neutral inputs.")
        self._emit("true_vec = self.make_truth(1.0)")
        self._emit("for _ in range(int(iters)):")
        self._indent += 1
        self._emit("t = self.eq(t, true_vec)")
        self._indent -= 1
        self._emit("return t")
        self._indent -= 1
        self._emit()
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
        self._emit('in the signature for API compatibility with the fly-brain VSA.')
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
        self._emit("def loop(self, initial_state, rotation, compiled_prototypes,")
        self._indent += 1
        self._emit("target_name=None, threshold=0.5, max_iters=50, frame_seed=None):")
        self._emit('"""Eigenrotation: iterate state <- R @ state until match."""')
        self._emit("state = initial_state.copy()")
        self._emit("for iters in range(1, max_iters + 1):")
        self._indent += 1
        self._emit("state = rotation @ state")
        self._emit("n = _np.linalg.norm(state)")
        self._emit("if n > 0: state = state / n")
        self._emit("best_name, best_score = None, -1.0")
        self._emit("for nm, proto in compiled_prototypes.items():")
        self._indent += 1
        self._emit("s = self.similarity(state, proto)")
        self._emit("if s > best_score:")
        self._indent += 1
        self._emit("best_score = s; best_name = nm")
        self._indent -= 1
        self._indent -= 1
        self._emit("if target_name is not None and best_name == target_name and best_score >= threshold:")
        self._indent += 1
        self._emit("return best_name, state, iters")
        self._indent -= 1
        self._emit("if target_name is None and best_score >= threshold:")
        self._indent += 1
        self._emit("return best_name, state, iters")
        self._indent -= 1
        self._indent -= 1
        self._emit("return best_name, state, max_iters")
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
    """Translate a parsed Sutra module to self-contained numpy Python.

    Runs the simplification pass over the AST before handing to the
    codegen so identity rewrites (bundle(v) -> v, bundle flattening)
    happen in source-to-source form rather than in the emitted
    Python. Also collects every `basis_vector("...")` string literal
    so the codegen can emit a batched Ollama pre-fetch at module init
    (N HTTP round-trips collapse into one batched embed call).
    These are prerequisites for the PyTorch/GPU backend port.
    """
    from .simplify import simplify_module, collect_basis_vector_strings
    simplify_module(module)
    strings = collect_basis_vector_strings(module)
    cg = NumpyCodegen(**kwargs)
    cg._prefetch_strings = strings
    return cg.translate(module)
