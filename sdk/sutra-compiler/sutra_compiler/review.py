"""Review mode — language-level trace of parsing + algebraic simplification.

Run as:

    python sutrac.py --review FILE.su

This mode is about seeing how the compiler understands your program
at the language level — how it parses, how it simplifies. It does
NOT show the emitted Python/PyTorch code (that's downstream codegen
boilerplate and not the interesting thing); use `--emit` if you
want that separately.

Stages shown:

  1. Source              — the .su source you wrote.
  2. Parsing             — Sutra text -> abstract syntax tree,
                           pretty-printed back as pseudo-Sutra.
  3. Stdlib inlining     — stdlib function bodies copied in-place.
  4. Simplification      — each rewrite rule that fired + before/after.

Stages that do nothing (e.g. inlining on a program with no stdlib
calls) are collapsed to one line instead of re-dumping the whole AST,
so the output focuses on what actually changed.

The headline stage is #4 — the simplification trace. That's where
you see which of the 16 algebraic rewrites touched your program and
what they turned your expressions into. If no rewrites fired, the
trace says so explicitly and points at `examples/review_demo.su` as
a sample program that does trigger several.
"""
from __future__ import annotations

import os
import sys
from typing import List, Tuple

from . import ast_nodes as ast
from .lexer import Lexer
from .parser import Parser
from .simplify import set_trace_callback, simplify_module
from .inliner import inline_stdlib_calls


# ---------------------------------------------------------------------
# Pretty-printer — emit a pseudo-Sutra-source form of the AST
# ---------------------------------------------------------------------


def pretty_expr(node) -> str:
    if node is None:
        return "<none>"
    if isinstance(node, ast.Identifier):
        return node.name
    if isinstance(node, ast.IntLiteral):
        return str(node.value)
    if isinstance(node, ast.FloatLiteral):
        return f"{node.value!r}"
    if isinstance(node, ast.BoolLiteral):
        return "true" if node.value else "false"
    if isinstance(node, ast.StringLiteral):
        return f'"{node.value}"'
    if isinstance(node, ast.CharLiteral):
        return f"'{chr(node.value)}'"
    if isinstance(node, ast.ImaginaryLiteral):
        return f"{node.value}i"
    if isinstance(node, ast.ComplexLiteral):
        return f"({node.re} + {node.im}i)"
    if hasattr(ast, "UnknownLiteral") and isinstance(node, ast.UnknownLiteral):
        return "unknown"
    if isinstance(node, ast.Parenthesized):
        return f"({pretty_expr(node.inner)})"
    if isinstance(node, ast.UnaryOp):
        return f"{node.op}{pretty_expr(node.operand)}"
    if isinstance(node, ast.BinaryOp):
        return f"{pretty_expr(node.left)} {node.op} {pretty_expr(node.right)}"
    if isinstance(node, ast.Call):
        callee = (node.callee.name
                  if isinstance(node.callee, ast.Identifier)
                  else pretty_expr(node.callee))
        args = ", ".join(pretty_expr(a) for a in node.args)
        return f"{callee}({args})"
    if isinstance(node, ast.ArrayLiteral):
        return "[" + ", ".join(pretty_expr(e) for e in node.elements) + "]"
    if isinstance(node, ast.Subscript):
        return f"{pretty_expr(node.target)}[{pretty_expr(node.index)}]"
    if isinstance(node, ast.MemberAccess):
        return f"{pretty_expr(node.obj)}.{node.member}"
    if isinstance(node, ast.EmbedExpr):
        return f"embed({pretty_expr(node.expr)})"
    if isinstance(node, ast.DefuzzyExpr):
        return f"defuzzy({pretty_expr(node.expr)})"
    return f"<{type(node).__name__}>"


