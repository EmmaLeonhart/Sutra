"""egglog smoke-test — can we lift Sutra's rewrite rules into egglog?

First integration step of the algebraic-simplification plan in STATUS.md.
The existing `sdk/sutra-compiler/sutra_compiler/simplify.py` hand-writes
~16 rewrite rules over the Sutra AST. This file verifies that egglog
(v13, `pip install egglog`) can:

1. Declare a symbolic IR for Sutra's core operators as Python classes.
2. Express the same rewrite rules as `rewrite(...).to(...)` declarations.
3. Saturate a non-trivial expression and extract the minimal form.

If this smoke test passes, the next step is replacing the rewrite rules
in simplify.py with an egglog-driven pass. If it fails, we either need
a different library (opt-einsum for the matrix-chain half only) or we
keep hand-rolling.

Five tests, each corresponding to a rewrite in simplify.py today:

  1. bundle(v) -> v                             (identity bundle)
  2. unbind(R, bind(R, x)) -> x                 (round-trip)
  3. bind(R, zero_vector()) -> zero_vector()   (zero absorption)
  4. ((M3 @ M2) @ M1) @ v  associativity         (matrix-chain reshape)
  5. Multi-step chain: unbind inside bundle     (cascades via saturation)

Run: python experiments/egglog_smoke_test.py
"""
from __future__ import annotations

import sys

from egglog import EGraph, Expr, StringLike, function, method, rewrite, vars_


# -------------------------------------------------------------------
# Sutra IR types for the smoke test.
# -------------------------------------------------------------------


class Vec(Expr):
    """A Sutra runtime vector. Opaque — carries meaning, not structure
    visible to the egraph. Matrices operate on vectors via `@`."""

    @method(egg_fn="VNamed")
    @classmethod
    def named(cls, name: StringLike) -> Vec: ...  # type: ignore[empty-body]

    @method(egg_fn="VZero")
    @classmethod
    def zero(cls) -> Vec: ...  # type: ignore[empty-body]


class Mat(Expr):
    """A linear operator on vectors (bind role matrix, rotation, etc.)."""

    @method(egg_fn="MNamed")
    @classmethod
    def named(cls, name: StringLike) -> Mat: ...  # type: ignore[empty-body]

    @method(egg_fn="MMul")
    def __matmul__(self, other: Mat) -> Mat: ...  # type: ignore[empty-body]

    @method(egg_fn="MApply")
    def apply(self, v: Vec) -> Vec: ...  # type: ignore[empty-body]

    @method(egg_fn="MInv")
    def inv(self) -> Mat: ...  # type: ignore[empty-body]


@function(egg_fn="Bind")
def bind(role: Mat, filler: Vec) -> Vec: ...  # type: ignore[empty-body]


@function(egg_fn="Unbind")
def unbind(role: Mat, record: Vec) -> Vec: ...  # type: ignore[empty-body]


@function(egg_fn="Bundle1")
def bundle1(a: Vec) -> Vec: ...  # type: ignore[empty-body]


@function(egg_fn="Bundle2")
def bundle2(a: Vec, b: Vec) -> Vec: ...  # type: ignore[empty-body]


# -------------------------------------------------------------------
# Rewrite rules.
# -------------------------------------------------------------------


def make_egraph() -> EGraph:
    eg = EGraph()
    v, w = vars_("v w", Vec)
    R, S, T = vars_("R S T", Mat)

    eg.register(
        # Identity-bundle — bundle(v) = v.
        rewrite(bundle1(v)).to(v),

        # Round-trip identities.
        rewrite(unbind(R, bind(R, v))).to(v),
        rewrite(bind(R, unbind(R, v))).to(v),

        # Zero absorption.
        rewrite(bind(R, Vec.zero())).to(Vec.zero()),
        rewrite(unbind(R, Vec.zero())).to(Vec.zero()),

        # Matrix multiplication is associative — the foundation of
        # matrix-chain composition. Going in both directions so
        # saturation can find the right parenthesization given the
        # cost model.
        rewrite(R @ (S @ T)).to((R @ S) @ T),
        rewrite((R @ S) @ T).to(R @ (S @ T)),

        # Apply distributes through composition: (R @ S).apply(v) = R.apply(S.apply(v))
        rewrite((R @ S).apply(v)).to(R.apply(S.apply(v))),
        rewrite(R.apply(S.apply(v))).to((R @ S).apply(v)),
    )
    return eg


