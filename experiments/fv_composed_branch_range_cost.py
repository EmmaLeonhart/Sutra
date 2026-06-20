"""Characterise the cost of the closed-form branch-range bounder on COMPOSED
(whole-program) Kleene polynomials, not just the atomic connectives.

`planning/sutra-spec/formal-verification.md` Pillar-2 branch-range obligation is
discharged in closed form for `&&`/`||`/`!` individually
(`test_fv_poly_obligation_checker.py`). The named-open remainder (todo.md
§"Formal verification" → "Branch-range obligation discharge"):

    Remaining: run the bounder on the *composed* polynomials of whole reduced
    programs (degree grows with branch-nesting; characterise the numerical cost
    there).

This probe runs `check_branch_range` on nested Kleene expressions of increasing
branch-nesting depth / arity, each in a worker process with a hard timeout, and
prints exact range + critical-point count + wall time. A timeout is a DATUM (the
closed-form extremum search hit its scaling wall), not a failure — that is the
cost characterisation the obligation asks for.

Usage:  python experiments/fv_composed_branch_range_cost.py [timeout_s]
"""
from __future__ import annotations

import multiprocessing as mp
import sys
import time


# (label, expr_src, var_names) — increasing composition depth / arity.
CASES = [
    ("d1  a&&b", "a && b", ["a", "b"]),
    ("d2  (a&&b)||c", "(a && b) || c", ["a", "b", "c"]),
    ("d3  (a&&b)||(c&&d)", "(a && b) || (c && d)", ["a", "b", "c", "d"]),
    ("d3b !((a&&b)||c)", "!((a && b) || c)", ["a", "b", "c"]),
    ("d4  ((a&&b)||(c&&d))&&!e", "((a && b) || (c && d)) && !e",
     ["a", "b", "c", "d", "e"]),
    ("d5  ((a&&b)||(c&&d))&&(!e||(a&&c))",
     "((a && b) || (c && d)) && (!e || (a && c))", ["a", "b", "c", "d", "e"]),
]


def _worker(expr_src, var_names, q):
    import sympy
    from sutra_compiler.fv_obligation_checker import (
        check_branch_range, extract_truth_polynomial)
    poly, _ = extract_truth_polynomial(expr_src, var_names)
    used = sorted(poly.free_symbols, key=lambda s: s.name)
    deg = sympy.Poly(poly, *used).total_degree() if used else 0
    t0 = time.perf_counter()
    rb = check_branch_range(expr_src, var_names)
    dt = time.perf_counter() - t0
    q.put((str(rb.minimum), str(rb.maximum), bool(rb.within(-1, 1)),
           int(deg), int(rb.candidates), dt))


def main() -> None:
    timeout = float(sys.argv[1]) if len(sys.argv) > 1 else 30.0
    print(f"closed-form branch-range bounder on COMPOSED polynomials "
          f"(per-case timeout {timeout:.0f}s)\n")
    print(f"{'case':<38} {'range':<12} {'sound':<6} {'deg':<4} "
          f"{'crit_pts':<9} {'time'}")
    for label, src, vs in CASES:
        q: mp.Queue = mp.Queue()
        p = mp.Process(target=_worker, args=(src, vs, q))
        t0 = time.perf_counter()
        p.start()
        p.join(timeout)
        if p.is_alive():
            p.terminate()
            p.join()
            print(f"{label:<38} {'TIMEOUT':<12} {'?':<6} {'?':<4} "
                  f"{'?':<9} >{timeout:.0f}s")
            continue
        if q.empty():
            print(f"{label:<38} {'ERROR (no result)':<12}")
            continue
        lo, hi, sound, deg, crit, dt = q.get()
        rng = f"[{lo},{hi}]"
        print(f"{label:<38} {rng:<12} {str(sound):<6} {deg:<4} "
              f"{crit:<9} {dt*1000:.0f}ms")


if __name__ == "__main__":
    main()
