"""AST → FlyBrainVSA Python source translator.

This module walks a parsed Sutra `Module` and emits Python source that
targets the `FlyBrainVSA` runtime in `fly-brain/vsa_operations.py`. The
generated code mirrors the shape of the hand-written
`fly-brain/permutation_conditional.py` but is produced mechanically from
the corresponding `.su` source — closing the "compile-to-brain" gap
described in `fly-brain/STATUS.md` §Medium term.

Scope for V2:
    - Top-level `VarDecl` with `vector`, `permutation`, or `map<_, _>` type
    - Top-level `FunctionDecl`
    - Inside functions: `VarDecl`, `ReturnStmt`, `ExprStmt` over `Assignment`
    - Expressions: `Identifier`, `StringLiteral`, `Call` to a VSA builtin,
      `ArrayLiteral`, `Subscript`, `MapLiteral`, `Parenthesized`
    - Deterministic substrate via `FixedFrameFlyBrainVSA` (fixed-frame
      contract is the "compile-time guarantee" item from the todo.)
    - `WhileStmt` — compiled to a geometric loop on the brain via
      `FlyBrainVSA.loop()`. The loop body is a rotation matrix R,
      each iteration applies R and snaps through the mushroom body
      circuit, and the condition is prototype matching in KC space.
      Iteration happens on the brain, not in the host runtime.
    - `ForStmt` — compiled to a bounded geometric loop (N rotations).
    - Geometric loop builtins: `make_rotation`, `compile_prototypes`,
      `geometric_loop` — compile to the rotation + snap + prototype-match
      loop primitive in `FlyBrainVSA.loop()`.

Anything outside that scope raises `CodegenNotSupported` with the source
span of the offending node, which is strictly better than silently
emitting incorrect Python.
"""

from __future__ import annotations

from typing import List

from . import ast_nodes as ast


# ============================================================
# Error type
# ============================================================


def _is_bind_call(expr) -> bool:
    """Match a direct `bind(role, filler)` Call — used by the fused
    bundle-of-binds lowering in `_translate_call`. Does not match
    `_VSA.bind(...)` via MemberAccess (those don't appear in .su source).
    """
    return (isinstance(expr, ast.Call)
            and isinstance(expr.callee, ast.Identifier)
            and expr.callee.name == "bind"
            and len(expr.args) == 2)


class CodegenNotSupported(Exception):
    """Raised when the translator hits an AST node it cannot lower.

    Carries the source span of the offending node so the CLI can print a
    compiler-style `line:col` diagnostic. The file path is not on the
    span itself (it lives on `Diagnostic` in the parser's diagnostic
    bag), so callers that know the source path should prepend it when
    formatting for the user.
    """

    def __init__(self, node: ast.Node, message: str):
        self.node = node
        self.message = message
        span = node.span
        super().__init__(
            f"{span.start.line}:{span.start.column}: codegen: {message}"
        )


# ============================================================
# Builtin name → Python expression template
# ============================================================
#
# Each entry maps an Sutra builtin identifier to a callable that takes
# the already-translated argument strings and returns the Python
# expression to emit. Keeping this as a single table means the list of
# supported builtins is easy to audit against `planning/sutra-spec/21-builtins.md`.

def _builtin_basis_vector(args: List[str]) -> str:
    return f"_VSA.embed({args[0]})"


def _builtin_permutation_key(args: List[str]) -> str:
    return f"_VSA.make_sign_flip_key({args[0]})"


def _builtin_permute(args: List[str]) -> str:
    return f"_VSA.sign_flip({args[0]}, {args[1]})"


def _builtin_bind(args: List[str]) -> str:
    return f"_VSA.bind({args[0]}, {args[1]})"


def _builtin_unbind(args: List[str]) -> str:
    return f"_VSA.unbind({args[0]}, {args[1]})"


def _builtin_bundle(args: List[str]) -> str:
    return f"_VSA.bundle({', '.join(args)})"


def _builtin_zero_vector(args: List[str]) -> str:
    # Zero vector in the runtime's d-dim substrate. Produced by the
    # simplifier for `displacement(a, a)` and as an absorption element
    # for bundle/addition. Not yet user-callable from .su, but the
    # builtin path is ready for it.
    return "_VSA.zero_vector()"


def _builtin_displacement(args: List[str]) -> str:
    # displacement(a, b) = a - b  (vector subtraction).
    # Matches the cartography-paper primitive: a displacement is the
    # rank-0 case of a learned role matrix. king - man + woman is
    # expressed as bundle(displacement(king, man), woman).
    return f"({args[0]} - {args[1]})"


def _builtin_similarity(args: List[str]) -> str:
    return f"_VSA.similarity({args[0]}, {args[1]})"


def _builtin_snap(args: List[str]) -> str:
    return f"_VSA.snap({args[0]})"


def _builtin_identity_permutation(args: List[str]) -> str:
    return "_np.ones(_VSA.dim)"


def _builtin_argmax_cosine(args: List[str]) -> str:
    return f"_argmax_cosine({args[0]}, {args[1]})"


def _builtin_select(args: List[str]) -> str:
    # Spec: planning/sutra-spec/26-select-and-gate.md.
    # `select(scores, options)` is softmax-weighted superposition — the
    # named conditional-branching primitive. No defuzz; the result is a
    # vector usable as the input to further operations.
    return f"_select_softmax({args[0]}, {args[1]})"


