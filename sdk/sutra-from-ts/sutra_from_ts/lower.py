"""TS / JS → Sutra lowering pass.

Walks a tree-sitter parse tree and emits Sutra (.su) source. Two-pass
design: a pre-pass collects top-level type and function declarations
(so cross-references resolve regardless of source order), then the main
pass walks each function body emitting Sutra syntax with type
information available.

Scope today:

- Function declarations with typed or implicit-`any` parameters.
- `const` / `let` / `var` declarations, including object-literal RHS
  that targets an interface-shaped type (lowered to `Axon` + `add`).
- `interface` and `type` declarations are erased (their only effect is
  registering "this name is Axon-shaped" in the context).
- Member access: `p.x` lowers to `p.item("x")` when `p` is Axon-typed,
  passes through otherwise.
- Binary `+`: lowers to `JavaScriptObject.add(a, b)` when either operand
  is JavaScriptObject-typed (JS coercive `+` semantics); plain numeric
  `+` otherwise.
- Function call argument coercion: a primitive literal passed to a
  JavaScriptObject parameter is wrapped as `JavaScriptObject.from(...)`.
- The if-then-implicit-else statement pattern lowers to a strong-defuzz
  blend; statement-form if without a trailing return falls through to a
  diagnostic comment.

Anything outside this scope falls through to a `// UNSUPPORTED:
<node-type>` comment in the output, so the caller can see what features
blocked translation. See DESIGN.md for the full intended scope.
"""

from __future__ import annotations

import pathlib
from dataclasses import dataclass, field
from typing import Optional


# Extensions tried (in order) when resolving an `import { … } from "./x"`
# specifier. `.ts` / `.tsx` are recursively lowered; `.su` is read raw
# and inlined as-is, the same way the Sutra stdlib loader treats its
# own .su files. Order mirrors TypeScript's own extension search.
_IMPORT_RESOLVE_EXTENSIONS = (".ts", ".tsx", ".su")


_TS_PRIMITIVE_TO_SUTRA = {
    "number": "int",      # default; float-vs-int inference is future work
    "string": "String",
    "boolean": "bool",
    "void": "void",
    "any": "JavaScriptObject",
    "unknown": "JavaScriptObject",
}


@dataclass
class Context:
    """Compile-time information collected by the pre-pass and used during
    the main lowering walk.

    `interface_names` and `type_alias_names` map a TS-side type name to
    "this name is Axon-shaped." `class_names` collects user-defined TS
    class names so the lowering can pass their type identifiers through
    as-is rather than treating them as Axons. `function_param_types` is
    a name → list-of-Sutra-types map for resolving call-site coercions.
    `local_types` is updated as the main pass walks function bodies.
    `extras` and `loop_counter` thread through so loop-hoisting can
    deposit declared `while_loop` definitions at module scope.
    """

    interface_names: set[str] = field(default_factory=set)
    type_alias_names: set[str] = field(default_factory=set)
    class_names: set[str] = field(default_factory=set)
    # TS `enum Color { Red, Green = 5, Blue }` → record the integer
    # value of each member so `Color.Red` expressions can lower to
    # the literal integer at the call site. Members without explicit
    # `= N` auto-increment from the previous (default starting at 0).
    # Keys: f"{EnumName}.{Member}" → int. Param types declared as
    # `c: Color` lower to `int c` (the runtime carrier of an enum).
    enum_member_values: dict[str, int] = field(default_factory=dict)
    enum_names: set[str] = field(default_factory=set)
    function_param_types: dict[str, list[str]] = field(default_factory=dict)
    local_types: dict[str, str] = field(default_factory=dict)
    extras: list[str] = field(default_factory=list)
    loop_counter: list[int] = field(default_factory=lambda: [0])
    # arrow_captures maps an arrow-function's emitted Sutra name to the
    # ordered list of local-variable names it captured from its enclosing
    # scope. Per the user's 2026-05-09 framing: Sutra has no closure, so
    # captured locals are lifted to extra parameters at transpile time
    # and threaded through at every direct call site. Used by both the
    # arrow-as-const lowering (which emits the lifted parameters) and
    # the call-site lowering (which appends the captured argument values
    # in the same order).
    arrow_captures: dict[str, list[str]] = field(default_factory=dict)
    # field_types maps an interface/type-alias field NAME to its Sutra
    # type ("int"/"float"/"String"/…), collected across every declared
    # interface and type alias. Used at member access (`p.x`) to decide
    # whether a numeric field read needs a `.real()` projection — without
    # it, an axon numeric field read comes back as the raw filler vector
    # and arithmetic on it collapses to ~0 on the substrate. String /
    # literal-tag fields must NOT get `.real()` (they feed string
    # comparisons). On a name collision with conflicting types the field
    # is marked non-numeric to stay safe.
    field_types: dict[str, str] = field(default_factory=dict)

    def is_axon_typed(self, type_name: str) -> bool:
        return (
            type_name in self.interface_names
            or type_name in self.type_alias_names
        )

    def lookup_local(self, name: str) -> Optional[str]:
        return self.local_types.get(name)

    def next_loop_index(self) -> int:
        idx = self.loop_counter[0]
        self.loop_counter[0] = idx + 1
        return idx

    def child_scope(self) -> "Context":
        """Return a context with the same global state and a fresh local
        scope."""
        return Context(
            interface_names=self.interface_names,
            type_alias_names=self.type_alias_names,
            class_names=self.class_names,
            enum_member_values=self.enum_member_values,
            enum_names=self.enum_names,
            function_param_types=self.function_param_types,
            local_types={},
            extras=self.extras,
            loop_counter=self.loop_counter,
            arrow_captures=self.arrow_captures,
            field_types=self.field_types,
        )


def _node_text(node, source: bytes) -> str:
    return source[node.start_byte:node.end_byte].decode("utf-8")


def _ts_type_to_sutra(annotation_node, source: bytes, ctx: Context) -> str:
    """Given a `type_annotation` node, return the Sutra type name."""
    if annotation_node is None:
        return "JavaScriptObject"
    inner = annotation_node.named_children[0] if annotation_node.named_children else None
    if inner is None:
        return "JavaScriptObject"
    if inner.type == "predefined_type":
        text = _node_text(inner, source)
        return _TS_PRIMITIVE_TO_SUTRA.get(text, "JavaScriptObject")
    if inner.type == "type_identifier":
        name = _node_text(inner, source)
        if ctx.is_axon_typed(name):
            return "Axon"
        # Enum-typed parameters carry their integer value at runtime.
        # The Sutra-side parameter type is plain `int`; the enum's
        # "type" is purely a transpile-time tag for name lookups.
        if name in ctx.enum_names:
            return "int"
        return name
    if inner.type == "array_type":
        # `T[]` — Sutra-side we use the marker name `Array` so the
        # transpiler knows to dispatch `.length` / `[i]` through the
        # array builtins. The Sutra type system doesn't have a real
        # parameterized `Array<T>` yet; underneath it's a vector / a
        # Python list at runtime depending on how it's constructed.
        return "Array"
    if inner.type == "generic_type":
        # `Promise<T>` (and any other `Foo<T>` generic) — preserve the
        # parameterised form so it round-trips into Sutra's type-ref
        # syntax. Inner T is recursively lowered as if it were the
        # body of a synthetic type_annotation. See planning/sutra-spec/
        # promises.md for the Promise<T> handling specifically.
        head = inner.child_by_field_name("name")
        args_node = next(
            (c for c in inner.named_children if c.type == "type_arguments"),
            None,
        )
        if head is None or args_node is None:
            return "JavaScriptObject"
        name = _node_text(head, source)
        arg_srcs = []
        for arg in args_node.named_children:
            # arg is a type expression; reuse the same lowering by
            # synthesising the predefined-type / type_identifier / etc.
            # branches inline.
            if arg.type == "predefined_type":
                t = _node_text(arg, source)
                arg_srcs.append(_TS_PRIMITIVE_TO_SUTRA.get(t, "JavaScriptObject"))
            elif arg.type == "type_identifier":
                arg_srcs.append(_node_text(arg, source))
            else:
                arg_srcs.append("JavaScriptObject")
        return f"{name}<{', '.join(arg_srcs)}>"
    return "JavaScriptObject"


