"""FV end-to-end worked example: a named program vs its published contract.

The first *integrative* FV artifact (todo.md § "Formal verification" → "End-to-end
worked example"): one named Sutra program carried through the WHOLE obligation
pipeline, so the framework is demonstrated on a concrete case rather than as
separate per-check tests. Composes the public FV API (`from sutra_compiler import
fv`); no new mechanism. Feeds a paper revision (paper/formal-verification/paper.md).

The program: a NAND gate, written in **De Morgan form** (`!a || !b`) — deliberately
NOT syntactically identical to its contract, so "computes the contract's function"
is a real claim, not a tautology.

    function vector nand(vector a, vector b) { return !a || !b; }

Its published contract:
  - FUNCTION: it computes NAND, i.e. `!(a && b)` (the canonical form).
  - RANGE:    its output is a valid truth value — stays in [-1, +1] over the whole
              fuzzy truth domain.

The obligations discharged below (all exact / decidable, none sampled):
  1. Function-correctness  — the implementation reduces to the SAME tensor graph as
     the contract's NAND function (polynomial identity; holds off-grid too, any
     nesting depth). A plausible-but-WRONG implementation (NOR) is REJECTED.
  2. Branch-range soundness — the implementation's exact output range is within
     [-1, +1] (by structural composition, degree-insensitively).
  3. Substrate cross-check — the COMPILED program, run on the torch substrate at the
     nine Kleene grid points, reproduces the NAND truth table (so the symbolic
     verdict is not a claim about a hand-copied polynomial — it is the running
     program; integrity discipline, CLAUDE.md).

Run:  python experiments/fv_worked_example.py
"""
from __future__ import annotations

import itertools

# The implementation (De Morgan) and the contract (canonical NAND); a wrong impl.
IMPL = "!a || !b"
CONTRACT = "!(a && b)"
WRONG = "!(a || b)"  # NOR — plausible but not NAND
VARS = ["a", "b"]
GRID = (-1.0, 0.0, 1.0)  # false, unknown, true


def _substrate_grid_check():
    """Compile the NAND program and evaluate it at the nine grid points on the
    torch substrate; return (worst_abs_error, rows) vs the NAND truth table.
    On antipodal Kleene (true=+1, false=-1): a&&b = min, !x = -x, so
    NAND(a,b) = !(a&&b) = -min(a, b)."""
    from sutra_compiler.codegen_pytorch import translate_module
    from sutra_compiler.lexer import Lexer
    from sutra_compiler.parser import Parser

    src = ("function vector nand(vector a, vector b) { return %s; }\n"
           "function vector main() { return true; }\n" % IMPL)
    lx = Lexer(src, file="<fv-nand>")
    ps = Parser(lx.tokenize(), file="<fv-nand>", diagnostics=lx.diagnostics)
    py = translate_module(ps.parse_module(), llm_model="nomic-embed-text",
                          runtime_dim=64)
    ns: dict = {}
    exec(compile(py, "<fv-nand>", "exec"), ns)
    vsa, nand = ns["_VSA"], ns["nand"]

    worst, rows = 0.0, []
    for a, b in itertools.product(GRID, GRID):
        got = float(vsa.truth_axis(nand(vsa.make_truth(a), vsa.make_truth(b))))
        exp = -min(a, b)  # NAND
        worst = max(worst, abs(got - exp))
        rows.append((a, b, got, exp))
    return worst, rows


def run() -> dict:
    """Discharge every obligation; return a verdict dict (also used by the test)."""
    from sutra_compiler import fv

    rb = fv.check_branch_range(IMPL, VARS)
    worst, rows = _substrate_grid_check()
    return {
        "function_correct": fv.reduces_to_same_graph(IMPL, CONTRACT, VARS),
        "wrong_rejected": not fv.reduces_to_same_graph(WRONG, CONTRACT, VARS),
        "range_sound": fv.range_sound_by_composition(IMPL, VARS),
        "exact_range": (str(rb.minimum), str(rb.maximum), bool(rb.within(-1, 1))),
        "substrate_worst_err": worst,
        "substrate_rows": rows,
    }


def main() -> None:
    r = run()
    print("FV WORKED EXAMPLE — NAND gate vs its published contract\n")
    print(f"  program (impl):  function nand(a, b) = {IMPL}")
    print(f"  contract (fn):   NAND = {CONTRACT}\n")
    print("Obligation 1 — function-correctness (graph equivalence):")
    print(f"  De Morgan impl reduces to the contract's NAND graph : {r['function_correct']}")
    print(f"  wrong impl (NOR = {WRONG}) correctly REJECTED        : {r['wrong_rejected']}")
    lo, hi, ok = r["exact_range"]
    print("\nObligation 2 — branch-range soundness:")
    print(f"  range-sound by structural composition (any depth)   : {r['range_sound']}")
    print(f"  exact output range [{lo}, {hi}] within [-1, +1]        : {ok}")
    print("\nObligation 3 — substrate cross-check (compiled program on torch):")
    print("    a    b   | got    exp(NAND)")
    for a, b, got, exp in r["substrate_rows"]:
        print(f"   {a:+.0f}   {b:+.0f}  | {got:+.3f}  {exp:+.0f}")
    print(f"  worst |error| vs NAND truth table                   : {r['substrate_worst_err']:.2e}")
    allok = (r["function_correct"] and r["wrong_rejected"] and r["range_sound"]
             and r["exact_range"][2] and r["substrate_worst_err"] < 1e-5)
    print(f"\n  ALL OBLIGATIONS DISCHARGED: {allok}")


if __name__ == "__main__":
    main()
