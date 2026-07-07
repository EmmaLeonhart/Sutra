"""grep -E on the neural computer — Unix-utility rung 11 (regex, via the NFA).

Extended-regex `grep -E PATTERN` prints the lines that contain a REGEX match. The
matcher is the on-substrate NFA (`neural_regex.py`, prerequisite P2): the pattern is
Thompson-constructed to an NFA at compile time and simulated per line on the
substrate (active-state buffer stepped by transition + epsilon-closure matmuls, char
classes selected by exact indicators). One NFA is built per pattern and reused
across lines; the host feeds each line's codepoints and reads accept at the boundary.

Supported subset: literals, `.`, `[...]`/`[^...]`/ranges, `* + ?`, `|`, `( )`,
`^ $` (see planning/sutra-spec/neural-regex-nfa.md). Verified against coreutils
`grep -E`. `-v` inverts.

Run: python experiments/ntm_ram/run_grep_regex.py           (self-test)
     <text> | python experiments/ntm_ram/run_grep_regex.py -E 'a.*z'
     <text> | python experiments/ntm_ram/run_grep_regex.py -v -E '[0-9]'
"""
from __future__ import annotations

import io
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from neural_regex import NeuralRegex       # noqa: E402


def _lines_of(text: str):
    if text == "":
        return []
    lines = text.split("\n")
    if text.endswith("\n"):
        lines = lines[:-1]
    return lines


def neural_grep_e(text: str, pattern: str, *, invert: bool = False) -> str:
    nfa = NeuralRegex(pattern)             # compile the NFA once, reuse per line
    out = [line for line in _lines_of(text) if nfa.search(line) != invert]
    return "".join(line + "\n" for line in out)


def _find_grep():
    import shutil
    for c in (r"C:\Program Files\Git\usr\bin\grep.exe",
              r"C:\Program Files (x86)\Git\usr\bin\grep.exe", "/usr/bin/grep", "/bin/grep"):
        if os.path.exists(c):
            return c
    return shutil.which("grep")


_GREP_EXE = _find_grep()


def real_grep_e(text: str, pattern: str, invert: bool = False) -> str:
    args = [_GREP_EXE, "-E"] + (["-v"] if invert else []) + [pattern]
    res = subprocess.run(args, input=text.encode("utf-8"), capture_output=True)
    return res.stdout.decode("utf-8").replace("\r\n", "\n")


# (text, pattern, invert)
CASES = [
    ("cat\ndog\ncatfish\nbird\n", "cat", False),
    ("color\ncolour\ncolouur\n", "colou?r", False),
    ("abc123\nxyz\nq7\n", "[0-9]+", False),
    ("grey\ngray\ngrry\n", "gr[ae]y", False),
    ("i love cats\ndogs rule\nbirds fly\n", "cat|dog", False),
    ("axz\naz\nabbz\naq\n", "ab*z", False),
    ("foobar\nxfoo\nfoo\n", "^foo", False),
    ("endbar\nbar\nbarx\n", "bar$", False),
    ("keep1\nnope\nkeep2\n", "[0-9]", True),      # invert
    ("anything\n", "a.*g", False),
]


def _self_test() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    ok = True
    for text, pat, inv in CASES:
        neural = neural_grep_e(text, pat, invert=inv)
        truth = real_grep_e(text, pat, inv)
        m = neural == truth
        ok = ok and m
        flag = "-v " if inv else ""
        print(f"[{'OK ' if m else 'FAIL'}] grep -E {flag}{pat!r:12} "
              f"neural={neural!r} truth={truth!r}")
    passed = sum(1 for t, p, i in CASES if neural_grep_e(t, p, invert=i) == real_grep_e(t, p, i))
    print(f"\n{'ALL PASS' if ok else 'FAILURES PRESENT'}: {passed}/{len(CASES)}")
    return 0 if ok else 1


def main() -> int:
    args = sys.argv[1:]
    if not args:
        return _self_test()
    invert = "-v" in args
    rest = [a for a in args if a not in ("-v", "-E")]
    sys.stdout.write(neural_grep_e(sys.stdin.read(), rest[0], invert=invert))
    return 0


if __name__ == "__main__":
    sys.exit(main())