def _expr_type(node, source: bytes, ctx: Context) -> Optional[str]:
    """Best-effort type of an expression. Returns None when the type
    cannot be determined locally."""
    if node.type == "identifier":
        return ctx.lookup_local(_node_text(node, source))
    if node.type == "number":
        return "int"
    if node.type == "string":
        return "String"
    if node.type in ("true", "false"):
        return "bool"
    if node.type == "parenthesized_expression" and node.named_children:
        return _expr_type(node.named_children[0], source, ctx)
    return None


def _lower_object_literal_into_axon(
    obj_node, target_name: str, source: bytes, ctx: Context, indent: str,
) -> str:
    """Lower an object literal `{ k1: v1, k2: v2 }` as a sequence of
    `target_name.add(k, v)` augmented-assignment statements. Used when
    the object literal is the RHS of a typed-variable declaration whose
    type is Axon-shaped."""
    out = ""
    for child in obj_node.named_children:
        if child.type != "pair":
            continue
        key = child.child_by_field_name("key")
        value = child.child_by_field_name("value")
        if key is None or value is None:
            continue
        key_text = _node_text(key, source)
        if key.type == "property_identifier":
            key_str = f'"{key_text}"'
        elif key.type == "string":
            key_str = key_text
        else:
            key_str = f'"{key_text}"'
        value_src = _lower_expression(value, source, ctx)
        out += f"{indent}{target_name}.add({key_str}, {value_src});\n"
    return out


def _lower_expression(node, source: bytes, ctx: Context) -> str:
    if node.type == "number":
        return _node_text(node, source)
    if node.type == "string":
        text = _node_text(node, source)
        return f"String.make_string({text})"
    if node.type == "true":
        return "true"
    if node.type == "false":
        return "false"
    if node.type == "identifier":
        return _node_text(node, source)
    if node.type == "this":
        return "this"
    if node.type == "array":
        # `[1, 2, 3]` array literal — emits as a Sutra array literal,
        # which the codegen lowers to a Python list. Array helpers
        # (`array_length`, `array_get`) work on these.
        elem_srcs = [
            _lower_expression(e, source, ctx)
            for e in node.named_children
        ]
        return f"[{', '.join(elem_srcs)}]"
    if node.type == "subscript_expression":
        # `arr[i]` — Sutra has subscript built in (lowers to Python
        # `arr[i]`), so passing through as-is works for plain Python-
        # list arrays.
        target = node.child_by_field_name("object")
        index = node.child_by_field_name("index")
        target_src = (
            _lower_expression(target, source, ctx)
            if target is not None else "/* missing */"
        )
        index_src = (
            _lower_expression(index, source, ctx)
            if index is not None else "0"
        )
        return f"{target_src}[{index_src}]"
    if node.type == "new_expression":
        # `new ClassName(args)` — passes through to Sutra's `new`
        # auto-constructor sugar (which emits `<Class>_new(args)`).
        callee = node.child_by_field_name("constructor")
        args_node = node.child_by_field_name("arguments")
        if callee is None:
            return "/* UNSUPPORTED: new without constructor name */"
        class_name = _node_text(callee, source)
        arg_srcs = [
            _lower_expression(a, source, ctx)
            for a in (args_node.named_children if args_node else [])
        ]
        return f"new {class_name}({', '.join(arg_srcs)})"
    if node.type == "binary_expression":
        left = node.child_by_field_name("left")
        right = node.child_by_field_name("right")
        op = node.child_by_field_name("operator")
        op_text = _node_text(op, source) if op is not None else "+"
        op_text = {"===": "==", "!==": "!="}.get(op_text, op_text)
        left_src = _lower_expression(left, source, ctx)
        right_src = _lower_expression(right, source, ctx)
        if op_text == "+":
            left_t = _expr_type(left, source, ctx)
            right_t = _expr_type(right, source, ctx)
            if left_t == "JavaScriptObject" or right_t == "JavaScriptObject":
                # `js_add` rather than `add` to avoid colliding with the
                # axon `add` runtime method, and to make the JS-coercive
                # `+` semantics explicit at the Sutra level.
                return f"JavaScriptObject.js_add({left_src}, {right_src})"
            # `string + string` → `String.string_concat(a, b)`. Sutra's
            # default `+` doesn't lower to anything meaningful for two
            # vectors with the AXIS_STRING_FLAG set; the dedicated
            # `string_concat` intrinsic walks the codepoint axes.
            if left_t == "String" and right_t == "String":
                return f"String.string_concat({left_src}, {right_src})"
        # Ordered comparisons against a JSO use the JS-coercion path:
        # both-string → lex compare, otherwise numeric. The plain Sutra
        # `<`/`>` lowering does fuzzy similarity on the truth axis,
        # which is wrong for JS semantics (a JS program that writes
        # `if (s < t)` against two strings expects a lex result).
        if op_text in ("<", ">", "<=", ">="):
            left_t = _expr_type(left, source, ctx)
            right_t = _expr_type(right, source, ctx)
            if left_t == "JavaScriptObject" or right_t == "JavaScriptObject":
                method = {
                    "<":  "js_lt",
                    ">":  "js_gt",
                    "<=": "js_le",
                    ">=": "js_ge",
                }[op_text]
                return f"JavaScriptObject.{method}({left_src}, {right_src})"
        return f"{left_src} {op_text} {right_src}"
    if node.type == "unary_expression":
        op = node.child_by_field_name("operator")
        arg = node.child_by_field_name("argument")
        op_text = _node_text(op, source) if op is not None else "-"
        return f"({op_text}{_lower_expression(arg, source, ctx)})"
    if node.type == "parenthesized_expression":
        inner = node.named_children[0]
        # Preserve source-level grouping. Binary expressions don't auto-
        # parenthesize anymore (precedence is left to the Sutra parser),
        # so an explicit `(a+b)*c` in the source must keep its parens to
        # not be reparsed as `a + b*c`.
        return f"({_lower_expression(inner, source, ctx)})"
    if node.type == "call_expression":
        func = node.child_by_field_name("function")
        args_node = node.child_by_field_name("arguments")
        func_src = _lower_expression(func, source, ctx)
        callee_param_types = None
        callee_captures: list[str] = []
        if func is not None and func.type == "identifier":
            callee_name = _node_text(func, source)
            callee_param_types = ctx.function_param_types.get(callee_name)
            # Closure-free closure capture: if the callee is an arrow
            # function whose original body referenced enclosing-scope
            # locals, those locals were lifted to extra parameters by
            # _lower_arrow_as_function. Append them to the call's
            # explicit args here so the generated function gets the
            # captured values without any runtime closure machinery.
            callee_captures = ctx.arrow_captures.get(callee_name, [])
        arg_nodes = list(args_node.named_children) if args_node else []
        arg_srcs = []
        for i, a in enumerate(arg_nodes):
            arg_src = _lower_expression(a, source, ctx)
            if (callee_param_types is not None
                    and i < len(callee_param_types)
                    and callee_param_types[i] == "JavaScriptObject"
                    and a.type in ("number", "string", "true", "false")):
                # `wrap` rather than `from` because `from` is a Python
                # keyword — Sutra's static-intrinsic dispatch routes
                # `JavaScriptObject.from(x)` to `_VSA.from(x)` which is
                # a syntax error in the emitted Python. `wrap` avoids
                # the conflict.
                arg_src = f"JavaScriptObject.wrap({arg_src})"
            arg_srcs.append(arg_src)
        # Append captured-locals as explicit args, in the same order
        # they were lifted as parameters. The names must already be in
        # scope at the call site (the capture set was computed at
        # arrow-declaration time from the enclosing scope's locals).
        for cap in callee_captures:
            arg_srcs.append(cap)
        return f"{func_src}({', '.join(arg_srcs)})"
    if node.type == "assignment_expression":
        # `x = expr` — plain reassignment. The Sutra-side slot machinery
        # is what makes this compile; lowering emits the bare assignment
        # form and trusts the upstream `let` lowering to have declared
        # the LHS as `slot TYPE`.
        left = node.child_by_field_name("left")
        right = node.child_by_field_name("right")
        return f"{_lower_expression(left, source, ctx)} = {_lower_expression(right, source, ctx)}"
    if node.type == "augmented_assignment_expression":
        # `x += expr` desugars to `x = x + expr`. Operator is one of
        # `+=`, `-=`, `*=`, `/=`, `%=`. We strip the trailing `=`.
        left = node.child_by_field_name("left")
        right = node.child_by_field_name("right")
        op = node.child_by_field_name("operator")
        op_text = _node_text(op, source) if op is not None else "+="
        bin_op = op_text.rstrip("=")
        left_src = _lower_expression(left, source, ctx)
        right_src = _lower_expression(right, source, ctx)
        return f"{left_src} = {left_src} {bin_op} {right_src}"
    if node.type == "update_expression":
        # `i++` / `i--` desugar to `i = i + 1` / `i = i - 1`. Prefix and
        # postfix forms are not distinguished — Sutra has no notion of
        # an expression's pre- vs post-increment value, so we treat both
        # as the statement form.
        arg = node.child_by_field_name("argument")
        op = node.child_by_field_name("operator")
        op_text = _node_text(op, source) if op is not None else "++"
        bin_op = "+" if op_text == "++" else "-"
        arg_src = _lower_expression(arg, source, ctx)
        return f"{arg_src} = {arg_src} {bin_op} 1"
    if node.type == "member_expression":
        obj = node.child_by_field_name("object")
        prop = node.child_by_field_name("property")
        # Enum member access — `Color.Red` lowers to the integer the
        # prepass recorded for that member. Has to happen BEFORE the
        # generic member-access lowering because the enum name is not
        # an in-scope value (the enum itself is erased) — emitting
        # `Color.Red` literally would be a NameError at runtime.
        if (obj is not None and obj.type == "identifier"
                and prop is not None and prop.type == "property_identifier"):
            obj_name = _node_text(obj, source)
            prop_name = _node_text(prop, source)
            if obj_name in ctx.enum_names:
                key = f"{obj_name}.{prop_name}"
                if key in ctx.enum_member_values:
                    return str(ctx.enum_member_values[key])
        obj_src = _lower_expression(obj, source, ctx)
        prop_text = _node_text(prop, source) if prop is not None else ""
        obj_t = _expr_type(obj, source, ctx) if obj is not None else None
        if obj_t == "Axon":
            # Numeric axon field reads need a `.real()` projection to
            # decode the number off the axon's number-axis — without it
            # the read is the raw filler vector and arithmetic collapses
            # to ~0 on the substrate (measured 2026-06-05). String /
            # literal-tag fields must NOT get `.real()` (they feed string
            # comparisons). The field's type comes from the global
            # interface/alias field-type map; unknown fields default to
            # no projection (safe for strings).
            if ctx.field_types.get(prop_text) in ("int", "float"):
                return f'{obj_src}.item("{prop_text}").real()'
            return f'{obj_src}.item("{prop_text}")'
        # Array-typed `arr.length` → `array_length(arr)` (a Sutra
        # builtin that emits Python `len(arr)`).
        if obj_t == "Array" and prop_text == "length":
            return f"array_length({obj_src})"
        _PROPERTY_TO_METHOD = {
            "length": "string_length",
        }
        if prop_text in _PROPERTY_TO_METHOD:
            return f"{obj_src}.{_PROPERTY_TO_METHOD[prop_text]}()"
        return f"{obj_src}.{prop_text}"
    if node.type == "await_expression":
        # `await expr` — passes through as Sutra `await expr`. Only
        # legal inside an async function body; the Sutra parser
        # accepts the syntax and the codegen errors with a
        # promises.md pointer until the lowering pass lands. See
        # planning/sutra-spec/promises.md §"Lowering".
        operand = node.named_children[0] if node.named_children else None
        operand_src = (
            _lower_expression(operand, source, ctx)
            if operand is not None
            else "/* UNSUPPORTED-AWAIT: empty */"
        )
        return f"await {operand_src}"
    return f"/* UNSUPPORTED-EXPR: {node.type} */"


