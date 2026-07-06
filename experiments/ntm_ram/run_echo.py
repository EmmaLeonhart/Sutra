"""echo on the neural computer — Unix-utility rung 1 (NTM RAM + substrate scan).

echo is the identity / passthrough utility: its only "logic" is joining its
arguments with single spaces and appending a newline (unless -n). On the neural
computer that means laying the exact output byte-sequence into the host RAM
device and driving the compiled substrate read-head (`text_scan.su`) to scan and
emit it cell by cell through the orchestrator; the decoded emit-stream IS echo's
stdout. Verified char-for-char against the real coreutils `echo.exe` — "it ran"
is not success (CLAUDE.md integrity rules).

Honesty (CLAUDE.md § "Subtler substrate breaches"): echo does essentially NO
transformation, so the substrate's genuine work here is only the sequential
scan/emit (the recurring-cursor read head). The arg-join-with-spaces is trivial
host-side RAM layout (I/O at the wire), NOT a substrate op — stated plainly
because echo is the passthrough base case. Real substrate transforms arrive with
`wc` (counting), `tr` (codebook argmax map), etc. Dim audit: the read head is
model-free (no basis_vector/embed), so semantic_dim=2 is the honest tiny dim.

Run: python experiments/ntm_ram/run_echo.py
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
from orchestrator import Orchestrator     # noqa: E402
from run_demo import compile_su           # noqa: E402  (reuse the compile helper)

HERE = os.path.dirname(os.path.abspath(__file__))


def posix_echo(args, trailing_newline=True):
    """Reference POSIX echo output: args single-space-joined + optional newline."""
    return " ".join(args) + ("\n" if trailing_newline else "")


def neural_echo(args, trailing_newline=True):
    """Run echo on the neural computer: lay the output bytes into the RAM device,
    scan them out on the compiled substrate read head, return the decoded stream."""
    out = posix_echo(args, trailing_newline)
    ns = compile_su(os.path.join(HERE, "text_scan.su"), semantic_dim=2)
    vsa = ns["_VSA"]
    ram = RamDevice(vsa, size=max(64, len(out) + 4))
    ram.load_text(out, base=0, terminator=True)  # one codepoint per cell + zero sentinel
    orch = Orchestrator(vsa, ram, ns["read_head"])
    trace = orch.run_read_scan(max_steps=len(out) + 4, stop_on_sentinel=True)
    return orch.decode_text(trace)


def _find_echo_exe():
    """Locate the real coreutils `echo` binary. PATH `bash`/`echo` may resolve
    to a broken WSL relay on Windows, so prefer the Git-for-Windows coreutils
    echo.exe by full path, then fall back to a PATH lookup."""
    import shutil
    candidates = [
        r"C:\Program Files\Git\usr\bin\echo.exe",
        r"C:\Program Files (x86)\Git\usr\bin\echo.exe",
        "/usr/bin/echo.exe",
        "/usr/bin/echo",
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    found = shutil.which("echo")
    if found:
        return found
    raise RuntimeError("no real `echo` binary found for ground-truth comparison")


_ECHO_EXE = _find_echo_exe()


def real_echo(args, trailing_newline=True):
    """Ground truth: the real coreutils `echo` binary, invoked directly."""
    argv = [_ECHO_EXE] + ([] if trailing_newline else ["-n"]) + list(args)
    res = subprocess.run(argv, capture_output=True, text=True)
    # coreutils echo emits \n line endings; text-mode read on Windows can turn a
    # bare \n into \r\n on some streams — normalise CRLF->LF so the comparison is
    # about echo's semantics, not the pipe's line-ending translation.
    return res.stdout.replace("\r\n", "\n")


CASES = [
    (["hello", "world"], True),
    (["a", "b", "c"], True),
    (["single"], True),
    (["no", "newline"], False),
    (["Hello,", "RAM!"], True),
]


def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    all_ok = True
    for args, nl in CASES:
        neural = neural_echo(args, nl)
        truth = real_echo(args, nl)
        match = neural == truth
        all_ok = all_ok and match
        tag = "OK " if match else "FAIL"
        print(f"[{tag}] echo{' -n' if not nl else ''} {' '.join(args)!r:30} "
              f"neural={neural!r:22} truth={truth!r}")
        if not match:
            n = max(len(neural), len(truth))
            diffs = [(i,
                      truth[i] if i < len(truth) else None,
                      neural[i] if i < len(neural) else None)
                     for i in range(n)
                     if (truth[i] if i < len(truth) else None)
                     != (neural[i] if i < len(neural) else None)]
            print(f"       delta ({len(diffs)} positions, (i, truth, neural)): {diffs}")
    print(f"\n{'ALL PASS' if all_ok else 'FAILURES PRESENT'}: "
          f"{sum(1 for a, n in CASES if neural_echo(a, n) == real_echo(a, n))}/{len(CASES)}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
