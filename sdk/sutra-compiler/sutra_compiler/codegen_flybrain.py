"""AST → FlyBrainVSA Python source translator.

This module walks a parsed Akasha `Module` and emits Python source that
targets the `FlyBrainVSA` runtime in `fly-brain/vsa_operations.py`. The
generated code mirrors the shape of the hand-written
`fly-brain/permutation_conditional.py` but is produced mechanically from
the corresponding `.ak` source — closing the "compile-to-brain" gap
described in `fly-brain/STATUS.md` §Medium term.

Scope for V1 (deliberately narrow):
    - Top-level `VarDecl` with `vector`, `permutation`, or `map<_, _>` type
    - Top-level `FunctionDecl`
    - Inside functions: `VarDecl`, `ReturnStmt`, `ExprStmt` over `Assignment`
    - Expressions: `Identifier`, `StringLiteral`, `Call` to a VSA builtin,
      `ArrayLiteral`, `Subscript`, `MapLiteral`, `Parenthesized`
    - Deterministic substrate via `FixedFrameFlyBrainVSA` (fixed-frame
      contract is the "compile-time guarantee" item from the todo.)

Anything outside that scope raises `CodegenNotSupported` with the source
span of the offending node, which is strictly better than silently
emitting incorrect Python. Loops are *intentionally* unsupported — they
are the next research question in `fly-brain/STATUS.md`, not a codegen
oversight.
"""

from __future__ import annotations

from typing import List

from . import ast_nodes as ast


# ============================================================
# Error type
# ============================================================


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
# Each entry maps an Akasha builtin identifier to a callable that takes
# the already-translated argument strings and returns the Python
# expression to emit. Keeping this as a single table means the list of
# supported builtins is easy to audit against `planning/akasha-spec/21-builtins.md`.

def _builtin_basis_vector(args: List[str]) -> str:
    return f"_VSA.embed({args[0]})"


def _builtin_permutation_key(args: List[str]) -> str:
    return f"_VSA.make_permutation_key({args[0]})"


def _builtin_permute(args: List[str]) -> str:
    return f"_VSA.permute({args[0]}, {args[1]})"


def _builtin_bind(args: List[str]) -> str:
    return f"_VSA.bind({args[0]}, {args[1]})"


def _builtin_unbind(args: List[str]) -> str:
    return f"_VSA.unbind({args[0]}, {args[1]})"


def _builtin_bundle(args: List[str]) -> str:
    return f"_VSA.bundle({', '.join(args)})"


def _builtin_similarity(args: List[str]) -> str:
    return f"_VSA.similarity({args[0]}, {args[1]})"


def _builtin_snap(args: List[str]) -> str:
    return f"_VSA.snap({args[0]})"


def _builtin_identity_permutation(args: List[str]) -> str:
    return "_np.ones(_VSA.dim)"


def _builtin_argmax_cosine(args: List[str]) -> str:
    return f"_argmax_cosine({args[0]}, {args[1]})"


def _builtin_compose(args: List[str]) -> str:
    # Composition of two sign-flip permutations is pointwise multiply.
    return f"({args[0]} * {args[1]})"


BUILTINS = {
    "basis_vector": (_builtin_basis_vector, 1),
    "permutation_key": (_builtin_permutation_key, 1),
    "identity_permutation": (_builtin_identity_permutation, 0),
    "permute": (_builtin_permute, 2),
    "bind": (_builtin_bind, 2),
    "unbind": (_builtin_unbind, 2),
    "bundle": (_builtin_bundle, None),   # variadic, at least 1
    "similarity": (_builtin_similarity, 2),
    "snap": (_builtin_snap, 1),
    "argmax_cosine": (_builtin_argmax_cosine, 2),
    "compose": (_builtin_compose, 2),
}


# ============================================================
# Translator
# ============================================================