def _collect_referenced_locals(node, source: bytes, ctx: Context) -> set[str]:
    """Walk an AST subtree and return the set of local variable names
    referenced under it. A name is "local" if it's already declared
    in the surrounding context (`ctx.local_types`). The `this`
    keyword and member-property identifiers are skipped — only the
    object side of a member expression counts as a reference."""
    seen: set[str] = set()

    def walk(n):
        if n is None:
            return
        t = n.type
        if t == "identifier":
            name = _node_text(n, source)
            if name in ctx.local_types and name != "this":
                seen.add(name)
            return
        if t == "this":
            return
        if t == "member_expression":
            obj = n.child_by_field_name("object")
            walk(obj)
            return
        for child in n.named_children:
            walk(child)

    walk(node)
    return seen


def _collect_mutated_locals(node, source: bytes, ctx: Context) -> set[str]:
    """Walk an AST subtree and return the set of local variable names
    that are assigned to. Counts assignment_expression,
    augmented_assignment_expression, and update_expression where the
    LHS is a plain identifier referencing an outer-scope local."""
    seen: set[str] = set()

    def walk(n):
        if n is None:
            return
        t = n.type
        if t == "assignment_expression":
            left = n.child_by_field_name("left")
            if left is not None and left.type == "identifier":
                name = _node_text(left, source)
                if name in ctx.local_types and name != "this":
                    seen.add(name)
            right = n.child_by_field_name("right")
            walk(right)
            return
        if t == "augmented_assignment_expression":
            left = n.child_by_field_name("left")
            if left is not None and left.type == "identifier":
                name = _node_text(left, source)
                if name in ctx.local_types and name != "this":
                    seen.add(name)
            right = n.child_by_field_name("right")
            walk(right)
            return
        if t == "update_expression":
            arg = n.child_by_field_name("argument")
            if arg is not None and arg.type == "identifier":
                name = _node_text(arg, source)
                if name in ctx.local_types and name != "this":
                    seen.add(name)
            return
        for child in n.named_children:
            walk(child)

    walk(node)
    return seen


