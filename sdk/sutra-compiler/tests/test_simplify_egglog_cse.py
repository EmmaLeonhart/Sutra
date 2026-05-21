"""Unit tests for the egglog CSE post-pass.

Covers the three primitives added in 2026-05-20:
  * `cse_aware_cost_model` — alias-shaped delegate of
    `matrix_chain_cost_model`. Tested by confirming identical costs.
  * `find_repeated_subexprs` — counts balanced-paren call substrings.
  * `cse_let_form` — greedy longest-first let-binding extraction.

Codegen integration is deferred. These tests verify the primitives in
isolation; the next session can wire `cse_let_form` into the Python
codegen with confidence the binding shape is sane.
"""
from __future__ import annotations

import pytest

pytest.importorskip("egglog")

from sutra_compiler.simplify_egglog import (  # noqa: E402
    Mat, Vec,
    bind, bundle,
    cse_aware_cost_model, cse_let_form, find_repeated_subexprs,
    matrix_chain_cost_model, simplify_with_cost,
)


# ---------------------------------------------------------------------
# find_repeated_subexprs
# ---------------------------------------------------------------------


def test_find_repeated_finds_outer_bind():
    """The repeated `bind(...)` in a doubled-bundle should be found.

    Construct the str() form directly so the test doesn't depend on
    saturating the e-graph in this test (saturation is exercised in
    test_simplify_egglog.py). The substring shape is what egglog
    produces for `bundle(bind(R, v), bind(R, v))`.
    """
    s = ('bundle(bind(Mat.named("R"), Vec.named("v")), '
         'bind(Mat.named("R"), Vec.named("v")))')
    repeated = find_repeated_subexprs(s)
    found = [sub for sub, _cnt in repeated]
    assert 'bind(Mat.named("R"), Vec.named("v"))' in found
    # Should be reported as count >= 2.
    counts = dict(repeated)
    assert counts['bind(Mat.named("R"), Vec.named("v"))'] == 2


def test_find_repeated_respects_min_size():
    """Short repeated substrings below `min_size` are filtered out."""
    s = "f(a, a, a)"  # `a` repeats but is shorter than min_size=15.
    assert find_repeated_subexprs(s, min_size=15) == []


def test_find_repeated_empty_when_no_repeats():
    """A linear chain with no shared subterms returns nothing."""
    s = 'bundle(Vec.named("a"), Vec.named("b"))'
    assert find_repeated_subexprs(s) == []


def test_find_repeated_orders_longest_first():
    """When multiple things repeat, the longer one wins the tie."""
    inner = 'Vec.named("xx")'                       # 15 chars
    outer = f'bind(Mat.named("R"), {inner})'        # ~36 chars
    s = f'bundle({outer}, {outer})'
    repeated = find_repeated_subexprs(s, min_size=15)
    # Outer appears before inner in the sorted result.
    subs = [sub for sub, _ in repeated]
    assert subs.index(outer) < subs.index(inner)


def test_find_repeated_accepts_egglog_expr():
    """Accepts an egglog Expr (not just a str) via str()."""
    R = Mat.named("R")
    v = Vec.named("v")
    expr = bundle(bind(R, v), bind(R, v))
    repeated = find_repeated_subexprs(expr)
    subs = [sub for sub, _ in repeated]
    # Whatever egglog's exact stringification is, the bind subterm
    # appears twice and is long enough to clear min_size.
    assert any('bind(' in sub for sub in subs)


# ---------------------------------------------------------------------
# cse_let_form
# ---------------------------------------------------------------------


def test_cse_let_form_collapses_outer_repeat():
    """A doubled-bind body produces one binding and a body referencing it
    twice. The inner `Mat.named("R")` / `Vec.named("v")` repeats are
    absorbed (they no longer appear in the post-replacement body)."""
    s = ('bundle(bind(Mat.named("R"), Vec.named("v")), '
         'bind(Mat.named("R"), Vec.named("v")))')
    bindings, body = cse_let_form(s)
    assert len(bindings) == 1
    name, sub = bindings[0]
    assert sub == 'bind(Mat.named("R"), Vec.named("v"))'
    # The body refers to the temp twice, replacing both bind sites.
    assert body == f'bundle({name}, {name})'
    # The temp name should start with the default prefix.
    assert name.startswith("_cse")


def test_cse_let_form_no_change_when_nothing_repeats():
    """No repeats → empty bindings, body unchanged."""
    s = 'bundle(Vec.named("a"), Vec.named("b"))'
    bindings, body = cse_let_form(s)
    assert bindings == []
    assert body == s


def test_cse_let_form_handles_two_independent_repeats():
    """Two disjoint repeated subterms each get their own binding."""
    a = 'bind(Mat.named("R"), Vec.named("a"))'
    b = 'bind(Mat.named("R"), Vec.named("b"))'
    s = f'bundle(bundle({a}, {a}), bundle({b}, {b}))'
    bindings, body = cse_let_form(s)
    # Two repeated outer subterms collapse to two bindings.
    sub_strs = {sub for _name, sub in bindings}
    assert a in sub_strs
    assert b in sub_strs
    # Body has both temp names, each appearing twice.
    for name, _sub in bindings:
        assert body.count(name) == 2


def test_cse_let_form_custom_prefix():
    """The temp-name prefix is configurable."""
    s = ('bundle(bind(Mat.named("R"), Vec.named("v")), '
         'bind(Mat.named("R"), Vec.named("v")))')
    bindings, _body = cse_let_form(s, prefix="t")
    assert all(name.startswith("t") for name, _ in bindings)


def test_cse_let_form_min_size_filters():
    """`min_size` is forwarded — short repeats stay inline."""
    s = "f(a, a, a)"
    bindings, body = cse_let_form(s, min_size=15)
    assert bindings == []
    assert body == s


# ---------------------------------------------------------------------
# cse_aware_cost_model
# ---------------------------------------------------------------------


def test_cse_aware_cost_model_matches_matrix_chain():
    """Cost-aware extraction with `cse_aware_cost_model` produces the
    same integer cost as `matrix_chain_cost_model` on a representative
    expression. Codegen-side CSE is what makes it cheaper at runtime;
    the cost model itself is a deliberate alias."""
    R = Mat.named("R")
    v = Vec.named("v")
    expr = bundle(bind(R, v), bind(R, v))
    _extr1, cost_matrix = simplify_with_cost(
        expr, cost_model=matrix_chain_cost_model,
    )
    _extr2, cost_cse = simplify_with_cost(
        expr, cost_model=cse_aware_cost_model,
    )
    assert cost_matrix == cost_cse
