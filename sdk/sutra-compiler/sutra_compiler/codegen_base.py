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


# Transcendentals not yet wired through the substrate. Empty as of
# 2026-05-10 — exp / log / pow / sqrt landed via the interpolated
# lookup table, sin / cos / tan landed via the same architecture with
# modulo-reduction to [-π, π] (periodic functions don't need an
# overflow exception). See
# planning/findings/2026-05-10-interpolated-lookup-table-works.md.
_TRANSCENDENTALS_DISABLED = frozenset()


# Mapping from Sutra operator symbols to the spelled-out form used in
# mangled function names. User-class operator overloads emit as
# `Class_operator_<name>` so the Python identifier is valid.
_OP_NAME_TO_PYTHON = {
    "+": "plus", "-": "minus", "*": "mul", "/": "div", "%": "mod",
    "==": "eq", "!=": "neq",
    "<": "lt", ">": "gt", "<=": "le", ">=": "ge",
    "!": "not",
}


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


def _and_chain(parts: List[str]) -> str:
    """Fold `parts` into a left-associative `_VSA.logical_and` chain.
    `[x, y, z]` -> `_VSA.logical_and(_VSA.logical_and(x, y), z)`."""
    if len(parts) == 0:
        return "_VSA.make_truth(1.0)"
    if len(parts) == 1:
        return parts[0]
    expr = parts[0]
    for p in parts[1:]:
        expr = f"_VSA.logical_and({expr}, {p})"
    return expr


def _builtin_equals(args: List[str]) -> str:
    """N-ary equality: `Equals(a, b, c, ...)` -> all-pairwise-equal
    along the chain. Lowers to fuzzy-AND of `_VSA.eq(a, b)` between
    each adjacent pair. Produced by the parser's chained-comparison
    reduction for `a == b == c == ...`."""
    if len(args) < 2:
        return "_VSA.make_truth(1.0)"
    pairs = [f"_VSA.eq({args[i]}, {args[i + 1]})" for i in range(len(args) - 1)]
    return _and_chain(pairs)


def _builtin_has_order(args: List[str]) -> str:
    """Strict-ascending check: `hasOrder(a, b, c, ...)` ->
    fuzzy-AND of `(b > a)` for each adjacent pair. The runtime's
    `_VSA.gt` is intrinsic; `a < b` is just `b > a`. Produced by
    the parser's chained-comparison reduction for `a < b < c < ...`
    (or `a > b > c > ...` with args reversed so the reduction is
    always-ascending)."""
    if len(args) < 2:
        return "_VSA.make_truth(1.0)"
    pairs = [f"_VSA.gt({args[i + 1]}, {args[i]})" for i in range(len(args) - 1)]
    return _and_chain(pairs)


def _builtin_has_order_or_equal(args: List[str]) -> str:
    """Non-strict-ascending check: `hasOrderOrEqual(a, b, c, ...)`.
    The current K3-tanh `<=` collapses to `<` (both produce
    tanh(0)=0 on exact ties); when a real `le` semantics lands the
    body switches. For now this is identical to `hasOrder`."""
    return _builtin_has_order(args)




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
    # `compose` over the permutation primitive class is elementwise
    # multiplication of the two underlying ±1 mask vectors.
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


def _builtin_array_length(args: List[str]) -> str:
    # `array_length(arr)` — Python `len(arr)` for plain lists. Used by
    # the TS transpiler's `arr.length` lowering for primitive arrays.
    # The runtime's `_VSA.array_length` works on tensor binding-arrays;
    # this builtin path handles the Python-list case which TS array
    # literals lower to.
    return f"len({args[0]})"


