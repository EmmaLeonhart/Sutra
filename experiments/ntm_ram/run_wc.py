"""wc on the neural computer — Unix-utility rung 3 (first REAL transform).

Unlike echo/cat (passthrough), wc COUNTS: lines, words, bytes. The counting is
done on the substrate by streaming accumulators — recurring VRAM vectors updated
every tick by substrate tensor ops (`wc_heads.su`), never by a host counter
(CLAUDE.md § state-locus audit: the count is a vector surviving across calls via
substrate add). The orchestrator streams the input codepoints in (host addressing
is I/O) and reads the final accumulator values at the terminal boundary.

Substrate mechanism (measured exact, 0 leakage): each count is driven by an EXACT
codepoint indicator `is_cp(c, center) = relu(1 - |c - center|)` — 1 only AT the
center codepoint, a hard 0 (relu clamp) at every other, so no saturation residual
accumulates. bytes = +1 per codepoint; lines = += is_cp(c, 10); words counts
whitespace→nonspace transitions, packing its two state values (running count +
was-previous-nonspace) into the real/imag axes of one complex recurring slot (v1
allows one recurring slot per function). Verified against coreutils `wc`.

Dim audit: the heads are model-free (no basis_vector/embed), so semantic_dim=2 is
the honest tiny dim.

Run: python experiments/ntm_ram/run_wc.py           (self-test vs coreutils)
     <text> | python experiments/ntm_ram/run_wc.py --stdin
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

# One compiled module, reused; the recurring accumulator globals are reset per run.
_NS = compile_su(os.path.join(HERE, "wc_heads.su"), semantic_dim=2)
_VSA = _NS["_VSA"]
_ACC_GLOBALS = [k for k in _NS if k.endswith("_state")]


def _real(v) -> float:
    return float(v[_VSA.semantic_dim + _VSA.AXIS_REAL])


def neural_wc(text: str):
    """Count (lines, words, bytes) on the substrate. Streams each codepoint of
    `text` into the three recurring accumulator heads and reads the final counts
    at the boundary. Returns integers (the accumulators are exact)."""
    for g in _ACC_GLOBALS:          # reset recurring state for a fresh count
        _NS[g] = None
    ram = RamDevice(_VSA, size=max(8, len(text) + 2))
    ram.load_text(text, base=0, terminator=True)
    lines = words = bytes_ = 0.0
    for addr in range(len(text)):   # host addressing (I/O); substrate does the counting
        cell = ram.read_vector(addr)
        bytes_ = _real(_NS["byte_count"](cell))
        lines = _real(_NS["line_count"](cell))
        words = _real(_NS["word_count"](cell))
    return round(lines), round(words), round(bytes_)


def _find_wc_exe():
    import shutil
    for c in (r"C:\Program Files\Git\usr\bin\wc.exe",
              r"C:\Program Files (x86)\Git\usr\bin\wc.exe",
              "/usr/bin/wc.exe", "/usr/bin/wc", "/bin/wc"):
        if os.path.exists(c):
            return c
    found = shutil.which("wc")
    if found:
        return found
    raise RuntimeError("no real `wc` binary found for ground-truth comparison")


_WC_EXE = _find_wc_exe()


def real_wc(text: str):
    """Ground truth: coreutils `wc`. Fed as BYTES so the Windows text pipe does
    not translate \\n -> \\r\\n and inflate the byte count."""
    res = subprocess.run([_WC_EXE], input=text.encode("utf-8"), capture_output=True)
    p = res.stdout.split()
    return (int(p[0]), int(p[1]), int(p[2]))


CASES = [
    "hello world\n",
    "one two three\nfour five\n",
    "  spaced  out  \n",
    "single",
    "a\nb\nc\n",
    "",
    "tab\tsep\ttext\n",
    "trailing   \n\n",
    "no newline at end",
    "multiple   internal     spaces and\ttabs\tmixed\n",
]


def _self_test() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    all_ok = True
    for text in CASES:
        neural = neural_wc(text)
        truth = real_wc(text)
        ok = neural == truth
        all_ok = all_ok and ok
        preview = text if len(text) <= 26 else text[:26] + "..."
        print(f"[{'OK ' if ok else 'FAIL'}] wc {preview!r:34} "
              f"neural(l,w,c)={neural} coreutils={truth}")
    passed = sum(1 for t in CASES if neural_wc(t) == real_wc(t))
    print(f"\n{'ALL PASS' if all_ok else 'FAILURES PRESENT'}: {passed}/{len(CASES)}")
    return 0 if all_ok else 1


def main() -> int:
    if "--stdin" in sys.argv[1:]:
        data = sys.stdin.read()
        l, w, c = neural_wc(data)
        sys.stdout.write(f"{l:>7} {w:>7} {c:>7}\n")
        return 0
    return _self_test()


if __name__ == "__main__":
    sys.exit(main())
