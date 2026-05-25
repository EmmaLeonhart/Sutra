"""Formal-verification tooling: a closed-form polynomial range-bounder.

This is the first real piece of the *bespoke polynomial-obligation checker*
that `planning/sutra-spec/formal-verification.md` (Pillar 2) and
`paper/formal-verification/paper.md` (§3.2) describe. The branch-range
obligation — "for each reduced branch polynomial, bound its range over the
truth-axis domain [-1, +1]" — is a closed-form polynomial-extremum question,
NOT a path enumeration and NOT a numerical sweep. This module answers it
exactly.

Why a bespoke tool rather than an SMT solver: off-the-shelf SMT targets
Boolean and linear arithmetic. The obligations the compiled graph produces are *polynomial*
(the Kleene connectives reach degree 2 per variable, with an a^2*b^2 term).
We bound a polynomial over an axis-aligned box by the standard compact-domain
extremum argument: a continuous function on a closed box attains its extrema
either at an interior stationary point (gradient zero) or on the boundary;
recursing on the boundary, the candidate set is the union, over every face of
the box (obtained by fixing each variable at a bound or leaving it free), of
the stationary points of the function restricted to that face, intersected
with the closed box. The 0-dimensional faces are the corners. Evaluating the
polynomial at this finite candidate set gives the exact global min and max.

This is closed-form (a finite set of stationary-point solves via sympy), exact
(rational / algebraic arithmetic, no floating point), and sound by the
extremum theorem (no extremum can lie off the candidate set). It is *not* a
general program-equivalence decision procedure — it bounds one reduced
polynomial obligation, which is exactly what Pillar 2 asks for.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass

import sympy


@dataclass(frozen=True)
class RangeBound:
    """Exact global extrema of a polynomial over a box, with witnesses."""

    minimum: sympy.Expr
    maximum: sympy.Expr
    argmin: dict
    argmax: dict
    candidates: int  # how many critical points were evaluated

    def within(self, lo, hi) -> bool:
        """True iff [minimum, maximum] is contained in [lo, hi], decided
        exactly (sympy can compare algebraic numbers)."""
        return bool(self.minimum >= sympy.Integer(lo)) and bool(
            self.maximum <= sympy.Integer(hi)
        )


def bound_polynomial_over_box(
    expr: sympy.Expr, var_bounds: list[tuple[sympy.Symbol, object, object]]
) -> RangeBound:
    """Return the exact (min, max) of ``expr`` over the closed axis-aligned box
    ``var_bounds`` = [(symbol, lo, hi), ...].

    The method (see module docstring): enumerate the box faces; on each face
    solve grad(restriction) = 0 for the free variables; keep solutions inside
    the closed box; evaluate ``expr`` at every candidate; take the extremes.
    Exact and sound — not a sample.
    """
    lo_of = {s: lo for s, lo, _ in var_bounds}
    hi_of = {s: hi for s, _, hi in var_bounds}

    candidate_points: list[dict] = []
    # Each variable is fixed at its low bound, fixed at its high bound, or free.
    for choice in itertools.product(("lo", "hi", "free"), repeat=len(var_bounds)):
        fixed: dict = {}
        free: list[sympy.Symbol] = []
        for (sym, lo, hi), c in zip(var_bounds, choice):
            if c == "lo":
                fixed[sym] = sympy.sympify(lo)
            elif c == "hi":
                fixed[sym] = sympy.sympify(hi)
            else:
                free.append(sym)

        if not free:
            candidate_points.append(dict(fixed))  # a corner (0-dim face)
            continue

        restricted = expr.subs(fixed)
        grad = [sympy.diff(restricted, s) for s in free]
        solutions = sympy.solve(grad, free, dict=True)
        for sol in solutions:
            point = dict(fixed)
            ok = True
            for s in free:
                v = sol.get(s)
                if v is None or not v.is_real:
                    ok = False
                    break
                if not (lo_of[s] <= v <= hi_of[s]):
                    ok = False
                    break
                point[s] = sympy.nsimplify(v)
            if ok:
                candidate_points.append(point)

    if not candidate_points:  # pragma: no cover - a box always has corners
        raise ValueError("no candidate critical points; box is degenerate")

    evaluated = [(sympy.simplify(expr.subs(p)), p) for p in candidate_points]
    vmin, argmin = min(evaluated, key=lambda t: t[0])
    vmax, argmax = max(evaluated, key=lambda t: t[0])
    return RangeBound(
        minimum=vmin,
        maximum=vmax,
        argmin=argmin,
        argmax=argmax,
        candidates=len(candidate_points),
    )
