"""AST → Python source translator — backend-agnostic base.

This module walks a parsed Sutra `Module` and emits Python source.
Concrete backends (the CPU IR codegen and the PyTorch codegen)
subclass `BaseCodegen` and override `_emit_prelude` (and a few
per-backend hook methods for literal lowering — `_char_literal_src`,
`_embed_expr_src`, `_logical_op_src`, `_bool_literal_src`, etc.) to
target their specific runtime. The AST walker and the builtin-call
table are shared across backends.

See also `codegen.py` (the canonical CPU IR codegen) and
`codegen_pytorch.py` (the GPU/PyTorch codegen).

Unsupported AST nodes raise `CodegenNotSupported` with the source
span of the offending node so the CLI can print a compiler-style
`line:col` diagnostic instead of silently emitting wrong Python.
"""

from __future__ import annotations

from typing import List, Optional

from . import ast_nodes as ast


# Transcendental intrinsic names that the codegen actively rejects.
# The 2026-04-29 implementation was withdrawn 2026-04-30 because it
# ran as host Python scalar arithmetic at runtime, not as substrate
# tensor ops. The intrinsic declarations remain in `stdlib/math.su`
# (so the parser knows the names exist) but the codegen rejects any
# call before it reaches a backend. See
# `planning/findings/2026-04-30-runtime-substrate-purity-audit.md`.
_TRANSCENDENTALS_DISABLED = frozenset({
    "log", "sqrt", "exp", "sin", "cos", "tan", "pow",
})


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
    # make_truth — runtime methods provided by the _VSA runtime class.
    # A backend that doesn't implement them will fail at runtime with a
    # clear AttributeError.
    "real_number": (_builtin_real_number, 1),
    "complex_number": (_builtin_complex_number, 2),
    "truth_value": (_builtin_truth_value, 1),
}


# ============================================================
# Translator
# ============================================================


