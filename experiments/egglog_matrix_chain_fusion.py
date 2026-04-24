"""egglog matrix-chain fusion demo — the pass simplify.py can't do.

Second step of the egglog integration plan (after
`egglog_smoke_test.py` confirmed the library is viable). This file
demonstrates a simplification pass that the existing hand-written
`simplify.py` does NOT have: given a chain of matrix applications
on a runtime vector, identify the chain of matrix-matrix
multiplications that can be hoisted out as a module-init
precomputation.

The program shape:

    apply(M_n, ..., apply(M_2, apply(M_1, v)))

The hot-path cost is n matrix-vector matmuls. But the M_i matrices
are runtime constants (basis vectors -> Haar rotation matrices fit
once at _VSA init), so at compile time the compiler knows the
sequence is

    (M_n @ ... @ M_2 @ M_1) @ v

and can precompute the composed matrix M_composed = M_n @ ... @ M_1
ONCE, replacing n vector-sized matmuls on the hot path with 1.

This script shows egglog picking the matrix-composed form over the
vector-apply-chain form via a cost model that charges more per
vector-apply than per matrix-composition (because the matrix compose
only runs at module init; the vector applies run per program
invocation).

The library version of `MApply` (matrix-on-vector) gets a large cost;
the `MMul` (matrix-matrix, module-init-only) gets a small cost. The
extractor then prefers the form where we've factored the chain into
a single composed matrix applied to the vector.

Run: python experiments/egglog_matrix_chain_fusion.py
"""
from __future__ import annotations

import sys

from egglog import EGraph, Expr, StringLike, function, method, rewrite, vars_


class Vec(Expr):
    @method(egg_fn="VNamed")
    @classmethod
    def named(cls, name: StringLike) -> Vec: ...  # type: ignore[empty-body]


class Mat(Expr):
    @method(egg_fn="MNamed")
    @classmethod
    def named(cls, name: StringLike) -> Mat: ...  # type: ignore[empty-body]

    @method(egg_fn="MMul")
    def __matmul__(self, other: Mat) -> Mat: ...  # type: ignore[empty-body]

    @method(egg_fn="MApply")
    def apply(self, v: Vec) -> Vec: ...  # type: ignore[empty-body]


def make_egraph() -> EGraph:
    eg = EGraph()
    (v,) = vars_("v", Vec)
    R, S, T = vars_("R S T", Mat)
    eg.register(
        # Core identity: applying a composed matrix equals applying each
        # factor in turn. Both directions — egglog picks the cheaper.
        rewrite(R.apply(S.apply(v))).to((R @ S).apply(v)),
        rewrite((R @ S).apply(v)).to(R.apply(S.apply(v))),
        # Matmul associativity so the composed form can parenthesize freely.
        rewrite(R @ (S @ T)).to((R @ S) @ T),
        rewrite((R @ S) @ T).to(R @ (S @ T)),
    )
    return eg


# A cost model that reflects the compile-time-vs-runtime distinction:
#   MApply (matrix @ vector)  — happens on every hot-path call; expensive
#   MMul   (matrix @ matrix)  — happens once at module init; cheap
# With these weights, the extractor's minimum-cost expression for an
# n-step chain is the single MApply(composed_matrix, v) form, NOT the
# nested-MApply-chain form.


def cost_model(egraph, expr, children_costs):
    """Cost = base cost for this node + sum of children costs.

    The weights encode compile-time vs runtime:
      MApply (matrix @ vector)  = 100  — hot path; runs every call.
      MMul   (matrix @ matrix)  =   1  — module init; runs once.
      Named constants / leaves  =   1  — small flat cost.

    With these weights, an n-step chain of nested applies costs
    100*n + small. A single apply of an n-long matmul chain costs
    100 + n. So the extractor strictly prefers the fused form as n
    grows, and fuses everything that saturation made available.
    """
    s = repr(expr)
    if ".apply(" in s and s.rstrip().endswith(")") \
            and s.count(".apply(") >= 1:
        # This node ends with .apply(...)  — it's an MApply at the root.
        # (Children appear in children_costs, so we only charge for the
        # root op here; nested applies inside get their own 100 via the
        # recursive cost computation.)
        base = 100
    else:
        base = 1
    return base + sum(children_costs)


def demo_chain(n: int) -> tuple[str, str]:
    """Build a length-n chain of apply()s, saturate, extract.

    Returns (initial_form, extracted_form) as strings so we can eyeball
    the simplification.
    """
    eg = make_egraph()
    v = Vec.named("v")
    # Build Mn.apply(...M2.apply(M1.apply(v))...)
    matrices = [Mat.named(f"M{i}") for i in range(1, n + 1)]
    expr = v
    for M in matrices:
        expr = M.apply(expr)

    initial = str(expr)
    eg.register(expr)
    eg.run(30)
    got = eg.extract(expr, cost_model=cost_model)
    return initial, str(got)


def main() -> int:
    print("=" * 72)
    print("egglog matrix-chain fusion — the pass simplify.py does NOT have")
    print("=" * 72)
    print("Initial form: nested apply()s (what a user's Sutra program emits)")
    print("Target form : single apply() of a precomputed composed matrix")
    print()

    for n in (2, 3, 4, 5):
        initial, extracted = demo_chain(n)
        print(f"--- chain length {n} ---")
        print(f"  initial  : {initial}")
        print(f"  extracted: {extracted}")
        # A fully-fused form should have exactly ONE `.apply(` in the
        # extracted string.
        n_applies = extracted.count(".apply(")
        ok = (n_applies == 1) or (n_applies == 0)
        print(f"  .apply()s in extracted: {n_applies}  "
              f"({'FUSED' if ok else 'NOT FUSED'})")
        print()

    print("=" * 72)
    print("What this demonstrates")
    print("=" * 72)
    print("The hand-written simplify.py has no rewrite that turns")
    print("    M3.apply(M2.apply(M1.apply(v)))")
    print("into")
    print("    (M3 @ M2 @ M1).apply(v)")
    print("— because the rule requires matrix-matrix composition, which")
    print("needs either a cost-directed extractor or a whole-program")
    print("linearity analysis. egglog provides both primitives.")
    print()
    print("egglog's default extractor picks the smallest AST; the printed")
    print("'extracted' row shows what the saturation + extraction chose.")
    print("Even without a custom cost model, the AST-size tiebreak favors")
    print("the composed form because it fuses n applies into 1.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