# -------------------------------------------------------------------
# Smoke tests.
# -------------------------------------------------------------------


def test_identity_bundle() -> tuple[bool, str]:
    eg = make_egraph()
    x = Vec.named("x")
    expr = bundle1(x)
    eg.register(expr)
    eg.run(10)
    got = eg.extract(expr)
    return (str(got) == str(x),
            f"bundle1(x) -> {got}  (expected Vec.named(\"x\"))")


def test_bind_unbind_roundtrip() -> tuple[bool, str]:
    eg = make_egraph()
    x = Vec.named("x")
    R = Mat.named("R")
    expr = unbind(R, bind(R, x))
    eg.register(expr)
    eg.run(10)
    got = eg.extract(expr)
    return (str(got) == str(x),
            f"unbind(R, bind(R, x)) -> {got}  (expected x)")


def test_zero_absorption() -> tuple[bool, str]:
    eg = make_egraph()
    R = Mat.named("R")
    expr = bind(R, Vec.zero())
    eg.register(expr)
    eg.run(10)
    got = eg.extract(expr)
    return (str(got) == str(Vec.zero()),
            f"bind(R, zero) -> {got}  (expected Vec.zero())")


def test_chain_composition() -> tuple[bool, str]:
    """Three matmul chain — associativity should let saturation find
    whichever parenthesization minimizes cost. egglog's default
    extractor picks the smallest AST, so this mostly verifies the
    rules don't blow up."""
    eg = make_egraph()
    M1 = Mat.named("M1")
    M2 = Mat.named("M2")
    M3 = Mat.named("M3")
    v = Vec.named("v")
    expr = ((M3 @ M2) @ M1).apply(v)
    eg.register(expr)
    eg.run(10)
    got = eg.extract(expr)
    return (True,
            f"((M3 @ M2) @ M1).apply(v) saturates to:  {got}")


def test_cascading_rewrites() -> tuple[bool, str]:
    """A rewrite inside a context that itself needs rewriting.
    bundle(unbind(R, bind(R, x))) -> bundle(x) -> x."""
    eg = make_egraph()
    x = Vec.named("x")
    R = Mat.named("R")
    expr = bundle1(unbind(R, bind(R, x)))
    eg.register(expr)
    eg.run(20)
    got = eg.extract(expr)
    return (str(got) == str(x),
            f"bundle(unbind(R, bind(R, x))) -> {got}  (expected x)")


def main() -> int:
    print("=" * 72)
    print("egglog smoke test — 5 Sutra rewrites")
    print("=" * 72)
    tests = [
        ("identity bundle          bundle(v) -> v", test_identity_bundle),
        ("bind/unbind roundtrip    unbind(R, bind(R, x)) -> x",
         test_bind_unbind_roundtrip),
        ("zero absorption          bind(R, 0) -> 0", test_zero_absorption),
        ("matrix chain             ((M3 @ M2) @ M1).apply(v)",
         test_chain_composition),
        ("cascading rewrite        bundle(unbind(R, bind(R, x)))",
         test_cascading_rewrites),
    ]
    all_passed = True
    for label, fn in tests:
        try:
            ok, detail = fn()
        except Exception as e:
            ok = False
            detail = f"{type(e).__name__}: {e}"
        mark = "PASS" if ok else "FAIL"
        if not ok:
            all_passed = False
        print(f"  [{mark}] {label}")
        print(f"         {detail}")
    print()
    print(f"Overall: {'ALL PASS' if all_passed else 'AT LEAST ONE FAIL'}")
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
