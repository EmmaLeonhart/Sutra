"""cat on the neural computer — Unix-utility rung 2 (streamed stdin axon).

`cat` with no file operands is stdin→stdout passthrough. Like echo it does no
transformation, so the substrate's genuine work is again only the sequential
scan/emit (the recurring-cursor read head, `text_scan.su`) — but cat forces the
NEXT piece of the P0 boundary: a streamed STDIN axon. Where echo's bytes were
host-constructed from argv, cat's bytes ARRIVE on stdin, in chunks, and are fed
into the addressable RAM device as they come; the substrate then scans the
assembled stream and emits it cell by cell, and the decoded emit-stream IS cat's
stdout.

Honesty (CLAUDE.md § "Subtler substrate breaches"): cat performs NO transform, so
this rung adds no new substrate op over echo — it is the passthrough base case for
PIPED input. The genuine new work is the host stdin-axon path (reading the pipe in
chunks into RAM); the scan/emit is the same substrate read head. Real transforms
start at `wc` (streaming accumulators) and `tr` (codebook argmax map). Dim audit:
the read head is model-free (no basis_vector/embed), so semantic_dim=2 stays the
honest tiny dim. Verified char-for-char against the real coreutils `cat` binary.

Run: python experiments/ntm_ram/run_cat.py         (self-test over fixed cases)
     <something> | python experiments/ntm_ram/run_cat.py --stdin   (real pipe)
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
from orchestrator import Orchestrator      # noqa: E402
from run_demo import compile_su            # noqa: E402  (reuse the compile helper)

HERE = os.path.dirname(os.path.abspath(__file__))


def _stream_load(ram: RamDevice, data: str, chunk_size: int = 8) -> int:
    """Feed `data` into the RAM device as a STREAMED stdin axon: hand it over in
    successive chunks (as a pipe delivers it), each appended at the growing write
    offset, one codepoint per cell. The terminator (a trailing zero cell) is left
    only AFTER the final chunk, so the substrate read head sees one contiguous
    stream, not a sentinel between chunks. Returns the number of bytes laid in."""
    offset = 0
    for i in range(0, len(data), chunk_size):
        chunk = data[i:i + chunk_size]
        for ch in chunk:
            ram.write_number(offset, float(ord(ch)))
            offset += 1
    # Cells beyond `offset` are already zero_vector() == end-of-stream sentinel.
    return offset


def neural_cat(data: str, chunk_size: int = 8) -> str:
    """Run cat on the neural computer: stream stdin bytes into the RAM device,
    scan them out on the compiled substrate read head, return the decoded stream."""
    ns = compile_su(os.path.join(HERE, "text_scan.su"), semantic_dim=2)
    vsa = ns["_VSA"]
    ram = RamDevice(vsa, size=max(64, len(data) + 4))
    n = _stream_load(ram, data, chunk_size=chunk_size)
    orch = Orchestrator(vsa, ram, ns["read_head"])
    trace = orch.run_read_scan(max_steps=n + 4, stop_on_sentinel=True)
    return orch.decode_text(trace)


def _find_cat_exe():
    """Locate the real coreutils `cat` binary. PATH may resolve to a broken WSL
    relay on Windows, so prefer the Git-for-Windows coreutils cat.exe by full
    path, then fall back to a PATH lookup."""
    import shutil
    candidates = [
        r"C:\Program Files\Git\usr\bin\cat.exe",
        r"C:\Program Files (x86)\Git\usr\bin\cat.exe",
        "/usr/bin/cat.exe",
        "/usr/bin/cat",
        "/bin/cat",
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    found = shutil.which("cat")
    if found:
        return found
    raise RuntimeError("no real `cat` binary found for ground-truth comparison")


_CAT_EXE = _find_cat_exe()


def real_cat(data: str) -> str:
    """Ground truth: the real coreutils `cat` binary, fed `data` on stdin.
    Normalise CRLF->LF so the comparison is about cat's passthrough, not the
    pipe's Windows line-ending translation (same discipline as run_echo.py)."""
    res = subprocess.run([_CAT_EXE], input=data, capture_output=True, text=True)
    return res.stdout.replace("\r\n", "\n")


CASES = [
    "hello world\n",
    "one\ntwo\nthree\n",              # multi-line (what stdin brings that argv didn't)
    "no trailing newline",
    "",                                # empty stdin
    "  leading and trailing spaces  \n",
    "punct: ,.;:!?()[]{}<>@#$%^&*\n",
    "a longer paragraph that spans more than one eight-byte chunk to exercise the "
    "streamed stdin loader across several chunk boundaries.\n",
]


def _run_self_test() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    all_ok = True
    for data in CASES:
        neural = neural_cat(data)
        truth = real_cat(data)
        match = neural == truth
        all_ok = all_ok and match
        tag = "OK " if match else "FAIL"
        preview = data if len(data) <= 24 else data[:24] + "..."
        print(f"[{tag}] cat <<< {preview!r:34} match={match}")
        if not match:
            n = max(len(neural), len(truth))
            diffs = [(i,
                      truth[i] if i < len(truth) else None,
                      neural[i] if i < len(neural) else None)
                     for i in range(n)
                     if (truth[i] if i < len(truth) else None)
                     != (neural[i] if i < len(neural) else None)]
            print(f"       delta ({len(diffs)} positions, (i, truth, neural)): {diffs}")
    passed = sum(1 for d in CASES if neural_cat(d) == real_cat(d))
    print(f"\n{'ALL PASS' if all_ok else 'FAILURES PRESENT'}: {passed}/{len(CASES)}")
    return 0 if all_ok else 1


def main() -> int:
    if "--stdin" in sys.argv[1:]:
        # Real pipe mode: consume stdin, emit the neural passthrough to stdout.
        data = sys.stdin.read()
        sys.stdout.write(neural_cat(data))
        return 0
    return _run_self_test()


if __name__ == "__main__":
    sys.exit(main())
