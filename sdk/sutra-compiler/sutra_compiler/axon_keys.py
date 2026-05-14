"""Static analysis: collect axon-internal keys bound and read by a module.

Walks a parsed Sutra AST and returns two sets:

  - **bound keys**: every `<expr>.add("K", <value>)` call where
    the first argument is a string literal. These are the keys
    producers bind into Axons (per the `Axon a; a.add("k", v);`
    pattern in `examples/multi_program_axon/producer.su` and
    `examples/axon_demo.su`).
  - **read keys**: every `axon_item(<expr>, "K")` call where the
    second argument is a string literal. These are the keys
    consumers read out of Axons (per the
    `axon_item(state, "k")` pattern in
    `examples/multi_program_axon/consumer.su`).

Use case: downstream tooling — most directly Yantra's kernel
router for lazy axon evaluation, where the (bound, read) sets per
program become the static wiring table for the connectome — needs
to know which keys flow without re-parsing the .su source.

Conservative over-collection by design:

  - Any `<expr>.add(string_literal, ...)` is counted as a bound
    key, even on non-Axon receivers (e.g. a hypothetical
    `list.add("foo", ...)`). For real Axon programs the .add
    pattern is dominant; spurious non-Axon entries can be filtered
    downstream by intersecting with the bound-keys-this-module-
    actually-produces set the consumer also computes statically.
  - Non-string-literal first args to `add()` (`a.add(some_var, v)`)
    are skipped — we can't statically resolve dynamic key names
    without a deeper analysis. The conservative answer is "this
    program has dynamic keys we don't know about"; downstream
    tooling can treat that as the eager-fallback case.
  - `axon_item(state, dynamic_key)` likewise skipped.

The pass is read-only: it does not mutate the AST. Safe to call
before or after other passes (simplify, inliner, etc.).
"""

from __future__ import annotations

from . import ast_nodes as ast


def collect_axon_keys(
    module: ast.Module,
) -> tuple[frozenset[str], frozenset[str]]:
    """Return (bound_keys, read_keys) for the module.

    `bound_keys` are static (string-literal) first args to any
    `<expr>.add(...)` call.

    `read_keys` are static (string-literal) second args to any
    `axon_item(<expr>, ...)` call.

    Both sets are frozensets so the caller can hash / cache them.
    """
    bound: set[str] = set()
    read: set[str] = set()
    for item in module.items:
        _walk_top_level(item, bound, read)
    return frozenset(bound), frozenset(read)


# ---------- internals ------------------------------------------------


def _walk_top_level(node: object, bound: set[str], read: set[str]) -> None:
    """Recurse into a TopLevel item (function decl, class decl, etc.).

    We don't enumerate the TopLevel union exhaustively here — we
    walk attributes generically. Anything that holds Stmt or Expr
    children gets descended.
    """
    _walk_generic(node, bound, read)


def _walk_generic(node: object, bound: set[str], read: set[str]) -> None:
    """Generic AST walker.

    Looks at Call nodes for the two patterns of interest; recurses
    into every attribute that holds a Node, a list of Nodes, or a
    tuple of Nodes. This is intentionally tolerant — new AST
    attributes that hold child nodes get walked automatically as
    long as they're stored in normal Python attributes/lists.
    """
    if node is None:
        return

    # The two patterns we care about, both shaped as `Call`:
    if isinstance(node, ast.Call):
        _check_call(node, bound, read)

    # Recurse into every attribute that could hold child nodes.
    if isinstance(node, ast.Node):
        for slot in vars(node).values():
            _walk_value(slot, bound, read)


def _walk_value(value: object, bound: set[str], read: set[str]) -> None:
    """Walk a single attribute value: scalar, Node, list of Nodes, etc."""
    if isinstance(value, ast.Node):
        _walk_generic(value, bound, read)
    elif isinstance(value, (list, tuple)):
        for elem in value:
            _walk_value(elem, bound, read)
    # Scalars (str, int, etc.) and dicts are leaves — nothing to
    # recurse into. Dict-of-Node is not a pattern in the current AST;
    # if it lands later, add a branch here.


def _check_call(call: ast.Call, bound: set[str], read: set[str]) -> None:
    """If this Call matches `<expr>.add(strlit, ...)` or `axon_item(<expr>, strlit)`, record the key."""
    callee = call.callee

    # Pattern 1: <expr>.add(string_literal, ...)
    if (
        isinstance(callee, ast.MemberAccess)
        and callee.member == "add"
        and len(call.args) >= 1
    ):
        key = _string_literal_value(call.args[0])
        if key is not None:
            bound.add(key)

    # Pattern 2: axon_item(<expr>, string_literal)
    if (
        isinstance(callee, ast.Identifier)
        and callee.name == "axon_item"
        and len(call.args) >= 2
    ):
        key = _string_literal_value(call.args[1])
        if key is not None:
            read.add(key)


def _string_literal_value(expr: ast.Expr) -> str | None:
    """If `expr` is a string-literal, return its value; otherwise None.

    Matches `StringLiteral`. Does not unwrap arbitrary expressions
    that might evaluate to a string at runtime — the goal is
    static, not dynamic, key resolution.
    """
    if isinstance(expr, ast.StringLiteral):
        return expr.value
    return None