def _hoist_loop(
    cond_inner, body_stmts: list, kind: str,
    source: bytes, ctx: Context, indent: str,
    extra_increment=None,
) -> str:
    """Common backend for `while`, `do-while`, and `for` lowering.
    Hoists into a top-level loop-function decl + slot decls +
    `loop NAME(...)` call.

    Args:
      cond_inner: the condition AST node (already unwrapped from
        parenthesized_expression for while/do, or the bare cond
        expression for for).
      body_stmts: list of AST statement nodes that form the body.
      kind: "while_loop" or "do_while" — chooses the Sutra keyword.
      extra_increment: optional AST expression that runs at the end
        of each iteration (the for-loop increment). Folded into the
        body's variable analysis and emitted last.
    """
    refs: set[str] = set()
    mutated: set[str] = set()
    if cond_inner is not None:
        refs |= _collect_referenced_locals(cond_inner, source, ctx)
    for stmt in body_stmts:
        refs |= _collect_referenced_locals(stmt, source, ctx)
        mutated |= _collect_mutated_locals(stmt, source, ctx)
    if extra_increment is not None:
        refs |= _collect_referenced_locals(extra_increment, source, ctx)
        mutated |= _collect_mutated_locals(extra_increment, source, ctx)
    state_vars = sorted(refs | mutated)

    if not state_vars:
        return f"{indent}// UNSUPPORTED: loop with no referenced locals\n"

    loop_idx = ctx.next_loop_index()
    loop_fn = f"_loop_{loop_idx}"
    state_param_decls = ", ".join(
        f"{ctx.local_types[v]} {v} = 0" for v in state_vars
    )
    cond_src = (
        _lower_expression(cond_inner, source, ctx)
        if cond_inner is not None else "false"
    )

    body_ctx = ctx.child_scope()
    for v in state_vars:
        body_ctx.local_types[v] = ctx.local_types[v]
    body_src = ""
    for stmt in body_stmts:
        body_src += _lower_statement(stmt, source, body_ctx, "    ")
    if extra_increment is not None:
        # The for-loop increment is an expression; emit it as a
        # statement at the end of each iteration.
        incr_src = _lower_expression(extra_increment, source, body_ctx)
        body_src += f"    {incr_src};\n"

    ctx.extras.append(
        f"{kind} {loop_fn}({cond_src}, {state_param_decls}) {{\n"
        f"{body_src}}}\n\n"
    )

    # Call site: slot copies + loop call + write-back for mutated.
    out = ""
    slot_args: list[str] = []
    for v in state_vars:
        slot_name = f"_{v}_l{loop_idx}"
        t = ctx.local_types[v]
        out += f"{indent}slot {t} {slot_name} = {v};\n"
        slot_args.append(slot_name)
    out += (
        f"{indent}loop {loop_fn}({cond_src}, {', '.join(slot_args)});\n"
    )
    # Write back all state vars from their slot copies. For read-only
    # vars this is a no-op (the slot still holds the input value).
    # We can't restrict to `mutated` because Sutra's void-method
    # augmented-assignment (`c.method(); → c = Class_method(c)`)
    # rebinds the receiver but isn't visible to my mutation analysis
    # — covering all referenced vars catches that case correctly.
    for v, slot_name in zip(state_vars, slot_args):
        out += f"{indent}{v} = {slot_name};\n"
    return out


def _lower_while_to_declared_loop(
    while_node, source: bytes, ctx: Context, indent: str,
) -> str:
    cond_node = while_node.child_by_field_name("condition")
    body_node = while_node.child_by_field_name("body")
    cond_inner = (
        cond_node.named_children[0]
        if cond_node is not None and cond_node.named_children else None
    )
    body_stmts = (
        list(body_node.named_children)
        if body_node is not None and body_node.type == "statement_block"
        else ([body_node] if body_node is not None else [])
    )
    return _hoist_loop(
        cond_inner, body_stmts, "while_loop",
        source, ctx, indent,
    )


def _lower_do_while_to_declared_loop(
    do_node, source: bytes, ctx: Context, indent: str,
) -> str:
    cond_node = do_node.child_by_field_name("condition")
    body_node = do_node.child_by_field_name("body")
    cond_inner = (
        cond_node.named_children[0]
        if cond_node is not None and cond_node.named_children else None
    )
    body_stmts = (
        list(body_node.named_children)
        if body_node is not None and body_node.type == "statement_block"
        else ([body_node] if body_node is not None else [])
    )
    return _hoist_loop(
        cond_inner, body_stmts, "do_while",
        source, ctx, indent,
    )


def _lower_for_to_declared_loop(
    for_node, source: bytes, ctx: Context, indent: str,
) -> str:
    """Lower `for (init; cond; incr) body` by emitting the init as a
    regular statement (so its declarations land in scope) and then
    hoisting (cond, body+incr) into a declared `while_loop`."""
    init = for_node.child_by_field_name("initializer")
    cond = for_node.child_by_field_name("condition")
    incr = for_node.child_by_field_name("increment")
    body = for_node.child_by_field_name("body")
    out = ""
    if init is not None:
        if init.type in ("lexical_declaration", "variable_declaration"):
            out += _lower_lexical_declaration(init, source, ctx, indent)
        else:
            out += f"{indent}{_lower_expression(init, source, ctx)};\n"
    body_stmts = (
        list(body.named_children)
        if body is not None and body.type == "statement_block"
        else ([body] if body is not None else [])
    )
    out += _hoist_loop(
        cond, body_stmts, "while_loop",
        source, ctx, indent,
        extra_increment=incr,
    )
    return out


def _lower_lexical_declaration(
    node, source: bytes, ctx: Context, indent: str
) -> str:
    """Lower `const x: T = expr;` / `let x: T = expr;` / `var x: T = expr;`
    to a Sutra typed declaration. When `expr` is an object literal and
    `T` is Axon-shaped, emit a multi-statement axon construction.

    `const` lowers to a plain typed declaration (immutable). `let` and
    `var` lower with the `slot` keyword so subsequent reassignments
    compile (the Sutra-side slot codegen does the SSA-elision/state-
    threading internally)."""
    # Detect const vs let/var by looking at the leading keyword in the
    # source span. Tree-sitter exposes a `kind` field on some grammars,
    # but it's more reliable across versions to read the first
    # non-whitespace token.
    head = _node_text(node, source).lstrip()
    is_mutable = head.startswith("let") or head.startswith("var")
    type_prefix = "slot " if is_mutable else ""

    out = ""
    for declarator in node.named_children:
        if declarator.type != "variable_declarator":
            continue
        name_node = declarator.child_by_field_name("name")
        type_node = declarator.child_by_field_name("type")
        value_node = declarator.child_by_field_name("value")
        if name_node is None:
            continue
        name = _node_text(name_node, source)
        if type_node is not None:
            sutra_type = _ts_type_to_sutra(type_node, source, ctx)
        else:
            # No explicit annotation — infer from the initializer if it's
            # a primitive literal. Falls back to JavaScriptObject.
            inferred = _expr_type(value_node, source, ctx) if value_node else None
            sutra_type = inferred if inferred is not None else "JavaScriptObject"
        ctx.local_types[name] = sutra_type
        if (value_node is not None
                and value_node.type == "object"
                and sutra_type == "Axon"):
            # Object-literal axon construction is inherently mutable
            # (we emit `add` calls into it), so `slot` is implicit.
            out += f"{indent}Axon {name};\n"
            out += _lower_object_literal_into_axon(
                value_node, name, source, ctx, indent
            )
        elif (value_node is not None
                and value_node.type == "arrow_function"):
            # Arrow function declared inside another function body.
            # Sutra's codegen doesn't allow nested function decls, so
            # we hoist the arrow to the module top level (just like
            # the loop-hoisting pass does) and rely on the call-site
            # lowering to reference it by name. Closure captures are
            # detected inside _lower_arrow_as_function and lifted to
            # extra parameters; ctx.arrow_captures records them so the
            # call sites thread the values through.
            arrow_src = _lower_arrow_as_function(name, value_node, source, ctx)
            ctx.extras.append(arrow_src)
            # No inline emission — the variable `name` is just an
            # identifier the call site resolves to the hoisted fn.
            # ctx.local_types still records `name` so further uses
            # don't trigger inference fallback to JavaScriptObject.
        elif value_node is not None:
            value_src = _lower_expression(value_node, source, ctx)
            out += f"{indent}{type_prefix}{sutra_type} {name} = {value_src};\n"
        else:
            out += f"{indent}{type_prefix}{sutra_type} {name};\n"
    return out


