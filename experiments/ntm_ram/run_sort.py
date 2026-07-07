"""sort on the neural computer — Unix-utility rung 9 (substrate comparison network).

`sort` orders lines lexicographically (byte order, `LC_ALL=C`). The primitive is a
comparison, and every ordering decision runs on the substrate: `sort_head.su`'s
`line_less_step` streams two lines' codepoints and latches, at the first differing
position, whether A < B (packing decided/result into one complex recurring slot).
The host sequences the comparisons (the sorting network) and moves the lines — the
same division as the other rungs: substrate does the decision, host does the I/O.

This is Tier B's hard leap: a full-buffer comparison network whose comparator is
neural. Verified against coreutils `sort` (LC_ALL=C). Dim audit: model-free
(no basis_vector/embed) => semantic_dim=2 honest.

Run: python experiments/ntm_ram/run_sort.py            (self-test)
     <text> | python experiments/ntm_ram/run_sort.py --sort
"""
from __future__ import annotations

import functools
import io
import os
import subprocess
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(REPO, "sdk", "sutra-compiler"))
sys.path.insert(0, os.path.dirname(__file__))

from run_demo import compile_su            # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
_NS = compile_su(os.path.join(HERE, "sort_head.su"), semantic_dim=2)
_VSA = _NS["_VSA"]
_ACC = [k for k in _NS if k.endswith("_state")]
_PAD = -1.0   # sentinel below every real codepoint => shorter prefix-equal sorts first


def _real(v) -> float:
    return float(v[_VSA.semantic_dim + _VSA.AXIS_REAL])


def _line_less(a: str, b: str) -> bool:
    """Substrate lexicographic less-than: stream padded (a_i, b_i) pairs through
    line_less_step; the final return is 1 iff a < b."""
    for g in _ACC:
        _NS[g] = None
    n = max(len(a), len(b))
    if n == 0:
        return False
    res = 0.0
    for i in range(n):
        ca = float(ord(a[i])) if i < len(a) else _PAD
        cb = float(ord(b[i])) if i < len(b) else _PAD
        res = _real(_NS["line_less_step"](_VSA.make_real(ca), _VSA.make_real(cb)))
    return round(res) == 1


def _cmp(a: str, b: str) -> int:
    if _line_less(a, b):
        return -1
    if _line_less(b, a):
        return 1
    return 0


def _lines_of(text: str):
    if text == "":
        return []
    lines = text.split("\n")
    if text.endswith("\n"):
        lines = lines[:-1]
    return lines


def neural_sort(text: str) -> str:
    lines = sorted(_lines_of(text), key=functools.cmp_to_key(_cmp))
    return "".join(line + "\n" for line in lines)


def _find_sort():
    import shutil
    for c in (r"C:\Program Files\Git\usr\bin\sort.exe",
              r"C:\Program Files (x86)\Git\usr\bin\sort.exe", "/usr/bin/sort", "/bin/sort"):
        if os.path.exists(c):
            return c
    return shutil.which("sort")


_SORT_EXE = _find_sort()


def real_sort(text: str) -> str:
    env = dict(os.environ, LC_ALL="C")
    res = subprocess.run([_SORT_EXE], input=text.encode("utf-8"),
                         capture_output=True, env=env)
    return res.stdout.decode("utf-8").replace("\r\n", "\n")


CASES = [
    "banana\napple\ncherry\n",
    "3\n1\n2\n10\n",                  # lexical (not numeric): 1,10,2,3
    "b\na\nc\nb\na\n",
    "Apple\napple\nBanana\nbanana\n",  # case: uppercase before lowercase in C
    "same\nsame\n",
    "",
    "one\n",
    "ab\nabc\na\n",                    # prefix ordering
    "zebra\nyak\nx\nwolf\n",
]


def _self_test() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    ok = True
    for text in CASES:
        neural, truth = neural_sort(text), real_sort(text)
        m = neural == truth
        ok = ok and m
        print(f"[{'OK ' if m else 'FAIL'}] sort {text!r:34} "
              f"neural={neural!r} truth={truth!r}")
    passed = sum(1 for t in CASES if neural_sort(t) == real_sort(t))
    print(f"\n{'ALL PASS' if ok else 'FAILURES PRESENT'}: {passed}/{len(CASES)}")
    return 0 if ok else 1


def main() -> int:
    if "--sort" in sys.argv[1:]:
        sys.stdout.write(neural_sort(sys.stdin.read())); return 0
    return _self_test()


if __name__ == "__main__":
    sys.exit(main())