def _builtin_array_get(args: List[str]) -> str:
    # `array_get(arr, i)` — Python `arr[i]`. Used by the TS transpiler
    # for indexing array-typed locals when the array is a Python list.
    return f"{args[0]}[{args[1]}]"


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
    "Equals": (_builtin_equals, None),
    "hasOrder": (_builtin_has_order, None),
    "hasOrderOrEqual": (_builtin_has_order_or_equal, None),
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
    # Plain-list array helpers used by the TS transpiler's primitive-
    # array lowering. The richer binding-array runtime methods on the
    # `_VSA` class are reached through different paths.
    "array_length": (_builtin_array_length, 1),
    "array_get": (_builtin_array_get, 2),
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
                 loop_max_iterations: int = 50) -> None:
        self.runtime_dim = runtime_dim
        self.runtime_seed = runtime_seed
        # Compile-time loop unroll depth. Defaults to 50 but is
        # configurable via the CLI's --loop-T flag and via
        # [project.compile] loop_max_iterations in atman.toml. Larger
        # values cost a longer emitted tensor-op graph but no runtime
        # overhead beyond unroll length, since the soft-halt cell
        # freezes state once halt-cum saturates.
        self._LOOP_T = loop_max_iterations
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
        # Set of variable names declared with type `Axon`. An axon's
        # instance methods route specially: `a.add(k, v)` (statement)
        # rebinds `a` to `_VSA.axon_add(a, k, v)`; `a.item(k)`
        # (expression) emits `_VSA.axon_item(a, k)`. See
        # planning/sutra-spec/axons.md.
        self._axon_declared: set[str] = set()
        # For each axon-typed local in the current function scope,
        # the set of literal-string keys whose `.add(K, V);` statements
        # are elidable (never read via `.item(K)` and the axon doesn't
        # escape the function). Populated by `_compute_axon_elision`
        # at function entry; consumed by `_translate_stmt` on
        # `obj.add(K, V);` to skip emission. The spec calls this
        # "the compiler treats `a.item(k) = v` as SSA-rename when no
        # boundary crossing forces materialization" — see
        # planning/sutra-spec/axons.md §"The mutating-looking syntax
        # is sugar; the compiler usually elides the axon entirely."
        self._axon_elide_keys: dict[str, set[str]] = {}
        # Maps (class_name, method_name) -> return type name, for class
        # methods declared in user code or in the stdlib. Used by the
        # general void-method-as-augmented-assignment dispatch:
        # `obj.m(args);` (statement) where m returns void emits
        # `obj = Class_m(obj, args)`. Populated alongside the
        # _class_static_methods / _class_instance_methods registers.
        self._class_method_return_types: dict[tuple[str, str], str] = {}
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
        # Set to True while translating an `iterative_loop` function
        # body, so the `iterator` keyword translates to the runtime
        # Python local `_iterator` rather than a compile-time constant.
        # Restored on exit.
        self._iterator_runtime_in_scope: bool = False
        # Set to True while translating a `foreach_loop` function body,
        # so the `element` keyword translates to the runtime Python local
        # `_element` (the current array element this tick).
        self._element_runtime_in_scope: bool = False
        self._loop_state_stack: List[tuple[str, List[str]]] = []
        # Registry of loop function declarations seen so far in the
        # module, name -> LoopFunctionDecl. Used by LoopCallStmt
        # translation to look up the state-param shape for the call's
        # writeback. Populated in _translate_loop_function_decl.
        self._loop_decls: dict[str, "ast.LoopFunctionDecl"] = {}
        # Current function's return type name (e.g. "vector", "string").
        # Set in _translate_function_decl / _translate_loop_function_decl.
        # Halt-propagation (`return value * _program_halt`) only applies
        # when the return is a vector — strings/ints/bools cannot be
        # multiplied by a float halt accumulator.
        self._current_return_type: str | None = None
        # Function-signature table — populated by a pre-pass in translate()
        # before any user code is walked, so call-site translation can ask
        # "what type does function `f` expect at argument position k?" and
        # coerce literal args accordingly. Per planning/sutra-spec/strings.md
        # § "Literal coercion": a StringLiteral landing in a `string`-typed
        # slot wraps via `_VSA.make_string(...)`. Same rule generalizes to
        # int/float literals into vector-typed slots.
        # Maps function-name (or class-qualified `Class.method`) to its
        # parameter type-name list. None entries mark untyped params.
        self._func_param_types: dict[str, list[str | None]] = {}
        # Static methods declared inside class bodies. Maps
        # class_name -> set of static method names. Populated by
        # _translate_top_level when seeing a ClassDecl. Used by
        # _translate_call to dispatch `Math.foo(x)` to the mangled
        # top-level function `Math_foo(x)` that the codegen emits.
        # Non-static class methods are tracked separately and rejected
        # at call time today (instance dispatch isn't wired yet).
        self._class_static_methods: dict[str, set[str]] = {}
        # Intrinsic static methods declared inside class bodies. These
        # have no Sutra body — the runtime class implements them. A
        # call `Math.log(x)` for an intrinsic dispatches directly to
        # `_VSA.log(x)` without going through a mangled wrapper.
        self._class_intrinsic_methods: dict[str, set[str]] = {}
        # Non-static (instance) methods declared inside class bodies.
        # Same shape as _class_static_methods. Calls of the form
        # `this.method(args)` from inside another method on the same
        # class dispatch to `{Class}_{method}(this, *args)`. Top-level
        # `Class.method(instance, args)` also works the same way (the
        # instance is the explicit first arg). True instance-syntax
        # dispatch (`g.method(args)` for a typed variable `g`) needs
        # variable type tracking which isn't wired today.
        self._class_instance_methods: dict[str, set[str]] = {}
        # Field declarations per class, mapping
        # class_name -> {field_name -> Sutra type name}. Populated in
        # the pre-pass below when seeing a ClassDecl. Used by
        # MemberAccess and Assignment-to-MemberAccess lowering: a field
        # read on a class-typed receiver lowers to `_VSA.axon_item(c,
        # "name")`, a field write lowers to the augmented-assignment
        # `c = _VSA.axon_add(c, "name", value)`. Per the 2026-05-08
        # class-field design, fields share the axon machinery — the
        # class declaration is just the schema.
        self._class_fields: dict[str, dict[str, str]] = {}
        # `class Foo extends Bar` registry. Populated in the pre-pass
        # when seeing a ClassDecl. Used by user-class operator dispatch
        # to walk up the inheritance chain when looking for a matching
        # operator override. The chain bottoms out at a primitive
        # (vector / int / fuzzy / etc.) — that primitive isn't itself
        # a key in this map.
        self._class_parent: dict[str, str] = {}
        # User-class operator overloads, mapping
        # (class_name, sutra_op) -> mangled python name. Populated in
        # the pre-pass over class methods. `sutra_op` is the source
        # operator (`+`, `-`, `*`, etc.); the mangled name is
        # `Class_operator_<op-name>` where op-name is the spelled-out
        # form (`plus` / `minus` / `mul` / ...). Used by BinaryOp
        # translation to dispatch class-typed operands through the
        # user's operator method instead of the default Python operator.
        self._class_operators: dict[tuple[str, str], str] = {}
        # Name of the class whose method body is currently being
        # emitted. Used by `this.method(args)` dispatch to know which
        # class to mangle with. None when not inside a class method.
        self._current_class_name: Optional[str] = None

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
        # Pre-pass A: pull in stdlib class intrinsics (e.g.
        # `Tensor.MatrixMul`, `Tensor.matmul`, etc.) so namespaced
        # stdlib calls dispatch to `_VSA.<name>` even though the
        # stdlib class isn't declared in the user's module AST.
        try:
            from .stdlib_loader import (
                stdlib_class_intrinsic_methods,
                stdlib_class_parents,
                stdlib_class_operators,
            )
            for cls_name, method_names in stdlib_class_intrinsic_methods().items():
                self._class_static_methods.setdefault(
                    cls_name, set()
                ).update(method_names)
                self._class_intrinsic_methods.setdefault(
                    cls_name, set()
                ).update(method_names)
            # Register stdlib class parents so the operator dispatch's
            # inheritance walk resolves `String → vector` /
            # `Character → String → vector` / etc. Without this, a
            # `String`-typed variable doesn't participate in dispatch
            # because the walk's `t in self._class_parent` check fails.
            for cls_name, parent_name in stdlib_class_parents().items():
                self._class_parent.setdefault(cls_name, parent_name)
            # Register stdlib operator overloads. Each becomes a
            # mangled top-level Python function emitted by the
            # backend's prelude (`_emit_stdlib_class_operators`).
            self._stdlib_class_operator_decls: dict[tuple[str, str], "ast.MethodDecl"] = {}
            from .codegen_base import _OP_NAME_TO_PYTHON  # local-only constant
            for cls_name, op_map in stdlib_class_operators().items():
                for op_sym, method_decl in op_map.items():
                    mangled = (
                        f"{cls_name}_operator_"
                        f"{_OP_NAME_TO_PYTHON.get(op_sym, op_sym)}"
                    )
                    self._class_operators[(cls_name, op_sym)] = mangled
                    self._stdlib_class_operator_decls[(cls_name, op_sym)] = method_decl
        except Exception:
            # If stdlib loading fails for any reason, fall back to
            # user-class-only dispatch. Stdlib failures show up
            # elsewhere with clearer diagnostics.
            pass
        # Pre-pass B: register every class's method names so call sites
        # can dispatch even when the class declaration comes after the
        # calling function in the file. Static methods land in
        # _class_static_methods (intrinsic ones also in
        # _class_intrinsic_methods so the call site goes to _VSA.<name>
        # directly). Non-static methods land in _class_instance_methods
        # so `this.method(args)` from inside another method on the same
        # class can dispatch.
        # Pre-pass C: register function-parameter types so call-site
        # translation can coerce literal arguments to the called
        # function's declared parameter types. Necessary for the
        # strings.md § "Literal coercion" rule (substrate-encode string
        # literals at substrate boundaries — no host Python strings
        # crossing into user code). Stdlib functions also get registered
        # so calls like `String.make_string("x")` know their param types.
        for item in module.items:
            if isinstance(item, ast.FunctionDecl) and not item.is_operator:
                self._func_param_types[item.name] = [
                    (p.type_ref.name if p.type_ref is not None else None)
                    for p in item.params
                ]
            elif isinstance(item, ast.ClassDecl):
                for m in item.methods:
                    if m.is_operator or m.type_params:
                        continue
                    ptypes = [
                        (p.type_ref.name if p.type_ref is not None else None)
                        for p in m.params
                    ]
                    # Register under bare name (for `make_string(...)` shape)
                    # AND class-qualified (for `String.make_string(...)`).
                    self._func_param_types[m.name] = ptypes
                    self._func_param_types[f"{item.name}.{m.name}"] = ptypes
        # Same registration for stdlib functions (loaded out-of-band) so
        # user code calling e.g. `axon_add(a, "k", "v")` gets the same
        # literal-coercion treatment for string params.
        try:
            from .stdlib_loader import load_stdlib
            for fname, fdecl in load_stdlib().items():
                ptypes = [
                    (p.type_ref.name if p.type_ref is not None else None)
                    for p in fdecl.params
                ]
                self._func_param_types.setdefault(fname, ptypes)
        except Exception:
            pass

        for item in module.items:
            if isinstance(item, ast.ClassDecl):
                # Register field schema. Fields lower to axon
                # rotation-bound entries; the class declaration is
                # just the schema.
                if item.fields:
                    field_map = self._class_fields.setdefault(item.name, {})
                    for fd in item.fields:
                        field_map[fd.name] = fd.type_ref.name
                # Register the inheritance link so user-class operator
                # dispatch can walk up the chain.
                self._class_parent[item.name] = item.parent_name
                # Register user-class operator overloads.
                for m in item.methods:
                    if m.is_operator and not m.type_params:
                        op_sym = m.name[len("operator"):]  # strip `operator` prefix
                        mangled = (
                            f"{item.name}_operator_{_OP_NAME_TO_PYTHON.get(op_sym, op_sym)}"
                        )
                        self._class_operators[(item.name, op_sym)] = mangled
                for m in item.methods:
                    if m.is_operator or m.type_params:
                        continue
                    # Track return type for the augmented-assignment
                    # rule: void-returning instance methods called as
                    # statements rebind their receiver.
                    if m.return_type is not None:
                        self._class_method_return_types[(item.name, m.name)] = (
                            m.return_type.name
                        )
                    if m.modifiers.is_static:
                        self._class_static_methods.setdefault(
                            item.name, set()
                        ).add(m.name)
                        if m.is_intrinsic:
                            self._class_intrinsic_methods.setdefault(
                                item.name, set()
                            ).add(m.name)
                    else:
                        self._class_instance_methods.setdefault(
                            item.name, set()
                        ).add(m.name)
        # Emit auto-constructor factory functions for each class with
        # field declarations. `new ClassName(args)` lowers to a call to
        # the corresponding `<Class>_new(args)` function. Fields are
        # filled positionally in declaration order; the factory starts
        # from a fresh axon vector and adds each field via axon_add.
        for item in module.items:
            if isinstance(item, ast.ClassDecl) and item.fields:
                self._emit_class_factory(item)
                self._emit()
        # Emit stdlib class operator overloads as top-level Python
        # functions before user code, so call sites that dispatch to
        # mangled names like `String_operator_plus` resolve.
        self._emit_stdlib_class_operators()
        for item in module.items:
            self._translate_top_level(item)
            self._emit()
        return self.output

    def _emit_stdlib_class_operators(self) -> None:
        """Emit each stdlib-class operator overload as a top-level
        Python function with the mangled name the operator-dispatch
        registered. Body translation reuses the same `_translate_stmt`
        machinery user-class methods go through — `return string_concat(a, b)`
        becomes `return _VSA.string_concat(a, b)` via the inliner-
        backed intrinsic dispatch.
        """
        decls = getattr(self, "_stdlib_class_operator_decls", None)
        if not decls:
            return
        for (cls_name, op_sym), method_decl in decls.items():
            mangled = self._class_operators.get((cls_name, op_sym))
            if mangled is None:
                continue
            param_names = [p.name for p in method_decl.params]
            self._emit(f"def {mangled}({', '.join(param_names)}):")
            self._indent += 1
            # Register parameter types so the body's translation knows
            # `a` and `b` are String-typed (etc.) — needed for the
            # type-driven literal-coercion and operator-dispatch paths.
            outer_var_type = dict(self._var_type)
            for p in method_decl.params:
                if p.type_ref is not None:
                    self._var_type[p.name] = p.type_ref.name
            outer_return_type = self._current_return_type
            self._current_return_type = (
                method_decl.return_type.name if method_decl.return_type else None
            )
            self._emit("_program_halt = 1.0")
            if not method_decl.body.statements:
                self._emit("pass")
            else:
                for stmt in method_decl.body.statements:
                    self._translate_stmt(stmt)
            self._var_type = outer_var_type
            self._current_return_type = outer_return_type
            self._indent -= 1
            self._emit()

    def _resolve_user_operator(
        self, op: str, left: "ast.Expr", right: "ast.Expr"
    ) -> Optional[str]:
        """Walk the inheritance chain of either operand looking for a
        user-defined `operator <op>` method on a class. Returns the
        mangled Python name to dispatch to, or None if no user override
        applies. The chain bottoms out at a primitive class which is
        not itself in `_class_parent`; once we hit it, we stop.

        Per the user's 2026-05-08 design: "Operator overloading for
        user classes = inheritance-chain dispatch over the existing
        primitive operators." The first class up the chain that
        defines the operator wins.
        """
        def _expr_class(e: "ast.Expr") -> Optional[str]:
            if isinstance(e, ast.Identifier):
                t = self._var_type.get(e.name)
                # Only walk when the type is a user class (one we've
                # registered in `_class_parent`). Primitives keep the
                # default substrate dispatch.
                if t is not None and t in self._class_parent:
                    return t
            return None

        def _walk(start: Optional[str]) -> Optional[str]:
            seen: set[str] = set()
            cur = start
            while cur is not None and cur not in seen:
                seen.add(cur)
                key = (cur, op)
                if key in self._class_operators:
                    return self._class_operators[key]
                cur = self._class_parent.get(cur)
            return None

        return _walk(_expr_class(left)) or _walk(_expr_class(right))

    def _emit_class_factory(self, decl: "ast.ClassDecl") -> None:
        """Emit `def <Class>_new(field1, field2, ...): ...` which
        constructs an instance by starting from a fresh axon vector
        and adding each field in declaration order. Called from
        `_translate_expr` for `NewExpr` nodes."""
        param_names = [f.name for f in decl.fields]
        params_src = ", ".join(param_names)
        self._emit(f"def {decl.name}_new({params_src}):")
        self._indent += 1
        self._emit("_c = _VSA.axon_new()")
        for fd in decl.fields:
            self._emit(f'_c = _VSA.axon_add(_c, "{fd.name}", {fd.name})')
        self._emit("return _c")
        self._indent -= 1

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
            for method in item.methods:
                self._translate_class_method(item.name, method)
            for lf in item.loop_functions:
                self._translate_loop_function_decl(lf, class_name=item.name)
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
        # Track Axon declarations so that a.add(...) / a.item(...) on
        # the typed local route to the runtime axon methods.
        if decl.type_ref is not None and decl.type_ref.name == "Axon":
            self._axon_declared.add(decl.name)
            if decl.initializer is None:
                self._emit(f"{decl.name} = _VSA.axon_new()")
                return

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
        init_src = self._translate_expr(
            decl.initializer,
            map_key_type=(
                decl.type_ref.type_args[0].name
                if decl.type_ref is not None
                and decl.type_ref.name == "map"
                and len(decl.type_ref.type_args) >= 1
                else None
            ),
            # Per strings.md § "Literal coercion": a string literal in
            # `string s = "hello";` lands as a substrate String via
            # _VSA.make_string, not a host Python str. dest_type is
            # the declared type of the variable; the StringLiteral path
            # in _translate_expr does the wrap when dest_type matches
            # the string family.
            dest_type=(
                decl.type_ref.name if decl.type_ref is not None else None
            ),
        )
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

    def _translate_class_method(self, class_name: str, decl: ast.MethodDecl) -> None:
        """Emit a class-body method as a mangled top-level Python function.

        Static methods inside `class Math { static method scalar twice(x) {...} }`
        emit as `def Math_twice(x): ...` at module level; call sites of
        the form `Math.twice(5)` are routed to that mangled name in
        `_translate_call`.

        User-class operator overloads (`method operator + (Cat o) {...}`)
        emit as `def Cat_operator_plus(this, o): ...`; BinaryOp
        translation routes `a + b` (with a class-typed) through these
        mangled names per inheritance-chain dispatch.

        Intrinsic methods (declared `static intrinsic method ...;`) have
        no Sutra body — the runtime class implements them — so this
        method emits nothing for them. The pre-pass in `translate()`
        registers them in `_class_intrinsic_methods` so the call-site
        dispatch routes `Math.log(x)` to `_VSA.log(x)`.
        """
        if decl.type_params:
            raise CodegenNotSupported(
                decl,
                "generic method declarations are not supported by the V1 codegen",
            )
        is_static = decl.modifiers.is_static
        # Register in the lookup tables the call-dispatch path consults.
        if is_static:
            self._class_static_methods.setdefault(class_name, set()).add(decl.name)
            if decl.is_intrinsic:
                # Signature-only declaration; runtime class implements
                # the body. Emit nothing — the pre-pass already
                # registered the method in `_class_intrinsic_methods`
                # for call-site dispatch.
                self._class_intrinsic_methods.setdefault(
                    class_name, set()
                ).add(decl.name)
                return
        else:
            if decl.is_intrinsic:
                raise CodegenNotSupported(
                    decl,
                    f"non-static intrinsic methods are not supported — "
                    f"intrinsics live on the runtime class which has no "
                    f"per-instance state. Mark `{class_name}.{decl.name}` "
                    f"as `static intrinsic method` instead.",
                )
            self._class_instance_methods.setdefault(class_name, set()).add(decl.name)

        # Non-static methods get `this` as an implicit first parameter.
        # Static methods don't.
        param_names = [p.name for p in decl.params]
        if not is_static:
            param_names = ["this", *param_names]
        # Operator methods mangle `operator+` → `operator_plus` for a
        # valid Python identifier; the BinaryOp dispatch site uses the
        # same convention. Non-operator methods keep their name as-is.
        if decl.is_operator:
            op_sym = decl.name[len("operator"):]
            op_py = _OP_NAME_TO_PYTHON.get(op_sym, op_sym)
            mangled = f"{class_name}_operator_{op_py}"
        else:
            mangled = f"{class_name}_{decl.name}"
        self._emit(f"def {mangled}({', '.join(param_names)}):")
        self._indent += 1
        outer_slot_vars = self._slot_vars
        self._slot_vars = {}
        outer_return_type = self._current_return_type
        self._current_return_type = (
            decl.return_type.name if decl.return_type else None
        )
        outer_class_name = self._current_class_name
        self._current_class_name = class_name
        # Register method-parameter types so field-access lowering works
        # for class-typed parameters (e.g. `other.cents` inside an
        # operator overload reads `other`'s declared type from
        # _var_type and lowers to _VSA.axon_item(other, "cents")).
        # `this` is implicit on non-static methods and gets the current
        # class type. The dict is process-wide; method params shadow
        # any same-named outer variable for the duration of this body
        # (and the existing FunctionDecl path has the same shadowing
        # behavior — both leak across function boundaries today, but
        # are consistent within the current scope).
        if not is_static:
            self._var_type["this"] = class_name
        for p in decl.params:
            if p.type_ref is not None:
                self._var_type[p.name] = p.type_ref.name
        self._emit("_program_halt = 1.0")
        if _has_slot_decl(decl.body):
            self._emit("_slot_state = _VSA.zero_vector()")
        if not decl.body.statements:
            self._emit("pass")
        else:
            for stmt in decl.body.statements:
                self._translate_stmt(stmt)
        # For non-static void-returning methods, auto-emit `return this`
        # at the end of the body so the augmented-assignment desugar
        # (`obj.method(...)` → `obj = Class_method(obj)`) sees the
        # rebound this. Without this, void methods that mutate this.field
        # via the axon-add rebind would discard the mutation when the
        # caller assigns the return value back. Static methods and
        # value-returning methods don't need this — they have an
        # explicit return.
        if (not is_static
                and (decl.return_type is None
                     or decl.return_type.name == "void")):
            self._emit("return this")
        self._slot_vars = outer_slot_vars
        self._current_return_type = outer_return_type
        self._current_class_name = outer_class_name
        self._indent -= 1

    def _translate_function_decl(self, decl: ast.FunctionDecl) -> None:
        if decl.is_operator:
            raise CodegenNotSupported(
                decl, "operator declarations are not supported by the V1 codegen"
            )
        if decl.is_async:
            raise CodegenNotSupported(
                decl,
                "`async function` parses but its lowering to a gated "
                "while_loop is not yet implemented. The full design is "
                "specified in planning/sutra-spec/promises.md; the "
                "lowering pass is the next phase per queue.md item 1.",
            )
        if decl.type_params:
            raise CodegenNotSupported(
                decl, "generic function declarations are not supported by the V1 codegen"
            )
        param_names = [p.name for p in decl.params]
        self._emit(f"def {decl.name}({', '.join(param_names)}):")
        self._indent += 1
        # Register parameter types so instance-method dispatch
        # (Axon-typed params) and the general typed-receiver path
        # find them. Without this, `function int f(Axon a) {
        # return a.item("k"); }` would not route `a.item(...)` to
        # the runtime axon_item method.
        for p in decl.params:
            if p.type_ref is not None:
                self._var_type[p.name] = p.type_ref.name
                if p.type_ref.name == "Axon":
                    self._axon_declared.add(p.name)
        # Reset the slot table for this function scope. If the body
        # has any slot declarations we'll need a `_slot_state` local,
        # initialized to a zero vector before the first slot_store.
        outer_slot_vars = self._slot_vars
        self._slot_vars = {}
        outer_return_type = self._current_return_type
        self._current_return_type = decl.return_type.name if decl.return_type else None
        outer_axon_elide = self._axon_elide_keys
        self._axon_elide_keys = self._compute_axon_elision(decl)
        self._emit("_program_halt = 1.0")
        if _has_slot_decl(decl.body):
            self._emit("_slot_state = _VSA.zero_vector()")
        if not decl.body.statements:
            self._emit("pass")
        else:
            for stmt in decl.body.statements:
                self._translate_stmt(stmt)
        self._slot_vars = outer_slot_vars
        self._current_return_type = outer_return_type
        self._axon_elide_keys = outer_axon_elide
        self._indent -= 1

    def _compute_axon_elision(
        self, decl: ast.FunctionDecl
    ) -> dict[str, set[str]]:
        """Pre-pass over a function body to find axon-typed locals
        whose writes can be elided.

        Within a single function body, an `a.add("k", v);` statement
        on an axon-typed local is dead if the literal key `"k"` is
        never read via `a.item("k")` AND the axon `a` doesn't escape
        (return, pass to another function, etc.).

        Returns: dict mapping each axon-typed local name to the set of
        string-literal keys that are dead in that function. The
        translator skips emission when an `add` call's key is in the
        elide set.

        Conservative: any escape causes ALL keys to stay materialized
        for that local. Any read with a non-literal key (e.g. a
        runtime-computed key) keeps everything materialized too.
        """
        # Find axon-typed parameter names + Axon-typed locals declared
        # in the function body.
        axon_locals: set[str] = set()
        for p in decl.params:
            if p.type_ref is not None and p.type_ref.name == "Axon":
                axon_locals.add(p.name)
        # First scan: find all `Axon` declarations + collect read/write
        # info per axon var. Initialize every axon as conservative
        # (not yet known to escape, no reads, no writes).
        reads: dict[str, set[str]] = {}
        writes: dict[str, set[str]] = {}
        escaped: set[str] = set()
        any_dynamic_read: set[str] = set()

        def collect_decls(node):
            if isinstance(node, ast.VarDecl):
                if (node.type_ref is not None
                        and node.type_ref.name == "Axon"):
                    axon_locals.add(node.name)
            # Walk all attribute children for nested statements.
            for attr_name in dir(node):
                if attr_name.startswith("_"):
                    continue
                try:
                    val = getattr(node, attr_name)
                except Exception:
                    continue
                if isinstance(val, ast.Node):
                    collect_decls(val)
                elif isinstance(val, list):
                    for v in val:
                        if isinstance(v, ast.Node):
                            collect_decls(v)

        for stmt in decl.body.statements:
            collect_decls(stmt)

        for v in axon_locals:
            reads[v] = set()
            writes[v] = set()

        def visit_expr(node, position: str) -> None:
            """position is one of:
                 'value' — node's evaluated value flows into something
                           (an arg, a return, an assignment RHS, etc.)
                 'recv'  — node is the receiver of a member access
                 'lhs'   — node is the LHS of an assignment.
            Identifiers in `value` position that name an axon local
            cause that axon to be marked as escaped.
            """
            if node is None:
                return
            if isinstance(node, ast.Identifier):
                if node.name in axon_locals and position == "value":
                    escaped.add(node.name)
                return
            if isinstance(node, ast.MemberAccess):
                # `obj.member` — obj is the receiver. The member name
                # itself is just an identifier name, not an Identifier
                # node here (it's a string field on MemberAccess).
                visit_expr(node.obj, "recv")
                return
            if isinstance(node, ast.Call):
                callee = node.callee
                # `a.add(K, V)` and `a.item(K)` are special-cased — they
                # are NOT escapes for `a`. `a` is the receiver; other args
                # are values.
                axon_method_call = (
                    isinstance(callee, ast.MemberAccess)
                    and isinstance(callee.obj, ast.Identifier)
                    and callee.obj.name in axon_locals
                    and callee.member in ("add", "item")
                )
                if axon_method_call:
                    var = callee.obj.name
                    member = callee.member
                    # Receiver doesn't escape.
                    visit_expr(callee.obj, "recv")
                    # Args are values — they DO contribute to escape if
                    # an axon flows through them.
                    if member == "add":
                        # Args: (key, value). Track the literal key.
                        if (len(node.args) >= 1
                                and isinstance(node.args[0], ast.StringLiteral)):
                            writes[var].add(node.args[0].value)
                        for arg in node.args:
                            visit_expr(arg, "value")
                    else:  # item
                        if (len(node.args) >= 1
                                and isinstance(node.args[0], ast.StringLiteral)):
                            reads[var].add(node.args[0].value)
                        else:
                            # Non-literal key: all writes are needed.
                            any_dynamic_read.add(var)
                        for arg in node.args:
                            visit_expr(arg, "value")
                    return
                # Generic call: callee in 'value' position (or recv if
                # MemberAccess, but a non-axon-method MemberAccess
                # receiver flows on too).
                visit_expr(callee, "value")
                for arg in node.args:
                    visit_expr(arg, "value")
                return
            if isinstance(node, ast.Assignment):
                # LHS in 'lhs' position; RHS in 'value' position.
                visit_expr(node.target, "lhs")
                visit_expr(node.value, "value")
                return
            # Fallback: visit any sub-expression in value position. We
            # only care about catching axon-named Identifiers in
            # places where they'd escape, so this is safe.
            for attr_name in dir(node):
                if attr_name.startswith("_"):
                    continue
                try:
                    val = getattr(node, attr_name)
                except Exception:
                    continue
                if isinstance(val, ast.Node):
                    visit_expr(val, "value")
                elif isinstance(val, list):
                    for v in val:
                        if isinstance(v, ast.Node):
                            visit_expr(v, "value")

        def visit_stmt(stmt) -> None:
            if isinstance(stmt, ast.VarDecl):
                # `Axon a = expr;` — the LHS is the declared name; the
                # initializer is in value position.
                if stmt.initializer is not None:
                    visit_expr(stmt.initializer, "value")
                return
            if isinstance(stmt, ast.ReturnStmt):
                # Returning an axon counts as escape.
                visit_expr(stmt.value, "value")
                return
            if isinstance(stmt, ast.ExprStmt):
                expr = stmt.expr
                # `a = expr;` — LHS is in lhs position, RHS in value.
                if isinstance(expr, ast.Assignment):
                    visit_expr(expr.target, "lhs")
                    visit_expr(expr.value, "value")
                    return
                # `a.add(...);` / `a.item(...);` — handled in the
                # generic Call path above (axon receiver is OK).
                visit_expr(expr, "value")
                return
            # All other statement kinds: walk inner expressions and
            # nested statements.
            for attr_name in dir(stmt):
                if attr_name.startswith("_"):
                    continue
                try:
                    val = getattr(stmt, attr_name)
                except Exception:
                    continue
                if isinstance(val, ast.Node):
                    if isinstance(val, ast.Stmt):
                        visit_stmt(val)
                    else:
                        visit_expr(val, "value")
                elif isinstance(val, list):
                    for v in val:
                        if isinstance(v, ast.Node):
                            if isinstance(v, ast.Stmt):
                                visit_stmt(v)
                            else:
                                visit_expr(v, "value")

        for stmt in decl.body.statements:
            visit_stmt(stmt)

        elide: dict[str, set[str]] = {}
        for v in axon_locals:
            if v in escaped or v in any_dynamic_read:
                elide[v] = set()
            else:
                elide[v] = writes[v] - reads[v]
        return elide


    # _LOOP_T is now a per-instance attribute set in __init__ from the
    # `loop_max_iterations` kwarg (default 50). The class attribute is
    # kept as a fallback for any subclass that constructs the codegen
    # without going through __init__.
    _LOOP_T = 50

    def _translate_loop_function_decl(
        self, decl: "ast.LoopFunctionDecl", *, class_name: Optional[str] = None
    ) -> None:
        """Emit a Python function for a loop function declaration.

        When `class_name` is set, the loop function is being emitted on
        behalf of a class body (object loop, step 6 of the
        encapsulation taxonomy). The registry key uses the dotted form
        `Class.name`, and the Python identifier mangles `.` to `_` so
        `_loop_Greeter_run` is a valid name.
        """
        if class_name is not None:
            registry_key = f"{class_name}.{decl.name}"
            py_loop_name = f"_loop_{class_name}_{decl.name}"
        else:
            registry_key = decl.name
            py_loop_name = f"_loop_{decl.name}"
        # Register so LoopCallStmt knows the state-param shape.
        self._loop_decls[registry_key] = decl

        # Non-static class-bodied loops thread `this` as an implicit
        # first state parameter. The body has access to `this.field`
        # via the field-access machinery (which keys off
        # _current_class_name + _var_type["this"]). Pass statements
        # update only the explicit state params; `this` carries over
        # via Python local rebinding from `this.field = value` writes.
        is_class_method = (class_name is not None and not decl.is_static)

        state_names = [p.name for p in decl.state_params]
        init_param_names = [f"_init_{n}" for n in state_names]

        # foreach_loop adds the array as the first Python parameter
        # (before the state inits). The condition Expr names it.
        py_params = list(init_param_names)
        if decl.kind == "foreach_loop":
            if isinstance(decl.condition, ast.Identifier):
                py_params.insert(0, decl.condition.name)
        if is_class_method:
            # `_init_this` goes first so the call site can pass the
            # instance positionally. For foreach_loop this lands
            # before the array param; that's a known wart but no
            # known programs use foreach as a class loop yet.
            py_params.insert(0, "_init_this")
        self._emit(
            f"def {py_loop_name}({', '.join(py_params)}):"
        )
        self._indent += 1
        self._emit(
            f'"""Loop function `{decl.name}` (kind={decl.kind}).'
        )
        self._emit(f"")
        self._emit(
            f"T-step soft-halt cell. Returns ({', '.join(state_names) or 'no state'}, halted)."
        )
        self._emit(f'"""')
        # State locals init from caller args.
        if is_class_method:
            self._emit("this = _init_this")
        for state_name, init_name in zip(state_names, init_param_names):
            self._emit(f"{state_name} = {init_name}")
        self._emit("_halted = 0.0")

        # Push (loop_name, state_names) so PassStmt and tail-call
        # ReturnStmt translation know what to assign and which loop
        # name a `return NAME(args)` surface targets. `this` is NOT
        # in state_names; it threads via Python local rebinding from
        # field writes inside the body.
        self._loop_state_stack.append((decl.name, state_names))
        # For iterative_loop, `iterator` in the body resolves to the
        # runtime Python local `_iterator` instead of erroring.
        prior_iter_runtime = self._iterator_runtime_in_scope
        prior_elem_runtime = self._element_runtime_in_scope
        if decl.kind == "iterative_loop":
            self._iterator_runtime_in_scope = True
        if decl.kind == "foreach_loop":
            self._element_runtime_in_scope = True
        # Class context for non-static class loops: lets `this.field`
        # in the body lower through axon_item / axon_add.
        prior_class_name = self._current_class_name
        prior_var_type_this = self._var_type.get("this")
        if is_class_method:
            self._current_class_name = class_name
            self._var_type["this"] = class_name

        # do_while: body runs once unconditionally first.
        if decl.kind == "do_while":
            self._emit(f"# do_while: body runs once unconditionally first.")
            for inner in decl.body.statements:
                self._translate_stmt(inner)

        # Loop driver (Python). The body is substrate-pure; the driver
        # is Python and reads `_halted` at iteration boundary to
        # decide whether to continue — the same kind of boundary scalar
        # read as the codebook nearest_string lookup. There is no
        # compile-time iteration count: programs halt themselves when
        # the loop's halt condition fires, just like any other
        # programming language. `_t` is kept as a Python iteration
        # counter for diagnostics / iterative_loop arithmetic.
        self._emit("_t = 0")
        self._emit("while True:")
        self._indent += 1
        # Snapshot pre-step state for soft-mux freeze on halt.
        if is_class_method:
            self._emit(f"_pre_this = this")
        for state_name in state_names:
            self._emit(f"_pre_{state_name} = {state_name}")
        # Evaluate condition (semantics depend on kind).
        if decl.kind in ("do_while", "while_loop"):
            cond_src = self._translate_expr(decl.condition)
            self._emit(f"_cond = {cond_src}")
            self._emit(f"_cond_truth = _VSA.truth_axis(_cond)")
            self._emit(f"_keep = _VSA.heaviside(_cond_truth)")
        elif decl.kind == "iterative_loop":
            # condition is the count; iterator = _t + 1 (1-indexed).
            count_src = self._translate_expr(decl.condition)
            self._emit(f"# iterative_loop: tick = _t+1, halt when tick > count.")
            self._emit(f"_iterator = _t + 1")
            # Heaviside of (count - iterator + 1): positive while iterator
            # <= count; zero or negative once past. Substrate-pure scalar.
            self._emit(
                f"_keep = _VSA.heaviside(int({count_src}) - _iterator + 1)"
            )
        elif decl.kind == "foreach_loop":
            # foreach: condition is the array parameter (an Identifier
            # naming the array). The function takes the array as its
            # first parameter (in addition to state inits). Each tick:
            # halt when _t >= length; bind `element` to arr[_t].
            if not isinstance(decl.condition, ast.Identifier):
                raise CodegenNotSupported(
                    decl.condition,
                    "foreach_loop's first parameter must be a plain "
                    "identifier naming the array (e.g. `arr`). Got "
                    f"{type(decl.condition).__name__}.",
                )
            arr_param_name = decl.condition.name
            self._emit(f"# foreach_loop: array param `{arr_param_name}`,")
            self._emit(f"# bind `element` to {arr_param_name}[_t] each tick.")
            self._emit(f"_length = _VSA.array_length({arr_param_name})")
            # Heaviside of (_length - _t): positive while _t < _length.
            self._emit(f"_keep = _VSA.heaviside(_length - _t)")
            # Fetch the element BEFORE running body. Bind to `_element`.
            # For halted ticks the read is wasted but harmless (default
            # element-of-arr index is the last valid one or 0).
            self._emit(f"_element = _VSA.array_get({arr_param_name}, "
                       f"min(_t, max(_length - 1, 0)))")
        else:
            raise CodegenNotSupported(
                decl, f"unknown loop kind `{decl.kind}`"
            )
        self._emit(f"_halt_term = 1.0 - _keep")
        # Substrate-pure saturation: numpy.minimum / torch.minimum, not
        # Python's min(). Keeps _halted a substrate scalar.
        self._emit(f"_halted = _VSA.saturate_unit(_halted + _halt_term)")
        # Body re-runs each tick; PassStmt updates state locals.
        for inner in decl.body.statements:
            self._translate_stmt(inner)
        # Soft mux: freeze state at pre-step value once halt saturates.
        # This makes the iteration that converges produce a state
        # numerically equivalent to its pre-state, so the early-break
        # below exits with the converged value.
        if is_class_method:
            self._emit(
                "this = (1.0 - _halted) * this + _halted * _pre_this"
            )
        for state_name in state_names:
            self._emit(
                f"{state_name} = (1.0 - _halted) * {state_name} "
                f"+ _halted * _pre_{state_name}"
            )
        # Self-halt: programs terminate when the loop's halt condition
        # fires. `float(_halted)` is one boundary scalar read per
        # iteration (same kind of boundary op as the codebook lookup).
        # No fixed iteration cap; if the program writes a non-
        # converging loop, that's a programmer bug — same as any
        # `while True` in any other language.
        self._emit("_t += 1")
        self._emit("if float(_halted) >= 0.99:")
        self._indent += 1
        self._emit("break")
        self._indent -= 1
        self._indent -= 1  # close the while loop

        # Pop state stack and restore iterator/element runtime flags.
        self._loop_state_stack.pop()
        self._iterator_runtime_in_scope = prior_iter_runtime
        self._element_runtime_in_scope = prior_elem_runtime
        # Restore class context if it was set for this loop body.
        if is_class_method:
            self._current_class_name = prior_class_name
            if prior_var_type_this is None:
                self._var_type.pop("this", None)
            else:
                self._var_type["this"] = prior_var_type_this

        # Return final state values + halted (last). Non-static class
        # loops also return `this` (first), so the call site can
        # rebind the caller's instance variable.
        return_items: List[str] = []
        if is_class_method:
            return_items.append("this")
        return_items.extend(state_names)
        return_items.append("_halted")
        self._emit(f"return ({', '.join(return_items)},)")
        self._indent -= 1  # close the function

    def _translate_loop_call_class_method(
        self, stmt: "ast.LoopCallStmt", decl: "ast.LoopFunctionDecl"
    ) -> None:
        """Call a non-static class-bodied loop. The condition_arg is
        the receiver (a class-typed local — not a slot var); state
        args are slot vars as in the static path. After the loop, the
        returned `this` is assigned back to the receiver var so the
        caller sees the updated instance."""
        if len(stmt.state_arg_names) != len(decl.state_params):
            raise CodegenNotSupported(
                stmt,
                f"loop call `{stmt.name}` expects "
                f"{len(decl.state_params)} state arg(s), got "
                f"{len(stmt.state_arg_names)}",
            )
        instance_name = stmt.condition_arg.name
        slot_args: List[tuple[str, int]] = []
        for arg_name in stmt.state_arg_names:
            if arg_name not in self._slot_vars:
                raise CodegenNotSupported(
                    stmt,
                    f"loop call state argument `{arg_name}` must be a "
                    f"slot variable in the caller scope.",
                )
            slot_args.append((arg_name, self._slot_vars[arg_name]))
        init_args = [instance_name] + [
            f"_VSA.slot_load(_slot_state, {idx})" for _, idx in slot_args
        ]
        ret_names = (
            ["_loopret_this"]
            + [f"_loopret_{n}" for n, _ in slot_args]
            + ["_loopret_halt"]
        )
        py_loop_name = f"_loop_{stmt.name.replace('.', '_')}"
        self._emit(f"# loop call (non-static): {stmt.name}({instance_name}, ...)")
        self._emit(
            f"({', '.join(ret_names)},) = {py_loop_name}"
            f"({', '.join(init_args)})"
        )
        # Assign the returned `this` back to the caller's instance var.
        self._emit(f"{instance_name} = _loopret_this")
        # Slot writebacks (skip the leading _loopret_this and trailing halt).
        for (arg_name, idx), ret_name in zip(slot_args, ret_names[1:-1]):
            self._emit(
                f"_slot_state = _VSA.slot_store(_slot_state, {idx}, "
                f"{ret_name})"
            )
        # Accumulate halted into the function-scope program-halt.
        self._emit("_program_halt = _program_halt * (1.0 - _loopret_halt)")

    def _translate_loop_call(self, stmt: "ast.LoopCallStmt") -> None:
        """Emit a call to a previously-declared loop function + writeback.

        State args at the call site MUST be slot-variable names; on
        completion, the loop's final state values are written back into
        those slot vars (by-reference). The condition arg is evaluated
        once (for any side effects + visual symmetry with the function-
        decl form) but its value is unused — the loop function uses its
        own decl-time condition expression against the state locals each
        tick.

        Non-static class-bodied loops add a wrinkle: the condition_arg
        position carries the receiver instance (a class-typed local,
        NOT a slot var). The instance gets passed as `_init_this` and
        the returned `this` value is assigned back to the caller's
        instance var.
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
        # Class-method loops: detect by the dotted name + non-static.
        is_class_method_call = (
            "." in stmt.name and not getattr(decl, "is_static", False)
        )
        if (is_class_method_call
                and isinstance(stmt.condition_arg, ast.Identifier)):
            self._translate_loop_call_class_method(stmt, decl)
            return
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
        # Evaluate the condition arg. For foreach_loop with an array
        # literal, route through array_from_literal so the array is the
        # substrate-stored binding-array (not a plain Python list).
        if (decl.kind == "foreach_loop"
                and isinstance(stmt.condition_arg, ast.ArrayLiteral)):
            elem_srcs = [
                self._translate_expr(e)
                for e in stmt.condition_arg.elements
            ]
            cond_src = f"_VSA.array_from_literal({', '.join(elem_srcs)})"
        else:
            cond_src = self._translate_expr(stmt.condition_arg)
        self._emit(f"# loop call: {stmt.name}({cond_src}, ...)")
        # Read current slot values to pass as init args.
        init_args = [
            f"_VSA.slot_load(_slot_state, {idx})"
            for _, idx in slot_args
        ]
        # Generate distinct names for the unpacked return values.
        ret_names = [f"_loopret_{n}" for n, _ in slot_args] + ["_loopret_halt"]
        # Mangled python identifier for the emitted loop function.
        # For class-bodied loops the source name is dotted
        # (`Greeter.run`); replace `.` with `_` so the name is a valid
        # Python identifier (`_loop_Greeter_run`).
        py_loop_name = f"_loop_{stmt.name.replace('.', '_')}"
        if decl.kind == "foreach_loop":
            # Pass the array (cond_src) as the first Python arg, then
            # state inits. The function reads the array each tick to
            # fetch the next `element`.
            all_args = [cond_src] + init_args
            self._emit(
                f"({', '.join(ret_names)},) = {py_loop_name}("
                f"{', '.join(all_args)})"
            )
        else:
            # Other kinds: cond_src evaluated for side effects only;
            # runtime uses the loop's decl-time condition each tick.
            self._emit(f"# Condition arg evaluated for side effects; runtime")
            self._emit(f"# uses the loop's decl-time condition expression.")
            self._emit(f"_ = {cond_src}")
            self._emit(
                f"({', '.join(ret_names)},) = {py_loop_name}("
                f"{', '.join(init_args)})"
            )
        # Write back to caller's slot vars.
        for (arg_name, idx), ret_name in zip(slot_args, ret_names[:-1]):
            self._emit(
                f"_slot_state = _VSA.slot_store(_slot_state, {idx}, "
                f"{ret_name})"
            )
        # Accumulate halted into the function-scope program-halt so
        # this loop's completion gates the function's return value.
        self._emit("_program_halt = _program_halt * _loopret_halt")

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
            _loop_name, state_names = self._loop_state_stack[-1]
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
            if (self._loop_state_stack
                    and stmt.value is not None
                    and isinstance(stmt.value, ast.Call)
                    and isinstance(stmt.value.callee, ast.Identifier)):
                loop_name, state_names = self._loop_state_stack[-1]
                if stmt.value.callee.name == loop_name:
                    args = stmt.value.args
                    if len(args) != len(state_names):
                        raise CodegenNotSupported(
                            stmt,
                            f"tail call `return {loop_name}(...)` expects "
                            f"{len(state_names)} arg(s) (one per state "
                            f"parameter `{', '.join(state_names)}`), got "
                            f"{len(args)}",
                        )
                    for state_name, value in zip(state_names, args):
                        if isinstance(value, ast.ReplaceMarker):
                            self._emit(f"{state_name} = _init_{state_name}")
                        else:
                            value_src = self._translate_expr(value)
                            self._emit(f"{state_name} = {value_src}")
                    return
            if stmt.value is None:
                self._emit("return")
            else:
                # Multiply the returned value by _program_halt so that
                # any unconverged loop in this function (halted≈0)
                # wipes the output. For functions without loops the
                # accumulator stays 1.0 and this is a no-op. String
                # returns can't be multiplied by a float (codebook
                # nearest-string lookup at the edge yields a host
                # str), so we emit a bare return for those — halt
                # wipe doesn't apply at the string boundary anyway,
                # since a wiped-vector lookup already returns the
                # nearest-string of zero (which is the right
                # behavior).
                if self._current_return_type in ("string", "String", "Character"):
                    # dest_type=string so a bare `return "hello";` in a
                    # `function string main()` wraps via make_string at
                    # emit time instead of returning a host Python str.
                    self._emit(
                        f"return "
                        f"{self._translate_expr(stmt.value, dest_type=self._current_return_type)}"
                    )
                else:
                    self._emit(
                        f"return ({self._translate_expr(stmt.value, dest_type=self._current_return_type)}) "
                        f"* _program_halt"
                    )
            return
        if isinstance(stmt, ast.ExprStmt):
            expr = stmt.expr
            # `a.add(k, v);` as a statement on an Axon-typed local rebinds
            # `a` to the new axon. This is the augmented-assignment shape
            # for void-returning instance methods — see the spec rule in
            # planning/sutra-spec/axons.md ("axons are completely
            # un-imperative aside from the ergonomics"). For axons,
            # `add` is the mutating method; `item` is read-only and does
            # not rebind. The general "any void-returning instance method
            # on any class is augmented assignment" rule is not yet
            # implemented for non-axon classes.
            # `d.Add(k, v);` on a dict-typed local — C#-style spelling
            # of `d[k] = v;`. Lowers to the same functional update as the
            # subscript-assign form: `d = _VSA.hashmap_set(d, k, v)`.
            if (isinstance(expr, ast.Call)
                    and isinstance(expr.callee, ast.MemberAccess)
                    and isinstance(expr.callee.obj, ast.Identifier)
                    and expr.callee.obj.name in self._dict_declared
                    and expr.callee.member == "Add"):
                dict_name = expr.callee.obj.name
                arg_srcs = [self._translate_expr(a) for a in expr.args]
                self._emit(
                    f"{dict_name} = _VSA.hashmap_set({dict_name}, "
                    f"{', '.join(arg_srcs)})"
                )
                return
            if (isinstance(expr, ast.Call)
                    and isinstance(expr.callee, ast.MemberAccess)
                    and isinstance(expr.callee.obj, ast.Identifier)
                    and expr.callee.obj.name in self._axon_declared):
                obj_name = expr.callee.obj.name
                method_name = expr.callee.member
                runtime_name = {
                    "add": "axon_add",
                    "item": "axon_item",
                }.get(method_name)
                if runtime_name is not None:
                    # SSA-elision: if this `add` writes a literal key
                    # that's never read in this function (and the
                    # axon doesn't escape), skip emission entirely.
                    # The key flows nowhere; computing the bind would
                    # be pure waste. See `_compute_axon_elision`.
                    if (method_name == "add"
                            and len(expr.args) >= 1
                            and isinstance(expr.args[0], ast.StringLiteral)
                            and expr.args[0].value in self._axon_elide_keys.get(obj_name, set())):
                        return
                    arg_srcs = [self._translate_expr(a) for a in expr.args]
                    all_args = [obj_name] + arg_srcs
                    if method_name == "add":
                        # Mutating instance method → augmented assignment.
                        self._emit(
                            f"{obj_name} = _VSA.{runtime_name}"
                            f"({', '.join(all_args)})"
                        )
                    else:
                        # Read-only instance method as a discarded
                        # statement (rare). Emit the call without rebind.
                        self._emit(
                            f"_VSA.{runtime_name}({', '.join(all_args)})"
                        )
                    return
            # General void-returning-instance-method rule: for any
            # class C, an instance method declared `method void m(...)`
            # called as a statement `obj.m(args);` rebinds the
            # receiver to the static form's return value. The static
            # form (mangled `C_m` or runtime `_VSA.m` for intrinsics)
            # takes the receiver as its first arg and returns the new
            # receiver value. This is the user's compilation rule:
            # "every void-returning instance method is an augmented
            # assignment." See planning/sutra-spec/axons.md and the
            # broader class-system note on it.
            if (isinstance(expr, ast.Call)
                    and isinstance(expr.callee, ast.MemberAccess)
                    and isinstance(expr.callee.obj, ast.Identifier)
                    and expr.callee.obj.name in self._var_type):
                obj_name = expr.callee.obj.name
                obj_class = self._var_type[obj_name]
                method_name = expr.callee.member
                return_type = self._class_method_return_types.get(
                    (obj_class, method_name)
                )
                if return_type == "void":
                    arg_srcs = [self._translate_expr(a) for a in expr.args]
                    all_args = [obj_name] + arg_srcs
                    if (obj_class in self._class_intrinsic_methods
                            and method_name in self._class_intrinsic_methods[obj_class]):
                        self._emit(
                            f"{obj_name} = _VSA.{method_name}"
                            f"({', '.join(all_args)})"
                        )
                        return
                    if (obj_class in self._class_instance_methods
                            and method_name in self._class_instance_methods[obj_class]):
                        self._emit(
                            f"{obj_name} = {obj_class}_{method_name}"
                            f"({', '.join(all_args)})"
                        )
                        return
            if isinstance(expr, ast.Assignment):
                # Class-field write: `c.name = value;` where c is a
                # class-typed local and `name` is declared as a field.
                # Lowers via the same axon machinery as field reads.
                # Only plain `=` is supported; compound forms (`+=`, etc.)
                # would need a read-modify-write that we leave for a
                # follow-up — the field surface is new (2026-05-08).
                if (isinstance(expr.target, ast.MemberAccess)
                        and isinstance(expr.target.obj, ast.Identifier)):
                    fld_obj_name = expr.target.obj.name
                    fld_obj_class = self._var_type.get(fld_obj_name)
                    fld_name = expr.target.member
                    if (fld_obj_class is not None
                            and fld_obj_class in self._class_fields
                            and fld_name in self._class_fields[fld_obj_class]):
                        if expr.op != "=":
                            raise CodegenNotSupported(
                                stmt,
                                f"compound assignment on a class field "
                                f"(`{expr.op}`) is not yet supported; use "
                                "plain `=` for now",
                            )
                        value_src = self._translate_expr(expr.value)
                        self._emit(
                            f'{fld_obj_name} = _VSA.axon_add('
                            f'{fld_obj_name}, "{fld_name}", {value_src})'
                        )
                        return
                # Same field-write rule for `this.field = value` inside
                # a class method body. Rebinds the local `this` param,
                # which propagates back to the caller via the existing
                # `obj.method(...);` augmented-assignment desugar.
                if (isinstance(expr.target, ast.MemberAccess)
                        and isinstance(expr.target.obj, ast.ThisExpr)
                        and self._current_class_name is not None):
                    cls_name = self._current_class_name
                    fld_name = expr.target.member
                    if (cls_name in self._class_fields
                            and fld_name in self._class_fields[cls_name]):
                        if expr.op != "=":
                            raise CodegenNotSupported(
                                stmt,
                                f"compound assignment on a class field "
                                f"(`{expr.op}`) is not yet supported; use "
                                "plain `=` for now",
                            )
                        value_src = self._translate_expr(expr.value)
                        self._emit(
                            f'this = _VSA.axon_add(this, "{fld_name}", {value_src})'
                        )
                        return
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
                target_src = self._translate_expr(expr.target)
                value_src = self._translate_expr(expr.value)
                self._emit(f"{target_src} {expr.op} {value_src}")
                return
            if isinstance(expr, ast.PostfixOp):
                # `i++` / `i--` as a statement. Lower to Python
                # `i += 1` / `i -= 1`. Used in expression position
                # (rare in Sutra; postfix's value is the OLD value of
                # i which Python can't express as an expression
                # without walrus + an extra binding) it remains
                # unsupported and the expression-translation path
                # below errors with a clear message.
                target_src = self._translate_expr(expr.operand)
                delta = "+= 1" if expr.op == "++" else "-= 1"
                self._emit(f"{target_src} {delta}")
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
                return
            # loop(cond) — old body-discard form. Rejected today;
            # superseded by the function-declaration loop kinds. The
            # implicit `loop(x){body}` → state-inference → tail-recursive
            # loop-function desugaring is the planned revival of this
            # surface (todo.md §"Implicit tail-recursive loops").
            raise CodegenNotSupported(
                stmt,
                "`loop(cond) { body }` is no longer supported. The body-"
                "discard form is replaced by the function-"
                "declaration loop kinds (`do_while NAME(...)`, "
                "`while_loop NAME(...)`, `iterative_loop NAME(...)`, "
                "`foreach_loop NAME(...)` + `loop NAME(...);` call site). "
                "See planning/open-questions/loop-function-declarations.md.",
            )
        if isinstance(stmt, ast.WhileStmt):
            raise CodegenNotSupported(
                stmt,
                "C-style `while (cond) { body }` is no longer supported. "
                "Use a `while_loop NAME(cond, ...state) { ...; pass ...; }` "
                "function declaration + `loop NAME(cond, args);` call site. "
                "See planning/open-questions/loop-function-declarations.md.",
            )
        if isinstance(stmt, ast.ForStmt):
            raise CodegenNotSupported(
                stmt,
                "C-style `for (init; cond; step) { body }` is no longer "
                "supported. Use `iterative_loop NAME(count, ...state) { "
                "...; pass ...; }` for fixed-count iteration (with the "
                "`iterator` keyword for the tick number), or "
                "`while_loop NAME(cond, ...state) { ... }` for general "
                "data-dependent iteration. See "
                "planning/open-questions/loop-function-declarations.md.",
            )
        if isinstance(stmt, ast.DoWhileStmt):
            raise CodegenNotSupported(
                stmt,
                "C-style `do { body } while (cond);` is no longer "
                "supported. Use `do_while NAME(cond, ...state) { ...; "
                "pass ...; }` function declaration + "
                "`loop NAME(cond, args);` call site. See "
                "planning/open-questions/loop-function-declarations.md.",
            )
        if isinstance(stmt, ast.ForeachStmt):
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
                f"collections or computed expressions is future work. "
                f"Rewrite as `foreach (x in [a, b, c]) {{ ... }}` or "
                f"unroll by hand.",
            )
        if isinstance(stmt, ast.IfStmt):
            raise CodegenNotSupported(
                stmt,
                "if/else is not supported by the V1 codegen — the whole "
                "point is to compile it away into a prototype-table lookup",
            )
        if isinstance(stmt, ast.TryStmt):
            self._translate_try_catch(stmt)
            return
        raise CodegenNotSupported(
            stmt, f"unsupported statement: {type(stmt).__name__}"
        )

    def _translate_try_catch(self, stmt: ast.TryStmt) -> None:
        """Lower `try { return e1; } catch { return e2; }` to a polarized
        blend on AXIS_PROMISE_REJECTED — the substrate's exception axis.

        Per the user's 2026-05-09 framing: try/catch is not a true fuzzy
        superposition — the polarizer pushes the exception axis hard
        toward 0 or 1 so the result is effectively binary even when the
        underlying axis read is fractional. The blend is

            v_try = e1
            exc   = tanh(k * v_try[AXIS_PROMISE_REJECTED])    # polarize
            v_cat = e2
            return (1 - exc) * v_try + exc * v_cat

        where `k` is large (50 by default) — anything past the tanh
        knee saturates to ±1, so a value with rejected=1.0 selects the
        catch branch entirely and a value with rejected=0.0 selects the
        try branch entirely. The substrate evaluates BOTH branches (no
        early exit, no throw) — the polarized blend just decides which
        one's value survives.

        First-cut constraint: both blocks must be a single
        `return <expr>;`. Multi-statement bodies aren't supported yet
        (would need slot-state hoisting like the loops do). See
        planning/sutra-spec/control-flow.md for the current scope.
        """
        try_stmts = stmt.try_body.statements
        catch_stmts = stmt.catch_body.statements
        if (len(try_stmts) != 1
                or not isinstance(try_stmts[0], ast.ReturnStmt)
                or try_stmts[0].value is None
                or len(catch_stmts) != 1
                or not isinstance(catch_stmts[0], ast.ReturnStmt)
                or catch_stmts[0].value is None):
            raise CodegenNotSupported(
                stmt,
                "try/catch first cut requires both blocks to be a "
                "single `return <expr>;`. Multi-statement bodies need "
                "slot hoisting (like the loops use) and aren't done "
                "yet. See planning/sutra-spec/control-flow.md.",
            )
        v_try_src = self._translate_expr(try_stmts[0].value)
        v_cat_src = self._translate_expr(catch_stmts[0].value)
        # Use a temp local so we read the rejected axis off the
        # already-evaluated try result (rather than re-evaluating).
        self._emit(f"_try_v = {v_try_src}")
        self._emit(
            "_try_exc = float(_torch.tanh(50.0 * "
            "_try_v[_VSA.semantic_dim + _VSA.AXIS_PROMISE_REJECTED]))"
            if self._is_pytorch_backend()
            else "_try_exc = float(_np.tanh(50.0 * "
            "_try_v[_VSA.semantic_dim + _VSA.AXIS_PROMISE_REJECTED]))"
        )
        self._emit(f"_catch_v = {v_cat_src}")
        if self._current_return_type in ("string", "String", "Character"):
            self._emit("return _catch_v if _try_exc > 0.5 else _try_v")
        else:
            self._emit(
                "return ((1.0 - _try_exc) * _try_v + _try_exc * _catch_v) "
                "* _program_halt"
            )

    def _is_pytorch_backend(self) -> bool:
        """Backend hook so try/catch can pick the right tanh emitter.

        Default: numpy. The PyTorch codegen overrides this to True.
        """
        return False

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

    # The eigenrotation-loop translation helpers
    # (_translate_eigenrotation_loop, _translate_while_as_geometric_loop,
    # _translate_for_as_geometric_loop, _extract_loop_state_var,
    # _extract_loop_target, _extract_for_bound) were removed
    # 2026-05-10 along with the C-style loop surface. The current
    # surface uses the function-decl loop forms (do_while, while_loop,
    # iterative_loop, foreach_loop) — see planning/sutra-spec/control-
    # flow.md §"Loops" and _translate_loop_function_decl /
    # _translate_loop_call_stmt below. _next_loop_id stays — still
    # used as a unique-id source for other emit contexts.

    _loop_counter = 0  # unique names for emit-time temporaries

    def _next_loop_id(self) -> str:
        BaseCodegen._loop_counter += 1
        return f"_loop{BaseCodegen._loop_counter}"

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
        would be wrong for fuzzy operands. Base refuses; concrete
        backends override and implement properly.
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
        # Call whose resolved return type is `complex`. This makes the
        # literate stdlib bodies correct: after the inliner expands
        # `Math.cexp(z)` to `realExp(z) * imaginaryExp(z)`, the `*`
        # only dispatches to complex_mul if these calls are seen as
        # complex. Resolution sources, both authoritative and already
        # loaded: user-class method return types, and the stdlib
        # symbol table (FunctionDecl.return_type from the loader).
        # Conservative by construction — only fires for a callee whose
        # declared return type is literally `complex`, so int/float
        # call results are unaffected and `*` stays element-wise for
        # them.
        if isinstance(expr, ast.Call):
            rt = self._resolved_return_type(expr.callee)
            return rt == "complex"
        return False

    def _resolved_return_type(self, callee: ast.Expr) -> str | None:
        """Declared return-type name of a call target, or None.

        Checks (1) user-class methods via `_class_method_return_types`
        and (2) the stdlib symbol table (bare `name` and namespaced
        `Class.member`), whose FunctionDecls carry `.return_type`.
        Cached stdlib load — same table the inliner uses."""
        # Bare-name call: `realExp(z)` (the post-inline shape).
        if isinstance(callee, ast.Identifier):
            name = callee.name
            for (_cls, m), rt in self._class_method_return_types.items():
                if m == name:
                    return rt
            decl = self._stdlib_symbol(name)
            if decl is not None and decl.return_type is not None:
                return decl.return_type.name
            return None
        # Namespaced call: `Math.cexp(z)`.
        if (isinstance(callee, ast.MemberAccess)
                and isinstance(callee.obj, ast.Identifier)):
            cls, m = callee.obj.name, callee.member
            rt = self._class_method_return_types.get((cls, m))
            if rt is not None:
                return rt
            decl = self._stdlib_symbol(f"{cls}.{m}") or self._stdlib_symbol(m)
            if decl is not None and decl.return_type is not None:
                return decl.return_type.name
        return None

    def _stdlib_symbol(self, name: str):
        """Look a name up in the cached stdlib symbol table. Returns
        the FunctionDecl or None. The table is the inliner's cache, so
        no extra parse cost."""
        try:
            from .stdlib_loader import load_stdlib
            return load_stdlib().get(name)
        except Exception:
            return None

    _TRUTH_TYPES = frozenset({"bool", "fuzzy", "trit"})
    # `number` canonical; `scalar` deprecated alias (both classify
    # identically — see lexer.py PRIMITIVE_TYPE_NAMES).
    _NUMBER_TYPES = frozenset(
        {"int", "float", "complex", "number", "scalar", "char"}
    )
    # Synthetic-axis-encoded types: numbers and strings live in the
    # synthetic block of the extended state vector. Per the user's
    # 2026-05-08 directive, equality on these uses Euclidean-distance
    # + tanh rather than cosine similarity (which doesn't distinguish
    # well between values that share direction but differ in
    # magnitude — `1` and `2` are cosine-similar but Euclidean-far).
    _SYNTHETIC_AXIS_TYPES = frozenset(
        {"int", "float", "complex", "number", "scalar", "char", "string"}
    )

    def _is_synthetic_axis_expr(self, expr: ast.Expr) -> bool:
        """True iff expr is provably a synthetic-axis-encoded value at
        compile time — int, float, complex, scalar, char, or string.
        Conservative — unknown types fall through to the default
        cosine-similarity equality path."""
        if isinstance(expr, (ast.IntLiteral, ast.FloatLiteral,
                             ast.ImaginaryLiteral, ast.ComplexLiteral,
                             ast.CharLiteral, ast.StringLiteral)):
            return True
        if isinstance(expr, ast.Identifier):
            return self._var_type.get(expr.name) in self._SYNTHETIC_AXIS_TYPES
        if isinstance(expr, ast.Parenthesized):
            return self._is_synthetic_axis_expr(expr.inner)
        return False

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

    def _complex_add_src(self, expr: ast.BinaryOp,
                        left_src: str, right_src: str) -> str:
        """Override point for `complex + anything` / `anything + complex`."""
        raise CodegenNotSupported(
            expr,
            "complex addition is not supported by this backend "
            "(no real/imag-axis runtime); use the numpy or pytorch backend",
        )

    def _complex_sub_src(self, expr: ast.BinaryOp,
                        left_src: str, right_src: str) -> str:
        """Override point for `complex - anything` / `anything - complex`."""
        raise CodegenNotSupported(
            expr,
            "complex subtraction is not supported by this backend "
            "(no real/imag-axis runtime); use the numpy or pytorch backend",
        )

    def _complex_div_src(self, expr: ast.BinaryOp,
                        left_src: str, right_src: str) -> str:
        """Override point for `complex / anything` / `anything / complex`."""
        raise CodegenNotSupported(
            expr,
            "complex division is not supported by this backend "
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

    def _translate_expr(
        self,
        expr: ast.Expr,
        *,
        map_key_type: str | None = None,
        dest_type: str | None = None,
    ) -> str:
        if isinstance(expr, ast.StringLiteral):
            # Per planning/sutra-spec/strings.md § "Literal coercion":
            # a string literal landing in a `string` / `String` /
            # `Character`-typed slot wraps via `_VSA.make_string(...)` so
            # the value crosses the boundary as a substrate String, not a
            # host Python string. CLAUDE.md § safety-critical rule:
            # every Sutra operation must run on the substrate where the
            # spec says it runs — passing host Python strings into user
            # functions violates that.
            if dest_type in ("string", "String", "Character"):
                return f"_VSA.make_string({expr.value!r})"
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
                # Two contexts where `iterator` is meaningful:
                # 1. Compile-time-unrolled `loop (N) { ... }`: substitute
                #    the literal int (1..N) — handled via _iterator_value.
                # 2. Runtime `iterative_loop NAME(N, ...) { ... }`: refer
                #    to the Python local `_iterator` (1-indexed tick count
                #    set by the cell). Handled via _iterator_runtime_in_scope.
                if self._iterator_runtime_in_scope:
                    return "_iterator"
                if self._iterator_value is None:
                    raise CodegenNotSupported(
                        expr,
                        "`iterator` is only valid inside an unrolling "
                        "`loop (N) { ... }` body or an `iterative_loop` "
                        "function body. Use `loop (N as i)` and reference "
                        "`i` for the compile-time named-index form.",
                    )
                return repr(self._iterator_value)
            if expr.name == "element":
                # Contextual: only valid inside a foreach_loop function
                # body. Refers to the current array element on this tick
                # — the Python local `_element` set by the cell via
                # `_VSA.array_get(arr_param, _t)`.
                if not self._element_runtime_in_scope:
                    raise CodegenNotSupported(
                        expr,
                        "`element` is only valid inside a `foreach_loop` "
                        "function body, where it binds to the current "
                        "array element each tick.",
                    )
                return "_element"
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
            # User-class operator dispatch — walk the inheritance chain
            # of either operand looking for a defined `operator <op>`
            # method. The first class up the chain to define one wins.
            # Falls through to the default operator handling if no
            # user-class override is found, which in turn dispatches to
            # the primitive-class operator on the substrate.
            user_op_name = self._resolve_user_operator(
                expr.op, expr.left, expr.right
            )
            if user_op_name is not None:
                return f"{user_op_name}({left}, {right})"
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
            # Complex `+` / `-` / `/` dispatch. Element-wise tensor add
            # on two extended-state vectors gives correct complex
            # addition (real axes add, imag axes add); but `complex +
            # real_scalar` broadcasts the scalar across BOTH axes,
            # corrupting imag — routing through `_VSA.complex_add`
            # coerces the scalar via `make_real` first. Complex `/`
            # cannot use element-wise division at all: `(a+bi)/(c+di) =
            # ((ac+bd) + (bc-ad)i)/(c²+d²)`, which the element-wise
            # path computes as `(a/c) + (b/d)i` — mathematically wrong
            # and silently inf-poisoning when imag is zero. All three
            # dispatch through substrate-pure runtime methods.
            if expr.op == "+" and (self._is_complex_expr(expr.left)
                                   or self._is_complex_expr(expr.right)):
                return self._complex_add_src(expr, left, right)
            if expr.op == "-" and (self._is_complex_expr(expr.left)
                                   or self._is_complex_expr(expr.right)):
                return self._complex_sub_src(expr, left, right)
            if expr.op == "/" and (self._is_complex_expr(expr.left)
                                   or self._is_complex_expr(expr.right)):
                return self._complex_div_src(expr, left, right)
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
            # `%` is the JS / C / C# / Rust / TS truncation modulus.
            # The fall-through `left % right` below would emit Python's
            # `%`, which is FLOOR-mod (-1 % 3 == 2) AND runs on host
            # Python scalars — a substrate-purity leak. Route through
            # `_VSA.fmod` (defined in stdlib/modulus.su; runtime
            # implementation in codegen_pytorch.py) which gives
            # truncation modulus on the device. See queue.md item 3
            # for the eigen-rotation form `_VSA.mod` (floor-mod,
            # differentiable) that callers reach via `Math.mod(x, m)`.
            if expr.op == "%":
                return f"_VSA.fmod({left}, {right})"
            return f"({left} {expr.op} {right})"
        if isinstance(expr, ast.UnaryOp):
            if expr.op == "!":
                return self._logical_not_src(expr, self._translate_expr(expr.operand))
            return f"({expr.op}{self._translate_expr(expr.operand)})"
        if isinstance(expr, ast.AwaitExpr):
            raise CodegenNotSupported(
                expr,
                "`await` parses but its lowering to a gated while_loop "
                "is not yet implemented. The full design is specified "
                "in planning/sutra-spec/promises.md; the lowering pass "
                "is the next phase per queue.md item 1.",
            )
        if isinstance(expr, ast.ThisExpr):
            return "this"
        if isinstance(expr, ast.NewExpr):
            # `new ClassName(args)` — auto-constructor sugar. Lowers to
            # `<Class>_new(args)` where the factory is emitted by
            # `_emit_class_factory` in the pre-pass. Per the user's
            # 2026-05-08 design: a constructor is "a function that
            # returns something that is in the class"; `new` is just
            # ergonomic sugar for the field-init form.
            #
            # Primitive-class constructors route to the runtime's
            # `<class>_new` helper directly. `new dict()` gives C#-style
            # dictionary instantiation matching the existing subscript
            # syntax for that type.
            if expr.class_name == "dict":
                return "_VSA.hashmap_new()"
            arg_srcs = [self._translate_expr(a) for a in expr.args]
            return f"{expr.class_name}_new({', '.join(arg_srcs)})"
        if isinstance(expr, ast.MemberAccess):
            # Class-field read: `c.name` where c is a class-typed local
            # and `name` is declared as a field on that class. Per the
            # 2026-05-08 class-field design, fields share the axon
            # rotation-binding machinery — emit `_VSA.axon_item(c,
            # "name")`. Falls through to the pass-through form if the
            # member isn't a declared field (so `.string_length()`,
            # `Class.method` static dispatch, and other patterns keep
            # working).
            if isinstance(expr.obj, ast.Identifier):
                obj_name = expr.obj.name
                obj_class = self._var_type.get(obj_name)
                if (obj_class is not None
                        and obj_class in self._class_fields
                        and expr.member in self._class_fields[obj_class]):
                    return f'_VSA.axon_item({obj_name}, "{expr.member}")'
            # Same field-read rule, but for `this.field` inside a class
            # method body. The current class is captured in
            # `_current_class_name`; if the member is a declared field
            # on it, emit the axon read on the `this` param.
            if (isinstance(expr.obj, ast.ThisExpr)
                    and self._current_class_name is not None):
                cls_name = self._current_class_name
                if (cls_name in self._class_fields
                        and expr.member in self._class_fields[cls_name]):
                    return f'_VSA.axon_item(this, "{expr.member}")'
            # Math namespace constants. PI and TAU are stored scalars
            # (true constants); E is *not* a cached constant — it
            # beta-reduces live to `_VSA.exp(1.0)` at every reference,
            # so the value is visibly computed via the substrate's exp
            # implementation per Emma's 2026-05-10 directive ("E is
            # just the exponential function of one"). TAU = 2π is a
            # native first-class constant alongside PI.
            if (isinstance(expr.obj, ast.Identifier)
                    and expr.obj.name == "Math"):
                if expr.member == "PI":
                    return "_VSA.PI"
                if expr.member == "TAU":
                    return "_VSA.TAU"
                if expr.member == "E":
                    return "_VSA.exp(1.0)"
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
            if (name == "bundle"
                    and len(call.args) >= 2
                    and all(_is_bind_call(a) for a in call.args)):
                pair_srcs = []
                for bind_call in call.args:
                    role_src = self._translate_expr(bind_call.args[0])
                    filler_src = self._translate_expr(bind_call.args[1])
                    pair_srcs.append(f"({role_src}, {filler_src})")
                return f"_VSA.bundle_of_binds({', '.join(pair_srcs)})"
            if name in ("hasOrder", "hasOrderOrEqual"):
                for arg in call.args:
                    if isinstance(arg, ast.Call):
                        raise CodegenNotSupported(
                            call,
                            f"`{name}(...)` with a nested `Equals(...)` "
                            "group arg is reserved syntax — produced by "
                            "the parser for source like `a == b > c == "
                            "d > e` (equality groups separated by "
                            "ordering). The expansion (chain-AND with "
                            "internal group equality plus cross-group "
                            "ordering) is not yet wired in codegen. "
                            "For now, rewrite the comparison without "
                            "the mixed `==` and ordering pattern (e.g. "
                            "as separate AND-joined comparisons).",
                        )
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
            # Look up the called function's param types (registered in
            # Pre-pass C of translate()). Used for literal-coercion at
            # the call boundary so `f("alice")` against
            # `function int f(string s)` wraps "alice" via make_string.
            param_types = self._func_param_types.get(name)
            # Axon role-key intrinsics: the `key` arg is a role NAME the
            # runtime embeds into a basis vector (axons.su:
            # `axon_item(a,k) → unbind(basis_vector(k), a)`), NOT string
            # content. It must reach the runtime as a host str so
            # axon_add / axon_item take their `isinstance(key, str)` →
            # embed(key) branch — consistently with the member-access
            # path (`a.item("k")`, which passes no dest_type) and with
            # the producer side. Coercing it via make_string (because
            # the stdlib signature types it `string`) hands the runtime
            # a codepoint vector → wrong role rotation → silent
            # cross-module axon decode corruption. Regression introduced
            # by the 2026-05-08 parallel string model; root-caused
            # 2026-05-15 (multi_program_axon recovered +0.04 vs +0.40,
            # producer/member-access used embed-key, consumer/free-call
            # used make_string-key — they disagreed).
            _axon_key_arg = {"axon_add": 1, "axon_item": 1}.get(name)
            def _arg_dest(i: int) -> str | None:
                if _axon_key_arg is not None and i == _axon_key_arg:
                    return None
                if param_types is None or i >= len(param_types):
                    return None
                return param_types[i]
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
                arg_srcs = [
                    self._translate_expr(a, dest_type=_arg_dest(i))
                    for i, a in enumerate(call.args)
                ]
                return f"_VSA.{name}({', '.join(arg_srcs)})"
            # User-defined call: emit as-is.
            arg_srcs = [
                self._translate_expr(a, dest_type=_arg_dest(i))
                for i, a in enumerate(call.args)
            ]
            return f"{name}({', '.join(arg_srcs)})"
        if isinstance(callee, ast.MemberAccess):
            # `this.method(args)` from inside a class method body —
            # dispatch to `{CurrentClass}_{method}(this, *args)`. The
            # current class name is captured in
            # `_current_class_name` while a class method body is
            # being emitted.
            if (isinstance(callee.obj, ast.ThisExpr)
                    and self._current_class_name is not None):
                cls_name = self._current_class_name
                method_name = callee.member
                if (cls_name in self._class_instance_methods
                        and method_name in self._class_instance_methods[cls_name]):
                    arg_srcs = [self._translate_expr(a) for a in call.args]
                    all_args = ["this", *arg_srcs]
                    return f"{cls_name}_{method_name}({', '.join(all_args)})"
                if (cls_name in self._class_static_methods
                        and method_name in self._class_static_methods[cls_name]):
                    # `this.staticMethod(...)` — surfaces as a class-
                    # namespace call too (static doesn't take `this`).
                    if (cls_name in self._class_intrinsic_methods
                            and method_name in self._class_intrinsic_methods[cls_name]):
                        arg_srcs = [self._translate_expr(a) for a in call.args]
                        return f"_VSA.{method_name}({', '.join(arg_srcs)})"
                    arg_srcs = [self._translate_expr(a) for a in call.args]
                    return f"{cls_name}_{method_name}({', '.join(arg_srcs)})"
            # Class-namespace dispatch: `Math.log(x)` where `Math` is a
            # declared class and `log` is a static method on it. We
            # emit it as `Math_log(x)` — the mangled name that
            # _translate_class_method registered. Instance method
            # dispatch (`g.Hello()` on a Greeter instance) is not
            # wired today; that path falls through to the generic
            # `obj.member(args)` form which works iff `obj` is a
            # native Python object that already has the method (e.g.
            # vector accessors handled in the numpy-backend override).
            if isinstance(callee.obj, ast.Identifier):
                # Instance dispatch on an Axon-typed local:
                # `a.add(k, v)` and `a.item(k)` route to the runtime
                # axon methods with `a` as the first argument.
                # Statement-context augmented-assignment (rebinding `a`
                # for void-returning calls) is handled in
                # `_translate_stmt`; this expression path always emits
                # the call as a value.
                if callee.obj.name in self._axon_declared:
                    method_name = callee.member
                    runtime_name = {
                        "add": "axon_add",
                        "item": "axon_item",
                    }.get(method_name)
                    if runtime_name is not None:
                        arg_srcs = [self._translate_expr(a) for a in call.args]
                        all_args = [callee.obj.name] + arg_srcs
                        return f"_VSA.{runtime_name}({', '.join(all_args)})"
            # String runtime methods: when an expression like
            # `<expr>.string_length()` appears, route to the runtime
            # regardless of whether the receiver is a known typed
            # local. The receiver is whatever expression evaluates
            # there at runtime; the String runtime methods accept any
            # tensor and behave correctly when the AXIS_STRING_FLAG is
            # set. Same convention will extend to other class-bound
            # runtime intrinsics as the language adds them.
            _RUNTIME_INSTANCE_METHODS = {
                "string_length", "string_char_at", "is_string",
            }
            if callee.member in _RUNTIME_INSTANCE_METHODS:
                obj_src = self._translate_expr(callee.obj)
                arg_srcs = [self._translate_expr(a) for a in call.args]
                all_args = [obj_src] + arg_srcs
                return f"_VSA.{callee.member}({', '.join(all_args)})"
            if isinstance(callee.obj, ast.Identifier):
                # General instance dispatch: when `obj` is a typed
                # local whose declared type is a known class with the
                # called method, route to the appropriate static-form
                # name (`_VSA.<name>` for intrinsics, `Class_<name>`
                # for non-intrinsic instance methods). This is the
                # generalized version of the axon hardcode above —
                # the rule "any class's instance method is callable
                # via dot syntax on a typed receiver" applies to all
                # classes, not just Axon. Statement-context
                # augmented-assignment for void-returning methods is
                # handled in `_translate_stmt`; this path is the
                # expression-form translation.
                obj_name = callee.obj.name
                if obj_name in self._var_type:
                    obj_class = self._var_type[obj_name]
                    method_name_g = callee.member
                    if (obj_class in self._class_intrinsic_methods
                            and method_name_g in self._class_intrinsic_methods[obj_class]):
                        arg_srcs = [self._translate_expr(a) for a in call.args]
                        all_args = [obj_name] + arg_srcs
                        return f"_VSA.{method_name_g}({', '.join(all_args)})"
                    if (obj_class in self._class_instance_methods
                            and method_name_g in self._class_instance_methods[obj_class]):
                        arg_srcs = [self._translate_expr(a) for a in call.args]
                        all_args = [obj_name] + arg_srcs
                        return f"{obj_class}_{method_name_g}({', '.join(all_args)})"
                cls_name = callee.obj.name
                method_name = callee.member
                # Intrinsic methods on a class route directly to the
                # runtime: `Math.log(x)` -> `_VSA.log(x)`. The mangled
                # wrapper isn't emitted for intrinsic-marked methods.
                if (cls_name in self._class_intrinsic_methods
                        and method_name in self._class_intrinsic_methods[cls_name]):
                    arg_srcs = [self._translate_expr(a) for a in call.args]
                    return f"_VSA.{method_name}({', '.join(arg_srcs)})"
                if (cls_name in self._class_static_methods
                        and method_name in self._class_static_methods[cls_name]):
                    arg_srcs = [self._translate_expr(a) for a in call.args]
                    return f"{cls_name}_{method_name}({', '.join(arg_srcs)})"
                # Non-static class method called via class-namespace
                # syntax: `Greeter.Hello(g, ...)`. The first arg is the
                # instance and becomes `this` inside the method body.
                # The mangled function takes `this` as its first param,
                # so we just emit the args straight through — Python
                # doesn't care about the param name at the call site.
                if (cls_name in self._class_instance_methods
                        and method_name in self._class_instance_methods[cls_name]):
                    arg_srcs = [self._translate_expr(a) for a in call.args]
                    return f"{cls_name}_{method_name}({', '.join(arg_srcs)})"
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


