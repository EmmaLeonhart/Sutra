"""cat FILE / ls on the neural computer — Unix-utility rung 14 (Tier D, uses P1).

The filesystem's first two tools, on the disk device (`disk_device.py`, prerequisite
P1). `cat FILE` resolves the path to a region (host I/O), loads the file's codepoints
into RAM, and drives the SAME substrate read head (`text_scan.su`) that streamed stdin
for the Tier-A `cat` — the disk changes only WHERE the bytes come from. `ls` streams
the directory entries (the namespace) through the same scan/emit, one name per record.
The substrate does the scan/emit; the disk lookup and directory listing are host I/O
at the wire.

Verified against coreutils `cat` / `ls -1` over a sandbox directory. Dim audit:
model-free read head (no basis_vector/embed) => semantic_dim=2 honest.

Run: python experiments/ntm_ram/run_fs.py             (self-test on a temp sandbox)
"""
from __future__ import annotations

import io
import os
import subprocess
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(REPO, "sdk", "sutra-compiler"))
sys.path.insert(0, os.path.dirname(__file__))

from ram_device import RamDevice          # noqa: E402  (re-exported for parity)
from orchestrator import Orchestrator      # noqa: E402
from disk_device import DiskDevice         # noqa: E402
from neural_regex import NeuralRegex        # noqa: E402
from run_demo import compile_su            # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
_NS = compile_su(os.path.join(HERE, "text_scan.su"), semantic_dim=2)
_VSA = _NS["_VSA"]


_SCAN_ACC = [k for k in _NS if k.endswith("_state")]


def _scan_region(ram: RamDevice, n: int) -> str:
    """Drive the substrate read head over a RAM region, decode the emitted stream.
    Resets the read head's recurring cursor first (the module is reused across
    scans, so the cursor must restart at 0 each time)."""
    for g in _SCAN_ACC:
        _NS[g] = None
    orch = Orchestrator(_VSA, ram, _NS["read_head"])
    trace = orch.run_read_scan(max_steps=n + 4, stop_on_sentinel=True)
    return orch.decode_text(trace)


def neural_cat_file(disk: DiskDevice, *paths: str) -> str:
    """cat FILE...: resolve each path to a region (host I/O) and scan+emit it on
    the substrate, concatenating."""
    out = []
    for p in paths:
        ram, n = disk.read_region(p)
        out.append(_scan_region(ram, n))
    return "".join(out)


def _fnmatch_to_regex(pat: str) -> str:
    """Convert a shell glob to the neural_regex subset: `*`->`.*`, `?`->`.`,
    `[...]`/`[!...]`->`[...]`/`[^...]`, every other regex-special char escaped."""
    out, i = [], 0
    while i < len(pat):
        c = pat[i]
        if c == "*":
            out.append(".*")
        elif c == "?":
            out.append(".")
        elif c == "[":
            j = i + 1
            if j < len(pat) and pat[j] == "!":
                out.append("[^"); j += 1
            else:
                out.append("[")
            while j < len(pat) and pat[j] != "]":
                out.append(pat[j]); j += 1
            out.append("]"); i = j
        elif c in ".+(){}|^$\\":
            out.append("\\" + c)
        else:
            out.append(c)
        i += 1
    return "".join(out)


def neural_find(start: str, name: str | None = None) -> str:
    """find START [-name GLOB]: pre-order walk of the tree (host I/O) emitting each
    path; `-name` keeps entries whose BASENAME matches GLOB via the on-substrate NFA
    (fnmatch -> regex -> fullmatch). Traversal is I/O; the name test is substrate."""
    nfa = NeuralRegex(_fnmatch_to_regex(name)) if name is not None else None
    paths = [start]
    for dp, dns, fns in os.walk(start):
        for n in dns + fns:
            paths.append(os.path.join(dp, n))
    out = []
    for p in paths:
        base = os.path.basename(p.rstrip(os.sep)) or p
        if nfa is None or nfa.fullmatch(base):
            out.append(p.replace(os.sep, "/"))
    return "".join(s + "\n" for s in out)


def neural_ls(disk: DiskDevice, include_hidden: bool = False) -> str:
    """ls: stream the directory entries through the substrate scan/emit, one name
    per record (== `ls -1`)."""
    names = disk.list(include_hidden=include_hidden)
    out = []
    for name in names:
        ram = RamDevice(_VSA, size=max(8, len(name) + 2))
        ram.load_text(name, base=0, terminator=True)
        out.append(_scan_region(ram, len(name)))
    return "".join(s + "\n" for s in out)