class BaseCodegen:
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
        # Maps variable names to their declared primitive-class type
        # string (`"complex"`, `"int"`, `"fuzzy"`, ...). Used by
        # `*` dispatch: if either operand is known to be a complex,
        # the BinaryOp lowers to _VSA.complex_mul instead of Python
        # element-wise multiply. Populated in _translate_var_decl.
        self._var_type: dict[str, str] = {}
        # Per-function-scope slot-table: maps slot-declared variable
        # name -> slot index. Populated when a `slot TYPE name = expr;`
        # is translated; reset at function entry. Each slot variable
        # gets a unique 2D Givens plane in the function-scope
        # `_slot_state` vector. Used by the Identifier emit path
        # (slot var -> _VSA.slot_load) and the Assignment emit path
        # (target is slot var -> _VSA.slot_store + reassign).
        self._slot_vars: dict[str, int] = {}
        # When unrolling a `loop (N) { ... }` with N a compile-time
        # integer literal, this is set to the current iteration's value
        # (1-based: 1, 2, ..., N) before each copy of the body is
        # translated. The Identifier translation path checks this when
        # it sees the name `iterator` and substitutes the constant.
        # Outside an unrolling context this stays None, and a reference
        # to `iterator` raises CodegenNotSupported.
        self._iterator_value: Optional[int] = None
        # Stack of state-parameter name lists, pushed when entering a
        # loop function body and popped on exit. Used by PassStmt
        # translation to know which Python locals to assign. Outside a
        # loop body the stack is empty and `pass` is a compile error.
        # Stack (not single value) so nested loop calls don't collide,
        # though loop-inside-loop bodies are an open question per the
        # design doc.
        self._loop_state_stack: List[List[str]] = []
        # Registry of loop function declarations seen so far in the
        # module, name -> LoopFunctionDecl. Used by LoopCallStmt
        # translation to look up the state-param shape for the call's
        # writeback. Populated in _translate_loop_function_decl.
        self._loop_decls: dict[str, "ast.LoopFunctionDecl"] = {}

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
        """Emit the top-of-module prelude for this backend.

        Each concrete backend (CPU IR, PyTorch) is responsible for
        importing its runtime, instantiating the _VSA class, and
        emitting any helper functions the translator references
        (`_argmax_cosine`, `_select_softmax`, `_vector_map_lookup`, ...).
        Called from `translate(module)` before the top-level walk.
        """
        raise NotImplementedError(
            "_emit_prelude must be implemented by a concrete backend subclass"
        )

    # -- top level --------------------------------------------------------

    def _translate_top_level(self, item: ast.TopLevel) -> None:
        if isinstance(item, ast.VarDecl):
            self._translate_var_decl(item, at_top_level=True)
        elif isinstance(item, ast.FunctionDecl):
            self._translate_function_decl(item)
        elif isinstance(item, ast.LoopFunctionDecl):
            self._translate_loop_function_decl(item)
        elif isinstance(item, ast.MethodDecl):
            raise CodegenNotSupported(
                item, "method declarations are not supported by the V1 codegen"
            )
        elif isinstance(item, ast.ClassDecl):
            # Class declarations are compile-time-only metadata. The
            # validator has already registered the inheritance chain
            # and verified it bottoms out at a primitive. Codegen
            # emits nothing — instances of user classes are plain
            # vectors at runtime, same as the primitive parent.
            return
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
        fall through to the default codegen path. Base returns None.
        """
        return None

    def _translate_var_decl(self, decl: ast.VarDecl, *, at_top_level: bool) -> None:
        # `slot TYPE name = expr;` — rotation-bound storage in the
        # synthetic subspace. Allocates a 2D Givens plane in the
        # function-scope slot state and emits slot_store / slot_load
        # for assignments / reads. The runtime primitives landed
        # 2026-04-24; this codegen integration landed 2026-04-25.
        if decl.is_slot:
            if at_top_level:
                raise CodegenNotSupported(
                    decl,
                    "slot declarations are only valid at function scope; "
                    "top-level slot vars don't have a state vector to "
                    "thread through.",
                )
            slot_idx = len(self._slot_vars)
            self._slot_vars[decl.name] = slot_idx
            init_src = (
                self._translate_expr(decl.initializer)
                if decl.initializer is not None
                else "0.0"
            )
            self._emit(
                f"_slot_state = _VSA.slot_store(_slot_state, {slot_idx}, "
                f"{init_src})"
            )
            return

        # Track map<K, V> declarations so that a later subscript on this
        # name can dispatch to the right lookup helper.
        if decl.type_ref is not None and decl.type_ref.name == "map":
            if len(decl.type_ref.type_args) >= 1:
                self._map_key_type[decl.name] = decl.type_ref.type_args[0].name
        # Record the declared type so binary-op dispatch can reason
        # about the value's primitive class later. Needed for `*`
        # to route complex multiplication through _VSA.complex_mul
        # instead of Python element-wise multiply.
        if decl.type_ref is not None:
            self._var_type[decl.name] = decl.type_ref.name
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

        # `int x = wait;` — explicit deferred initializer. The
        # validator enforces that a real assignment happens before
        # any read of `x`, so the value emitted here is a placeholder.
        # We reuse the same zero-of-type emission used for the
        # uninitialized var-colon form: same lowering, different
        # ergonomics (the `wait` keyword is the explicit signal in
        # source). Both backends inherit this path; only the validator
        # treats `wait` differently from "no initializer."
        is_wait_init = isinstance(decl.initializer, ast.WaitLiteral)

        # `var x : TYPE;` without an initializer — the rotation-bound
        # storage-slot form from the 2026-04-21 surface-syntax decision
        # (Candidate B: role/var). Emit a zero-valued slot of the
        # declared type. `var[N] x : TYPE;` emits a Python list of N
        # zero slots.
        if (decl.initializer is None and decl.is_var_colon) or is_wait_init:
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
            # Fuzzy / bool / trit / complex are (per spec target) scalars
            # on canonical axes. `trit` defaults to 0 — "explicit
            # neutrality," the first-class neutral on the truth axis.
            # `complex` defaults to 0+0i — the origin of the plane.
            # Until the full runtime lands for these in every backend,
            # use a plain float zero as the placeholder; the numpy /
            # pytorch backends' make_truth / make_complex paths are
            # used by initialized declarations.
            if type_name in ("fuzzy", "bool", "int", "scalar", "number",
                             "trit", "complex"):
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
        # Reset the slot table for this function scope. If the body
        # has any slot declarations we'll need a `_slot_state` local,
        # initialized to a zero vector before the first slot_store.
        outer_slot_vars = self._slot_vars
        self._slot_vars = {}
        if _has_slot_decl(decl.body):
            self._emit("_slot_state = _VSA.zero_vector()")
        if not decl.body.statements:
            self._emit("pass")
        else:
            for stmt in decl.body.statements:
                self._translate_stmt(stmt)
        self._slot_vars = outer_slot_vars
        self._indent -= 1

    # -- loop function declarations (Emma 2026-04-30) --------------------
    #
    # Loops with runtime data dependence are first-class declared functions
    # whose recurrent state is the named state parameters. Compiles to a
    # T-step soft-halt cell: each tick evaluates the condition, runs the
    # body (which uses `pass` to update state locals), accumulates a soft
    # halt indicator, and freezes state via soft-mux once halt saturates.
    # Spec: planning/open-questions/loop-function-declarations.md.

    _LOOP_T = 50  # max tick count per loop function — compile-time-fixed

    def _translate_loop_function_decl(self, decl: "ast.LoopFunctionDecl") -> None:
        """Emit a Python function for a loop function declaration."""
        # Register so LoopCallStmt knows the state-param shape.
        self._loop_decls[decl.name] = decl

        state_names = [p.name for p in decl.state_params]
        init_param_names = [f"_init_{n}" for n in state_names]

        self._emit(
            f"def _loop_{decl.name}({', '.join(init_param_names)}):"
        )
        self._indent += 1
        self._emit(
            f'"""Loop function `{decl.name}` (kind={decl.kind}).'
        )
        self._emit(f"")
        self._emit(
            f"T-step soft-halt cell. Returns ({', '.join(state_names) or 'no state'}, halt_cum)."
        )
        self._emit(f'"""')
        # State locals init from caller args.
        for state_name, init_name in zip(state_names, init_param_names):
            self._emit(f"{state_name} = {init_name}")
        self._emit("_halt_cum = 0.0")

        # Push state names so PassStmt translation knows what to assign.
        self._loop_state_stack.append(state_names)

        # do_while: body runs once unconditionally first.
        if decl.kind == "do_while":
            self._emit(f"# do_while: body runs once unconditionally first.")
            for inner in decl.body.statements:
                self._translate_stmt(inner)

        # T-step soft-halt loop. The Python `for _t in range(T)` is
        # meta-iteration over a compile-time-fixed count.
        self._emit(f"for _t in range({self._LOOP_T}):")
        self._indent += 1
        # Snapshot pre-step state for soft-mux freeze on halt.
        for state_name in state_names:
            self._emit(f"_pre_{state_name} = {state_name}")
        # Evaluate condition (semantics depend on kind).
        if decl.kind in ("do_while", "while_loop"):
            cond_src = self._translate_expr(decl.condition)
            self._emit(f"_keep = 1.0 if bool({cond_src}) else 0.0")
        elif decl.kind == "iterative_loop":
            # condition is the count; iterator = _t + 1 (1-indexed).
            count_src = self._translate_expr(decl.condition)
            self._emit(f"# iterative_loop: tick = _t+1, halt when tick > count.")
            self._emit(f"_iterator = _t + 1")
            self._emit(f"_keep = 1.0 if (_iterator <= int({count_src})) else 0.0")
        elif decl.kind == "foreach_loop":
            # foreach: condition is an array; element-binding TBD.
            # For V1, error out — implementation pending.
            raise CodegenNotSupported(
                decl,
                "foreach_loop kind is not yet implemented; only do_while, "
                "while_loop, iterative_loop are supported in V1. See "
                "planning/open-questions/loop-function-declarations.md.",
            )
        else:
            raise CodegenNotSupported(
                decl, f"unknown loop kind `{decl.kind}`"
            )
        self._emit(f"_halt_term = 1.0 - _keep")
        self._emit(f"_halt_cum = min(_halt_cum + _halt_term, 1.0)")
        # Body re-runs each tick; PassStmt updates state locals.
        for inner in decl.body.statements:
            self._translate_stmt(inner)
        # Soft mux: freeze state at pre-step value once halt saturates.
        for state_name in state_names:
            self._emit(
                f"{state_name} = (1.0 - _halt_cum) * {state_name} "
                f"+ _halt_cum * _pre_{state_name}"
            )
        self._indent -= 1  # close the for loop

        # Pop state stack.
        self._loop_state_stack.pop()

        # Return final state values + halt_cum (last).
        return_items = state_names + ["_halt_cum"]
        self._emit(f"return ({', '.join(return_items)},)")
        self._indent -= 1  # close the function

    def _translate_loop_call(self, stmt: "ast.LoopCallStmt") -> None:
        """Emit a call to a previously-declared loop function + writeback.

        State args at the call site MUST be slot-variable names; on
        completion, the loop's final state values are written back into
        those slot vars (by-reference). The condition arg is evaluated
        once (for any side effects + visual symmetry with the function-
        decl form) but its value is unused — the loop function uses its
        own decl-time condition expression against the state locals each
        tick.
        """
        decl = self._loop_decls.get(stmt.name)
        if decl is None:
            raise CodegenNotSupported(
                stmt,
                f"loop function `{stmt.name}` is not declared. Loop "
                f"functions must be declared with one of `do_while`, "
                f"`while_loop`, `iterative_loop`, `foreach_loop` keywords "
                f"before being invoked with `loop NAME(...)`.",
            )
        if len(stmt.state_arg_names) != len(decl.state_params):
            raise CodegenNotSupported(
                stmt,
                f"loop call `{stmt.name}` expects "
                f"{len(decl.state_params)} state arg(s), got "
                f"{len(stmt.state_arg_names)}",
            )
        # Each state arg must be a slot variable in the caller.
        slot_args: List[tuple[str, int]] = []
        for arg_name in stmt.state_arg_names:
            if arg_name not in self._slot_vars:
                raise CodegenNotSupported(
                    stmt,
                    f"loop call state argument `{arg_name}` must be a "
                    f"slot variable in the caller scope; was not declared "
                    f"with `slot TYPE name = ...`.",
                )
            slot_args.append((arg_name, self._slot_vars[arg_name]))
        # Evaluate the condition arg for side effects + parser symmetry.
        cond_src = self._translate_expr(stmt.condition_arg)
        self._emit(f"# loop call: {stmt.name}({cond_src}, ...)")
        self._emit(f"# Condition arg evaluated for side effects; runtime")
        self._emit(f"# uses the loop's decl-time condition expression.")
        self._emit(f"_ = {cond_src}")
        # Read current slot values to pass as init args.
        init_args = [
            f"_VSA.slot_load(_slot_state, {idx})"
            for _, idx in slot_args
        ]
        # Generate distinct names for the unpacked return values.
        ret_names = [f"_loopret_{n}" for n, _ in slot_args] + ["_loopret_halt"]
        self._emit(
            f"({', '.join(ret_names)},) = _loop_{stmt.name}("
            f"{', '.join(init_args)})"
        )
        # Write back to caller's slot vars.
        for (arg_name, idx), ret_name in zip(slot_args, ret_names[:-1]):
            self._emit(
                f"_slot_state = _VSA.slot_store(_slot_state, {idx}, "
                f"{ret_name})"
            )

    # -- statements -------------------------------------------------------

    def _translate_stmt(self, stmt: ast.Stmt) -> None:
        # PassStmt: tail-recursive yield in a loop function body.
        # Translates to assignment of the loop's state locals.
        # Handled here rather than in a more general dispatcher so that
        # it errors clearly outside a loop body.
        if isinstance(stmt, ast.PassStmt):
            if not self._loop_state_stack:
                raise CodegenNotSupported(
                    stmt,
                    "`pass` is only valid inside a loop function body. "
                    "See planning/open-questions/loop-function-declarations.md.",
                )
            state_names = self._loop_state_stack[-1]
            if len(stmt.values) != len(state_names):
                raise CodegenNotSupported(
                    stmt,
                    f"`pass` expects {len(state_names)} value(s) (one per "
                    f"state parameter `{', '.join(state_names)}`), got "
                    f"{len(stmt.values)}",
                )
            for state_name, value in zip(state_names, stmt.values):
                if isinstance(value, ast.ReplaceMarker):
                    # `replace` keyword: restore the parameter's input value.
                    self._emit(f"{state_name} = _init_{state_name}")
                else:
                    value_src = self._translate_expr(value)
                    self._emit(f"{state_name} = {value_src}")
            return
        # LoopCallStmt: invoke a loop function and write back state.
        if isinstance(stmt, ast.LoopCallStmt):
            self._translate_loop_call(stmt)
            return
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
                # Slot-bound variable assignment: `x = expr;` where
                # x is a slot variable lowers to `_slot_state =
                # _VSA.slot_store(_slot_state, idx, value)`. Compound
                # assignment (+=, -=) on slot variables would need
                # to read-modify-write through the slot — left for a
                # follow-up since the imperative-reversible pattern
                # only needs plain `=` to demonstrate.
                if (isinstance(expr.target, ast.Identifier)
                        and expr.target.name in self._slot_vars):
                    if expr.op != "=":
                        raise CodegenNotSupported(
                            stmt,
                            f"compound assignment on a slot variable "
                            f"(`{expr.op}`) is not yet supported; use "
                            "plain `=` for now",
                        )
                    idx = self._slot_vars[expr.target.name]
                    value_src = self._translate_expr(expr.value)
                    self._emit(
                        f"_slot_state = _VSA.slot_store(_slot_state, "
                        f"{idx}, {value_src})"
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
                "if/else is not supported by the V1 codegen — the whole "
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
                # Save and restore _iterator_value across the unroll —
                # nested unrolling loops save the outer value and pop
                # it back when this loop finishes. The keyword always
                # binds to the innermost surrounding unrolled loop.
                saved_iter = self._iterator_value
                for i in range(n):
                    self._iterator_value = i + 1  # 1-based: 1..N
                    for inner in stmt.body.statements:
                        self._translate_stmt(inner)
                self._iterator_value = saved_iter
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
        BaseCodegen._loop_counter += 1
        return f"_loop{BaseCodegen._loop_counter}"

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

        Char literals depend on the number-axis runtime, which the
        CPU IR and PyTorch backends implement via the extended-state
        layout. Base refuses; concrete backends override.
        """
        raise CodegenNotSupported(
            expr,
            "character literals require a number-axis runtime "
            "(extended-state layout) — overridden by the concrete backends",
        )

    def _unknown_literal_src(self, expr: ast.UnknownLiteral) -> str:
        """Override point for the `unknown` keyword — truth-axis neutral.

        Truth-axis representation lives on the extended-state-vector
        runtime. Base refuses; concrete backends override to emit
        `_VSA.make_truth(0.0)`.
        """
        raise CodegenNotSupported(
            expr,
            "`unknown` requires a truth-axis runtime "
            "(extended-state layout) — overridden by the concrete backends",
        )

    def _imaginary_literal_src(self, expr: ast.ImaginaryLiteral) -> str:
        """Override point for `5i`-style imaginary literals.

        Same extended-state-vector dependency as the truth-axis and
        char literals. Base refuses; concrete backends override to emit
        `_VSA.make_complex(0.0, magnitude)`.
        """
        raise CodegenNotSupported(
            expr,
            "imaginary literals require a complex-plane runtime "
            "(extended-state layout) — overridden by the concrete backends",
        )

    def _complex_literal_src(self, expr: ast.ComplexLiteral) -> str:
        """Override point for fold-produced `ComplexLiteral(re, im)` nodes.

        Only produced by the simplifier folding `N + Mi` / `N - Mi`
        patterns. Base refuses; concrete backends override.
        """
        raise CodegenNotSupported(
            expr,
            "complex literals require a complex-plane runtime "
            "(extended-state layout) — overridden by the concrete backends",
        )

    def _bool_literal_src(self, expr: ast.BoolLiteral) -> str:
        """Override point for `true` / `false` lowering.

        Base emits the Python literals directly. Concrete backends
        override to emit `_VSA.make_truth(±1.0)` so the entire runtime
        is vector-native (no Python-bool / vector split).
        """
        return "True" if expr.value else "False"

    def _logical_op_src(self, expr: ast.BinaryOp, op: str,
                        left_src: str, right_src: str) -> str:
        """Override point for `&&` and `||` on truth-axis values.

        Without a truth-axis runtime the Zadeh-min / max semantics
        can't be honored, and a silent Python `and`/`or` fallback
        would be wrong for fuzzy operands (CLAUDE.md §"NO MATH
        SHORTCUTS"). Base refuses; concrete backends override and
        implement properly.
        """
        raise CodegenNotSupported(
            expr,
            f"logical `{op}` requires a truth-axis runtime "
            "(extended-state layout) — overridden by the concrete backends",
        )

    def _logical_not_src(self, expr: ast.UnaryOp, operand_src: str) -> str:
        """Override point for `!` (logical not) on truth-axis values.

        Base refuses — the spec-aligned lowering is truth-axis
        negation, which requires the extended-state runtime.
        (The earlier permutation-based NOT was retired as a category
        error.)
        """
        raise CodegenNotSupported(
            expr,
            "source-level `!` is not yet lowered by the V1 codegen base; "
            "the spec-aligned lowering is truth-axis negation, "
            "implemented by the concrete backends",
        )

    def _equality_src(self, expr: ast.BinaryOp, op: str,
                      left_src: str, right_src: str) -> str:
        """Override point for `==` / `!=` on vectors.

        Base refuses — naive Python `a == b` on numpy arrays returns
        an element-wise boolean array which then explodes with
        'ambiguous truth value' when used in any boolean context.
        The spec-aligned lowering is cosine-similarity projected onto
        the truth axis, which requires the extended-state runtime.
        Numpy / pytorch override.
        """
        raise CodegenNotSupported(
            expr,
            f"source-level `{'==' if op == 'eq' else '!='}` on vectors "
            "is not supported by this backend; the spec-aligned lowering "
            "is cosine-similarity on the truth axis (numpy / pytorch only)",
        )

    def _is_complex_expr(self, expr: ast.Expr) -> bool:
        """True iff expr is provably a complex-plane value at compile time.

        Conservative: returns True only for cases the codegen can be
        certain about without full type inference. Returning False just
        means `*` falls through to element-wise multiply, so wrong
        answers only happen if the caller passes a complex-typed
        runtime value through a code path the compiler can't see.
        """
        if isinstance(expr, (ast.ComplexLiteral, ast.ImaginaryLiteral)):
            return True
        if isinstance(expr, ast.Identifier):
            return self._var_type.get(expr.name) == "complex"
        if isinstance(expr, ast.Parenthesized):
            return self._is_complex_expr(expr.inner)
        # Recurse into BinaryOp: if either side of an inner arithmetic
        # expression is complex, the whole expression is complex-typed.
        if isinstance(expr, ast.BinaryOp) and expr.op in ("+", "-", "*"):
            return (self._is_complex_expr(expr.left)
                    or self._is_complex_expr(expr.right))
        if isinstance(expr, ast.UnaryOp) and expr.op in ("-", "+"):
            return self._is_complex_expr(expr.operand)
        return False

    _TRUTH_TYPES = frozenset({"bool", "fuzzy", "trit"})
    _NUMBER_TYPES = frozenset({"int", "float", "complex", "scalar", "char"})

    def _is_number_expr(self, expr: ast.Expr) -> bool:
        """True iff expr is provably a number-axis value at compile time.

        Used by `<` / `>` dispatch to decide whether to route through
        the substrate's number-axis comparison. Numeric literals,
        number-typed identifiers, and unary +/- on same all qualify.
        Conservative — unknown types fall through to Python scalar
        comparison, which still handles plain Python ints / floats.
        """
        if isinstance(expr, (ast.IntLiteral, ast.FloatLiteral,
                             ast.ImaginaryLiteral, ast.ComplexLiteral,
                             ast.CharLiteral)):
            return True
        if isinstance(expr, ast.Identifier):
            return self._var_type.get(expr.name) in self._NUMBER_TYPES
        if isinstance(expr, ast.Parenthesized):
            return self._is_number_expr(expr.inner)
        if isinstance(expr, ast.BinaryOp) and expr.op in ("+", "-", "*", "/", "%"):
            return (self._is_number_expr(expr.left)
                    or self._is_number_expr(expr.right))
        if isinstance(expr, ast.UnaryOp) and expr.op in ("-", "+"):
            return self._is_number_expr(expr.operand)
        return False

    def _is_truth_expr(self, expr: ast.Expr) -> bool:
        """True iff expr is provably a truth-axis value at compile time.

        Used by `<` / `>` / `<=` / `>=` dispatch so comparisons route
        through the polynomial form when operands are truth-family,
        and fall back to Python scalar comparison for plain numbers.
        Conservative: bool literals, unknown, truth-typed identifiers,
        and the output of logical / comparison / equality operators
        all count.
        """
        if isinstance(expr, (ast.BoolLiteral, ast.UnknownLiteral)):
            return True
        if isinstance(expr, ast.Identifier):
            return self._var_type.get(expr.name) in self._TRUTH_TYPES
        if isinstance(expr, ast.Parenthesized):
            return self._is_truth_expr(expr.inner)
        # Logical / comparison / equality ops all return truth-axis
        # values, so an expression built from them is truth-typed too.
        if isinstance(expr, ast.BinaryOp):
            if expr.op in ("&&", "||", "==", "!=", "<", ">", "<=", ">="):
                return True
            # Pass-through through arithmetic on truth-axis operands
            # (rare, but `fuzzy_a - fuzzy_b` is a truth-axis vector).
            if expr.op in ("+", "-"):
                return (self._is_truth_expr(expr.left)
                        or self._is_truth_expr(expr.right))
        if isinstance(expr, ast.UnaryOp) and expr.op == "!":
            return True
        if isinstance(expr, ast.UnaryOp) and expr.op in ("-", "+"):
            return self._is_truth_expr(expr.operand)
        return False

    def _complex_mul_src(self, expr: ast.BinaryOp,
                        left_src: str, right_src: str) -> str:
        """Override point for `complex * anything` / `anything * complex`.

        Base refuses — the complex-multiplication runtime lives on
        the extended-state backends (numpy / pytorch). Fly-brain
        has no real/imag-axis representation.
        """
        raise CodegenNotSupported(
            expr,
            "complex multiplication is not supported by this backend "
            "(no real/imag-axis runtime); use the numpy or pytorch backend",
        )

    def _comparison_src(self, expr: ast.BinaryOp, op: str,
                        left_src: str, right_src: str) -> str:
        """Override point for `<` / `>` / `<=` / `>=` on number-axis values.

        `op` is `gt` or `lt` — `>=` maps to `gt` and `<=` to `lt`
        (ties give 0 = unknown in both, so the strict / non-strict
        distinction collapses). The numpy / pytorch backends project
        both operands onto the real axis, subtract, and sign the
        result onto the truth axis. Fly-brain refuses — no number-
        axis runtime.
        """
        raise CodegenNotSupported(
            expr,
            f"ordered comparison `{expr.op}` is not supported by this "
            "backend; use the numpy or pytorch backend",
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
        if isinstance(expr, ast.ImaginaryLiteral):
            return self._imaginary_literal_src(expr)
        if isinstance(expr, ast.ComplexLiteral):
            return self._complex_literal_src(expr)
        if isinstance(expr, ast.BoolLiteral):
            return self._bool_literal_src(expr)
        if isinstance(expr, ast.UnknownLiteral):
            return self._unknown_literal_src(expr)
        if isinstance(expr, ast.Identifier):
            # `iterator`: contextual keyword inside an unrolling
            # `loop (N) { ... }` body. The bounded-loop translator
            # sets self._iterator_value to the current iteration's
            # constant (1..N) before translating each copy of the
            # body; here we substitute the literal. Outside an
            # unrolling context, the reference is a compile error.
            if expr.name == "iterator":
                if self._iterator_value is None:
                    raise CodegenNotSupported(
                        expr,
                        "`iterator` is only valid inside an unrolling "
                        "`loop (N) { ... }` body where N is a compile-time "
                        "integer literal. Use `loop (N as i)` and reference "
                        "`i` instead for the named-index form.",
                    )
                return repr(self._iterator_value)
            # If this identifier names a slot-bound variable, emit
            # the slot_load call instead of a bare name reference.
            # The slot table is per-function-scope.
            if expr.name in self._slot_vars:
                idx = self._slot_vars[expr.name]
                return f"_VSA.slot_load(_slot_state, {idx})"
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
            # Logical operators dispatch through the substrate so they
            # work uniformly on bool / fuzzy / trit / truth-axis-vector
            # inputs. Zadeh fuzzy logic — min for AND, max for OR — on
            # the truth axis. See _logical_op_src for the override hook.
            if expr.op == "&&":
                return self._logical_op_src(expr, "and", left, right)
            if expr.op == "||":
                return self._logical_op_src(expr, "or", left, right)
            # Vector equality / inequality — cosine similarity projected
            # onto the truth axis. `a == b` returns a truth-axis vector
            # (a fuzzy), not a Python bool. Hook dispatched so backends
            # without a truth-axis runtime can refuse instead of emitting
            # Python == which does the wrong thing on numpy arrays.
            if expr.op == "==":
                return self._equality_src(expr, "eq", left, right)
            if expr.op == "!=":
                return self._equality_src(expr, "neq", left, right)
            # Complex multiplication dispatch: if either operand is
            # provably a complex-plane value (literal or complex-typed
            # variable), route `*` through the substrate's complex_mul
            # rather than element-wise Python multiply. Real-only
            # multiplication (int * int, float * float) stays on the
            # Python scalar fast path — there's no need to box scalars
            # into d-dim vectors to compute 5 * 3.
            if expr.op == "*" and (self._is_complex_expr(expr.left)
                                   or self._is_complex_expr(expr.right)):
                return self._complex_mul_src(expr, left, right)
            # Ordered comparison `>` / `<` / `>=` / `<=` is number-axis
            # only. Strict (>, <) give -1 on ties; non-strict (>=, <=)
            # give +1 on ties. Four distinct runtime methods — gt / lt
            # for strict, ge / le for non-strict. Truth-family operands
            # are rejected at compile time; plain Python scalars fall
            # through to Python's own comparison (which is fine for
            # int / float).
            _CMP_OP_NAMES = {">": "gt", "<": "lt", ">=": "ge", "<=": "le"}
            if expr.op in _CMP_OP_NAMES:
                if (self._is_truth_expr(expr.left)
                        or self._is_truth_expr(expr.right)):
                    raise CodegenNotSupported(
                        expr,
                        f"ordered comparison `{expr.op}` is not defined "
                        "on truth-axis values (bool / fuzzy / trit); "
                        "comparison is a number-axis operation. "
                        "Override the operator on a custom class if you "
                        "need comparison semantics for a truth-family type."
                    )
                if (self._is_number_expr(expr.left)
                        or self._is_number_expr(expr.right)):
                    return self._comparison_src(
                        expr, _CMP_OP_NAMES[expr.op], left, right
                    )
            return f"({left} {expr.op} {right})"
        if isinstance(expr, ast.UnaryOp):
            if expr.op == "!":
                return self._logical_not_src(expr, self._translate_expr(expr.operand))
            return f"({expr.op}{self._translate_expr(expr.operand)})"
        if isinstance(expr, ast.MemberAccess):
            return f"{self._translate_expr(expr.obj)}.{expr.member}"
        if isinstance(expr, ast.EmbedExpr):
            return self._embed_expr_src(expr)
        if isinstance(expr, ast.DefuzzyExpr):
            return self._defuzzy_expr_src(expr)
        raise CodegenNotSupported(
            expr, f"unsupported expression: {type(expr).__name__}"
        )

    def _embed_expr_src(self, expr: ast.EmbedExpr) -> str:
        """Override point for per-backend `embed(<expr>)` lowering.

        Base refuses — no frozen-LLM embedding runtime here.
        Concrete backends override to emit `_VSA.embed(<inner>)`.
        """
        raise CodegenNotSupported(
            expr,
            "embed(...) requires a frozen-LLM embedding runtime — "
            "overridden by the concrete backends",
        )

    def _defuzzy_expr_src(self, expr: ast.DefuzzyExpr) -> str:
        """Override point for `defuzzy(<expr>)` lowering.

        Base refuses — no truth-axis runtime to project onto.
        Concrete backends override to emit `_VSA.defuzzify(<inner>)`
        which matmul-projects onto the truth axis then iterates
        `eq(., true)` N times (default 10, matching the user's
        stated semantics).
        """
        raise CodegenNotSupported(
            expr,
            "defuzzy(...) requires a truth-axis runtime "
            "(extended-state layout) — overridden by the concrete backends",
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
            # scheduled parallel evaluation" item from queue.md.
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
            # Transcendental intrinsics — disabled 2026-04-30. The
            # 2026-04-29 implementation ran as Python scalar arithmetic at
            # runtime, not as substrate tensor ops. Withdrawn rather than
            # left as a working-but-architecturally-wrong impl. The future
            # direction is eigenrotation-as-modulus (see stdlib/math.su
            # and planning/findings/2026-04-30-runtime-substrate-purity-audit.md).
            # Programs that use these names fail to compile here.
            if name in _TRANSCENDENTALS_DISABLED:
                raise CodegenNotSupported(
                    call,
                    f"transcendental intrinsic `{name}` is not implemented. "
                    f"The 2026-04-29 implementation was withdrawn 2026-04-30 "
                    f"because it ran as host Python scalar arithmetic at "
                    f"runtime, violating the substrate-purity contract. "
                    f"See `sdk/sutra-compiler/sutra_compiler/stdlib/math.su` "
                    f"and `planning/findings/2026-04-30-runtime-substrate-purity-audit.md` "
                    f"for the rationale and the eigenrotation-as-modulus future direction.",
                )
            # Stdlib intrinsic? Route to the runtime class so the leaf
            # primitive (dot, sqrt, tanh, make_truth, embed, ...) is
            # dispatched to _VSA.<name>(...) instead of a bare identifier
            # call that would fail to resolve in the emitted Python.
            from .stdlib_loader import intrinsic_names
            if name in intrinsic_names():
                arg_srcs = [self._translate_expr(a) for a in call.args]
                return f"_VSA.{name}({', '.join(arg_srcs)})"
            # User-defined call: emit as-is.
            arg_srcs = [self._translate_expr(a) for a in call.args]
            return f"{name}({', '.join(arg_srcs)})"
        if isinstance(callee, ast.MemberAccess):
            arg_srcs = [self._translate_expr(a) for a in call.args]
            return f"{self._translate_expr(callee)}({', '.join(arg_srcs)})"
        raise CodegenNotSupported(
            call, f"unsupported callee expression: {type(callee).__name__}"
        )


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def _has_slot_decl(block: ast.Block) -> bool:
    """True iff `block` contains a `slot TYPE name [= expr];`
    declaration anywhere in its statement list. Used by
    `_translate_function_decl` to decide whether to emit the
    `_slot_state = _VSA.zero_vector()` initializer at the top of
    the function body. Doesn't recurse into nested control flow —
    if a slot decl appears inside a loop / branch, it'll still
    work at runtime (the slot_store call references _slot_state),
    so the only thing this scan affects is whether _slot_state is
    initialized when the function has zero slot decls at the top
    level.
    """
    if block is None:
        return False
    for stmt in block.statements:
        if isinstance(stmt, ast.VarDecl) and stmt.is_slot:
            return True
        # Recurse into common containers so a slot decl inside an
        # if/loop branch still triggers the init.
        if isinstance(stmt, ast.IfStmt):
            if _has_slot_decl(stmt.then_branch):
                return True
            if stmt.else_branch is not None and _has_slot_decl(stmt.else_branch):
                return True
        elif isinstance(stmt, ast.Block):
            if _has_slot_decl(stmt):
                return True
        elif isinstance(stmt, ast.LoopStmt):
            if _has_slot_decl(stmt.body):
                return True
        elif isinstance(stmt, ast.WhileStmt):
            if _has_slot_decl(stmt.body):
                return True
    return False