def _lower_statement(
    node, source: bytes, ctx: Context, indent: str = "    "
) -> str:
    if node.type == "return_statement":
        if node.named_children:
            expr_node = node.named_children[0]
            return f"{indent}return {_lower_expression(expr_node, source, ctx)};\n"
        return f"{indent}return;\n"
    if node.type == "expression_statement":
        inner = node.named_children[0] if node.named_children else None
        if inner is None:
            return ""
        return f"{indent}{_lower_expression(inner, source, ctx)};\n"
    if node.type in ("lexical_declaration", "variable_declaration"):
        return _lower_lexical_declaration(node, source, ctx, indent)
    if node.type == "while_statement":
        # Hoist into a top-level `while_loop NAME(...)` declaration +
        # slot decls + `loop NAME(...)` call. Sutra's codegen rejects
        # inline C-style `while (cond) { body }` in favor of the
        # declared loop form.
        return _lower_while_to_declared_loop(node, source, ctx, indent)
    if node.type == "for_statement":
        return _lower_for_to_declared_loop(node, source, ctx, indent)
    if node.type == "do_statement":
        return _lower_do_while_to_declared_loop(node, source, ctx, indent)
    if node.type == "if_statement":
        cond = node.child_by_field_name("condition")
        cons = node.child_by_field_name("consequence")
        alt = node.child_by_field_name("alternative")
        cond_src = (
            _lower_expression(cond.named_children[0], source, ctx)
            if cond and cond.named_children else "false"
        )
        cons_src = _lower_branch_result(cons, source, ctx)
        # Each product term is fully parenthesised — `((w) * (X))` — and
        # the two terms grouped before `/ 2`. A bare `* ({atom})` emits
        # `* (a) + …`, and the Sutra parser reads a parenthesised atom
        # before an infix operator (`(a) + …`) as a CAST `(Type) expr`,
        # which the codegen rejects (CastExpr). Full grouping avoids
        # placing a `(atom)` immediately before an infix op.
        w = f"truth_axis(defuzzy({cond_src}))"
        if alt is not None:
            alt_src = _lower_branch_result(alt, source, ctx)
            return (
                f"{indent}return (((1 + {w}) * ({cons_src})) "
                f"+ ((1 - {w}) * ({alt_src}))) / 2;\n"
            )
        # Emma 2026-05-10: if without else is the select-with-implicit-
        # zero-else form. The body is multiplied by the truthified
        # condition; the missing else contributes zero. Math:
        #   if (cond) { body }
        #     → ((1 + truth(defuzz(cond))) * body) / 2
        # When cond is true (defuzz → +1, truth → +1), the multiplier
        # is (1+1)/2 = 1 — body passes through unchanged. When cond is
        # false (defuzz → -1, truth → -1), the multiplier is (1-1)/2
        # = 0 — body is zeroed out. Differentiable, fuzzy at the
        # midpoint, no host-side control flow.
        return f"{indent}return (((1 + {w}) * ({cons_src}))) / 2;\n"
    if node.type == "statement_block":
        out = ""
        for child in node.named_children:
            out += _lower_statement(child, source, ctx, indent)
        return out
    if node.type == "comment":
        return ""
    return f"{indent}// UNSUPPORTED-STMT: {node.type}\n"


def _lower_branch_result(node, source: bytes, ctx: Context) -> str:
    """For `if/else` branches: extract the value the branch produces."""
    if node.type == "else_clause":
        # tree-sitter-typescript wraps the else branch in an `else_clause`
        # node (`else { … }` / `else if …`). Unwrap to its meaningful
        # child and recurse — otherwise the whole clause falls through to
        # the generic `_lower_expression` and emits
        # `/* UNSUPPORTED-EXPR: else_clause */`, silently dropping the
        # else branch.
        for c in node.named_children:
            if c.type != "comment":
                return _lower_branch_result(c, source, ctx)
        return "0"
    if node.type == "statement_block":
        if len(node.named_children) == 1:
            inner = node.named_children[0]
            if inner.type == "return_statement" and inner.named_children:
                return _lower_expression(inner.named_children[0], source, ctx)
    if node.type == "return_statement" and node.named_children:
        return _lower_expression(node.named_children[0], source, ctx)
    return _lower_expression(node, source, ctx)


def _branch_return_expr(node, source: bytes, ctx: Context) -> Optional[str]:
    if node is None:
        return None
    if node.type == "return_statement":
        if node.named_children:
            return _lower_expression(node.named_children[0], source, ctx)
        return None
    if node.type == "statement_block" and len(node.named_children) == 1:
        return _branch_return_expr(node.named_children[0], source, ctx)
    return None


def _lower_function_body(body_node, source: bytes, ctx: Context) -> str:
    """Lower a statement_block as a function body. Recognizes the
    if-then-(implicit-else) pattern and rewrites it to a strong-defuzz
    blend over the truth axis. See axes-of-strong-defuzz comments
    inline."""
    if body_node is None or body_node.type != "statement_block":
        return _lower_statement(body_node, source, ctx) if body_node else ""
    stmts = list(body_node.named_children)
    out_lines = []
    i = 0
    while i < len(stmts):
        cur = stmts[i]
        nxt = stmts[i + 1] if i + 1 < len(stmts) else None
        if (cur.type == "if_statement"
                and cur.child_by_field_name("alternative") is None
                and nxt is not None
                and nxt.type == "return_statement"):
            cons = cur.child_by_field_name("consequence")
            cons_ret = _branch_return_expr(cons, source, ctx)
            if cons_ret is not None and nxt.named_children:
                cond_node = cur.child_by_field_name("condition")
                cond_src = (
                    _lower_expression(cond_node.named_children[0], source, ctx)
                    if cond_node and cond_node.named_children else "false"
                )
                else_src = _lower_expression(nxt.named_children[0], source, ctx)
                # if/else lowering: strong-defuzz the condition, extract
                # the truth-axis scalar in [-1, 1] after polarization, and
                # blend the branches:
                #   weight = (1 + truth_axis(defuzzy(cond))) / 2
                #   return weight * X + (1 - weight) * Y
                # Conceptually a 2-option softmax with weights derived
                # from the truth axis. Used instead of `select(scores,
                # options)` because select is built for vector options;
                # for scalar branches it broadcasts incorrectly.
                # Fully-grouped product terms — see the _lower_statement
                # if_statement note: a bare `* ({atom})` emits `* (a) + …`,
                # which the Sutra parser reads as a cast (CastExpr).
                w = f"truth_axis(defuzzy({cond_src}))"
                out_lines.append(
                    f"    return (((1 + {w}) * ({cons_ret})) "
                    f"+ ((1 - {w}) * ({else_src}))) / 2;\n"
                )
                i += 2
                continue
        out_lines.append(_lower_statement(cur, source, ctx))
        i += 1
    return "".join(out_lines)


