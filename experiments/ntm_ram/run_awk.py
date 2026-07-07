"""awk on the neural computer — Unix-utility rung 13 (common subset).

awk is a whole language; this rung builds its SUBSTRATE core — field splitting —
plus a host interpreter for the common one-liner subset, honestly scoped. Each
record's `$N` field and `NF` are extracted on the substrate (`field_head.su` for
the default whitespace FS, `field_delim_head.su` for `-F<c>`): a recurring field
counter (exact, via the wc word-transition / delimiter-count logic) drives an
exact-indicator gate that emits the characters of the requested field. Patterns
`/regex/` reuse the on-substrate NFA (`neural_regex.py`). The host interprets the
`print` statement and tracks `NR` (record number — I/O bookkeeping).

Supported subset (verified vs coreutils/gawk `awk`):
  patterns : /regex/ | NR==k | NR>k | NR<k | (empty = every record)
  action   : { print <args> } | (empty = print $0)
  print arg: $0 | $N | $NF | NF | NR | "string literal"   (comma => OFS space)
  options  : -F<c>  (single-char field separator)

NOT supported (named, not silently dropped): user variables, arithmetic
expressions, BEGIN/END blocks, arrays, functions, printf, multiple rules, field
assignment. Those are the "whole language" that would make the Sutra compiler the
engine — far out (queue.md Tier C).
"""
from __future__ import annotations

import io
import os
import re as _re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run_demo import compile_su            # noqa: E402
from neural_regex import NeuralRegex       # noqa: E402

_HERE = os.path.dirname(os.path.abspath(__file__))
_WS = compile_su(os.path.join(_HERE, "field_head.su"), semantic_dim=2)
_FS = compile_su(os.path.join(_HERE, "field_delim_head.su"), semantic_dim=2)
_VSA = _WS["_VSA"]
_WS_ACC = [k for k in _WS if k.endswith("_state")]
_FS_ACC = [k for k in _FS if k.endswith("_state")]


def _real(v) -> float:
    return float(v[_VSA.semantic_dim + _VSA.AXIS_REAL])


def _fields_ws(line: str):
    """All whitespace-separated fields of `line`, extracted on the substrate."""
    for g in _WS_ACC:
        _WS[g] = None
    nf = 0
    for ch in line:
        nf = _real(_WS["field_count"](_VSA.make_real(float(ord(ch)))))
    nf = round(nf)
    fields = []
    for n in range(1, nf + 1):
        for g in _WS_ACC:
            _WS[g] = None
        s = []
        for ch in line:
            code = int(round(_real(_WS["field_select"](
                _VSA.make_real(float(ord(ch))), _VSA.make_real(float(n))))))
            if code > 0:
                s.append(chr(code))
        fields.append("".join(s))
    return fields


def _fields_delim(line: str, delim: str):
    """Fields for an explicit single-char FS, extracted on the substrate."""
    dv = _VSA.make_real(float(ord(delim)))
    for g in _FS_ACC:
        _FS[g] = None
    nf = 1
    for ch in line:
        nf = _real(_FS["field_count_delim"](_VSA.make_real(float(ord(ch))), dv))
    nf = round(nf) if line != "" else 0
    if line == "":
        return []
    fields = []
    for n in range(1, nf + 1):
        for g in _FS_ACC:
            _FS[g] = None
        s = []
        for ch in line:
            code = int(round(_real(_FS["field_select_delim"](
                _VSA.make_real(float(ord(ch))), _VSA.make_real(float(n)), dv))))
            if code > 0:
                s.append(chr(code))
        fields.append("".join(s))
    return fields


def _lines_of(text: str):
    if text == "":
        return []
    lines = text.split("\n")
    if text.endswith("\n"):
        lines = lines[:-1]
    return lines


def _parse_program(prog: str):
    """Split `pattern { action }` / `pattern` / `{ action }` into (pattern, action)."""
    prog = prog.strip()
    m = _re.match(r"^(.*?)\s*\{(.*)\}\s*$", prog, _re.S)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return prog, ""          # bare pattern (default action = print $0)


