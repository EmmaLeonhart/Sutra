"""Randomized PIT (Schwartz-Zippel) vs full expansion — scalability of the FV
program-equivalence decision procedure.

The FV obligation checker decides "do two Kleene expressions reduce to the same
tensor graph?" by polynomial identity. The exact route, ``expand(p_a - p_b) == 0``,
distributes the nested product-of-sums into monomials, whose count grows
GEOMETRICALLY with nesting depth — the scalability wall reviewers flagged (">1000
terms at depth 3"). This script confirms that wall on the SAME pipeline and shows
the randomized route (``reduces_to_same_graph_randomized``) decides the SAME
identities WELL PAST it: it evaluates the UNEXPANDED difference at random integer
points (Schwartz-Zippel) — poly-time, no distribution, sound one-sided (any nonzero
eval is an exact disproof; all-zero certifies identity with error
<= (degree/|S|)^trials).

Each expansion row runs in a worker process with a wall-clock timeout, so a single
blow-up cannot hang the run — that timeout IS the wall.

Run:  python experiments/randomized_pit_scaling.py
"""
from __future__ import annotations

import multiprocessing
import pathlib
import sys
import time

_COMPILER = pathlib.Path(__file__).resolve().parents[1] / "sdk" / "sutra-compiler"
if str(_COMPILER) not in sys.path:
    sys.path.insert(0, str(_COMPILER))

_VARS = [chr(ord("a") + k) for k in range(8)]


def nested(depth: int, i: int = 0) -> tuple[str, int]:
    """A balanced binary Kleene tree alternating && / || over cycled variables."""
    if depth == 0:
        return _VARS[i % len(_VARS)], i + 1
    op = " && " if depth % 2 == 0 else " || "
    left, i = nested(depth - 1, i)
    right, i = nested(depth - 1, i)
    return f"({left}{op}{right})", i


def _top_level_op_index(inner: str, op: str) -> int | None:
    depth = 0
    for k in range(len(inner)):
        c = inner[k]
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
        elif depth == 0 and inner[k:k + len(op)] == op:
            return k
    return None


def commuted(expr: str) -> str:
    """Swap the operands of the OUTERMOST binary op — a commutativity variant that
    reduces to the SAME graph but is a different syntax tree."""
    inner = expr[1:-1]
    for op in (" && ", " || "):
        k = _top_level_op_index(inner, op)
        if k is not None:
            return f"({inner[k + len(op):]}{op}{inner[:k]})"
    return expr


def perturbed(expr: str) -> str:
    """Change one leaf to a fresh variable — a NON-equivalent expression."""
    return expr.replace("a", "h", 1) if "a" in expr else expr.replace("b", "h", 1)


_EXP_COMPILER = str(_COMPILER)


def _expand_monomials_worker(expr: str, var_pool: int, q) -> None:
    """Worker: put the monomial count of expand(E) on the queue. Run in a process we
    can .terminate() on timeout — `expand` cannot be interrupted in-thread, and a
    timed-out worker that keeps grinding would block a pool's shutdown."""
    sys.path.insert(0, _EXP_COMPILER)
    from sutra_compiler.fv_obligation_checker import extract_truth_polynomial
    poly, _ = extract_truth_polynomial(expr, [chr(ord("a") + k) for k in range(var_pool)])
    q.put(len(poly.args) if poly.is_Add else 1)


def _expand_monomials(expr: str, var_pool: int, timeout_s: float):
    """Return the monomial count, or None if expand exceeds `timeout_s` (the wall)."""
    q = multiprocessing.Queue()
    proc = multiprocessing.Process(target=_expand_monomials_worker,
                                   args=(expr, var_pool, q))
    proc.start()
    proc.join(timeout_s)
    if proc.is_alive():
        proc.terminate()
        proc.join()
        return None
    return q.get() if not q.empty() else None


def main() -> None:
    from sutra_compiler.fv_obligation_checker import (
        reduces_to_same_graph, reduces_to_same_graph_randomized)

    per_row_timeout_s = 30.0

    print("== Table 1: the expansion wall (monomials of expand(E_d), var pool 3) ==",
          flush=True)
    print(f"{'depth':>5} | {'leaves':>6} | {'monomials':>14} | {'expand_s':>9}", flush=True)
    exact_feasible_max = 0
    for d in range(1, 7):
        e, _ = nested(d)
        t0 = time.time()
        nmono = _expand_monomials(e, 3, per_row_timeout_s)
        dt = time.time() - t0
        if nmono is None:
            print(f"{d:>5} | {2**d:>6} | {'INFEASIBLE':>14} | >{per_row_timeout_s:.0f}"
                  f"  <- the wall: expand blows up", flush=True)
            break
        print(f"{d:>5} | {2**d:>6} | {nmono:>14} | {dt:>9.3f}", flush=True)
        exact_feasible_max = d

    print("\n== Table 2: randomized PIT — same verdicts, cheap, far past the wall ==",
          flush=True)
    print(f"{'depth':>5} | {'pair':>9} | {'rand':>5} | {'exact':>7} | {'rand_s':>8} | "
          f"{'deg<=':>6} | fp_bound", flush=True)
    for d in range(2, 13):
        e, _ = nested(d)
        for label, other in (("commuted", commuted(e)), ("perturbed", perturbed(e))):
            t0 = time.time()
            ident, info = reduces_to_same_graph_randomized(e, other, _VARS, trials=32)
            dt = time.time() - t0
            exact_str = "-"
            if d <= exact_feasible_max:
                exact_str = str(reduces_to_same_graph(e, other, _VARS))
            fp = info.get("false_positive_bound", "(disproof)")
            print(f"{d:>5} | {label:>9} | {str(ident):>5} | {exact_str:>7} | "
                  f"{dt:>8.4f} | {info['degree_bound']:>6} | {fp}", flush=True)


if __name__ == "__main__":
    main()
