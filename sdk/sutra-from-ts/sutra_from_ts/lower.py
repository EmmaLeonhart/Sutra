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
    "this name is Axon-shaped." `function_param_types` is a name → list-
    of-Sutra-types map for resolving call-site coercions. `local_types`
    is updated as the main pass walks function bodies.
    """

    interface_names: set[str] = field(default_factory=set)
    type_alias_names: set[str] = field(default_factory=set)
    function_param_types: dict[str, list[str]] = field(default_factory=dict)
    local_types: dict[str, str] = field(default_factory=dict)

    def is_axon_typed(self, type_name: str) -> bool:
        return (
            type_name in self.interface_names
            or type_name in self.type_alias_names
        )

    def lookup_local(self, name: str) -> Optional[str]:
        return self.local_types.get(name)

    def child_scope(self) -> "Context":
        """Return a context with the same global state and a fresh local
        scope."""
        return Context(
            interface_names=self.interface_names,
            type_alias_names=self.type_alias_names,
            function_param_types=self.function_param_types,
            local_types={},
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
        cond = node.child_by_field_name("condition")
        body = node.child_by_field_name("body")
        cond_inner = (
            cond.named_children[0]
            if cond and cond.named_children else None
        )
        cond_src = (
            _lower_expression(cond_inner, source, ctx)
            if cond_inner else "false"
        )
        body_src = _lower_statement(body, source, ctx, indent + "    ") if body else ""
        return f"{indent}while ({cond_src}) {{\n{body_src}{indent}}}\n"
    if node.type == "for_statement":
        # Desugar `for (init; cond; incr) body` → `init; while (cond) {
        # body; incr; }`. This lets us reuse the while-loop lowering and
        # the existing initializer / increment lowerings without a
        # separate for-form on the Sutra side. Tradeoff: a `continue` in
        # the body would skip the increment with this desugar, but
        # `continue` isn't supported yet anyway.
        init = node.child_by_field_name("initializer")
        cond = node.child_by_field_name("condition")
        incr = node.child_by_field_name("increment")
        body = node.child_by_field_name("body")
        out = ""
        if init is not None:
            if init.type in ("lexical_declaration", "variable_declaration"):
                out += _lower_lexical_declaration(init, source, ctx, indent)
            else:
                out += f"{indent}{_lower_expression(init, source, ctx)};\n"
        cond_src = _lower_expression(cond, source, ctx) if cond else "true"
        body_src = (
            _lower_statement(body, source, ctx, indent + "    ")
            if body else ""
        )
        incr_src = (
            f"{indent}    {_lower_expression(incr, source, ctx)};\n"
            if incr is not None else ""
        )
        out += f"{indent}while ({cond_src}) {{\n{body_src}{incr_src}{indent}}}\n"
        return out
    if node.type == "do_statement":
        body = node.child_by_field_name("body")
        cond = node.child_by_field_name("condition")
        cond_inner = (
            cond.named_children[0]
            if cond and cond.named_children else None
        )
        cond_src = (
            _lower_expression(cond_inner, source, ctx)
            if cond_inner else "false"
        )
        body_src = _lower_statement(body, source, ctx, indent + "    ") if body else ""
        return f"{indent}do {{\n{body_src}{indent}}} while ({cond_src});\n"
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


def _prepass(root, source: bytes, ctx: Context) -> None:
    """Two-phase walk over top-level declarations: phase 1 collects
    interface and type-alias names, phase 2 collects function signatures
    (which depend on knowing which TS type names are Axon-shaped)."""
    for child in root.named_children:
        if child.type == "interface_declaration":
            name_node = child.child_by_field_name("name")
            if name_node is not None:
                ctx.interface_names.add(_node_text(name_node, source))
        elif child.type == "type_alias_declaration":
            name_node = child.child_by_field_name("name")
            if name_node is not None:
                ctx.type_alias_names.add(_node_text(name_node, source))

    for child in root.named_children:
        if child.type == "function_declaration":
            name_node = child.child_by_field_name("name")
            params_node = child.child_by_field_name("parameters")
            if name_node is None or params_node is None:
                continue
            name = _node_text(name_node, source)
            ptypes = []
            for p in params_node.named_children:
                if p.type in ("required_parameter", "optional_parameter"):
                    ann = p.child_by_field_name("type")
                    ptypes.append(_ts_type_to_sutra(ann, source, ctx))
                elif p.type == "identifier":
                    ptypes.append("JavaScriptObject")
            ctx.function_param_types[name] = ptypes


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
    for child in tree.root_node.named_children:
        if child.type == "function_declaration":
            out_parts.append(_lower_function(child, src_bytes, ctx))
        elif child.type in ("interface_declaration", "type_alias_declaration"):
            # Erased — only effect was registering the name as Axon-shaped
            # in the pre-pass.
            pass
        elif child.type == "comment":
            pass
        else:
            out_parts.append(f"// UNSUPPORTED-TOP-LEVEL: {child.type}\n")
    return "".join(out_parts)
