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
        # `if (cond) X else Y` lowers to a select over a strongly
        # defuzzified condition: `select(is_true(cond), X, Y)`. Sutra
        # has no statement-form `if` — it's expression-form only —
        # so the branches need to produce values. The two patterns
        # we recognize:
        #   1. if-then-else, both branches `return <expr>;`
        #   2. if-then with no else, treated by the function-body
        #      rewrite below: the next statement after the if is
        #      taken as the implicit else.
        cond = node.child_by_field_name("condition")
        cons = node.child_by_field_name("consequence")
        alt = node.child_by_field_name("alternative")
        cond_src = _lower_expression(cond.named_children[0], source) if cond else "false"
        cons_src = _lower_branch_result(cons, source)
        if alt is not None:
            alt_src = _lower_branch_result(alt, source)
            return (
                f"{indent}return ((1 + truth_axis(defuzzy({cond_src}))) "
                f"* ({cons_src}) + (1 - truth_axis(defuzzy({cond_src}))) "
                f"* ({alt_src})) / 2;\n"
            )
        # if-only — left as-is here; the function-body rewrite at
        # _lower_function_body merges this with the trailing return.
        # If we're not inside such a body, flag explicitly.
        return f"{indent}// UNSUPPORTED-STMT: if without else; place a `return` after the if\n"
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


def _lower_function_body(body_node, source: bytes) -> str:
    """Lower a statement_block as a function body. Recognizes the
    if-then-(implicit-else) pattern:

        if (cond) return X;
        return Y;

    and rewrites it to `return select(is_true(cond), X, Y);` — the
    user's "strong defuzz then select" rule for `if/else`. Without
    the rewrite, Sutra has no idiomatic way to express conditional
    returns (the language is expression-form, no statement-form
    `if`).

    Statement order in JS is meaningful: the rewrite is only safe
    when both branches are pure expressions. If a branch has side
    effects, the rewrite changes semantics (Sutra's `select`
    evaluates BOTH arms eagerly). For the demo subset that's fine;
    the limitation is documented.
    """
    if body_node is None or body_node.type != "statement_block":
        return _lower_statement(body_node, source) if body_node else ""
    stmts = list(body_node.named_children)
    # Pattern: [if_stmt(no-alt, return X), return Y] — possibly with
    # other statements before. We only rewrite when an if-with-no-alt
    # is immediately followed by a return.
    out_lines = []
    i = 0
    while i < len(stmts):
        cur = stmts[i]
        nxt = stmts[i + 1] if i + 1 < len(stmts) else None
        if (cur.type == "if_statement"
                and cur.child_by_field_name("alternative") is None
                and nxt is not None
                and nxt.type == "return_statement"):
            # Check the consequence is a single return.
            cons = cur.child_by_field_name("consequence")
            cons_ret = _branch_return_expr(cons, source)
            if cons_ret is not None and nxt.named_children:
                cond_node = cur.child_by_field_name("condition")
                cond_src = (
                    _lower_expression(cond_node.named_children[0], source)
                    if cond_node else "false"
                )
                else_src = _lower_expression(nxt.named_children[0], source)
                # if/else lowering: strong-defuzz the condition,
                # extract the truth-axis scalar (in [-1, 1] after
                # polarization), and blend the branches:
                #   weight = (1 + truth_axis(defuzzy(cond))) / 2
                #   return weight * X + (1 - weight) * Y
                # Conceptually identical to a 2-option softmax with
                # weights derived from the truth axis. Used instead of
                # `select(scores, options)` because select is built for
                # vector options — for scalar branches it broadcasts
                # incorrectly. The linear-blend form works for both
                # scalar and vector branches via PyTorch broadcasting.
                out_lines.append(
                    f"    return ((1 + truth_axis(defuzzy({cond_src}))) "
                    f"* ({cons_ret}) + (1 - truth_axis(defuzzy({cond_src}))) "
                    f"* ({else_src})) / 2;\n"
                )
                # Consume both statements.
                i += 2
                continue
        out_lines.append(_lower_statement(cur, source))
        i += 1
    return "".join(out_lines)


def _branch_return_expr(node, source: bytes) -> Optional[str]:
    """If `node` is a `return <expr>;` (or a block whose only stmt is
    such a return), return the lowered expression source. Else return
    None — meaning the branch isn't a single value-returning return."""
    if node is None:
        return None
    if node.type == "return_statement":
        if node.named_children:
            return _lower_expression(node.named_children[0], source)
        return None
    if node.type == "statement_block" and len(node.named_children) == 1:
        return _branch_return_expr(node.named_children[0], source)
    return None


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
    body_src = _lower_function_body(body_node, source)
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
