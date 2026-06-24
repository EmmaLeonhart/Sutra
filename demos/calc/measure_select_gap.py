"""Measure the signal-separation gap of the calc operator-select (`switch.su`).

CLAUDE.md "Subtler substrate breaches" #3 requires every substrate classifier to
ship a measured `gap = min(positive_class) - max(negative_class)`. The substrate
audit (2026-06-19) flagged that `demos/calc/switch.su` had no such table, only
end-to-end result checks in `test_calc.py`.

`switch.su` dispatches the four arithmetic operators by reading the operator
character's codepoint `cp` (on the substrate, via `string_char_at`) and scoring it
against each operator codepoint with

    s_t = -1000 * (cp - t)^2          t in {'+'=43, '-'=45, '*'=42, '/'=47}

which is exactly 0 when `cp == t` and <= -1000 otherwise; the four scores feed
`select`'s softmax, where `exp(-1000)` underflows to a TRUE one-hot. This script
recomputes that exact score on the substrate (the same codegen + runtime) and
reports, over the four operators:

    selected score  = s_t for t == cp        (want ~ 0, the positive class)
    max leaked      = max over t != cp of s_t (want <= -1000, negative class)
    gap             = min(selected) - max(leaked)

The tightest pair is '*'(42) vs '+'(43), one codepoint apart, so the worst leaked
score is -1000 and the gap is ~1000. A large positive gap means the operator
decision is real on the substrate, not an artifact of the host harness.

Run: python demos/calc/measure_select_gap.py
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
COMPILER = ROOT / "sdk" / "sutra-compiler"
if str(COMPILER) not in sys.path:
    sys.path.insert(0, str(COMPILER))

from sutra_compiler.lexer import Lexer  # noqa: E402
from sutra_compiler.parser import Parser  # noqa: E402
from sutra_compiler.codegen_pytorch import translate_module  # noqa: E402

# Operator characters and their codepoints, exactly as switch.su scores them.
OPS = {"+": 43, "-": 45, "*": 42, "/": 47}

PROBE_SRC = """
function number op_score(number cp, number target) {
    return 0.0 - 1000.0 * (cp - target) * (cp - target);
}
function int main() { return 0; }
"""


def _compile(runtime_dim: int) -> dict:
    lx = Lexer(PROBE_SRC, file="<probe>")
    ast = Parser(lx.tokenize(), file="<probe>", diagnostics=lx.diagnostics).parse_module()
    assert not lx.diagnostics.has_errors(), list(lx.diagnostics)
    ns: dict = {}
    exec(translate_module(ast, llm_model="none", runtime_dim=runtime_dim), ns)
    return ns


def measure(runtime_dim: int = 8) -> dict:
    ns = _compile(runtime_dim)
    op_score = ns["op_score"]
    vsa = ns["_VSA"]

    # Measurement boundary: decode the score's real-axis component for reporting.
    def score(cp: int, target: int) -> float:
        return float(vsa._re(op_score(float(cp), float(target))))

    selected: list = []   # (op, score) for target == cp
    leaked: list = []     # score for target != cp
    worst = None          # (op, max_leaked_score, target_op)
    for op, cp in OPS.items():
        row = []
        for t_op, t_cp in OPS.items():
            s = score(cp, t_cp)
            if t_cp == cp:
                selected.append((op, s))
            else:
                leaked.append(s)
                row.append((s, t_op))
        mx, mt = max(row)
        if worst is None or mx > worst[1]:
            worst = (op, mx, mt)

    min_selected = min(s for _, s in selected)
    max_leaked = max(leaked)
    return {
        "runtime_dim": runtime_dim,
        "min_selected": min_selected,
        "max_leaked": max_leaked,
        "gap": min_selected - max_leaked,
        "worst": worst,
        "selected": selected,
    }


if __name__ == "__main__":
    for dim in (8, 50):
        r = measure(dim)
        print(
            f"runtime_dim={r['runtime_dim']}: gap={r['gap']:.1f}  "
            f"(min selected={r['min_selected']:.1f}, max leaked={r['max_leaked']:.1f}; "
            f"tightest leak: operator {r['worst'][0]} scored against '{r['worst'][2]}' "
            f"= {r['worst'][1]:.1f})"
        )
        assert r["gap"] > 0, r
        assert abs(r["min_selected"]) < 1e-3, r  # selected score is exactly 0
    print("SEPARATED: the four operator-select scores separate on the substrate.")