def pretty_stmt(stmt, indent: int = 0) -> List[str]:
    pad = "  " * indent
    if isinstance(stmt, ast.VarDecl):
        type_str = f"{stmt.type_ref.name} " if stmt.type_ref else "var "
        init = f" = {pretty_expr(stmt.initializer)}" if stmt.initializer else ""
        return [f"{pad}{type_str}{stmt.name}{init};"]
    if isinstance(stmt, ast.ReturnStmt):
        return [f"{pad}return {pretty_expr(stmt.value)};"]
    if isinstance(stmt, ast.ExprStmt):
        return [f"{pad}{pretty_expr(stmt.expr)};"]
    if isinstance(stmt, ast.FunctionDecl):
        ret = stmt.return_type.name if stmt.return_type else "void"
        params = ", ".join(
            f"{p.type_ref.name if p.type_ref else 'var'} {p.name}"
            for p in (stmt.params or [])
        )
        lines = [f"{pad}function {ret} {stmt.name}({params}) {{"]
        for s in stmt.body.statements:
            lines.extend(pretty_stmt(s, indent + 1))
        lines.append(f"{pad}}}")
        return lines
    if isinstance(stmt, ast.IfStmt):
        lines = [f"{pad}if ({pretty_expr(stmt.condition)}) {{"]
        for s in stmt.then_branch.statements:
            lines.extend(pretty_stmt(s, indent + 1))
        lines.append(f"{pad}}}")
        return lines
    return [f"{pad}<{type(stmt).__name__}>"]


def pretty_module(module: ast.Module) -> str:
    """One line per statement — keep it compact so diffs read cleanly."""
    out: List[str] = []
    for item in module.items:
        out.extend(pretty_stmt(item))
    return "\n".join(out)


# ---------------------------------------------------------------------
# Trace collector
# ---------------------------------------------------------------------


class _TraceCollector:
    def __init__(self):
        self.events: List[Tuple[str, str, str]] = []

    def __call__(self, rule: str, before, after) -> None:
        self.events.append(
            (rule, pretty_expr(before), pretty_expr(after))
        )


# ---------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------


RULE_BAR = "=" * 72
SUB_BAR = "-" * 72


def _heading(num: int, title: str, explainer: str) -> str:
    """Numbered heading + a one-line explainer of what this section is."""
    return (f"\n{RULE_BAR}\n"
            f"Stage {num}: {title}\n"
            f"{SUB_BAR}\n"
            f"  {explainer}")


def _compare(before: str, after: str) -> str:
    """One-line description of whether two stages differ."""
    if before == after:
        return "(no change from previous stage)"
    n_before = before.count("\n") + 1
    n_after = after.count("\n") + 1
    delta = n_after - n_before
    sign = "+" if delta >= 0 else ""
    return f"(changed: {sign}{delta} lines vs previous stage)"


# ---------------------------------------------------------------------
# Review entry point
# ---------------------------------------------------------------------


