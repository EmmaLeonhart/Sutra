"""Measure the signal-separation gap of the mini_wasm_machine opcode dispatch.

CLAUDE.md  "Subtler substrate breaches" #3 requires every substrate classifier
to ship a measured gap = min(positive_class) - max(negative_class).

The machine dispatches each opcode with the indicator

    is_X = truth_axis(defuzzy(op == X))      # X a literal opcode 0..20

so for an actual opcode k the SELECTED indicator is is_k (positive class) and
all other is_j, j != k, are the negative class. We sweep every (k, target)
pair through the EXACT compile path (same codegen, same runtime_dim=2 the
regression test uses) and report:

  - selected truth   = is_k for the running opcode k        (want ~ +1)
  - max leaked truth  = max over j != k of is_j              (want well below)
  - gap              = min_k(selected_k) - max_{k,j!=k}(is_j)

A positive gap means the dispatch decision is real on the substrate, not an
artifact of the host harness.
"""

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
COMPILER = ROOT / "sdk" / "sutra-compiler"
if str(COMPILER) not in sys.path:
    sys.path.insert(0, str(COMPILER))

from sutra_compiler.lexer import Lexer
from sutra_compiler.parser import Parser
from sutra_compiler.codegen_pytorch import translate_module

N_OPCODES = 21  # 0..20

PROBE_SRC = """
function int indicator(int op, int target) {
    return truth_axis(defuzzy(op == target));
}
"""


def _compile(runtime_dim: int):
    lx = Lexer(PROBE_SRC, file="<probe>")
    ast = Parser(lx.tokenize(), file="<probe>", diagnostics=lx.diagnostics).parse_module()
    assert not lx.diagnostics.has_errors(), list(lx.diagnostics)
    ns: dict = {}
    exec(translate_module(ast, llm_model="none", runtime_dim=runtime_dim), ns)
    return ns


def measure(runtime_dim: int = 2):
    ns = _compile(runtime_dim)
    indicator = ns["indicator"]

    selected = []          # is_k for the running opcode k
    leaked = []            # is_j, j != k (negative class)
    worst_row = None       # (k, max_leaked_j, argmax_j)

    for k in range(N_OPCODES):
        row_leak = []
        for target in range(N_OPCODES):
            val = float(indicator(float(k), float(target)))
            if target == k:
                selected.append((k, val))
            else:
                leaked.append(val)
                row_leak.append((val, target))
        mx, mj = max(row_leak)
        if worst_row is None or mx > worst_row[1]:
            worst_row = (k, mx, mj)

    min_selected = min(v for _, v in selected)
    min_selected_k = min(selected, key=lambda kv: kv[1])[0]
    max_leaked = max(leaked)
    gap = min_selected - max_leaked
    return {
        "runtime_dim": runtime_dim,
        "min_selected": min_selected,
        "min_selected_opcode": min_selected_k,
        "max_leaked": max_leaked,
        "worst_leak_opcode": worst_row[0],
        "worst_leak_target": worst_row[2],
        "gap": gap,
        "selected": selected,
    }


if __name__ == "__main__":
    for dim in (2, 50):
        r = measure(dim)
        print(f"=== runtime_dim={r['runtime_dim']} ===")
        print(f"  min selected truth      = {r['min_selected']:+.6f} (opcode {r['min_selected_opcode']})")
        print(f"  max leaked truth        = {r['max_leaked']:+.6f} "
              f"(opcode {r['worst_leak_opcode']} misfiring on target {r['worst_leak_target']})")
        print(f"  GAP (min_sel - max_leak) = {r['gap']:+.6f}")
        print(f"  -> {'SEPARATED' if r['gap'] > 0 else 'NOT SEPARATED'}")
        print()
