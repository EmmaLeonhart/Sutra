"""head / tail on the neural computer — Unix-utility rung 4 (line-gated filters).

`head -n N` emits the first N lines, `tail -n N` the last N. Both are the same
substrate machine (`filter_heads.su`): a recurring line accumulator plus an EXACT
integer gate that masks each emitted codepoint by whether the current line index
is in range. The emitted codepoint is `served * gate` (gate in {0,1}); the
orchestrator collects the stream and drops the masked-out zeros. Line index and
gate are substrate tensor ops — no host branch on the content.

- head: gate = (line_index < N), so the first N lines (through the N-th newline)
  pass and the rest are masked.
- tail: two passes. Pass 1 counts the total lines on the substrate
  (`count_lines`); the host reads it at the boundary and computes the start offset
  `start = total - N` (pointer arithmetic at the wire, plus a +1 correction when
  the input does not end in a newline — a last-byte inspection, I/O); pass 2 gates
  `line_index >= start`.

Verified against coreutils `head` / `tail`. Dim audit: model-free heads
(no basis_vector/embed) => semantic_dim=2 honest.

Run: python experiments/ntm_ram/run_head_tail.py               (self-test)
     <text> | python experiments/ntm_ram/run_head_tail.py --head -n 3
     <text> | python experiments/ntm_ram/run_head_tail.py --tail -n 3
"""
from __future__ import annotations

import io
import os
import subprocess
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(REPO, "sdk", "sutra-compiler"))
sys.path.insert(0, os.path.dirname(__file__))

from ram_device import RamDevice          # noqa: E402
from run_demo import compile_su            # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
_NS = compile_su(os.path.join(HERE, "filter_heads.su"), semantic_dim=2)
_VSA = _NS["_VSA"]
_ACC_GLOBALS = [k for k in _NS if k.endswith("_state")]


def _real(v) -> float:
    return float(v[_VSA.semantic_dim + _VSA.AXIS_REAL])


def _reset():
    for g in _ACC_GLOBALS:
        _NS[g] = None


def _feed_ram(text: str) -> RamDevice:
    ram = RamDevice(_VSA, size=max(8, len(text) + 2))
    ram.load_text(text, base=0, terminator=True)
    return ram


def _gated_emit(fn_name: str, text: str, n: int) -> str:
    """Stream `text` through a gated filter head with budget/offset `n`; collect
    the emitted codepoints, dropping masked-out zeros."""
    _reset()
    ram = _feed_ram(text)
    nv = _VSA.make_real(float(n))
    out = []
    for addr in range(len(text)):
        code = int(round(_real(_NS[fn_name](ram.read_vector(addr), nv))))
        if code > 0:
            out.append(chr(code))
    return "".join(out)


def _substrate_line_total(text: str) -> int:
    """Pass-1 line total on the substrate (newline accumulator), plus the +1
    correction for a final line with no trailing newline (last-byte inspection)."""
    _reset()
    ram = _feed_ram(text)
    total = 0.0
    for addr in range(len(text)):
        total = _real(_NS["count_lines"](ram.read_vector(addr)))
    newlines = int(round(total))
    return newlines + (1 if text and text[-1] != "\n" else 0)


def neural_head(text: str, n: int) -> str:
    return _gated_emit("head_filter", text, n)


def neural_tail(text: str, n: int) -> str:
    total = _substrate_line_total(text)
    start = max(0, total - n)
    return _gated_emit("tail_filter", text, start)


def _find(exe):
    import shutil
    for c in (fr"C:\Program Files\Git\usr\bin\{exe}.exe",
              fr"C:\Program Files (x86)\Git\usr\bin\{exe}.exe",
              f"/usr/bin/{exe}", f"/bin/{exe}"):
        if os.path.exists(c):
            return c
    found = shutil.which(exe)
    if found:
        return found
    raise RuntimeError(f"no real `{exe}` binary for ground truth")


_HEAD_EXE, _TAIL_EXE = _find("head"), _find("tail")


def _real_util(exe_path, text, n):
    res = subprocess.run([exe_path, "-n", str(n)], input=text.encode("utf-8"),
                         capture_output=True)
    return res.stdout.decode("utf-8").replace("\r\n", "\n")


CASES = [
    "a\nb\nc\nd\ne\n",
    "one\ntwo\nthree\n",
    "no final newline\nsecond",       # unterminated last line
    "single line\n",
    "",
    "x\n\n\ny\n",                       # blank lines
]
NS = [0, 1, 2, 3, 5, 9]


def _self_test() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    ok = True
    for text in CASES:
        for n in NS:
            h, ht = neural_head(text, n), _real_util(_HEAD_EXE, text, n)
            t, tt = neural_tail(text, n), _real_util(_TAIL_EXE, text, n)
            hm, tm = h == ht, t == tt
            ok = ok and hm and tm
            if not (hm and tm):
                print(f"[FAIL] {text!r:24} n={n} head neural={h!r} truth={ht!r} | "
                      f"tail neural={t!r} truth={tt!r}")
    total = len(CASES) * len(NS) * 2
    print(f"{'ALL PASS' if ok else 'FAILURES PRESENT'}: {total} head/tail checks "
          f"across {len(CASES)} inputs x {len(NS)} N values")
    return 0 if ok else 1


def main() -> int:
    args = sys.argv[1:]
    n = 10
    if "-n" in args:
        n = int(args[args.index("-n") + 1])
    if "--head" in args:
        sys.stdout.write(neural_head(sys.stdin.read(), n)); return 0
    if "--tail" in args:
        sys.stdout.write(neural_tail(sys.stdin.read(), n)); return 0
    return _self_test()


if __name__ == "__main__":
    sys.exit(main())
