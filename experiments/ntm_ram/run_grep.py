"""grep on the neural computer — Unix-utility rung 10 (substrate substring match).

Fixed-string `grep PATTERN` prints the lines that CONTAIN the pattern. Containment
is a substring match and the match test runs on the substrate (`grep_head.su`): for
each candidate window (the pattern aligned at a start position in the line),
`match_step` streams the (line_char, pattern_char) pairs and accumulates a PRODUCT
of exact codepoint indicators — `*= is_cp(line_c, pat_c)` — which stays 1 only while
every char matches and collapses to 0 at the first mismatch. So each window's
returned value is 1 iff the window equals the pattern. The host slides the window
(I/O addressing) and OR's the per-window results into "line contains pattern"; the
per-window all-equal attention is the substrate work.

Fixed-string only (`grep -F` semantics; the regex/NFA matcher, prerequisite P2, is a
later rung). Supports `-v` (invert). Verified against coreutils `grep -F`. Dim
audit: model-free (no basis_vector/embed) => semantic_dim=2 honest.

Run: python experiments/ntm_ram/run_grep.py             (self-test)
     <text> | python experiments/ntm_ram/run_grep.py PATTERN
     <text> | python experiments/ntm_ram/run_grep.py -v PATTERN
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
_NS = compile_su(os.path.join(HERE, "grep_head.su"), semantic_dim=2)
_VSA = _NS["_VSA"]
_ACC = [k for k in _NS if k.endswith("_state")]


def _real(v) -> float:
    return float(v[_VSA.semantic_dim + _VSA.AXIS_REAL])


def _window_matches(line: str, pat: str, s: int) -> bool:
    """Substrate all-equal test for the window line[s:s+len(pat)] vs pat: the
    product of exact indicators is 1 iff every character matches."""
    for g in _ACC:
        _NS[g] = None
    prod = 1.0
    for j in range(len(pat)):
        prod = _real(_NS["match_step"](
            _VSA.make_real(float(ord(line[s + j]))),
            _VSA.make_real(float(ord(pat[j])))))
    return round(prod) == 1


def _contains(line: str, pat: str) -> bool:
    if pat == "":
        return True                       # empty pattern matches every line
    if len(pat) > len(line):
        return False
    return any(_window_matches(line, pat, s)
               for s in range(len(line) - len(pat) + 1))


def _lines_of(text: str):
    if text == "":
        return []
    lines = text.split("\n")
    if text.endswith("\n"):
        lines = lines[:-1]
    return lines


def neural_grep(text: str, pat: str, *, invert: bool = False) -> str:
    out = [line for line in _lines_of(text) if _contains(line, pat) != invert]
    return "".join(line + "\n" for line in out)


def _find_grep():
    import shutil
    for c in (r"C:\Program Files\Git\usr\bin\grep.exe",
              r"C:\Program Files (x86)\Git\usr\bin\grep.exe", "/usr/bin/grep", "/bin/grep"):
        if os.path.exists(c):
            return c
    return shutil.which("grep")


_GREP_EXE = _find_grep()


def real_grep(text: str, pat: str, invert: bool = False) -> str:
    args = [_GREP_EXE, "-F"] + (["-v"] if invert else []) + [pat]
    res = subprocess.run(args, input=text.encode("utf-8"), capture_output=True)
    return res.stdout.decode("utf-8").replace("\r\n", "\n")


# (text, pattern, invert)
CASES = [
    ("foobar\nbaz\nfoo\nqux\n", "foo", False),
    ("apple\nbanana\ncherry\n", "an", False),
    ("hit\nmiss\nhit again\n", "hit", False),
    ("one two\nthree four\n", "two", False),
    ("nomatch here\n", "xyz", False),
    ("keep\ndrop\nkeep\n", "keep", True),          # invert
    ("aaa\naa\na\n", "aa", False),                  # overlapping windows
    ("end match end\n", "end", False),
    ("", "any", False),
]


def _self_test() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    ok = True
    for text, pat, inv in CASES:
        neural, truth = neural_grep(text, pat, invert=inv), real_grep(text, pat, inv)
        m = neural == truth
        ok = ok and m
        flag = "-v " if inv else ""
        print(f"[{'OK ' if m else 'FAIL'}] grep -F {flag}{pat!r:8} {text!r:26} "
              f"neural={neural!r} truth={truth!r}")
    passed = sum(1 for t, p, i in CASES if neural_grep(t, p, invert=i) == real_grep(t, p, i))
    print(f"\n{'ALL PASS' if ok else 'FAILURES PRESENT'}: {passed}/{len(CASES)}")
    return 0 if ok else 1


def main() -> int:
    args = sys.argv[1:]
    if not args:
        return _self_test()
    invert = "-v" in args
    pats = [a for a in args if a != "-v"]
    sys.stdout.write(neural_grep(sys.stdin.read(), pats[0], invert=invert))
    return 0


if __name__ == "__main__":
    sys.exit(main())