def review_file(path: str) -> int:
    if not os.path.exists(path):
        print(f"{path}: error: file not found", file=sys.stderr)
        return 1

    with open(path, encoding="utf-8") as f:
        src = f.read()

    # Banner — orient the reader before anything else.
    print(RULE_BAR)
    print(f"REVIEW MODE  —  {path}")
    print(RULE_BAR)
    print("""
Shows how the compiler parses your .su source and then applies
algebraic simplification rewrites to it. Four stages:

  1. Source — what you wrote.
  2. Parsing — the AST, pretty-printed back as Sutra-ish syntax.
  3. Stdlib inlining — if you called any stdlib function, its body
                       gets copied in-place here.
  4. Simplification — each algebraic rewrite that fired, with the
                      expression before and after.

Stage 4 is the interesting one. If zero rewrites fire, your program
is already in minimal form — try `examples/review_demo.su` to see a
program that triggers five of them.

(Downstream codegen -> PyTorch is not shown here — use `--emit` for
that if you want it. This mode is strictly language-level.)
""".strip())

    # --- Stage 1: Source ---
    print(_heading(1, "Source",
                   "The .su text you wrote. Input to the compiler."))
    print()
    for line in src.rstrip().splitlines():
        print(f"  {line}")

    # --- Stage 2: Parsing ---
    lexer = Lexer(src, file=path)
    tokens = lexer.tokenize()
    parser = Parser(tokens, file=path, diagnostics=lexer.diagnostics)
    module = parser.parse_module()
    if lexer.diagnostics.errors:
        print("\nParse errors:")
        for d in lexer.diagnostics.errors:
            print(f"  {d.format()}")
        return 1

    parsed_repr = pretty_module(module)
    print(_heading(
        2, "Parsing",
        "Source text becomes an Abstract Syntax Tree. Below is the "
        "AST pretty-printed back as (pseudo-)Sutra syntax — it should "
        "look similar to your source, with comments removed and "
        "expressions normalized."))
    print()
    for line in parsed_repr.splitlines():
        print(f"  {line}")

    # --- Stage 3: Stdlib inlining ---
    try:
        inline_stdlib_calls(module)
    except Exception as e:
        print(f"\nInliner error: {type(e).__name__}: {e}")
        return 1
    inlined_repr = pretty_module(module)
    print(_heading(
        3, "Stdlib inlining",
        "Calls to stdlib functions (e.g. logical_and, defuzzy) get "
        "replaced by their polynomial bodies in-place, so the "
        "downstream simplifier can fold literal inputs. If your "
        "program doesn't call anything from stdlib, this is a no-op."))
    print(f"  {_compare(parsed_repr, inlined_repr)}")
    if inlined_repr != parsed_repr:
        print()
        for line in inlined_repr.splitlines():
            print(f"  {line}")

    # --- Stage 4: Simplification (the headline) ---
    collector = _TraceCollector()
    set_trace_callback(collector)
    try:
        simplify_module(module)
    finally:
        set_trace_callback(None)
    simplified_repr = pretty_module(module)

    print(_heading(
        4, "Simplification  (headline stage)",
        "The compiler applies algebraic rewrite rules that preserve "
        "meaning but reduce work. Each line below is one rewrite that "
        "fired, showing the expression BEFORE and AFTER the rule "
        "applied. Rule names (R01-R16) refer to the numbered rules "
        "documented in sdk/sutra-compiler/sutra_compiler/simplify.py."))
    print()
    if not collector.events:
        print("  No rewrites fired on this program.")
        print()
        print("  This means either (a) the program is already in minimal")
        print("  form, or (b) its expressions don't match any of the 16")
        print("  rewrite patterns. Programs that DO trigger rewrites:")
        print("    - examples/review_demo.su   (R01, R04, R05, R08, R16)")
        print("    - bundle(v)                 (R01)")
        print("    - similarity(king, king)    (R04)")
        print("    - unbind(r, bind(r, king))  (R08)")
        print("    - 2 + 3                     (R16)")
    else:
        print(f"  {len(collector.events)} rewrite(s) fired:")
        print()
        for i, (rule, before, after) in enumerate(collector.events, 1):
            print(f"  [{i}]  {rule}")
            print(f"        before:  {before}")
            print(f"        after:   {after}")
            print()

    # Only re-print the AST if simplification actually changed something.
    if simplified_repr != inlined_repr:
        print(f"  {SUB_BAR[2:]}")
        print(f"  Simplified AST:")
        print()
        for line in simplified_repr.splitlines():
            print(f"  {line}")

    # --- Final summary ---
    print(_heading(5, "Summary", "One-line recap."))
    print(f"  source:           {src.count(chr(10)) + 1} lines  "
          f"({len(src)} chars)")
    print(f"  AST statements:   {len(module.items)} top-level items")
    print(f"  inlining:         {'changed the AST' if inlined_repr != parsed_repr else 'no-op (no stdlib calls)'}")
    print(f"  simplification:   {len(collector.events)} rewrite(s) fired")
    print()
    print("  (To see the emitted Python/PyTorch code, run "
           "`python sutrac.py --emit FILE.su`.)")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python -m sutra_compiler.review FILE.su", file=sys.stderr)
        sys.exit(2)
    sys.exit(review_file(sys.argv[1]))
