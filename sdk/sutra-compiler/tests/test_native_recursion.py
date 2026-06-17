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
