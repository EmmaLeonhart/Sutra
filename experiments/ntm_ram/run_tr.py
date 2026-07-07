"""tr on the neural computer — Unix-utility rung 5 (substrate codebook map).

`tr SET1 SET2` translates each input codepoint that appears in SET1 to the paired
codepoint in SET2; `tr -d SET1` deletes codepoints in SET1. This is a codebook
lookup — Sutra's strength — done on the substrate with EXACT codepoint indicators:

    out(c) = Σ_i is_cp(c, key_i) * val_i  +  c * (1 - Σ_i is_cp(c, key_i))

where is_cp(c, k) = relu(1 - |c - k|) is exactly 1 at k and a hard 0 elsewhere.
So a matched codepoint becomes its paired value and an unmatched one passes
through unchanged; for delete, out(c) = c * (1 - Σ is_cp(c, key_i)) masks matched
codepoints to zero (dropped at decode). The whole per-byte map is one substrate
expression (a weighted sum of exact indicators); the host streams bytes in
(addressing = I/O) and drives the codebook table iteration, the substrate does the
match + select. The codebook is baked into a generated `.su` program (compiled once
per translation) — the codepoints of SET1/SET2 are the codebook.

Verified against coreutils `tr`. Dim audit: model-free (no basis_vector/embed) =>
semantic_dim=2 honest.

Run: python experiments/ntm_ram/run_tr.py                    (self-test)
     <text> | python experiments/ntm_ram/run_tr.py a-z A-Z
     <text> | python experiments/ntm_ram/run_tr.py -d 0-9
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


def expand_set(spec: str) -> str:
    """Expand a tr SET spec's `a-z` ranges to explicit characters (the common
    subset of tr's set syntax; escapes/classes like [:alpha:] are not handled)."""
    out, i = [], 0
    while i < len(spec):
        if i + 2 < len(spec) and spec[i + 1] == "-":
            lo, hi = ord(spec[i]), ord(spec[i + 2])
            out.extend(chr(c) for c in range(lo, hi + 1))
            i += 3
        else:
            out.append(spec[i]); i += 1
    return "".join(out)


def _pairs(set1: str, set2: str):
    """coreutils pads SET2 to SET1's length by repeating SET2's last char."""
    s1, s2 = expand_set(set1), expand_set(set2)
    if not s2:
        return []
    s2 = s2 + s2[-1] * max(0, len(s1) - len(s2))
    return list(zip(s1, s2[:len(s1)]))


def _codebook_su(keys, vals) -> str:
    """Generate a substrate codebook-map program for the given key->val codepoints
    (delete = empty vals). One expression: weighted sum of exact indicators."""
    matched = " + ".join(f"is_cp(c, make_real({ord(k)}.0))" for k in keys) or "make_real(0.0)"
    if vals:
        mapped = " + ".join(
            f"is_cp(c, make_real({ord(k)}.0)) * make_real({ord(v)}.0)"
            for k, v in zip(keys, vals)) or "make_real(0.0)"
    else:
        mapped = "make_real(0.0)"    # -d: matched chars map to 0 (deleted)
    return (
        "function vector is_cp(vector served, vector center) {\n"
        "    vector d = served - center;\n"
        "    vector ad = make_real(abs(d));\n"
        "    vector tri = make_real(1.0) - ad;\n"
        "    vector at = make_real(abs(tri));\n"
        "    return (tri + at) * make_real(0.5);\n"
        "}\n"
        "function vector tr_map(vector c) {\n"
        f"    vector matched = {matched};\n"
        f"    vector mapped = {mapped};\n"
        "    return mapped + c * (make_real(1.0) - matched);\n"
        "}\n"
        "function string main() { return \"ok\"; }\n"
    )


def _compile(src: str):
    lx = Lexer(src, file="<tr>")
    ast = Parser(lx.tokenize(), file="<tr>", diagnostics=lx.diagnostics).parse_module()
    if lx.diagnostics.has_errors():
        raise RuntimeError(f"parse errors: {list(lx.diagnostics)}")
    ns: dict = {}
    exec(translate_module(ast, llm_model="none", runtime_dim=2), ns)
    return ns


def neural_tr(text: str, set1: str, set2: str = "", *, delete: bool = False) -> str:
    if delete:
        keys, vals = expand_set(set1), ""
    else:
        pairs = _pairs(set1, set2)
        keys = "".join(k for k, _ in pairs)
        vals = "".join(v for _, v in pairs)
    ns = _compile(_codebook_su(keys, vals))
    vsa = ns["_VSA"]

    def real(v):
        return float(v[vsa.semantic_dim + vsa.AXIS_REAL])
    out = []
    for ch in text:
        code = int(round(real(ns["tr_map"](vsa.make_real(float(ord(ch)))))))
        if code > 0:
            out.append(chr(code))
    return "".join(out)


def _find_tr():
    import shutil
    for c in (r"C:\Program Files\Git\usr\bin\tr.exe",
              r"C:\Program Files (x86)\Git\usr\bin\tr.exe", "/usr/bin/tr", "/bin/tr"):
        if os.path.exists(c):
            return c
    found = shutil.which("tr")
    if found:
        return found
    raise RuntimeError("no real `tr` binary for ground truth")


_TR_EXE = _find_tr()


def real_tr(text, args):
    res = subprocess.run([_TR_EXE] + args, input=text.encode("utf-8"), capture_output=True)
    return res.stdout.decode("utf-8").replace("\r\n", "\n")


# (text, args-for-real-tr, kwargs-for-neural_tr)
CASES = [
    ("hello world\n", ["a-z", "A-Z"], ("a-z", "A-Z", {})),
    ("Hello World\n", ["A-Z", "a-z"], ("A-Z", "a-z", {})),
    ("abcdef\n", ["abc", "xyz"], ("abc", "xyz", {})),
    ("the quick brown fox\n", ["aeiou", "AEIOU"], ("aeiou", "AEIOU", {})),
    ("phone: 555-1234\n", ["-d", "0-9"], ("0-9", "", {"delete": True})),
    ("a1b2c3\n", ["-d", "abc"], ("abc", "", {"delete": True})),
    ("map short set\n", ["a-z", "X"], ("a-z", "X", {})),   # SET2 padding
]


def _self_test() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    ok = True
    for text, real_args, (s1, s2, kw) in CASES:
        neural = neural_tr(text, s1, s2, **kw)
        truth = real_tr(text, real_args)
        m = neural == truth
        ok = ok and m
        print(f"[{'OK ' if m else 'FAIL'}] tr {' '.join(real_args):10} "
              f"{text!r:24} neural={neural!r} truth={truth!r}")
    passed = sum(1 for t, ra, (s1, s2, kw) in CASES
                 if neural_tr(t, s1, s2, **kw) == real_tr(t, ra))
    print(f"\n{'ALL PASS' if ok else 'FAILURES PRESENT'}: {passed}/{len(CASES)}")
    return 0 if ok else 1


def main() -> int:
    args = sys.argv[1:]
    if not args:
        return _self_test()
    if args[0] == "-d":
        sys.stdout.write(neural_tr(sys.stdin.read(), args[1], delete=True))
    else:
        sys.stdout.write(neural_tr(sys.stdin.read(), args[0], args[1] if len(args) > 1 else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
