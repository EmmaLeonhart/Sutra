"""Native recursion via memoization (Phase 5.5 tier 4, step 4a).

Sutra has no native runtime recursion (a function can't call itself on the substrate). Tier 4's
answer: a multiple recursion is computed by a MEMOIZING LOOP — a `while_loop` (→ recurrent neurons,
native) that carries the running results as state, instead of a call stack. This test demonstrates
the native TARGET that step 4b will generate automatically: an iterative/tabulated `fib` (the memo
is the rolling last-two values carried as loop state) compiled + run on the real substrate via the
`sutrac` pipeline, producing fib(n) == ground truth — no recursion, no WASM.
"""
from __future__ import annotations

import io
import contextlib
import pathlib
import re
import sys

import pytest


def _gt_fib(n):
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a


# fib(N) as a memoizing while_loop: state (i, a, b, n); each step rolls (a, b) <- (b, a+b).
# This is the native loop form tier-4's transform must emit for fib (the memo is the last two
# results carried as recurrent `slot` state); the bound n is threaded invariant.
_FIB_LOOP = """\
while_loop _fibloop(i < n, int i = 0, int a = 0, int b = 1, int n = {N}) {{
    int t = a + b;
    a = b;
    b = t;
    i = i + 1;
}}
function int main() {{
    int n = {N};
    int i = 0;
    int a = 0;
    int b = 1;
    slot int _i = i;
    slot int _a = a;
    slot int _b = b;
    slot int _n = n;
    loop _fibloop(i < n, _i, _a, _b, _n);
    return _a;
}}
"""


def _run_su(src, tmp_path):
    pytest.importorskip("torch")
    repo = pathlib.Path(__file__).resolve().parents[3]
    compiler_src = repo / "sdk" / "sutra-compiler"
    if str(compiler_src) not in sys.path:
        sys.path.insert(0, str(compiler_src))
    from sutra_compiler.__main__ import main
    p = tmp_path / "fibloop.su"
    p.write_text(src, encoding="utf-8")
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        # --max-preeval-depth 0 keeps tier-3 pre-eval out of the way (this is a loop, not a
        # constant-arg recursive call) so we measure the loop's own substrate result.
        rc = main(["--run", "--max-preeval-depth", "0", str(p)])
    assert rc == 0, f"sutrac --run failed (rc={rc})"
    m = re.search(r"-?\d+(?:\.\d+)?", buf.getvalue())
    assert m, f"no numeric output: {buf.getvalue()!r}"
    return round(float(m.group()))


@pytest.mark.parametrize("n", [0, 1, 2, 5, 10, 15])
def test_fib_runs_natively_as_a_memoizing_loop(n, tmp_path):
    """fib(n) computed by the memoizing while_loop runs on the substrate == ground truth — the
    tier-4 native-recursion target (no call stack, no WASM)."""
    got = _run_su(_FIB_LOOP.format(N=n), tmp_path)
    assert got == _gt_fib(n), f"native-loop fib({n}) -> {got}, expected {_gt_fib(n)}"


def _gt_trib(n):
    t = [0, 1, 2]
    for i in range(3, n + 1):
        t.append(t[-1] + t[-2] + t[-3])
    return t[n]


# RECURSIVE source — Sutra has no native runtime recursion, so without the tier-4 transform this
# can't run on the substrate (recursive if/else). The default-on tabulation pass rewrites it into
# the memoizing while_loop automatically.
_FIB_RECURSIVE = ("function int fib(int n) { if (n < 2) { return n; } return fib(n-1) + fib(n-2); }\n"
                  "function int main() { return fib(@N@); }\n")
_TRIB_RECURSIVE = ("function int trib(int n) { if (n < 3) { return n; } "
                   "return trib(n-1) + trib(n-2) + trib(n-3); }\n"
                   "function int main() { return trib(@N@); }\n")


@pytest.mark.parametrize("n", [0, 1, 2, 5, 8, 12])
def test_recursive_fib_made_native_by_tabulation(n, tmp_path):
    """The AUTOMATIC tier-4 transform: a RECURSIVE fib (which Sutra can't run natively) is rewritten
    into the memoizing while_loop by the default-on tabulation pass and runs == ground truth on the
    substrate via the real `sutrac --run` pipeline — no recursion, no WASM."""
    got = _run_su(_FIB_RECURSIVE.replace("@N@", str(n)), tmp_path)
    assert got == _gt_fib(n), f"tabulated recursive fib({n}) -> {got}, expected {_gt_fib(n)}"


@pytest.mark.parametrize("n", [0, 1, 2, 3, 6, 9])
def test_recursive_tribonacci_made_native_by_tabulation(n, tmp_path):
    """Tribonacci (3 recursive calls) auto-tabulated + run natively == ground truth."""
    got = _run_su(_TRIB_RECURSIVE.replace("@N@", str(n)), tmp_path)
    assert got == _gt_trib(n), f"tabulated recursive trib({n}) -> {got}, expected {_gt_trib(n)}"
