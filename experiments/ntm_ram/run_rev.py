"""rev / tac on the neural computer — Unix-utility rung 6 (reverse permutation).

`rev` reverses the characters within each line; `tac` reverses the order of whole
lines. Both are PERMUTATIONS over a RAM buffer, and the permutation is computed on
the substrate by `rev_head.su`: a recurring cursor counts up 0,1,2,... and the head
emits `pointer = limit - cursor`, so the emitted address sequence runs DOWN from
`limit` to 0 — the reverse order — via one substrate subtraction per tick (not a
host counter). The host then serves the element at each substrate-emitted index
(RAM I/O for rev's codepoints; the line list for tac), exactly as the orchestrator
serves RAM at an emitted pointer in the forward heads.

`rev` is checked against a per-line reference (coreutils `rev` is util-linux, not
present in Git-for-Windows); `tac` is checked against the real coreutils `tac`.
Dim audit: model-free head (no basis_vector/embed) => semantic_dim=2 honest.

Run: python experiments/ntm_ram/run_rev.py             (self-test)
     <text> | python experiments/ntm_ram/run_rev.py --rev
     <text> | python experiments/ntm_ram/run_rev.py --tac
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
_NS = compile_su(os.path.join(HERE, "rev_head.su"), semantic_dim=2)
_VSA = _NS["_VSA"]
_ACC = [k for k in _NS if k.endswith("_state")]


def _real(v) -> float:
    return float(v[_VSA.semantic_dim + _VSA.AXIS_REAL])


def _reversed_indices(n: int):
    """The substrate-computed reverse permutation of 0..n-1: drives rev_head n
    times with limit=n-1 and collects the emitted pointers (n-1, n-2, ..., 0)."""
    for g in _ACC:
        _NS[g] = None
    limit = _VSA.make_real(float(n - 1))
    return [int(round(_real(_NS["rev_head"](limit)))) for _ in range(n)]


def _reverse(seq):
    """Reorder `seq` by the substrate reverse permutation."""
    idx = _reversed_indices(len(seq))
    return [seq[i] for i in idx]


def neural_rev(text: str) -> str:
    # reverse the codepoints within each newline-delimited segment
    segs = text.split("\n")
    return "\n".join("".join(_reverse(list(seg))) for seg in segs)


def _split_keepends(text: str):
    """Lines WITH their trailing newlines (tac reverses these as units)."""
    return text.splitlines(keepends=True)


def neural_tac(text: str) -> str:
    return "".join(_reverse(_split_keepends(text)))


def ref_rev(text: str) -> str:
    # coreutils rev: reverse each \n-delimited line's characters.
    return "\n".join(seg[::-1] for seg in text.split("\n"))


def _find_tac():
    import shutil
    for c in (r"C:\Program Files\Git\usr\bin\tac.exe", "/usr/bin/tac", "/bin/tac"):
        if os.path.exists(c):
            return c
    return shutil.which("tac")


_TAC_EXE = _find_tac()


def real_tac(text: str) -> str:
    res = subprocess.run([_TAC_EXE], input=text.encode("utf-8"), capture_output=True)
    return res.stdout.decode("utf-8").replace("\r\n", "\n")


CASES = [
    "hello\nworld\n",
    "abcdef\n",
    "one\ntwo\nthree\n",
    "no trailing newline",
    "",
    "a\nbb\nccc\n",
    "palindrome level\n",
]


def _self_test() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    ok = True
    for text in CASES:
        r, rr = neural_rev(text), ref_rev(text)
        t, tt = neural_tac(text), real_tac(text)
        rm, tm = r == rr, t == tt
        ok = ok and rm and tm
        print(f"[{'OK ' if rm else 'FAIL'}] rev {text!r:24} neural={r!r}")
        print(f"[{'OK ' if tm else 'FAIL'}] tac {text!r:24} neural={t!r} coreutils={tt!r}")
    print(f"\n{'ALL PASS' if ok else 'FAILURES PRESENT'}: "
          f"{2 * len(CASES)} rev/tac checks")
    return 0 if ok else 1


def main() -> int:
    args = sys.argv[1:]
    if "--rev" in args:
        sys.stdout.write(neural_rev(sys.stdin.read())); return 0
    if "--tac" in args:
        sys.stdout.write(neural_tac(sys.stdin.read())); return 0
    return _self_test()


if __name__ == "__main__":
    sys.exit(main())