def _lower_arrow_as_function(
    name: str, arrow_node, source: bytes, ctx: Context,
) -> str:
    """Lower a TS arrow function assigned to a `const` (or `let`) name
    as a Sutra named function declaration. Sutra has no anonymous-
    function surface today, so the user-facing name on the LHS becomes
    the Sutra function's name.

    The arrow's body is either a single expression (`(x) => x * 2`) or
    a statement block (`(x) => { return x * 2; }`); the lowering
    handles both.

    Closure capture: per the user's 2026-05-09 framing, Sutra has no
    closure. Locals referenced inside the arrow body that are NOT the
    arrow's own parameters get lifted to additional parameters here,
    and the call-site lowering threads the captured values through at
    each direct call site (see _lower_expression's call_expression
    branch). The captured names are recorded in ctx.arrow_captures
    keyed by the arrow's emitted Sutra name."""
    params_node = arrow_node.child_by_field_name("parameters")
    return_type_node = arrow_node.child_by_field_name("return_type")
    body_node = arrow_node.child_by_field_name("body")
    return_type = (
        _ts_type_to_sutra(return_type_node, source, ctx)
        if return_type_node else "JavaScriptObject"
    )
    fn_ctx = ctx.child_scope()
    param_parts: list[str] = []
    own_param_names: set[str] = set()
    if params_node is not None:
        for p in params_node.named_children:
            if p.type in ("required_parameter", "optional_parameter"):
                pat = p.child_by_field_name("pattern")
                ann = p.child_by_field_name("type")
                pname = _node_text(pat, source) if pat else "_arg"
                ptype = _ts_type_to_sutra(ann, source, ctx)
                param_parts.append(f"{ptype} {pname}")
                fn_ctx.local_types[pname] = ptype
                own_param_names.add(pname)
            elif p.type == "identifier":
                pname = _node_text(p, source)
                param_parts.append(f"JavaScriptObject {pname}")
                fn_ctx.local_types[pname] = "JavaScriptObject"
                own_param_names.add(pname)
    # Detect closure captures: locals from the enclosing scope that the
    # arrow body references. Lift them to extra params and record the
    # names so call sites can thread the values.
    captured_locals: list[str] = []
    if body_node is not None:
        referenced = _collect_referenced_locals(body_node, source, ctx)
        # ctx.local_types holds enclosing-scope locals (since fn_ctx is
        # a child scope with empty local_types apart from the arrow's
        # own params we just added). Anything in `referenced` that
        # isn't an own-param is a capture.
        for name_ref in sorted(referenced):
            if name_ref in own_param_names:
                continue
            captured_locals.append(name_ref)
    # Add the captures as extra parameters. They keep their original
    # names so the body's references resolve directly.
    for cap in captured_locals:
        cap_type = ctx.local_types.get(cap, "JavaScriptObject")
        param_parts.append(f"{cap_type} {cap}")
        fn_ctx.local_types[cap] = cap_type
    if captured_locals:
        ctx.arrow_captures[name] = captured_locals
    params_src = ", ".join(param_parts)
    if body_node is None:
        body_src = "    return;\n"
    elif body_node.type == "statement_block":
        body_src = _lower_function_body(body_node, source, fn_ctx)
    else:
        # Single-expression arrow: `(x) => x * 2`. Wrap as a return.
        expr_src = _lower_expression(body_node, source, fn_ctx)
        body_src = f"    return {expr_src};\n"
    return f"function {return_type} {name}({params_src}) {{\n{body_src}}}\n"


def _lower_function(node, source: bytes, ctx: Context) -> str:
    name_node = node.child_by_field_name("name")
    params_node = node.child_by_field_name("parameters")
    return_type_node = node.child_by_field_name("return_type")
    body_node = node.child_by_field_name("body")
    name = _node_text(name_node, source) if name_node else "anonymous"
    return_type = _ts_type_to_sutra(return_type_node, source, ctx)
    # `async function` — tree-sitter-typescript emits the `async`
    # keyword as an unnamed leaf child of the function_declaration.
    # When present, prepend `async` to the Sutra output. The Sutra
    # parser recognises `async function` as a function-decl modifier;
    # see planning/sutra-spec/promises.md for the lowering.
    is_async = any(c.type == "async" for c in node.children if not c.is_named)
    async_prefix = "async " if is_async else ""

    fn_ctx = ctx.child_scope()

    param_parts = []
    if params_node is not None:
        for p in params_node.named_children:
            if p.type in ("required_parameter", "optional_parameter"):
                pat = p.child_by_field_name("pattern")
                ann = p.child_by_field_name("type")
                pname = _node_text(pat, source) if pat else "_arg"
                ptype = _ts_type_to_sutra(ann, source, ctx)
                param_parts.append(f"{ptype} {pname}")
                fn_ctx.local_types[pname] = ptype
            elif p.type == "identifier":
                pname = _node_text(p, source)
                param_parts.append(f"JavaScriptObject {pname}")
                fn_ctx.local_types[pname] = "JavaScriptObject"
    params_src = ", ".join(param_parts)
    body_src = _lower_function_body(body_node, source, fn_ctx)
    return f"{async_prefix}function {return_type} {name}({params_src}) {{\n{body_src}}}\n"


def _lower_class_decl(node, source: bytes, ctx: Context) -> str:
    """Lower a TS `class_declaration` to a Sutra class. Per the
    2026-05-08 Sutra-side class work + 2026-05-10 inheritance
    direction, classes use:
        class Name extends JavaScriptObject { field T name; method ... }
    and `new Name(args)` to construct. The JavaScriptObject layer is
    where JS-specific operations (coercive `+`, prototype-chain
    semantics, etc.) live; today it's near-empty, but the inheritance
    placement makes the future surface land cleanly.

    Field discovery:
    - `public_field_definition` → explicit field.
    - Constructor parameter properties (`constructor(public x: T)`) →
      auto-generated field, in the order they appear.
    - Plain constructor params with a `this.x = x;` body whose names
      match field declarations are passed straight through to Sutra's
      auto-`new` factory; the constructor itself is not emitted.

    Methods: regular and static method_definition lower to Sutra
    `method` / `static method`. The constructor's body is not
    emitted as a method (Sutra's `new ClassName(args)` handles
    construction via the field schema)."""
    name_node = node.child_by_field_name("name")
    body_node = node.child_by_field_name("body")
    if name_node is None or body_node is None:
        return "// UNSUPPORTED-CLASS: malformed class_declaration\n"

    class_name = _node_text(name_node, source)

    fields: list[tuple[str, str]] = []  # (name, sutra_type)
    field_names: set[str] = set()
    methods: list[tuple[bool, "tree_sitter.Node"]] = []  # (is_static, node)
    constructor = None

    for member in body_node.named_children:
        if member.type == "public_field_definition":
            fname_node = member.child_by_field_name("name")
            ftype_node = member.child_by_field_name("type")
            if fname_node is None:
                continue
            fname = _node_text(fname_node, source)
            ftype = (
                _ts_type_to_sutra(ftype_node, source, ctx)
                if ftype_node else "JavaScriptObject"
            )
            if fname not in field_names:
                fields.append((fname, ftype))
                field_names.add(fname)
        elif member.type == "method_definition":
            mname_node = member.child_by_field_name("name")
            mname = _node_text(mname_node, source) if mname_node else ""
            if mname == "constructor":
                constructor = member
            else:
                is_static = any(c.type == "static" for c in member.children)
                methods.append((is_static, member))

    # Constructor parameter properties become fields.
    if constructor is not None:
        params_node = constructor.child_by_field_name("parameters")
        if params_node is not None:
            for p in params_node.named_children:
                if p.type != "required_parameter":
                    continue
                has_modifier = any(
                    c.type == "accessibility_modifier"
                    for c in p.named_children
                )
                if not has_modifier:
                    continue
                pat = p.child_by_field_name("pattern")
                ann = p.child_by_field_name("type")
                if pat is None:
                    continue
                pname = _node_text(pat, source)
                ptype = (
                    _ts_type_to_sutra(ann, source, ctx)
                    if ann else "JavaScriptObject"
                )
                if pname not in field_names:
                    fields.append((pname, ptype))
                    field_names.add(pname)

    # TS classes lower to `extends JavaScriptObject` (Emma 2026-05-10):
    # every TS class is conceptually a JS object, so the inheritance
    # chain is `class T extends JavaScriptObject extends vector`. The
    # JavaScriptObject layer is where JS-specific operations (coercive
    # `+`, etc.) will live as they get implemented; today most of that
    # surface is deferred and JavaScriptObject itself is near-empty.
    out = f"class {class_name} extends JavaScriptObject {{\n"
    for fname, ftype in fields:
        out += f"    field {ftype} {fname};\n"
    for is_static, mnode in methods:
        out += _lower_method(mnode, source, ctx, class_name, is_static)
    out += "}\n"
    return out


