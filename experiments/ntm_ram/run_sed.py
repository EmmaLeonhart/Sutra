"""sed on the neural computer — Unix-utility rung 12 (regex substitute).

`sed -E 's/RE/REPL/[g]'` replaces the leftmost-longest match of RE on each line
(or every non-overlapping match with `g`) by REPL. The matcher is the on-substrate
NFA (`neural_regex.py`); this rung adds match-SPAN extraction (spec open-question 1):
`NeuralRegex.match_span` finds the leftmost start (for a `^`-pattern, only position
0) and, for that start, the longest end at which an accept state is active — the
accept test runs on the substrate at each end position. The host then splices REPL
into the located span (`&` in REPL expands to the matched text). The MATCH decisions
are substrate; the splice is I/O, the same division as every rung.

Supported: the regex subset of neural_regex.py, `s///` and `s///g`, `&` in REPL.
(Backreferences `\1` need capture groups — the NFA does not track them; out of
scope, named not dropped.) Verified against coreutils `sed -E`.

Run: python experiments/ntm_ram/run_sed.py                 (self-test)
     <text> | python experiments/ntm_ram/run_sed.py 's/o+/O/g'
"""
from __future__ import annotations

import io
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from neural_regex import NeuralRegex       # noqa: E402


def _parse_s(cmd: str):
    """Parse an `s/RE/REPL/[flags]` command (delimiter is the char after `s`)."""
    assert cmd[0] == "s", "only s/// commands supported"
    d = cmd[1]
    parts = []
    buf = []
    i = 2
    while i < len(cmd) and len(parts) < 2:
        if cmd[i] == "\\" and i + 1 < len(cmd):
            buf.append(cmd[i:i + 2]); i += 2; continue
        if cmd[i] == d:
            parts.append("".join(buf)); buf = []; i += 1; continue
        buf.append(cmd[i]); i += 1
    flags = cmd[i:]
    return parts[0], parts[1], ("g" in flags)


def _expand(repl: str, matched: str) -> str:
    out, i = [], 0
    while i < len(repl):
        if repl[i] == "\\" and i + 1 < len(repl):
            out.append(repl[i + 1]); i += 2
        elif repl[i] == "&":
            out.append(matched); i += 1
        else:
            out.append(repl[i]); i += 1
    return "".join(out)


def _sub_line(nfa: NeuralRegex, repl: str, line: str, g: bool) -> str:
    out = []
    pos = 0
    n = len(line)
    while pos <= n:
        span = nfa.match_span(line, pos)
        if span is None:
            out.append(line[pos:]); break
        s, e = span
        out.append(line[pos:s])
        out.append(_expand(repl, line[s:e]))
        if e == s:                    # empty match: emit one char, advance, avoid loop
            if s < n:
                out.append(line[s])
            pos = s + 1
        else:
            pos = e
        if not g:
            out.append(line[pos:]); break
    return "".join(out)


def _lines_of(text: str):
    if text == "":
        return []
    lines = text.split("\n")
    if text.endswith("\n"):
        lines = lines[:-1]
    return lines


def neural_sed(text: str, cmd: str) -> str:
    pat, repl, g = _parse_s(cmd)
    nfa = NeuralRegex(pat)
    return "".join(_sub_line(nfa, repl, line, g) + "\n" for line in _lines_of(text))


def _find_sed():
    import shutil
    for c in (r"C:\Program Files\Git\usr\bin\sed.exe",
              r"C:\Program Files (x86)\Git\usr\bin\sed.exe", "/usr/bin/sed", "/bin/sed"):
        if os.path.exists(c):
            return c
    return shutil.which("sed")


_SED_EXE = _find_sed()


def real_sed(text: str, cmd: str) -> str:
    res = subprocess.run([_SED_EXE, "-E", cmd], input=text.encode("utf-8"),
                         capture_output=True)
    return res.stdout.decode("utf-8").replace("\r\n", "\n")


CASES = [
    ("hello world\n", "s/o/0/"),
    ("hello world\n", "s/o/0/g"),
    ("foo bar baz\n", "s/ba./XX/g"),
    ("aaa\n", "s/a+/A/"),
    ("aaa bbb aaa\n", "s/a+/A/g"),
    ("cat dog cat\n", "s/cat/pet/g"),
    ("2024-01-02\n", "s/[0-9]+/N/g"),
    ("wrap me\n", "s/wrap/[&]/"),           # & = whole match
    ("no match here\n", "s/xyz/Q/g"),
    ("color colour\n", "s/colou?r/C/g"),
]


def _self_test() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    ok = True
    for text, cmd in CASES:
        neural, truth = neural_sed(text, cmd), real_sed(text, cmd)
        m = neural == truth
        ok = ok and m
        print(f"[{'OK ' if m else 'FAIL'}] sed -E {cmd:14} {text!r:20} "
              f"neural={neural!r} truth={truth!r}")
    passed = sum(1 for t, c in CASES if neural_sed(t, c) == real_sed(t, c))
    print(f"\n{'ALL PASS' if ok else 'FAILURES PRESENT'}: {passed}/{len(CASES)}")
    return 0 if ok else 1


def main() -> int:
    args = sys.argv[1:]
    if not args:
        return _self_test()
    sys.stdout.write(neural_sed(sys.stdin.read(), args[0]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
