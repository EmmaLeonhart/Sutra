"""Tree RNN — approach 1 to non-tail recursion on the substrate.

Non-tail recursion in STRUCTURE (a node depends on fully-computed children) over a FIXED
tree topology needs no call stack: evaluate bottom-up in a single pass. The host knows the
tree shape and walks it level by level; the COMBINE step (`tree_combine.su`'s `combine`,
f(l,r) = 2*l + r) runs on the substrate at each internal node. The root value is decoded
at the display boundary and compared to an independent host computation of the same fold.

The combine is non-associative, so the result depends on the tree bracketing — this proves
the substrate computes the actual tree-structured reduction, not a flat reduce.
"""
from __future__ import annotations

import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "sdk" / "sutra-compiler"))

HERE = pathlib.Path(__file__).resolve().parent


def _compile():
    from sutra_compiler import compile_su
    mod = compile_su(HERE / "tree_combine.su",
                     llm_model="unused-no-basis-vectors", runtime_dim=8, verbose=False)
    return mod.combine, mod._VSA


def _f(l, r):
    """Host reference for the combine: f(l, r) = 2*l + r (non-associative)."""
    return 2.0 * l + r


def _fold_host(leaves):
    """Bottom-up balanced-binary-tree fold with the host combine. len(leaves) a power of 2."""
    level = list(leaves)
    while len(level) > 1:
        level = [_f(level[i], level[i + 1]) for i in range(0, len(level), 2)]
    return level[0]


def fold_substrate(leaves):
    """Same balanced-binary-tree fold, with the COMBINE running on the substrate. Returns
    the decoded root value (read at the display boundary — the substrate has no readout)."""
    import torch

    combine, vsa = _compile()
    ax = vsa.semantic_dim + vsa.AXIS_REAL

    def read(v):
        v = v.real if v.is_complex() else v
        return float(v[ax])

    level = [vsa.make_real(float(x)) for x in leaves]      # leaf hidden states (vectors)
    while len(level) > 1:                                  # bottom-up, level by level
        level = [combine(level[i], level[i + 1]) for i in range(0, len(level), 2)]
    return read(level[0])


def main() -> int:
    cases = [
        [1.0, 2.0, 3.0, 4.0],                              # f(f(1,2),f(3,4)) = f(4,10)=18
        [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0],         # depth-3, 8 leaves
        [2.0, 0.0, 0.0, 0.0],                              # bracketing matters: 2 ends up *8
    ]
    ok = True
    for leaves in cases:
        got = fold_substrate(leaves)
        want = _fold_host(leaves)
        match = abs(got - want) < 1e-5
        ok = ok and match
        print(f"leaves={leaves}: substrate={got:.4f} host={want:.4f} match={match}")
    print("TREE-RNN APPROACH:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