def _builtin_compose(args: List[str]) -> str:
    # Composition of two sign-flip permutations is pointwise multiply.
    return f"({args[0]} * {args[1]})"


def _builtin_make_rotation(args: List[str]) -> str:
    # make_rotation(angle, n_planes) → orthogonal matrix
    if len(args) == 1:
        return f"_VSA.make_random_rotation(angle={args[0]})"
    return f"_VSA.make_random_rotation(angle={args[0]}, n_planes={args[1]})"


def _builtin_compile_prototypes(args: List[str]) -> str:
    return f"_VSA.compile_prototypes({args[0]})"


def _builtin_geometric_loop(args: List[str]) -> str:
    # geometric_loop(initial_state, rotation, compiled_prototypes)
    # Optional 4th arg: target_name
    if len(args) >= 4:
        return (f"_VSA.loop({args[0]}, {args[1]}, {args[2]}, "
                f"target_name={args[3]})")
    return f"_VSA.loop({args[0]}, {args[1]}, {args[2]})"


def _builtin_real_number(args: List[str]) -> str:
    # Canonical-axis constructor: a scalar real number as an extended-
    # state vector with x at synthetic[0], zeros elsewhere. Part of the
    # int/float/complex shared-axis allocation — see project memory
    # project_sutra_complex_numbers_first_class.md.
    return f"_VSA.make_real({args[0]})"


def _builtin_complex_number(args: List[str]) -> str:
    # Canonical-axis constructor: a complex number with re at
    # synthetic[0] and im at synthetic[1]. Sutra's first-class complex.
    return f"_VSA.make_complex({args[0]}, {args[1]})"


def _builtin_truth_value(args: List[str]) -> str:
    # Canonical-axis constructor: a scalar truth value at synthetic[2].
    # Higher = more true; 0 = neither; negative = false-leaning. The
    # axis is orthogonal to real/imag by construction.
    return f"_VSA.make_truth({args[0]})"


BUILTINS = {
    "basis_vector": (_builtin_basis_vector, 1),
    "permutation_key": (_builtin_permutation_key, 1),
    "identity_permutation": (_builtin_identity_permutation, 0),
    "permute": (_builtin_permute, 2),
    "bind": (_builtin_bind, 2),
    "unbind": (_builtin_unbind, 2),
    "bundle": (_builtin_bundle, None),   # variadic, at least 1
    "zero_vector": (_builtin_zero_vector, 0),
    "displacement": (_builtin_displacement, 2),  # a - b (vector subtract)
    "similarity": (_builtin_similarity, 2),
    "snap": (_builtin_snap, 1),
    "argmax_cosine": (_builtin_argmax_cosine, 2),
    "select": (_builtin_select, 2),
    "compose": (_builtin_compose, 2),
    "make_rotation": (_builtin_make_rotation, None),  # 1-2 args
    "compile_prototypes": (_builtin_compile_prototypes, 1),
    "geometric_loop": (_builtin_geometric_loop, None),  # 3-4 args
    # Canonical-axis constructors. Lower to _VSA.make_real / make_complex /
    # make_truth — runtime methods provided by NumpyCodegen's _NumpyVSA.
    # A backend that doesn't implement them will fail at runtime with a
    # clear AttributeError; nothing in the current flybrain runtime
    # exercises these yet, so the shared table is fine.
    "real_number": (_builtin_real_number, 1),
    "complex_number": (_builtin_complex_number, 2),
    "truth_value": (_builtin_truth_value, 1),
}


# ============================================================
# Translator
# ============================================================