def _lower_method(
    method_node, source: bytes, ctx: Context, class_name: str, is_static: bool,
) -> str:
    """Lower a TS class method_definition to a Sutra method. Non-static
    methods get `this` registered with the class type so this.field
    reads/writes inside the body use the right axon-machinery
    lowering on the Sutra side."""
    name_node = method_node.child_by_field_name("name")
    params_node = method_node.child_by_field_name("parameters")
    return_type_node = method_node.child_by_field_name("return_type")
    body_node = method_node.child_by_field_name("body")
    name = _node_text(name_node, source) if name_node else "anonymous"
    return_type = (
        _ts_type_to_sutra(return_type_node, source, ctx)
        if return_type_node else "void"
    )

    method_ctx = ctx.child_scope()
    if not is_static:
        method_ctx.local_types["this"] = class_name

    param_parts: list[str] = []
    if params_node is not None:
        for p in params_node.named_children:
            if p.type in ("required_parameter", "optional_parameter"):
                pat = p.child_by_field_name("pattern")
                ann = p.child_by_field_name("type")
                pname = _node_text(pat, source) if pat else "_arg"
                ptype = _ts_type_to_sutra(ann, source, ctx)
                param_parts.append(f"{ptype} {pname}")
                method_ctx.local_types[pname] = ptype
    params_src = ", ".join(param_parts)
    body_src = _lower_function_body(body_node, source, method_ctx)
    static_kw = "static " if is_static else ""
    return (
        f"    {static_kw}method {return_type} {name}({params_src}) {{\n"
        f"{body_src}    }}\n"
    )


def _record_field(ctx: Context, name: str, sutra_type: str) -> None:
    """Record an interface/alias field's Sutra type into the global
    field-type map. On a name collision with a *different* type, mark the
    field non-numeric ("JavaScriptObject") so it won't get a `.real()`
    projection it might not want."""
    prev = ctx.field_types.get(name)
    if prev is None:
        ctx.field_types[name] = sutra_type
    elif prev != sutra_type:
        ctx.field_types[name] = "JavaScriptObject"


def _collect_fields_from_type(node, source: bytes, ctx: Context) -> None:
    """Walk an interface body or a type-alias value (object_type,
    union_type of object_types, …) and record each `property_signature`
    field's Sutra type into ctx.field_types."""
    if node is None:
        return
    t = node.type
    if t in ("interface_body", "object_type"):
        for m in node.named_children:
            if m.type != "property_signature":
                continue
            pid = next(
                (c for c in m.named_children if c.type == "property_identifier"),
                None,
            )
            ann = next(
                (c for c in m.named_children if c.type == "type_annotation"), None
            )
            if pid is None:
                continue
            sutra_t = (
                _ts_type_to_sutra(ann, source, ctx) if ann is not None
                else "JavaScriptObject"
            )
            _record_field(ctx, _node_text(pid, source), sutra_t)
    elif t in ("union_type", "intersection_type", "parenthesized_type"):
        for c in node.named_children:
            _collect_fields_from_type(c, source, ctx)


def _prepass(root, source: bytes, ctx: Context) -> None:
    """Two-phase walk over top-level declarations: phase 1 collects
    interface, type-alias, and class names; phase 2 collects function
    signatures (which depend on knowing which TS type names are
    Axon-shaped vs class-shaped)."""
    # Top-level children may be wrapped in `export_statement` when the
    # source uses ES-module export syntax. Unwrap once so the rest of
    # the prepass treats `export function foo()` identically to plain
    # `function foo()`. Module imports rely on this — an imported file
    # is almost always written with `export` keywords.
    def _unwrap_export(child):
        if child.type != "export_statement":
            return child
        for c in child.named_children:
            if c.type != "comment":
                return c
        return child

    for raw in root.named_children:
        child = _unwrap_export(raw)
        if child.type == "interface_declaration":
            name_node = child.child_by_field_name("name")
            if name_node is not None:
                ctx.interface_names.add(_node_text(name_node, source))
            body = next(
                (c for c in child.named_children if c.type == "interface_body"), None
            )
            _collect_fields_from_type(body, source, ctx)
        elif child.type == "type_alias_declaration":
            name_node = child.child_by_field_name("name")
            if name_node is not None:
                ctx.type_alias_names.add(_node_text(name_node, source))
            value = child.child_by_field_name("value")
            _collect_fields_from_type(value, source, ctx)
        elif child.type == "class_declaration":
            name_node = child.child_by_field_name("name")
            if name_node is not None:
                ctx.class_names.add(_node_text(name_node, source))
        elif child.type == "enum_declaration":
            # First-pass record only: name + per-member integer values.
            # The actual emission of the enum body (or rather, its
            # erasure — Sutra has no `enum` keyword today) happens in
            # the main pass when we reach this node. Recording happens
            # here so any later function-signature reference to the
            # enum type lowers correctly.
            enum_name = None
            body_node = None
            for c in child.named_children:
                if c.type == "identifier":
                    enum_name = _node_text(c, source)
                elif c.type == "enum_body":
                    body_node = c
            if enum_name is None or body_node is None:
                continue
            ctx.enum_names.add(enum_name)
            next_value = 0
            for member in body_node.named_children:
                if member.type == "property_identifier":
                    mname = _node_text(member, source)
                    ctx.enum_member_values[f"{enum_name}.{mname}"] = next_value
                    next_value += 1
                elif member.type == "enum_assignment":
                    mname_node = None
                    val_node = None
                    for mc in member.named_children:
                        if mc.type == "property_identifier":
                            mname_node = mc
                        elif mc.type == "number":
                            val_node = mc
                    if mname_node is None or val_node is None:
                        continue
                    mname = _node_text(mname_node, source)
                    try:
                        val = int(_node_text(val_node, source))
                    except ValueError:
                        continue
                    ctx.enum_member_values[f"{enum_name}.{mname}"] = val
                    next_value = val + 1

    def _register_sig(fn_name: str, params_node) -> None:
        ptypes: list[str] = []
        if params_node is not None:
            for p in params_node.named_children:
                if p.type in ("required_parameter", "optional_parameter"):
                    ann = p.child_by_field_name("type")
                    ptypes.append(_ts_type_to_sutra(ann, source, ctx))
                elif p.type == "identifier":
                    ptypes.append("JavaScriptObject")
        ctx.function_param_types[fn_name] = ptypes

    for raw in root.named_children:
        child = _unwrap_export(raw)
        if child.type == "function_declaration":
            name_node = child.child_by_field_name("name")
            params_node = child.child_by_field_name("parameters")
            if name_node is not None:
                _register_sig(_node_text(name_node, source), params_node)
        elif child.type in ("lexical_declaration", "variable_declaration"):
            # `const name = (args) => body;` — register the arrow's
            # signature under the LHS name so call-site coercion
            # (JavaScriptObject.from(...) wrapping) works.
            for declarator in child.named_children:
                if declarator.type != "variable_declarator":
                    continue
                value_node = declarator.child_by_field_name("value")
                name_node = declarator.child_by_field_name("name")
                if (value_node is not None
                        and value_node.type == "arrow_function"
                        and name_node is not None):
                    params_node = value_node.child_by_field_name("parameters")
                    _register_sig(_node_text(name_node, source), params_node)


def _resolve_import_path(
    specifier: str,
    source_path: pathlib.Path,
) -> Optional[pathlib.Path]:
    """Resolve a TS import specifier (`./helper`, `./util.ts`, etc.)
    against the importing file's path. Returns None if no candidate
    file exists on disk.

    Tries each extension in `_IMPORT_RESOLVE_EXTENSIONS` in order;
    returns the first that resolves. If the specifier already carries
    one of those extensions, that exact path is tried first. Bare
    package specifiers (`react`, `lodash`) — anything that doesn't
    start with `.` or `/` — are not resolved by this MVP.
    """
    if not (specifier.startswith("./") or specifier.startswith("../")
            or specifier.startswith("/")):
        return None
    base = (source_path.parent / specifier).resolve()
    if base.suffix in _IMPORT_RESOLVE_EXTENSIONS and base.exists():
        return base
    for ext in _IMPORT_RESOLVE_EXTENSIONS:
        candidate = base.with_suffix(ext) if base.suffix else pathlib.Path(
            str(base) + ext
        )
        if candidate.exists():
            return candidate
    return None


