"""cut on the neural computer — Unix-utility rung 7 (per-column gated emit).

`cut -c LIST` outputs the selected CHARACTER columns of each line (1-indexed;
LIST like `2-4`, `1,3`, `3-`, `-2`). It is a gated stream filter like head/tail,
but the gate keys on the COLUMN index within the current line instead of the line
index: a recurring column counter increments per character and RESETS at each
newline, and each character is emitted (`served * gate`) iff its column is in the
selected set. Newlines always pass and reset the counter. The column counter, the
range membership, and the gate are all substrate tensor ops (exact `ge1` integer
steps + the exact newline indicator) — no host branch on the content. The selected
ranges are baked into a generated `.su` (their bounds are the only per-invocation
data); the host streams bytes, the substrate does the count + gate + select.

Verified against coreutils `cut -c`. Dim audit: model-free (no basis_vector/embed)
=> semantic_dim=2 honest.

Run: python experiments/ntm_ram/run_cut.py               (self-test)
     <text> | python experiments/ntm_ram/run_cut.py -c 2-4
"""
from __future__ import annotations

import io
import os
import subprocess
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(REPO, "sdk", "sutra-compiler"))
sys.path.insert(0, os.path.dirname(__file__))

from sutra_compiler.lexer import Lexer                          # noqa: E402
from sutra_compiler.parser import Parser                        # noqa: E402
from sutra_compiler.codegen_pytorch import translate_module     # noqa: E402

_BIG = 1_000_000  # stands in for an open-ended range bound (`3-`, `-2`)


def parse_ranges(spec: str):
    """Parse a cut -c LIST like `2-4,7,9-` into [(lo, hi), ...] (1-indexed,
    inclusive; open ends use 1 / _BIG)."""
    ranges = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            lo, hi = part.split("-", 1)
            ranges.append((int(lo) if lo else 1, int(hi) if hi else _BIG))
        else:
            ranges.append((int(part), int(part)))
    return ranges


def _cut_su(ranges) -> str:
    # in_range(col, lo, hi) = ge1(col-lo+1) * ge1(hi-col+1); membership = OR over
    # ranges via ge1(sum). gate = is_nl + (1-is_nl)*membership.
    terms = " + ".join(
        f"ge1(col_cur - make_real({lo}.0) + make_real(1.0)) "
        f"* ge1(make_real({hi}.0) - col_cur + make_real(1.0))"
        for lo, hi in ranges) or "make_real(0.0)"
    return (
        "function vector is_cp(vector served, vector center) {\n"
        "    vector d = served - center;\n"
        "    vector tri = make_real(1.0) - make_real(abs(d));\n"
        "    return (tri + make_real(abs(tri))) * make_real(0.5);\n"
        "}\n"
        "function vector relu(vector x) { return (x + make_real(abs(x))) * make_real(0.5); }\n"
        "function vector ge1(vector x) {\n"
        "    vector r = relu(x);\n"
        "    return make_real(1.0) - relu(make_real(1.0) - r);\n"
        "}\n"
        "function vector cut_head(vector served) {\n"
        "    recurring vector col = make_real(0.0);\n"
        "    vector is_nl = is_cp(served, make_real(10.0));\n"
        "    vector one_m_nl = make_real(1.0) - is_nl;\n"
        "    vector col_cur = col + one_m_nl;\n"
        f"    vector membership = ge1({terms});\n"
        "    vector gate = is_nl + one_m_nl * membership;\n"
        "    vector out = served * gate;\n"
        "    vector col_next = one_m_nl * col_cur;\n"
        "    recur(col_next);\n"
        "    return out;\n"
        "}\n"
        "function string main() { return \"ok\"; }\n"
    )


def _compile(src: str):
    lx = Lexer(src, file="<cut>")
    ast = Parser(lx.tokenize(), file="<cut>", diagnostics=lx.diagnostics).parse_module()
    if lx.diagnostics.has_errors():
        raise RuntimeError(f"parse errors: {list(lx.diagnostics)}")
    ns: dict = {}
    exec(translate_module(ast, llm_model="none", runtime_dim=2), ns)
    return ns


def neural_cut(text: str, spec: str) -> str:
    ns = _compile(_cut_su(parse_ranges(spec)))
    vsa = ns["_VSA"]
    for g in [k for k in ns if k.endswith("_state")]:
        ns[g] = None

    def real(v):
        return float(v[vsa.semantic_dim + vsa.AXIS_REAL])
    out = []
    for ch in text:
        code = int(round(real(ns["cut_head"](vsa.make_real(float(ord(ch)))))))
        if code > 0:
            out.append(chr(code))
    return "".join(out)


def _find_cut():
    import shutil
    for c in (r"C:\Program Files\Git\usr\bin\cut.exe",
              r"C:\Program Files (x86)\Git\usr\bin\cut.exe", "/usr/bin/cut", "/bin/cut"):
        if os.path.exists(c):
            return c
    return shutil.which("cut")


_CUT_EXE = _find_cut()


def real_cut(text: str, spec: str) -> str:
    res = subprocess.run([_CUT_EXE, "-c", spec], input=text.encode("utf-8"),
                         capture_output=True)
    return res.stdout.decode("utf-8").replace("\r\n", "\n")


CASES = [
    ("abcdef\nghijkl\n", "2-4"),
    ("hello world\n", "1-5"),
    ("one\ntwo\nthree\n", "2"),
    ("abcdefgh\n", "3-"),
    ("abcdefgh\n", "-3"),
    ("columns\nof text\n", "1,3,5"),
    ("short\nlongerline\n", "4-6"),
    ("", "1-3"),
]


def _self_test() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    ok = True
    for text, spec in CASES:
        neural, truth = neural_cut(text, spec), real_cut(text, spec)
        m = neural == truth
        ok = ok and m
        print(f"[{'OK ' if m else 'FAIL'}] cut -c {spec:6} {text!r:22} "
              f"neural={neural!r} truth={truth!r}")
    passed = sum(1 for t, s in CASES if neural_cut(t, s) == real_cut(t, s))
    print(f"\n{'ALL PASS' if ok else 'FAILURES PRESENT'}: {passed}/{len(CASES)}")
    return 0 if ok else 1


def main() -> int:
    args = sys.argv[1:]
    if "-c" in args:
        spec = args[args.index("-c") + 1]
        sys.stdout.write(neural_cut(sys.stdin.read(), spec))
        return 0
    return _self_test()


if __name__ == "__main__":
    sys.exit(main())
