"""Minimal JS / TS → Sutra lowering pass.

Walks a tree-sitter parse tree and emits Sutra (.su) source. Scope
is intentionally tiny for the first cut: function declarations,
parameters with simple types, return statements, number / string /
boolean literals, basic binary operators, identifier references.

Anything outside this scope falls through to a `// UNSUPPORTED:
<node-type>` comment in the output, so the caller can see what
features blocked translation. This is by design — see DESIGN.md
for the full intended scope.
"""

from __future__ import annotations

from typing import Optional


_TS_TO_SUTRA_TYPE = {
    "number": "int",      # default; float-vs-int inference is future work
    "string": "String",
    "boolean": "bool",
    "void": "void",
    "any": "JavaScriptObject",
    "unknown": "JavaScriptObject",
}


def _node_text(node, source: bytes) -> str:
    return source[node.start_byte:node.end_byte].decode("utf-8")


def _child_named(node, kind: str):
    for c in node.named_children:
        if c.type == kind:
            return c
    return None


def _children_named(node, kind: str):
    return [c for c in node.named_children if c.type == kind]


def _ts_type_to_sutra(annotation_node, source: bytes) -> str:
    """Given a `type_annotation` node, return the Sutra type name."""
    if annotation_node is None:
        return "JavaScriptObject"
    inner = annotation_node.named_children[0] if annotation_node.named_children else None
    if inner is None:
        return "JavaScriptObject"
    if inner.type == "predefined_type":
        text = _node_text(inner, source)
        return _TS_TO_SUTRA_TYPE.get(text, "JavaScriptObject")
    if inner.type == "type_identifier":
        return _node_text(inner, source)
    return "JavaScriptObject"


def _lower_expression(node, source: bytes) -> str:
    if node.type == "number":
        return _node_text(node, source)
    if node.type == "string":
        # `"hello"` -> wrap in String.make_string per the deferred-string
        # rule from DESIGN.md.
        text = _node_text(node, source)
        return f"String.make_string({text})"
    if node.type == "true":
        return "true"
    if node.type == "false":
        return "false"
    if node.type == "identifier":
        return _node_text(node, source)
    if node.type == "binary_expression":
        # Children: left, operator, right (the operator is between
        # named children but accessible as a string field too).
        left = node.child_by_field_name("left")
        right = node.child_by_field_name("right")
        op = node.child_by_field_name("operator")
        op_text = _node_text(op, source) if op is not None else "+"
        # JS `===` and `!==` map to Sutra `==` / `!=`. Sutra is fuzzy,
        # so strict / loose equality collapse here.
        op_text = {"===": "==", "!==": "!="}.get(op_text, op_text)
        return f"({_lower_expression(left, source)} {op_text} {_lower_expression(right, source)})"
    if node.type == "unary_expression":
        op = node.child_by_field_name("operator")
        arg = node.child_by_field_name("argument")
        op_text = _node_text(op, source) if op is not None else "-"
        return f"({op_text}{_lower_expression(arg, source)})"
    if node.type == "parenthesized_expression":
        inner = node.named_children[0]
        return _lower_expression(inner, source)
    if node.type == "call_expression":
        func = node.child_by_field_name("function")
        args_node = node.child_by_field_name("arguments")
        func_src = _lower_expression(func, source)
        arg_srcs = [
            _lower_expression(a, source)
            for a in (args_node.named_children if args_node else [])
        ]
        return f"{func_src}({', '.join(arg_srcs)})"
    if node.type == "member_expression":
        obj = node.child_by_field_name("object")
        prop = node.child_by_field_name("property")
        obj_src = _lower_expression(obj, source)
        prop_text = _node_text(prop, source) if prop is not None else ""
        # JS / TS property accesses that have a Sutra-side method
        # equivalent. `.length` on a string is the most common one;
        # add more here as needed.
        _PROPERTY_TO_METHOD = {
            "length": "string_length",
        }
        if prop_text in _PROPERTY_TO_METHOD:
            return f"{obj_src}.{_PROPERTY_TO_METHOD[prop_text]}()"
        return f"{obj_src}.{prop_text}"
    return f"/* UNSUPPORTED-EXPR: {node.type} */"


