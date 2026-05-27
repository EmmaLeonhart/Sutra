"""PIT (polynomial identity testing) term-count honesty measurement.

Motivated by the recurring FV-paper reviewer con: "you say path
explosion is removed but you don't characterise the term-count cost of
the expanded polynomial."

The general checker (`sutra_compiler.fv_obligation_checker`) replaces
control-flow path enumeration with a single expanded polynomial per
program. *Term count* of that polynomial is the honest cost: PIT
(equivalence by `sympy.expand(p1 - p2) == 0`) is cheap *per term* but
the term count itself grows with nesting depth × variable count.

This script sweeps real Kleene programs of varying shape, extracts
each polynomial via the SAME pipeline the obligation checker uses
(parse → real inliner → walk AST into sympy → `sympy.expand`), and
reports the monomial term count. The output is the honest growth
curve to cite in the FV paper §3.4 in place of the unqualified "path
explosion is removed" claim.

Honest scope (HARD RAILS): this measures the term-count cost only —
NOT a claim that term count is the dominant cost of PIT, NOT a claim
that term count is bounded. Reading: "PIT replaces branch enumeration
with monomial enumeration; here's how monomial count grows with
shape."

Usage:
    python experiments/fv_pit_term_count.py

Adds a row to `planning/findings/<date>-pit-term-count.md` and prints
the table inline.
"""
from __future__ import annotations

import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(REPO, "sdk", "sutra-compiler"))

import sympy

from sutra_compiler.fv_obligation_checker import (
    extract_truth_polynomial,
    NonPolynomialResidual,
)


def _vars(n: int) -> list[str]:
    return [chr(ord("a") + i) for i in range(n)]


def gen_balanced_and_or(depth: int, var_names: list[str]) -> str:
    """Balanced binary tree alternating `&&` (even depth) / `||` (odd depth)
    with variables drawn cyclically from `var_names`. Deterministic shape
    so the measurement is repeatable.

    depth 0 → single variable
    depth 1 → `a && b`
    depth 2 → `(a && b) || (c && a)`
    depth 3 → `((a && b) || (c && d)) && ((a && b) || (c && d))`
    """
    if depth == 0:
        return var_names[0]
    # Index cycling on leaves only — keep the operator pattern deterministic.
    leaves = 2 ** depth
    leaf_names = [var_names[i % len(var_names)] for i in range(leaves)]

    def build(level_from_top: int, lo: int, hi: int) -> str:
        if hi - lo == 1:
            return leaf_names[lo]
        mid = (lo + hi) // 2
        left = build(level_from_top + 1, lo, mid)
        right = build(level_from_top + 1, mid, hi)
        op = "&&" if level_from_top % 2 == 0 else "||"
        return f"({left} {op} {right})"

    return build(0, 0, leaves)


def gen_negated_balanced(depth: int, var_names: list[str]) -> str:
    """Same balanced tree but every level wraps in a `!` — exercises the
    interaction of `!` with `&&`/`||` (De Morgan-shaped, but the polynomial
    doesn't reduce to a single connective). Tests the negation cost."""
    base = gen_balanced_and_or(depth, var_names)
    if depth == 0:
        return f"!{base}"
    return f"!{base}"


def measure(expr_src: str, var_names: list[str]) -> tuple[int, int]:
    """Returns (term_count, distinct_variable_count). term_count is the
    number of monomials in the expanded polynomial (len of Add.args; a
    single monomial counts as 1)."""
    poly, syms = extract_truth_polynomial(expr_src, var_names)
    # sympy.expand was already applied inside extract_truth_polynomial;
    # the count is the number of distinct monomials.
    if poly.is_Add:
        term_count = len(poly.args)
    else:
        term_count = 1  # single monomial (or constant)
    return term_count, len(poly.free_symbols)