class FlyBrainCodegen:
    """Stateful walker that emits Python source for one Akasha module.

    Instances are single-use — call `translate(module)` and then read
    `.output`. Not thread-safe, not reusable.
    """

    def __init__(self, *, runtime_dim: int = 50, runtime_seed: int = 42,
                 runtime_n_kc: int = 2000) -> None:
        self.runtime_dim = runtime_dim
        self.runtime_seed = runtime_seed
        self.runtime_n_kc = runtime_n_kc
        self._lines: List[str] = []
        self._indent = 0
        # Maps variable names to the *key* type of a map-typed declaration
        # so subscript expressions know whether to use the identity-based
        # vector-map helper or a plain dict lookup.
        self._map_key_type: dict[str, str] = {}

    # -- emission helpers -------------------------------------------------

    def _emit(self, line: str = "") -> None:
        if line:
            self._lines.append("    " * self._indent + line)
        else:
            self._lines.append("")

    @property
    def output(self) -> str:
        return "\n".join(self._lines) + "\n"

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
        self._emit("bridge = SpikeVSABridge(")
        self._indent += 1
        self._emit("dim=self.dim, seed=self.seed, n_kc=self.n_kc,")
        self._indent -= 1
        self._emit(")")
        self._emit("# Fit the biologically-plausible learned MBON readout.")
        self._emit("# Class-level cache in SpikeVSABridge makes this a")
        self._emit("# trivial hit on every call after the first.")
        self._emit("bridge.fit_learned_readout()")
        self._emit("decoded, _ = bridge.round_trip(vector, self.snap_duration_ms)")
        self._emit("return decoded")
        self._indent -= 1
        self._indent -= 1
        self._emit()
        self._emit()
        self._emit(
            f"_VSA = _FixedFrameFlyBrainVSA(dim={self.runtime_dim}, "
            f"n_kc={self.runtime_n_kc}, seed={self.runtime_seed})"
        )
        self._emit()
        self._emit()
        self._emit("def _argmax_cosine(query, candidates):")
        self._indent += 1
        self._emit('"""Return the candidate with the largest cosine similarity to query."""')
        self._emit("best = None")
        self._emit("best_score = float('-inf')")
        self._emit("for c in candidates:")
        self._indent += 1
        self._emit("s = _VSA.similarity(query, c)")
        self._emit("if s > best_score:")
        self._indent += 1
        self._emit("best_score = s")
        self._emit("best = c")
        self._indent -= 1
        self._indent -= 1
        self._emit("return best")
        self._indent -= 1
        self._emit()
        self._emit()
        self._emit("def _vector_map_lookup(pairs, key):")
        self._indent += 1
        self._emit('"""Identity-first lookup for vector-keyed maps, cosine fallback."""')
        self._emit("for k, v in pairs:")
        self._indent += 1
        self._emit("if k is key:")
        self._indent += 1
        self._emit("return v")
        self._indent -= 1
        self._indent -= 1
        self._emit("best_v = None")
        self._emit("best_score = float('-inf')")
        self._emit("for k, v in pairs:")
        self._indent += 1
        self._emit("s = _VSA.similarity(key, k)")
        self._emit("if s > best_score:")
        self._indent += 1
        self._emit("best_score = s")
        self._emit("best_v = v")
        self._indent -= 1
        self._indent -= 1
        self._emit("return best_v")
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

    def _translate_var_decl(self, decl: ast.VarDecl, *, at_top_level: bool) -> None:
        # Track map<K, V> declarations so that a later subscript on this
        # name can dispatch to the right lookup helper.
        if decl.type_ref is not None and decl.type_ref.name == "map":
            if len(decl.type_ref.type_args) >= 1:
                self._map_key_type[decl.name] = decl.type_ref.type_args[0].name
        if decl.initializer is None:
            raise CodegenNotSupported(
                decl, f"uninitialized declaration `{decl.name}` not supported"
            )
        init_src = self._translate_expr(decl.initializer, map_key_type=(
            decl.type_ref.type_args[0].name
            if decl.type_ref is not None
            and decl.type_ref.name == "map"
            and len(decl.type_ref.type_args) >= 1
            else None
        ))
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
                if expr.op != "=":
                    raise CodegenNotSupported(
                        stmt, f"compound assignment `{expr.op}` not supported"
                    )
                target_src = self._translate_expr(expr.target)
                value_src = self._translate_expr(expr.value)
                self._emit(f"{target_src} = {value_src}")
                return
            self._emit(self._translate_expr(expr))
            return
        if isinstance(stmt, ast.Block):
            for inner in stmt.statements:
                self._translate_stmt(inner)
            return
        if isinstance(stmt, (ast.WhileStmt, ast.ForStmt, ast.ForeachStmt, ast.DoWhileStmt)):
            raise CodegenNotSupported(
                stmt,
                "loops are intentionally unsupported by the V1 fly-brain codegen; "
                "see fly-brain/STATUS.md §Loops for why",
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

    # -- expressions ------------------------------------------------------

    def _translate_expr(self, expr: ast.Expr, *, map_key_type: str | None = None) -> str:
        if isinstance(expr, ast.StringLiteral):
            return repr(expr.value)
        if isinstance(expr, ast.IntLiteral):
            return repr(expr.value)
        if isinstance(expr, ast.FloatLiteral):
            return repr(expr.value)
        if isinstance(expr, ast.BoolLiteral):
            return "True" if expr.value else "False"
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
        raise CodegenNotSupported(
            expr, f"unsupported expression: {type(expr).__name__}"
        )

    def _translate_call(self, call: ast.Call) -> str:
        # Resolve the callee: we only support direct calls to a VSA builtin
        # identifier in V1. User-defined function calls *within* the module
        # do work because they emit as plain Python function calls.
        callee = call.callee
        if isinstance(callee, ast.Identifier):
            name = callee.name
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
) -> str:
    """Translate a parsed Akasha `Module` to a Python source string.

    Convenience wrapper around `FlyBrainCodegen`. Raises
    `CodegenNotSupported` with a source span for any unsupported node.
    """
    gen = FlyBrainCodegen(
        runtime_dim=runtime_dim,
        runtime_seed=runtime_seed,
        runtime_n_kc=runtime_n_kc,
    )
    return gen.translate(module)