def _pattern_matches(pattern: str, line: str, nr: int) -> bool:
    if pattern == "":
        return True
    if pattern.startswith("/") and pattern.endswith("/") and len(pattern) >= 2:
        return NeuralRegex(pattern[1:-1]).search(line)
    m = _re.match(r"^NR\s*(==|>=|<=|>|<|!=)\s*(\d+)$", pattern)
    if m:
        op, k = m.group(1), int(m.group(2))
        return {"==": nr == k, "!=": nr != k, ">": nr > k, "<": nr < k,
                ">=": nr >= k, "<=": nr <= k}[op]
    raise ValueError(f"unsupported awk pattern: {pattern!r}")


def _eval_print(action: str, fields, line: str, nr: int, ofs=" ") -> str:
    body = action[len("print"):].strip() if action.startswith("print") else ""
    if body == "":
        return line
    parts = [p.strip() for p in body.split(",")]
    vals = []
    nf = len(fields)
    for p in parts:
        if p.startswith('"') and p.endswith('"'):
            vals.append(p[1:-1])
        elif p == "$0":
            vals.append(line)
        elif p == "$NF":
            vals.append(fields[-1] if fields else "")
        elif p == "NF":
            vals.append(str(nf))
        elif p == "NR":
            vals.append(str(nr))
        elif p.startswith("$"):
            idx = int(p[1:])
            vals.append(fields[idx - 1] if 1 <= idx <= nf else "")
        else:
            raise ValueError(f"unsupported print arg: {p!r}")
    return ofs.join(vals)


def neural_awk(text: str, prog: str, fs: str | None = None) -> str:
    pattern, action = _parse_program(prog)
    out = []
    for nr, line in enumerate(_lines_of(text), start=1):
        if not _pattern_matches(pattern, line, nr):
            continue
        fields = _fields_delim(line, fs) if fs else _fields_ws(line)
        if action == "" or action.startswith("print"):
            out.append(_eval_print(action or "print", fields, line, nr))
        else:
            raise ValueError(f"unsupported awk action: {action!r}")
    return "".join(s + "\n" for s in out)


def _find_awk():
    import shutil
    for c in (r"C:\Program Files\Git\usr\bin\awk.exe", "/usr/bin/awk", "/bin/awk"):
        if os.path.exists(c):
            return c
    return shutil.which("awk")


_AWK_EXE = _find_awk()


def real_awk(text: str, prog: str, fs: str | None = None) -> str:
    args = [_AWK_EXE] + (["-F", fs] if fs else []) + [prog]
    res = subprocess.run(args, input=text.encode("utf-8"), capture_output=True)
    return res.stdout.decode("utf-8").replace("\r\n", "\n")


# (text, program, fs)
CASES = [
    ("alice 30 nyc\nbob 25 sf\n", "{print $1}", None),
    ("alice 30 nyc\nbob 25 sf\n", "{print $1, $3}", None),
    ("alice 30 nyc\nbob 25 sf\n", "{print $NF}", None),
    ("alice 30 nyc\nbob 25 sf\n", "{print NF}", None),
    ("a b\nc d e\nf\n", "{print NR, NF}", None),
    ("one two three\n", "{print $2}", None),
    ("keep\nskip\nkeep2\n", "/keep/", None),
    ("l1\nl2\nl3\nl4\n", "NR==2", None),
    ("l1\nl2\nl3\nl4\n", "NR>2", None),
    ("root:x:0:0\ndaemon:x:1:1\n", "{print $1}", ":"),
    ("a,b,c\nd,e,f\n", "{print $2}", ","),
    ("error: bad\ninfo: ok\nerror: worse\n", "/error/{print $2}", None),
]


def _self_test() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    ok = True
    for text, prog, fs in CASES:
        neural, truth = neural_awk(text, prog, fs), real_awk(text, prog, fs)
        m = neural == truth
        ok = ok and m
        fsl = f"-F{fs} " if fs else ""
        print(f"[{'OK ' if m else 'FAIL'}] awk {fsl}{prog!r:22} "
              f"neural={neural!r} truth={truth!r}")
    passed = sum(1 for t, p, f in CASES if neural_awk(t, p, f) == real_awk(t, p, f))
    print(f"\n{'ALL PASS' if ok else 'FAILURES PRESENT'}: {passed}/{len(CASES)}")
    return 0 if ok else 1


def main() -> int:
    args = sys.argv[1:]
    if not args:
        return _self_test()
    fs = None
    if args and args[0] == "-F":
        fs = args[1]; args = args[2:]
    elif args and args[0].startswith("-F"):
        fs = args[0][2:]; args = args[1:]
    sys.stdout.write(neural_awk(sys.stdin.read(), args[0], fs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