def _lower_statement(node, source: bytes, indent: str = "    ") -> str:
    if node.type == "return_statement":
        # `return <expr>;`
        if node.named_children:
            expr_node = node.named_children[0]
            return f"{indent}return {_lower_expression(expr_node, source)};\n"
        return f"{indent}return;\n"
    if node.type == "expression_statement":
        inner = node.named_children[0] if node.named_children else None
        if inner is None:
            return ""
        return f"{indent}{_lower_expression(inner, source)};\n"
    if node.type == "if_statement":
        cond = node.child_by_field_name("condition")
        cons = node.child_by_field_name("consequence")
        alt = node.child_by_field_name("alternative")
        # `if (x) y else z` -> `select(x, y, z)`. For simple
        # value-returning branches this lowers cleanly. Statement-
        # block consequents need return statements inside; we lift
        # them into the branch result.
        cond_src = _lower_expression(cond.named_children[0], source) if cond else "false"
        cons_src = _lower_branch_result(cons, source)
        if alt is not None:
            alt_src = _lower_branch_result(alt, source)
            return f"{indent}return select({cond_src}, {cons_src}, {alt_src});\n"
        return f"{indent}if ({cond_src}) {{ return {cons_src}; }}\n"
    if node.type == "statement_block":
        out = ""
        for child in node.named_children:
            out += _lower_statement(child, source, indent)
        return out
    return f"{indent}// UNSUPPORTED-STMT: {node.type}\n"


def _lower_branch_result(node, source: bytes) -> str:
    """For `if/else` branches: extract the value the branch produces.
    A statement block whose only statement is `return <expr>;` lowers
    to `<expr>`.
    """
    if node.type == "statement_block":
        if len(node.named_children) == 1:
            inner = node.named_children[0]
            if inner.type == "return_statement" and inner.named_children:
                return _lower_expression(inner.named_children[0], source)
    if node.type == "return_statement" and node.named_children:
        return _lower_expression(node.named_children[0], source)
    return _lower_expression(node, source)


def _lower_function(node, source: bytes) -> str:
    name_node = node.child_by_field_name("name")
    params_node = node.child_by_field_name("parameters")
    return_type_node = node.child_by_field_name("return_type")
    body_node = node.child_by_field_name("body")
    name = _node_text(name_node, source) if name_node else "anonymous"
    return_type = _ts_type_to_sutra(return_type_node, source)
    param_parts = []
    if params_node is not None:
        for p in params_node.named_children:
            if p.type in ("required_parameter", "optional_parameter"):
                pat = p.child_by_field_name("pattern")
                ann = p.child_by_field_name("type")
                pname = _node_text(pat, source) if pat else "_arg"
                ptype = _ts_type_to_sutra(ann, source)
                param_parts.append(f"{ptype} {pname}")
            elif p.type == "identifier":
                # Untyped JS parameter
                pname = _node_text(p, source)
                param_parts.append(f"JavaScriptObject {pname}")
    params_src = ", ".join(param_parts)
    body_src = _lower_statement(body_node, source) if body_node is not None else ""
    return f"function {return_type} {name}({params_src}) {{\n{body_src}}}\n"


def lower(source: str) -> str:
    """Top-level entry point. Source string -> Sutra source string."""
    import tree_sitter
    import tree_sitter_typescript
    lang = tree_sitter.Language(tree_sitter_typescript.language_typescript())
    parser = tree_sitter.Parser(lang)
    src_bytes = source.encode("utf-8")
    tree = parser.parse(src_bytes)
    out_parts = [
        "// Generated by sutra-from-ts. See sdk/sutra-from-ts/DESIGN.md.\n",
        "// Note: JavaScriptObject is referenced in places where a TS type\n",
        "// could not be resolved; the class itself is a deferred Sutra\n",
        "// stdlib piece. Programs that hit it won't run end-to-end yet.\n",
        "\n",
    ]
    for child in tree.root_node.named_children:
        if child.type == "function_declaration":
            out_parts.append(_lower_function(child, src_bytes))
        else:
            out_parts.append(f"// UNSUPPORTED-TOP-LEVEL: {child.type}\n")
    return "".join(out_parts)