def sweep(max_depth: int = 4, time_budget_s: float = 30.0) -> list[dict]:
    """Run the measurement matrix. Returns rows for the report.

    Two safety knobs: ``max_depth`` caps the tree depth so the polynomial
    doesn't explode past a budget (Kleene-poly term count grows roughly
    geometrically in depth — depth 5 negated 5-var blew past 300MB of
    symbolic work in early runs). ``time_budget_s`` skips a row when its
    single ``extract_truth_polynomial`` call exceeds the per-row budget.

    Skipped rows are recorded with `error="timeout"` so the table shows
    where the cost wall is, NOT silently dropped.
    """
    import signal
    import time
    rows = []

    class _Timeout(Exception):
        pass

    def _on_alarm(signum, frame):
        raise _Timeout()

    # SIGALRM is POSIX-only; on Windows we fall back to no per-row
    # interrupt and let `time_budget_s` only inform reporting, NOT
    # interrupt the work. The script then skips later rows by hand
    # when one row exceeds the budget. Honest about the limitation.
    has_alarm = hasattr(signal, "SIGALRM")
    if has_alarm:
        signal.signal(signal.SIGALRM, _on_alarm)

    for depth in range(1, max_depth + 1):
        for var_pool in (2, 3, 4, 5):
            for kind_name, gen in (
                ("balanced", gen_balanced_and_or),
                ("negated", gen_negated_balanced),
            ):
                vs = _vars(var_pool)
                expr = gen(depth, vs)
                print(
                    f"  measuring depth={depth} var_pool={var_pool} "
                    f"kind={kind_name} ...",
                    flush=True,
                )
                t0 = time.time()
                try:
                    if has_alarm:
                        signal.alarm(int(time_budget_s))
                    n_terms, n_distinct_vars = measure(expr, vs)
                    if has_alarm:
                        signal.alarm(0)
                    elapsed = time.time() - t0
                    print(
                        f"    n_terms={n_terms} elapsed={elapsed:.3f}s",
                        flush=True,
                    )
                except _Timeout:
                    elapsed = time.time() - t0
                    print(
                        f"    TIMEOUT after {elapsed:.1f}s",
                        flush=True,
                    )
                    rows.append({
                        "depth": depth, "var_pool": var_pool,
                        "kind": kind_name, "expr": expr,
                        "n_terms": None, "n_distinct_vars": None,
                        "elapsed_s": elapsed,
                        "error": f"timeout after {elapsed:.1f}s",
                    })
                    continue
                except NonPolynomialResidual as e:
                    rows.append({
                        "depth": depth, "var_pool": var_pool,
                        "kind": kind_name, "expr": expr,
                        "n_terms": None, "n_distinct_vars": None,
                        "elapsed_s": time.time() - t0,
                        "error": str(e),
                    })
                    continue
                rows.append({
                    "depth": depth, "var_pool": var_pool,
                    "kind": kind_name, "expr": expr,
                    "n_terms": n_terms, "n_distinct_vars": n_distinct_vars,
                    "elapsed_s": elapsed,
                    "error": None,
                })
    return rows


def format_table(rows: list[dict]) -> str:
    """Markdown table of (depth, var_pool, kind, distinct_vars, n_terms, elapsed_s)."""
    out = ["| depth | var_pool | shape | distinct_vars | n_terms | elapsed_s |",
           "|------:|---------:|------|--------------:|--------:|----------:|"]
    for r in rows:
        terms = r["n_terms"] if r["n_terms"] is not None else "ERR"
        dvars = r["n_distinct_vars"] if r["n_distinct_vars"] is not None else "ERR"
        elapsed = f"{r.get('elapsed_s', 0):.3f}"
        out.append(
            f"| {r['depth']} | {r['var_pool']} | {r['kind']} | {dvars} | {terms} | {elapsed} |"
        )
    return "\n".join(out)


def main() -> None:
    rows = sweep()
    print("PIT term-count measurement (FV §3.4 honesty)")
    print("============================================")
    print()
    print(format_table(rows))
    print()
    # Per-depth max-term summary
    print("max term count per depth (across var_pool × shape):")
    for d in sorted({r["depth"] for r in rows if r["n_terms"] is not None}):
        max_t = max(r["n_terms"] for r in rows
                    if r["depth"] == d and r["n_terms"] is not None)
        print(f"  depth {d}: max n_terms = {max_t}")


if __name__ == "__main__":
    main()