def _lower_import_module(
    resolved_path: pathlib.Path,
    imported: set[pathlib.Path],
) -> str:
    """Recursively lower a `.ts` / `.tsx` import target, or read a
    `.su` import target raw, returning the body to inline at the top
    of the importing file's output.

    `imported` is the visited-set used for diamond-import dedup. The
    caller adds `resolved_path` before calling so this function never
    re-enters the same file."""
    text = resolved_path.read_text(encoding="utf-8")
    suffix = resolved_path.suffix
    if suffix in (".ts", ".tsx"):
        # Recursive call: the imported module may itself import other
        # files, so it gets its own lowering pass with the same
        # imported-set so we don't re-inline shared targets.
        return lower(text, source_path=resolved_path, _imported=imported)
    if suffix == ".su":
        # Already-Sutra: pass through as-is. Comments at the top of
        # the imported .su file survive into the output.
        return text
    return f"// UNSUPPORTED-IMPORT-EXTENSION: {suffix}\n"


def _strip_generated_header(lowered: str) -> str:
    """Strip the `// Generated by sutra-from-ts. …` four-line header
    that `lower()` emits at the top of every output. Inlining an
    imported module shouldn't repeat the header inside the importing
    file — only the outermost call should carry it."""
    lines = lowered.splitlines(keepends=True)
    out = []
    skipping = True
    for line in lines:
        if skipping and (line.startswith("// Generated by sutra-from-ts")
                         or line.startswith("// Note: JavaScriptObject")
                         or line.startswith("// could not be resolved")
                         or line.startswith("// stdlib piece.")
                         or line.strip() == ""):
            continue
        skipping = False
        out.append(line)
    return "".join(out)


def lower(
    source: str,
    source_path: Optional[pathlib.Path] = None,
    _imported: Optional[set[pathlib.Path]] = None,
) -> str:
    """Top-level entry point. Source string -> Sutra source string.

    `source_path` is the on-disk path of `source`. Optional — when None,
    `import { … } from "./x"` statements lower to an UNSUPPORTED comment
    (no file to resolve against). When set, relative imports resolve
    against `source_path.parent`, the imported file is recursively
    lowered, and its declarations are inlined at the top of the output
    bracketed by `// --- begin module: <spec> ---` markers.

    `_imported` is the recursive-call accumulator for diamond-import
    dedup. Callers normally pass None; the recursive `_lower_import_module`
    threads the set through subsequent `lower()` calls so a module
    imported by two different files lands inlined exactly once.
    """
    import tree_sitter
    import tree_sitter_typescript
    lang = tree_sitter.Language(tree_sitter_typescript.language_typescript())
    parser = tree_sitter.Parser(lang)
    src_bytes = source.encode("utf-8")
    tree = parser.parse(src_bytes)

    if _imported is None:
        _imported = set()
        if source_path is not None:
            _imported.add(source_path.resolve())

    ctx = Context()
    _prepass(tree.root_node, src_bytes, ctx)

    is_recursive_call = source_path is not None and len(_imported) > 1
    out_parts: list[str] = []
    if not is_recursive_call:
        out_parts.extend([
            "// Generated by sutra-from-ts. See sdk/sutra-from-ts/DESIGN.md.\n",
            "// Note: JavaScriptObject is referenced in places where a TS type\n",
            "// could not be resolved; the class itself is a deferred Sutra\n",
            "// stdlib piece. Programs that hit it won't run end-to-end yet.\n",
            "\n",
        ])

    def _flush_extras() -> None:
        if ctx.extras:
            out_parts.extend(ctx.extras)
            ctx.extras.clear()

    # Top-level children come in source order, but imports must inline
    # BEFORE the importing file's own declarations so call sites resolve
    # the imported names. Two-pass: imports first, then the rest.
    children = list(tree.root_node.named_children)
    for child in children:
        if child.type != "import_statement":
            continue
        source_node = child.child_by_field_name("source")
        if source_node is None:
            # Some grammars name it differently; fall through to manual
            # search for the `string` child.
            for c in child.named_children:
                if c.type == "string":
                    source_node = c
                    break
        if source_node is None:
            out_parts.append(
                "// UNSUPPORTED-IMPORT: no string source on import_statement\n"
            )
            continue
        # The string node has a `string_fragment` child carrying the
        # bare specifier without quotes.
        spec_text = None
        for c in source_node.named_children:
            if c.type == "string_fragment":
                spec_text = _node_text(c, src_bytes)
                break
        if spec_text is None:
            out_parts.append(
                "// UNSUPPORTED-IMPORT: empty import specifier\n"
            )
            continue
        if source_path is None:
            out_parts.append(
                f"// UNSUPPORTED-IMPORT: cannot resolve {spec_text!r} "
                "without a source path (lower() called on a string with "
                "no source_path=)\n"
            )
            continue
        resolved = _resolve_import_path(spec_text, source_path)
        if resolved is None:
            out_parts.append(
                f"// UNSUPPORTED-IMPORT: could not resolve {spec_text!r} "
                f"relative to {source_path.parent}\n"
            )
            continue
        if resolved in _imported:
            # Diamond import: already inlined upstream, skip.
            continue
        _imported.add(resolved)
        body = _lower_import_module(resolved, _imported)
        body = _strip_generated_header(body)
        out_parts.append(f"// --- begin module: {spec_text} ---\n")
        out_parts.append(body)
        if not body.endswith("\n"):
            out_parts.append("\n")
        out_parts.append(f"// --- end module: {spec_text} ---\n")
        out_parts.append("\n")

    for child in children:
        # `export function foo() {…}` parses as `export_statement`
        # containing the inner declaration. Unwrap so the existing
        # dispatch handles it the same as a non-exported decl. The MVP
        # does not track which names are exported — every declaration
        # in an imported file is inlined regardless.
        if child.type == "export_statement":
            inner = None
            for c in child.named_children:
                if c.type != "comment":
                    inner = c
                    break
            if inner is None:
                continue
            child = inner
        if child.type == "import_statement":
            # Already handled in the pre-pass above.
            continue
        if child.type == "function_declaration":
            fn_src = _lower_function(child, src_bytes, ctx)
            # Loop-hoist extras emit into ctx.extras during lowering;
            # surface them at module scope just before the function
            # decl that referenced them so call sites see them.
            _flush_extras()
            out_parts.append(fn_src)
        elif child.type == "class_declaration":
            cls_src = _lower_class_decl(child, src_bytes, ctx)
            _flush_extras()
            out_parts.append(cls_src)
        elif child.type in ("interface_declaration", "type_alias_declaration"):
            # Erased — only effect was registering the name as Axon-shaped
            # in the pre-pass.
            pass
        elif child.type == "enum_declaration":
            # Erased — the prepass already collected member values into
            # ctx.enum_member_values. Every `EnumName.Member` reference
            # in expression position lowers to the recorded integer
            # literal. The enum itself emits nothing.
            pass
        elif child.type == "comment":
            pass
        elif child.type in ("lexical_declaration", "variable_declaration"):
            # Top-level `const name = (args) => body;` and equivalents
            # hoist to a Sutra function declaration. Sutra has no
            # anonymous-function surface today, so the LHS name on the
            # const becomes the Sutra function's name.
            arrow_emitted = False
            for declarator in child.named_children:
                if declarator.type != "variable_declarator":
                    continue
                value_node = declarator.child_by_field_name("value")
                name_node = declarator.child_by_field_name("name")
                if (value_node is not None
                        and value_node.type == "arrow_function"
                        and name_node is not None):
                    fn_name = _node_text(name_node, src_bytes)
                    fn_src = _lower_arrow_as_function(
                        fn_name, value_node, src_bytes, ctx
                    )
                    _flush_extras()
                    out_parts.append(fn_src)
                    arrow_emitted = True
            if not arrow_emitted:
                out_parts.append(
                    f"// UNSUPPORTED-TOP-LEVEL: {child.type} "
                    f"(non-arrow init at module scope is not yet wired)\n"
                )
        else:
            out_parts.append(f"// UNSUPPORTED-TOP-LEVEL: {child.type}\n")
    return "".join(out_parts)