# ---------------------------------------------------------------- self-test
def _find(exe):
    for c in (fr"C:\Program Files\Git\usr\bin\{exe}.exe", f"/usr/bin/{exe}", f"/bin/{exe}"):
        if os.path.exists(c):
            return c
    import shutil
    return shutil.which(exe)


def _self_test() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    import tempfile
    sandbox = tempfile.mkdtemp(prefix="neural_fs_")
    disk = DiskDevice(_VSA, sandbox)
    # populate the sandbox
    files = {"apple.txt": "red fruit\n", "banana.txt": "yellow\ncurved\n",
             "cherry.txt": "small red\n"}
    for name, content in files.items():
        disk.write_text(name, content)

    ok = True
    cat_exe, ls_exe = _find("cat"), _find("ls")

    # cat FILE, single and multiple
    for paths in (["apple.txt"], ["banana.txt"], ["apple.txt", "cherry.txt"]):
        neural = neural_cat_file(disk, *paths)
        truth = subprocess.run([cat_exe] + [os.path.join(sandbox, p) for p in paths],
                               capture_output=True).stdout.decode("utf-8").replace("\r\n", "\n")
        m = neural == truth
        ok = ok and m
        print(f"[{'OK ' if m else 'FAIL'}] cat {paths} neural={neural!r} truth={truth!r}")
    # missing file -> empty (no error)
    m = neural_cat_file(disk, "nope.txt") == ""
    ok = ok and m
    print(f"[{'OK ' if m else 'FAIL'}] cat missing -> empty")

    # ls
    neural_ls_out = neural_ls(disk)
    truth_ls = subprocess.run([ls_exe, "-1", sandbox],
                              capture_output=True).stdout.decode("utf-8").replace("\r\n", "\n")
    m = neural_ls_out == truth_ls
    ok = ok and m
    print(f"[{'OK ' if m else 'FAIL'}] ls neural={neural_ls_out!r} truth={truth_ls!r}")

    # cp / mv / rm round-trip (mutation, read back on the substrate)
    disk.copy("apple.txt", "apple2.txt")
    m = neural_cat_file(disk, "apple2.txt") == files["apple.txt"]
    ok = ok and m
    print(f"[{'OK ' if m else 'FAIL'}] cp then cat")
    disk.move("apple2.txt", "apple3.txt")
    m = disk.exists("apple3.txt") and not disk.exists("apple2.txt")
    ok = ok and m
    print(f"[{'OK ' if m else 'FAIL'}] mv")
    disk.remove("apple3.txt")
    m = not disk.exists("apple3.txt")
    ok = ok and m
    print(f"[{'OK ' if m else 'FAIL'}] rm")

    # find (recursive walk + -name via the substrate NFA). Rebuild a nested tree.
    import shutil
    shutil.rmtree(sandbox, ignore_errors=True)
    sandbox = tempfile.mkdtemp(prefix="neural_fs_")
    os.makedirs(os.path.join(sandbox, "sub"))
    open(os.path.join(sandbox, "a.txt"), "w").write("x")
    open(os.path.join(sandbox, "sub", "b.log"), "w").write("y")
    open(os.path.join(sandbox, "sub", "c.txt"), "w").write("z")
    find_exe = _find("find")

    def _sorted(s):
        return sorted(l for l in s.splitlines() if l)

    for name in (None, "*.txt", "*.log", "sub", "?.txt"):
        neural = neural_find(sandbox, name)
        args = [find_exe, sandbox] + (["-name", name] if name else [])
        truth = subprocess.run(args, capture_output=True).stdout.decode("utf-8")
        truth = truth.replace("\\", "/").replace("\r\n", "\n")
        m = _sorted(neural) == _sorted(truth)
        ok = ok and m
        print(f"[{'OK ' if m else 'FAIL'}] find -name {name!r}: "
              f"neural={_sorted(neural)} truth={_sorted(truth)}")
    shutil.rmtree(sandbox, ignore_errors=True)
    print(f"\n{'ALL PASS' if ok else 'FAILURES PRESENT'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(_self_test())