class FlyBrainCodegen:
    """Stateful walker that emits Python source for one Sutra module.

    Instances are single-use — call `translate(module)` and then read
    `.output`. Not thread-safe, not reusable.
    """

    def __init__(self, *, runtime_dim: int = 50, runtime_seed: int = 42,
                 runtime_n_kc: int = 2000,
                 runtime_use_hemibrain: bool = False) -> None:
        self.runtime_dim = runtime_dim
        self.runtime_seed = runtime_seed
        self.runtime_n_kc = runtime_n_kc
        self.runtime_use_hemibrain = runtime_use_hemibrain
        self._lines: List[str] = []
        self._indent = 0
        # Maps variable names to the *key* type of a map-typed declaration
        # so subscript expressions know whether to use the identity-based
        # vector-map helper or a plain dict lookup.
        self._map_key_type: dict[str, str] = {}
        # Set of variable names declared with type `dict<K, V>`. A dict
        # in Sutra is a rotation-hashmap — subscript access (d[k])
        # dispatches to _VSA.hashmap_get, assignment (d[k] = v)
        # dispatches to _VSA.hashmap_set (functional update).
        self._dict_declared: set[str] = set()

    # -- emission helpers -------------------------------------------------

    def _emit(self, line: str = "") -> None:
        if line:
            self._lines.append("    " * self._indent + line)
        else:
            self._lines.append("")

    @property
    def output(self) -> str:
        return "\n".join(self._lines) + "\n"

    def _emit_select_helper(self) -> None:
        """Emit `_select_softmax(scores, options)` — the runtime for the
        spec-level `select` primitive (planning/sutra-spec/26-select-and-gate.md).
        Softmax weights, weighted sum of option vectors, no defuzz."""
        self._emit("def _select_softmax(scores, options):")
        self._indent += 1
        self._emit('"""Softmax-weighted superposition of option vectors."""')
        self._emit("s = _np.asarray(scores, dtype=float)")
        self._emit("s = s - _np.max(s)")
        self._emit("w = _np.exp(s)")
        self._emit("w = w / _np.sum(w)")
        self._emit("opts = _np.asarray(options, dtype=float)")
        self._emit("return (w[:, None] * opts).sum(axis=0)")
        self._indent -= 1

    # -- public entry point -----------------------------------------------

    def translate(self, module: ast.Module) -> str:
        self._emit_prelude()
        self._emit()
        for item in module.items:
            self._translate_top_level(item)
            self._emit()
        return self.output

    # -- prelude ----------------------------------------------------------

    def _emit_prelude(self) -> None:
        self._emit('"""Generated by sutra_compiler.codegen_flybrain. Do not edit by hand."""')
        self._emit("from __future__ import annotations")
        self._emit()
        self._emit("import numpy as _np")
        self._emit()
        self._emit("from vsa_operations import FlyBrainVSA")
        self._emit("from spike_vsa_bridge import SpikeVSABridge")
        self._emit()
        self._emit()
        self._emit("class _FixedFrameFlyBrainVSA(FlyBrainVSA):")
        self._indent += 1
        self._emit('"""Pins the PN->KC connectivity seed across all snap() calls."""')
        self._emit()
        self._emit("def snap(self, vector):")
        self._indent += 1
        if self.runtime_use_hemibrain:
            self._emit("bridge_kwargs = dict(use_hemibrain=True)")
        else:
            self._emit("bridge_kwargs = dict(n_kc=self.n_kc)")
        self._emit("bridge = SpikeVSABridge(")
        self._indent += 1
        self._emit("dim=self.dim, seed=self.seed, **bridge_kwargs,")
        self._indent -= 1
        self._emit(")")
        self._emit("# Fit the biologically-plausible learned MBON readout.")
        self._emit("# Class-level cache in SpikeVSABridge makes this a")
        self._emit("# trivial hit on every call after the first.")
        n_samples = 80 if self.runtime_use_hemibrain else 20
        self._emit(f"bridge.fit_learned_readout(n_samples={n_samples})")
        self._emit("decoded, _ = bridge.round_trip(vector, self.snap_duration_ms)")
        self._emit("return decoded")
        self._indent -= 1
        self._indent -= 1
        self._emit()
        self._emit()
        if self.runtime_use_hemibrain:
            self._emit(
                f"_VSA = _FixedFrameFlyBrainVSA("
                f"seed={self.runtime_seed}, use_hemibrain=True)"
            )
        else:
            self._emit(
                f"_VSA = _FixedFrameFlyBrainVSA(dim={self.runtime_dim}, "
                f"n_kc={self.runtime_n_kc}, seed={self.runtime_seed})"
            )
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
        self._emit("# Guard zero-norm rows so division doesn't emit a warning and")
        self._emit("# the cosine for a zero candidate is 0, matching _VSA.similarity.")
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
        self._emit("Vectorized fallback: the cosine-nearest path stacks the key")
        self._emit("vectors into one matrix and matmuls, matching the shape")
        self._emit("_argmax_cosine uses. Identity-hit short-circuits before any")
        self._emit("matmul, which is the common case for literal vector keys.")
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

    # -- top level --------------------------------------------------------

    def _translate_top_level(self, item: ast.TopLevel) -> None:
        if isinstance(item, ast.VarDecl):
            self._translate_var_decl(item, at_top_level=True)
        elif isinstance(item, ast.FunctionDecl):
            self._translate_function_decl(item)
        elif isinstance(item, ast.MethodDecl):
            raise CodegenNotSupported(
                item, "method declarations are not supported by the V1 fly-brain codegen"
            )
        else:
            # Statements at top level (ExprStmt, etc.) — lower as a stmt.
            if isinstance(item, ast.Stmt):
                self._translate_stmt(item)
            else:
                raise CodegenNotSupported(
                    item, f"unsupported top-level item: {type(item).__name__}"
                )

    # -- declarations -----------------------------------------------------

    def _fuzzy_literal_init_src(self, decl: ast.VarDecl) -> str | None:
        """Hook: emit a fuzzy-typed var decl whose initializer is a literal.

        Per 2026-04-23 design, `fuzzy x = 0.7;` is conceptually
        `fuzzy x = true * 0.7;` — a truth-axis vector scaled by 0.7.
        The scalar-times-true folds at compile time to a single
        vector allocation on the truth axis. Backends that have a
        truth-axis runtime override this to emit `_VSA.make_truth(v)`.

        Returns the full assignment RHS string (e.g.
        `"_VSA.make_truth(0.7)"`) if the rewrite applies, or None to
        fall through to the default codegen path. Base returns None —
        fly-brain has no truth-axis runtime yet.
        """
        return None

    def _translate_var_decl(self, decl: ast.VarDecl, *, at_top_level: bool) -> None:
        # Track map<K, V> declarations so that a later subscript on this
        # name can dispatch to the right lookup helper.
        if decl.type_ref is not None and decl.type_ref.name == "map":
            if len(decl.type_ref.type_args) >= 1:
                self._map_key_type[decl.name] = decl.type_ref.type_args[0].name
        # Track dict<K, V> declarations so that d[k] / d[k] = v
        # dispatch to the rotation-hashmap runtime.
        if decl.type_ref is not None and decl.type_ref.name == "dict":
            self._dict_declared.add(decl.name)
            # Uninitialized `dict<K, V> d;` emits `d = _VSA.hashmap_new()`.
            # Initialized form falls through to the initializer translation.
            if decl.initializer is None:
                self._emit(f"{decl.name} = _VSA.hashmap_new()")
                return

        # Implicit fuzzy typing — `fuzzy x = 0.7;` compiles to a truth-axis
        # vector per the 2026-04-23 literals design. The backend hook
        # decides whether this applies and what RHS to emit.
        fuzzy_src = self._fuzzy_literal_init_src(decl)
        if fuzzy_src is not None:
            self._emit(f"{decl.name} = {fuzzy_src}")
            return

        # `var x : TYPE;` without an initializer — the rotation-bound
        # storage-slot form from the 2026-04-21 surface-syntax decision
        # (Candidate B: role/var). Emit a zero-valued slot of the
        # declared type. `var[N] x : TYPE;` emits a Python list of N
        # zero slots.
        if decl.initializer is None and decl.is_var_colon:
            type_name = decl.type_ref.name if decl.type_ref is not None else "vector"
            # Vector types get a zero d-dim array per slot.
            if type_name == "vector":
                if decl.array_size is not None:
                    self._emit(
                        f"{decl.name} = [_np.zeros(_VSA.dim) "
                        f"for _ in range({decl.array_size})]"
                    )
                else:
                    self._emit(f"{decl.name} = _np.zeros(_VSA.dim)")
                return
            # Fuzzy / bool / trit are (per spec target) scalars on the
            # canonical truth axis. `trit` / `luk` default to 0 —
            # "explicit neutrality," the first-class unknown value of
            # Ł₃. Until the truth-axis runtime lands for these in
            # every backend, use a plain float zero as the placeholder;
            # the numpy / pytorch backends' make_truth path is used by
            # initialized declarations.
            if type_name in ("fuzzy", "bool", "int", "scalar", "number",
                             "trit", "luk"):
                if decl.array_size is not None:
                    self._emit(f"{decl.name} = [0.0] * {decl.array_size}")
                else:
                    self._emit(f"{decl.name} = 0.0")
                return
            # Unknown colon-typed slot — fall through to the uninitialized
            # error below with a clearer message.

        if decl.initializer is None:
            raise CodegenNotSupported(
                decl,
                f"uninitialized declaration `{decl.name}` is only supported "
                f"for `var x : TYPE;` with TYPE in (vector, fuzzy, bool, "
                f"int, scalar). Add an initializer or use a supported type."
            )
        init_src = self._translate_expr(decl.initializer, map_key_type=(
            decl.type_ref.type_args[0].name
            if decl.type_ref is not None
            and decl.type_ref.name == "map"
            and len(decl.type_ref.type_args) >= 1
            else None
        ))
        # `role x = expr;` for now emits identical code to `vector x = expr;`.
        # When learned-matrix binding lands (STATUS "Deferred"), the is_role
        # flag will switch this branch to emit the matrix-fit path instead.
        # `var[N] x = expr;` with an initializer would need a
        # broadcast-or-replicate semantics that is not yet specified;
        # reject for now so the spec work lands before the codegen does.
        if decl.array_size is not None and decl.initializer is not None:
            raise CodegenNotSupported(
                decl,
                f"`var[{decl.array_size}] {decl.name} = ...;` initialized "
                "array declarations are not yet specified. Use "
                f"`var[{decl.array_size}] {decl.name} : TYPE;` for a "
                "zero-initialized slot array."
            )
        self._emit(f"{decl.name} = {init_src}")

    def _translate_function_decl(self, decl: ast.FunctionDecl) -> None:
        if decl.is_operator:
            raise CodegenNotSupported(
                decl, "operator declarations are not supported by the V1 codegen"
            )
        if decl.type_params:
            raise CodegenNotSupported(
                decl, "generic function declarations are not supported by the V1 codegen"
            )
        param_names = [p.name for p in decl.params]
        self._emit(f"def {decl.name}({', '.join(param_names)}):")
        self._indent += 1
        if not decl.body.statements:
            self._emit("pass")
        else:
            for stmt in decl.body.statements:
                self._translate_stmt(stmt)
        self._indent -= 1

    # -- statements -------------------------------------------------------

    def _translate_stmt(self, stmt: ast.Stmt) -> None:
        if isinstance(stmt, ast.VarDecl):
            self._translate_var_decl(stmt, at_top_level=False)
            return
        if isinstance(stmt, ast.ReturnStmt):
            if stmt.value is None:
                self._emit("return")
            else:
                self._emit(f"return {self._translate_expr(stmt.value)}")
            return
        if isinstance(stmt, ast.ExprStmt):
            expr = stmt.expr
            if isinstance(expr, ast.Assignment):
                # dict[key] = value dispatches to the rotation-hashmap
                # runtime's functional-update form (hashmap_set returns
                # a new accumulator). Only simple `=` is supported on
                # dict subscripts — compound assignment (`d[k] += v`) is
                # not yet specified.
                if (isinstance(expr.target, ast.Subscript)
                        and isinstance(expr.target.target, ast.Identifier)
                        and expr.target.target.name in self._dict_declared):
                    if expr.op != "=":
                        raise CodegenNotSupported(
                            stmt,
                            f"compound assignment on a dict subscript "
                            f"(`{expr.op}`) is not yet supported",
                        )
                    dict_name = expr.target.target.name
                    key_src = self._translate_expr(expr.target.index)
                    value_src = self._translate_expr(expr.value)
                    self._emit(
                        f"{dict_name} = _VSA.hashmap_set({dict_name}, "
                        f"{key_src}, {value_src})"
                    )
                    return
                # 2026-04-22: compound assignment (+=, -=, *=, /=) is
                # emitted directly to Python. Python's semantics match
                # Sutra's for scalars (float) and for numpy vectors (in-
                # place). The user's number-axis + integer-class design
                # makes augmented assignment a first-class operation on
                # scalars; emitting Python's native form is the direct
                # implementation. `=` is the simple case that always
                # worked.
                target_src = self._translate_expr(expr.target)
                value_src = self._translate_expr(expr.value)
                self._emit(f"{target_src} {expr.op} {value_src}")
                return
            self._emit(self._translate_expr(expr))
            return
        if isinstance(stmt, ast.Block):
            for inner in stmt.statements:
                self._translate_stmt(inner)
            return
        if isinstance(stmt, ast.LoopStmt):
            if stmt.count is not None:
                self._translate_bounded_loop(stmt)
            else:
                self._translate_eigenrotation_loop(stmt)
            return
        if isinstance(stmt, ast.WhileStmt):
            self._translate_while_as_geometric_loop(stmt)
            return
        if isinstance(stmt, ast.ForStmt):
            self._translate_for_as_geometric_loop(stmt)
            return
        if isinstance(stmt, ast.DoWhileStmt):
            # `do { body } while (cond)` desugars to the body executed
            # once, followed by a `while (cond) { body }`. User direction
            # 2026-04-22: "decompose to a single iteration, followed by
            # a while loop of it." The while half then lowers to the
            # same eigenrotation-loop machinery ForStmt / WhileStmt use.
            for inner in stmt.body.statements:
                self._translate_stmt(inner)
            synthesized_while = ast.WhileStmt(
                condition=stmt.condition,
                body=stmt.body,
                span=stmt.span,
            )
            self._translate_while_as_geometric_loop(synthesized_while)
            return
        if isinstance(stmt, ast.ForeachStmt):
            # `foreach (x in [a, b, c]) { body }` unrolls at compile time
            # — one body emission per element, with the loop variable
            # bound to each element's translated source. User direction
            # 2026-04-22: compile-time-known collections only; anything
            # else (e.g. a non-literal expression in the iterable
            # position) is a compile-time error pending the dynamic-
            # foreach design (see todo.md).
            if isinstance(stmt.iterable, ast.ArrayLiteral):
                for element_expr in stmt.iterable.elements:
                    element_src = self._translate_expr(element_expr)
                    self._emit(f"{stmt.var_name} = {element_src}")
                    for inner in stmt.body.statements:
                        self._translate_stmt(inner)
                return
            raise CodegenNotSupported(
                stmt,
                f"`foreach` is only supported over compile-time-known "
                f"collections (array literals like `[a, b, c]`). The "
                f"iterable here is a "
                f"{type(stmt.iterable).__name__}, which would require "
                f"runtime iteration. Dynamic `foreach` over named "
                f"collections or computed expressions is future work — "
                f"see todo.md. Rewrite as `foreach (x in [a, b, c]) "
                f"{{ ... }}` or unroll by hand.",
            )
        if isinstance(stmt, ast.IfStmt):
            raise CodegenNotSupported(
                stmt,
                "if/else is not supported by the V1 fly-brain codegen — the whole "
                "point is to compile it away into a prototype-table lookup",
            )
        raise CodegenNotSupported(
            stmt, f"unsupported statement: {type(stmt).__name__}"
        )

    # -- loop compilation ---------------------------------------------------
    #
    # Sutra's `loop` construct has two forms:
    #
    # 1. Bounded:  loop (N) { body }     → unrolled at compile time
    #              loop (N as i) { body } → unrolled with index
    #    The body is emitted N times in sequence. No rotation, no
    #    circuit iteration. Pure compile-time expansion.
    #
    # 2. Eigenrotation: loop (condition) { body } → geometric rotation
    #    Compiles to _VSA.loop() — the brain iterates via rotation
    #    in vector space with prototype matching for termination.
    #
    # The old while/for forms also compile to geometric rotation
    # (kept for backward compatibility with existing .su files).
    #
    # -- geometric loop compilation ----------------------------------------
    #
    # Sutra loops compile to geometric rotation on the brain, not to
    # host-runtime Python loops. The loop body is a rotation matrix R
    # applied at each iteration; each rotated state is snapped through
    # the mushroom body circuit; termination is by prototype matching
    # in the brain's native KC space.
    #
    # The generated code:
    #   1. Builds a rotation matrix R (from loop body analysis or default)
    #   2. Compiles the target condition as a KC-space prototype
    #   3. Calls _VSA.loop(state, R, prototypes) — the brain iterates
    #
    # This is how the brain counts: N iterations of rotation by angle
    # theta accumulates N*theta total rotation, and the loop terminates
    # when the trajectory enters the target prototype's basin.

    def _translate_bounded_loop(self, stmt: ast.LoopStmt) -> None:
        """Compile loop (N) { body } — unrolls at compile time.

        The body is emitted N times. No rotation matrix, no circuit
        iteration. This is syntactic sugar, not eigenrotation.

        loop (N as i) adds an index variable that counts 0..N-1.
        """
        count_src = self._translate_expr(stmt.count)

        if stmt.index_var:
            # loop (N as i) { body } → for i in range(N): body
            self._emit(f"for {stmt.index_var} in range({count_src}):")
            self._indent += 1
            if not stmt.body.statements:
                self._emit("pass")
            else:
                for inner in stmt.body.statements:
                    self._translate_stmt(inner)
            self._indent -= 1
        else:
            # loop (N) { body } → unroll body N times
            # For literal integers, actually unroll. For expressions, use range.
            if isinstance(stmt.count, ast.IntLiteral):
                n = stmt.count.value
                for _ in range(n):
                    for inner in stmt.body.statements:
                        self._translate_stmt(inner)
            else:
                self._emit(f"for _ in range({count_src}):")
                self._indent += 1
                if not stmt.body.statements:
                    self._emit("pass")
                else:
                    for inner in stmt.body.statements:
                        self._translate_stmt(inner)
                self._indent -= 1

    def _translate_eigenrotation_loop(self, stmt: ast.LoopStmt) -> None:
        """Compile loop (condition) { body } — eigenrotation on the brain.

        The condition determines the target prototype. The loop body
        is replaced by a rotation matrix. The brain iterates via
        _VSA.loop().
        """
        lid = self._next_loop_id()
        state_var = self._extract_loop_state_var(stmt.body)
        target_expr = self._extract_loop_target(stmt.condition)

        self._emit(f"{lid}_R = _VSA.make_random_rotation("
                   f"angle=_np.pi / 4, n_planes=20, seed=_VSA.seed)")
        self._emit(f"{lid}_target = {target_expr}")
        self._emit(f"{lid}_protos = _VSA.compile_prototypes("
                   f"{{\"target\": {lid}_target}})")
        self._emit(f"{lid}_name, {state_var}, {lid}_iters = _VSA.loop(")
        self._indent += 1
        self._emit(f"{state_var}, {lid}_R, {lid}_protos,")
        self._emit(f"target_name=\"target\", max_iters=50)")
        self._indent -= 1

    _loop_counter = 0  # unique names for loop temporaries

    def _next_loop_id(self) -> str:
        FlyBrainCodegen._loop_counter += 1
        return f"_loop{FlyBrainCodegen._loop_counter}"

    def _translate_while_as_geometric_loop(self, stmt: ast.WhileStmt) -> None:
        """Compile a while statement to a geometric loop on the brain.

        The while condition determines the target prototype (what we're
        looping UNTIL), and the loop body determines the rotation (what
        each iteration does geometrically).

        Generated code pattern:
            _loopN_R = _VSA.make_random_rotation(angle=pi/4, n_planes=20)
            _loopN_target = <condition target vector>
            _loopN_protos = _VSA.compile_prototypes({"target": _loopN_target})
            _loopN_name, <state_var>, _loopN_iters = _VSA.loop(
                <state_var>, _loopN_R, _loopN_protos, target_name="target")
        """
        lid = self._next_loop_id()

        # Extract the state variable from the loop body.
        # Look for assignments of the form: state = <expr>
        # The assigned variable is the state being rotated.
        state_var = self._extract_loop_state_var(stmt.body)

        # Extract the target from the condition.
        # The condition tells us what we're looping toward.
        target_expr = self._extract_loop_target(stmt.condition)

        # Build rotation matrix — the geometric step per iteration.
        # Uses multi-plane rotation for good separation in high-D space.
        self._emit(f"{lid}_R = _VSA.make_random_rotation("
                   f"angle=_np.pi / 4, n_planes=20, seed=_VSA.seed)")

        # Compile the target as a KC-space prototype.
        self._emit(f"{lid}_target = {target_expr}")
        self._emit(f"{lid}_protos = _VSA.compile_prototypes("
                   f"{{\"target\": {lid}_target}})")

        # Execute the geometric loop on the brain.
        self._emit(f"{lid}_name, {state_var}, {lid}_iters = _VSA.loop(")
        self._indent += 1
        self._emit(f"{state_var}, {lid}_R, {lid}_protos,")
        self._emit(f"target_name=\"target\", max_iters=50)")
        self._indent -= 1

    def _translate_for_as_geometric_loop(self, stmt: ast.ForStmt) -> None:
        """Compile a for statement to a bounded geometric loop.

        A C-style for loop `for (init; cond; step)` compiles to N
        iterations of geometric rotation, where N is extracted from
        the condition bound when possible.
        """
        lid = self._next_loop_id()

        # Emit the init statement (e.g., var i = 0)
        if stmt.init:
            self._translate_stmt(stmt.init)

        # Extract loop bound from condition (e.g., i < 10 → 10 iterations)
        max_iters = self._extract_for_bound(stmt.condition)

        # Extract state variable from body
        state_var = self._extract_loop_state_var(stmt.body)

        # Build rotation and run
        self._emit(f"{lid}_R = _VSA.make_random_rotation("
                   f"angle=_np.pi / {max_iters}, n_planes=20, seed=_VSA.seed)")
        self._emit(f"# Bounded geometric loop: {max_iters} rotation steps")
        self._emit(f"for {lid}_i in range({max_iters}):")
        self._indent += 1
        self._emit(f"{state_var} = {lid}_R @ {state_var}")
        self._emit(f"{state_var} = _VSA.snap({state_var})")
        self._indent -= 1

    def _extract_loop_state_var(self, body: ast.Block) -> str:
        """Find the state variable being mutated in the loop body.

        Looks for assignment statements like `current = snap(...)` or
        `state = bind(state, ...)` and returns the target variable name.
        Falls back to '_loop_state' if no assignment is found.
        """
        for stmt in body.statements:
            if isinstance(stmt, ast.ExprStmt) and isinstance(stmt.expr, ast.Assignment):
                if isinstance(stmt.expr.target, ast.Identifier):
                    return stmt.expr.target.name
            if isinstance(stmt, ast.VarDecl):
                return stmt.name
        return "_loop_state"

    def _extract_loop_target(self, condition: ast.Expr) -> str:
        """Extract the target vector from a while condition.

        Handles patterns like:
          - similarity(current, target) < threshold → target
          - defuzzy(Cosine(current, target)) → target
          - a general expression → translate it as the target
        """
        # If condition is a comparison (e.g., similarity(x, y) < 0.9),
        # the second argument to the similarity call is the target.
        if isinstance(condition, ast.BinaryOp):
            if isinstance(condition.left, ast.Call):
                call = condition.left
                if (isinstance(call.callee, ast.Identifier)
                        and call.callee.name in ("similarity", "Cosine")
                        and len(call.args) >= 2):
                    return self._translate_expr(call.args[1])
            # Also check right side
            if isinstance(condition.right, ast.Call):
                call = condition.right
                if (isinstance(call.callee, ast.Identifier)
                        and call.callee.name in ("similarity", "Cosine")
                        and len(call.args) >= 2):
                    return self._translate_expr(call.args[1])
        # Fallback: translate the whole condition as an expression that
        # produces the target vector. The programmer should use
        # geometric_loop() directly for complex cases.
        return self._translate_expr(condition)

    def _extract_for_bound(self, condition) -> int:
        """Extract the iteration count from a for-loop condition.

        Handles `i < N` where N is an integer literal.
        Returns 20 as default if the bound can't be extracted.
        """
        if condition is None:
            return 20
        if isinstance(condition, ast.BinaryOp) and condition.op == "<":
            if isinstance(condition.right, ast.IntLiteral):
                return condition.right.value
        return 20

    # -- expressions ------------------------------------------------------

    def _char_literal_src(self, expr: ast.CharLiteral) -> str:
        """Override point for per-backend char literal lowering.

        The base fly-brain backend doesn't have a number-axis runtime
        yet — char literals are number-axis + synthetic flag, a
        concept tied to the extended-state-vector layout that only
        the numpy / pytorch backends implement. Refuse here; numpy
        and pytorch override.
        """
        raise CodegenNotSupported(
            expr,
            "character literals are not supported on the fly-brain backend "
            "(no number-axis runtime); use the numpy or pytorch backend",
        )

    def _unknown_literal_src(self, expr: ast.UnknownLiteral) -> str:
        """Override point for the `unknown` keyword — truth-axis neutral.

        Same story as char: the truth-axis representation lives on
        the extended-state-vector runtime, which is numpy / pytorch
        only. Base refuses; numpy and pytorch override to emit
        `_VSA.make_truth(0.0)`.
        """
        raise CodegenNotSupported(
            expr,
            "`unknown` is not supported on the fly-brain backend "
            "(no truth-axis runtime); use the numpy or pytorch backend",
        )

    def _translate_expr(self, expr: ast.Expr, *, map_key_type: str | None = None) -> str:
        if isinstance(expr, ast.StringLiteral):
            return repr(expr.value)
        if isinstance(expr, ast.IntLiteral):
            return repr(expr.value)
        if isinstance(expr, ast.FloatLiteral):
            return repr(expr.value)
        if isinstance(expr, ast.CharLiteral):
            return self._char_literal_src(expr)
        if isinstance(expr, ast.BoolLiteral):
            return "True" if expr.value else "False"
        if isinstance(expr, ast.UnknownLiteral):
            return self._unknown_literal_src(expr)
        if isinstance(expr, ast.Identifier):
            return expr.name
        if isinstance(expr, ast.Parenthesized):
            return f"({self._translate_expr(expr.inner)})"
        if isinstance(expr, ast.ArrayLiteral):
            inner = ", ".join(self._translate_expr(e) for e in expr.elements)
            return f"[{inner}]"
        if isinstance(expr, ast.MapLiteral):
            if map_key_type == "vector":
                pairs = ", ".join(
                    f"({self._translate_expr(k)}, {self._translate_expr(v)})"
                    for k, v in zip(expr.keys, expr.values)
                )
                return f"[{pairs}]"
            # Non-vector keys: real Python dict.
            pairs = ", ".join(
                f"{self._translate_expr(k)}: {self._translate_expr(v)}"
                for k, v in zip(expr.keys, expr.values)
            )
            return "{" + pairs + "}"
        if isinstance(expr, ast.Subscript):
            target_src = self._translate_expr(expr.target)
            index_src = self._translate_expr(expr.index)
            # dict<K, V> subscripts route through the rotation-hashmap.
            if (isinstance(expr.target, ast.Identifier)
                    and expr.target.name in self._dict_declared):
                return f"_VSA.hashmap_get({target_src}, {index_src})"
            # Vector-keyed map lookups route through the identity-first helper.
            if (isinstance(expr.target, ast.Identifier)
                    and self._map_key_type.get(expr.target.name) == "vector"):
                return f"_vector_map_lookup({target_src}, {index_src})"
            return f"{target_src}[{index_src}]"
        if isinstance(expr, ast.Call):
            return self._translate_call(expr)
        if isinstance(expr, ast.BinaryOp):
            left = self._translate_expr(expr.left)
            right = self._translate_expr(expr.right)
            return f"({left} {expr.op} {right})"
        if isinstance(expr, ast.UnaryOp):
            if expr.op == "!":
                raise CodegenNotSupported(
                    expr,
                    "source-level `!` is not yet lowered by the V1 codegen; rewrite "
                    "as an explicit permutation-key application using `permute(NOT_X, .)`",
                )
            return f"({expr.op}{self._translate_expr(expr.operand)})"
        if isinstance(expr, ast.MemberAccess):
            return f"{self._translate_expr(expr.obj)}.{expr.member}"
        if isinstance(expr, ast.EmbedExpr):
            return self._embed_expr_src(expr)
        raise CodegenNotSupported(
            expr, f"unsupported expression: {type(expr).__name__}"
        )

    def _embed_expr_src(self, expr: ast.EmbedExpr) -> str:
        """Override point for per-backend `embed(<expr>)` lowering.

        Raises on the fly-brain backend — no frozen-LLM embedding
        runtime there. Numpy / pytorch override to emit
        `_VSA.embed(<inner>)`.
        """
        raise CodegenNotSupported(
            expr,
            "embed(...) is not supported on the fly-brain backend; "
            "use the numpy or pytorch backend",
        )

    def _translate_call(self, call: ast.Call) -> str:
        # Resolve the callee: we only support direct calls to a VSA builtin
        # identifier in V1. User-defined function calls *within* the module
        # do work because they emit as plain Python function calls.
        callee = call.callee
        if isinstance(callee, ast.Identifier):
            name = callee.name
            # Fused bundle-of-binds: `bundle(bind(r1,f1), ..., bind(rN,fN))`
            # where every argument is a literal bind call. Emit the runtime's
            # `bundle_of_binds` primitive so the rotation stack + batched
            # matmul + sum can execute as three kernels (GPU) or one numpy
            # einsum (CPU), instead of N separate bind calls plus an N-arg
            # bundle. This is the independence structure of a role-filler
            # record: every (role, filler) pair is completely independent of
            # the others. Matches the 2026-04-22 "PyTorch/GPU gated on
            # scheduled parallel evaluation" item from STATUS.md.
            if (name == "bundle"
                    and len(call.args) >= 2
                    and all(_is_bind_call(a) for a in call.args)):
                pair_srcs = []
                for bind_call in call.args:
                    role_src = self._translate_expr(bind_call.args[0])
                    filler_src = self._translate_expr(bind_call.args[1])
                    pair_srcs.append(f"({role_src}, {filler_src})")
                return f"_VSA.bundle_of_binds({', '.join(pair_srcs)})"
            if name in BUILTINS:
                emitter, arity = BUILTINS[name]
                if arity is not None and len(call.args) != arity:
                    raise CodegenNotSupported(
                        call,
                        f"builtin `{name}` expects {arity} argument(s), "
                        f"got {len(call.args)}",
                    )
                arg_srcs = [self._translate_expr(a) for a in call.args]
                return emitter(arg_srcs)
            # User-defined call: emit as-is.
            arg_srcs = [self._translate_expr(a) for a in call.args]
            return f"{name}({', '.join(arg_srcs)})"
        if isinstance(callee, ast.MemberAccess):
            arg_srcs = [self._translate_expr(a) for a in call.args]
            return f"{self._translate_expr(callee)}({', '.join(arg_srcs)})"
        raise CodegenNotSupported(
            call, f"unsupported callee expression: {type(callee).__name__}"
        )


# ============================================================
# Module-level helper
# ============================================================


def translate_module(
    module: ast.Module,
    *,
    runtime_dim: int = 50,
    runtime_seed: int = 42,
    runtime_n_kc: int = 2000,
    runtime_use_hemibrain: bool = False,
) -> str:
    """Translate a parsed Sutra `Module` to a Python source string.

    Convenience wrapper around `FlyBrainCodegen`. Raises
    `CodegenNotSupported` with a source span for any unsupported node.
    """
    gen = FlyBrainCodegen(
        runtime_dim=runtime_dim,
        runtime_seed=runtime_seed,
        runtime_n_kc=runtime_n_kc,
        runtime_use_hemibrain=runtime_use_hemibrain,
    )
    return gen.translate(module)
