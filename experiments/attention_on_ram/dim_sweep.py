"""Reduction study (design doc §5): the smallest runtime_dim at which the
attention-on-RAM parser still reproduces the oracle, measured.

The three OCaml→substrate fixtures (attn_sum_tape/attn_dot_tape/attn_select_field)
carry no semantic content (0 basis_vector calls — the dim audit, CLAUDE.md), so the
LLM codebook is unused and the runtime_dim can drop to the floor the synthetic axes
need (real/imag/truth) plus whatever the loop/slot machinery requires. This sweep
finds that floor per fixture by compiling each at decreasing runtime_dim and running
it on the substrate, comparing the decoded result to the oracle value.

Off any Sutra runtime hot path? No — this RUNS the .su on the substrate at each dim;
the only host read is the terminal result decode (the external orchestrator boundary),
exactly as the CLI `--run` does. No new readout.
"""

from __future__ import annotations

import pathlib
import sys

_HERE = pathlib.Path(__file__).resolve().parent
_REPO = _HERE.parents[1]
sys.path.insert(0, str(_REPO / "sdk" / "sutra-compiler"))

from sutra_compiler.lexer import Lexer  # noqa: E402
from sutra_compiler.parser import Parser  # noqa: E402
from sutra_compiler.codegen_pytorch import translate_module  # noqa: E402

_FIXTURES = _REPO / "sdk" / "sutra-from-ocaml" / "tests" / "fixtures"
CASES = [
    ("attn_sum_tape", 10.0),
    ("attn_dot_tape", -2.0),
    ("attn_select_field", 22.0),
]


def run_at_dim(su_src: str, dim: int):
    """Compile the .su at runtime_dim=dim, run main() on the substrate, decode the
    real-axis result. Returns the float, or None if compile/run fails at this dim."""
    lx = Lexer(su_src, file="<sweep>")
    ast = Parser(lx.tokenize(), file="<sweep>", diagnostics=lx.diagnostics).parse_module()
    if lx.diagnostics.has_errors():
        return None
    ns: dict = {}
    try:
        exec(translate_module(ast, llm_model="none", runtime_dim=dim), ns)
        vsa = ns["_VSA"]
        res = ns["main"]()
        return float(res[vsa.semantic_dim + vsa.AXIS_REAL])
    except Exception as e:  # noqa: BLE001 — a too-small dim may legitimately fail
        return f"ERR:{type(e).__name__}"


def smallest_passing_dim(name: str, expected: float, lo: int = 3, hi: int = 16):
    su = (_FIXTURES / name / "expected.su").read_text(encoding="utf-8")
    results = {}
    smallest = None
    for d in range(lo, hi + 1):
        got = run_at_dim(su, d)
        ok = isinstance(got, float) and abs(got - expected) < 0.5
        results[d] = (got, ok)
        if ok and smallest is None:
            smallest = d
    return smallest, results


def main() -> int:
    print("attention-on-RAM reduction study: smallest runtime_dim still passing oracle\n")
    all_ok = True
    for name, expected in CASES:
        smallest, results = smallest_passing_dim(name, expected)
        row = " ".join(
            f"{d}:{'OK' if ok else 'x'}" for d, (got, ok) in sorted(results.items())
        )
        print(f"  {name:<18} expected {expected:>6} -> smallest dim = {smallest}")
        print(f"      {row}")
        if smallest is None:
            all_ok = False
    print("\n" + ("PASS: each fixture has a measured smallest passing runtime_dim."
                   if all_ok else "FAIL: a fixture never passed in the swept range."))
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
