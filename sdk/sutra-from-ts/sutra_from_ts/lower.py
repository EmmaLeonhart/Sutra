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

from dataclasses import dataclass, field
from typing import Optional


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
    function_param_types: dict[str, list[str]] = field(default_factory=dict)
    local_types: dict[str, str] = field(default_factory=dict)
    extras: list[str] = field(default_factory=list)
    loop_counter: list[int] = field(default_factory=lambda: [0])

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
            function_param_types=self.function_param_types,
            local_types={},
            extras=self.extras,
            loop_counter=self.loop_counter,
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
        return name
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
                return f"JavaScriptObject.add({left_src}, {right_src})"
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
        if func is not None and func.type == "identifier":
            callee_param_types = ctx.function_param_types.get(_node_text(func, source))
        arg_nodes = list(args_node.named_children) if args_node else []
        arg_srcs = []
        for i, a in enumerate(arg_nodes):
            arg_src = _lower_expression(a, source, ctx)
            if (callee_param_types is not None
                    and i < len(callee_param_types)
                    and callee_param_types[i] == "JavaScriptObject"
                    and a.type in ("number", "string", "true", "false")):
                arg_src = f"JavaScriptObject.from({arg_src})"
            arg_srcs.append(arg_src)
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
        obj_src = _lower_expression(obj, source, ctx)
        prop_text = _node_text(prop, source) if prop is not None else ""
        obj_t = _expr_type(obj, source, ctx) if obj is not None else None
        if obj_t == "Axon":
            return f'{obj_src}.item("{prop_text}")'
        _PROPERTY_TO_METHOD = {
            "length": "string_length",
        }
        if prop_text in _PROPERTY_TO_METHOD:
            return f"{obj_src}.{_PROPERTY_TO_METHOD[prop_text]}()"
        return f"{obj_src}.{prop_text}"
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
        if alt is not None:
            alt_src = _lower_branch_result(alt, source, ctx)
            return (
                f"{indent}return ((1 + truth_axis(defuzzy({cond_src}))) "
                f"* ({cons_src}) + (1 - truth_axis(defuzzy({cond_src}))) "
                f"* ({alt_src})) / 2;\n"
            )
        return f"{indent}// UNSUPPORTED-STMT: if without else; place a `return` after the if\n"
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
                out_lines.append(
                    f"    return ((1 + truth_axis(defuzzy({cond_src}))) "
                    f"* ({cons_ret}) + (1 - truth_axis(defuzzy({cond_src}))) "
                    f"* ({else_src})) / 2;\n"
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
    handles both."""
    params_node = arrow_node.child_by_field_name("parameters")
    return_type_node = arrow_node.child_by_field_name("return_type")
    body_node = arrow_node.child_by_field_name("body")
    return_type = (
        _ts_type_to_sutra(return_type_node, source, ctx)
        if return_type_node else "JavaScriptObject"
    )
    fn_ctx = ctx.child_scope()
    param_parts: list[str] = []
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
    return f"function {return_type} {name}({params_src}) {{\n{body_src}}}\n"


def _lower_class_decl(node, source: bytes, ctx: Context) -> str:
    """Lower a TS `class_declaration` to a Sutra class. Per the
    2026-05-08 Sutra-side class work, classes use:
        class Name extends vector { field T name; method ... }
    and `new Name(args)` to construct.

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

    out = f"class {class_name} extends vector {{\n"
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


def _prepass(root, source: bytes, ctx: Context) -> None:
    """Two-phase walk over top-level declarations: phase 1 collects
    interface, type-alias, and class names; phase 2 collects function
    signatures (which depend on knowing which TS type names are
    Axon-shaped vs class-shaped)."""
    for child in root.named_children:
        if child.type == "interface_declaration":
            name_node = child.child_by_field_name("name")
            if name_node is not None:
                ctx.interface_names.add(_node_text(name_node, source))
        elif child.type == "type_alias_declaration":
            name_node = child.child_by_field_name("name")
            if name_node is not None:
                ctx.type_alias_names.add(_node_text(name_node, source))
        elif child.type == "class_declaration":
            name_node = child.child_by_field_name("name")
            if name_node is not None:
                ctx.class_names.add(_node_text(name_node, source))

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

    for child in root.named_children:
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


def lower(source: str) -> str:
    """Top-level entry point. Source string -> Sutra source string."""
    import tree_sitter
    import tree_sitter_typescript
    lang = tree_sitter.Language(tree_sitter_typescript.language_typescript())
    parser = tree_sitter.Parser(lang)
    src_bytes = source.encode("utf-8")
    tree = parser.parse(src_bytes)

    ctx = Context()
    _prepass(tree.root_node, src_bytes, ctx)

    out_parts = [
        "// Generated by sutra-from-ts. See sdk/sutra-from-ts/DESIGN.md.\n",
        "// Note: JavaScriptObject is referenced in places where a TS type\n",
        "// could not be resolved; the class itself is a deferred Sutra\n",
        "// stdlib piece. Programs that hit it won't run end-to-end yet.\n",
        "\n",
    ]
    def _flush_extras() -> None:
        if ctx.extras:
            out_parts.extend(ctx.extras)
            ctx.extras.clear()

    for child in tree.root_node.named_children:
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
