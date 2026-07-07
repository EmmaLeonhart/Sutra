"""uniq on the neural computer — Unix-utility rung 8 (substrate line comparison).

`uniq` collapses ADJACENT identical lines into one. The core operation is a
prev-vs-current line-equality test, and it runs on the substrate (`uniq_head.su`):
`line_cmp` streams the two lines' codepoints position by position and accumulates
a MISMATCH count — `+= (1 - is_cp(a_i, b_i))` with is_cp the exact codepoint
indicator (1 iff the codepoints are equal). The host pads the shorter line to the
longer length with a sentinel value no real codepoint equals, so a length
difference also registers as mismatches. mismatch == 0 iff the lines are
identical; the host reads that count at the boundary and drops a line iff it
equals its predecessor. This is Tier B's entry — the first rung that COMPARES two
buffered pieces of content rather than transforming one stream.

Verified against coreutils `uniq`. Dim audit: model-free (no basis_vector/embed)
=> semantic_dim=2 honest.

Run: python experiments/ntm_ram/run_uniq.py            (self-test)
     <text> | python experiments/ntm_ram/run_uniq.py --uniq
"""
from __future__ import annotations

import io
import os
import subprocess
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(REPO, "sdk", "sutra-compiler"))
sys.path.insert(0, os.path.dirname(__file__))

from run_demo import compile_su            # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
_NS = compile_su(os.path.join(HERE, "uniq_head.su"), semantic_dim=2)
_VSA = _NS["_VSA"]
_ACC = [k for k in _NS if k.endswith("_state")]
_PAD = -1.0   # sentinel codepoint no real character equals


def _real(v) -> float:
    return float(v[_VSA.semantic_dim + _VSA.AXIS_REAL])


def _lines_equal(a: str, b: str) -> bool:
    """Substrate equality test: stream padded (a_i, b_i) pairs through line_cmp,
    read the final mismatch count. mismatch == 0 iff a == b."""
    for g in _ACC:
        _NS[g] = None
    n = max(len(a), len(b))
    mismatch = 0.0
    for i in range(n):
        ca = float(ord(a[i])) if i < len(a) else _PAD
        cb = float(ord(b[i])) if i < len(b) else _PAD
        mismatch = _real(_NS["line_cmp"](_VSA.make_real(ca), _VSA.make_real(cb)))
    return round(mismatch) == 0


def _lines_of(text: str):
    """uniq's line model: \\n-separated lines; a trailing \\n does not add an empty
    line, and an unterminated last line is still a line."""
    if text == "":
        return []
    lines = text.split("\n")
    if text.endswith("\n"):
        lines = lines[:-1]
    return lines


def neural_uniq(text: str) -> str:
    out = []
    prev = None
    for line in _lines_of(text):
        if prev is None or not _lines_equal(line, prev):
            out.append(line)
        prev = line
    # uniq terminates every emitted line with a newline.
    return "".join(line + "\n" for line in out)


def _find_uniq():
    import shutil
    for c in (r"C:\Program Files\Git\usr\bin\uniq.exe",
              r"C:\Program Files (x86)\Git\usr\bin\uniq.exe", "/usr/bin/uniq", "/bin/uniq"):
        if os.path.exists(c):
            return c
    return shutil.which("uniq")


_UNIQ_EXE = _find_uniq()


def real_uniq(text: str) -> str:
    res = subprocess.run([_UNIQ_EXE], input=text.encode("utf-8"), capture_output=True)
    return res.stdout.decode("utf-8").replace("\r\n", "\n")


CASES = [
    "a\na\nb\nb\nb\nc\na\n",
    "one\none\ntwo\n",
    "no dups here\nall distinct\nlines\n",
    "same\nsame\nsame\n",
    "",
    "x\n",
    "ab\nabc\nabc\nab\n",             # length-difference adjacency
    "trailing\ntrailing",            # no final newline
]


def _self_test() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    ok = True
    for text in CASES:
        neural, truth = neural_uniq(text), real_uniq(text)
        m = neural == truth
        ok = ok and m
        print(f"[{'OK ' if m else 'FAIL'}] uniq {text!r:32} "
              f"neural={neural!r} truth={truth!r}")
    passed = sum(1 for t in CASES if neural_uniq(t) == real_uniq(t))
    print(f"\n{'ALL PASS' if ok else 'FAILURES PRESENT'}: {passed}/{len(CASES)}")
    return 0 if ok else 1


def main() -> int:
    if "--uniq" in sys.argv[1:]:
        sys.stdout.write(neural_uniq(sys.stdin.read())); return 0
    return _self_test()


if __name__ == "__main__":
    sys.exit(main())
