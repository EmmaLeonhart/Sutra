"""Disk device — persistent named storage for the neural filesystem (P1).

Per planning/sutra-spec/disk-device.md. The disk is an I/O device backed by REAL
host storage (a sandbox directory), exactly as RamDevice is host memory. It provides
the two things RAM lacks — a path namespace and persistence — while the substrate
work stays the byte processing (a file's codepoints are streamed through the same
`text_scan.su` read head that streamed stdin). Reading a file, listing a directory,
and mutating entries are host I/O at the wire (the honesty line in the spec).

A first-cut FLAT namespace (filenames in one sandbox dir) — enough for `cat FILE`
and `ls`; nested directories (for `find`) are a later rung.
"""
from __future__ import annotations

import os

from ram_device import RamDevice


class DiskDevice:
    def __init__(self, vsa, root: str):
        self._vsa = vsa
        self._root = os.path.abspath(root)
        os.makedirs(self._root, exist_ok=True)

    def _hostpath(self, path: str) -> str:
        # flat namespace: a file name resolves to one entry under the sandbox root.
        return os.path.join(self._root, path)

    # ---- namespace (backs `ls`) ------------------------------------------
    def list(self, include_hidden: bool = False):
        names = sorted(os.listdir(self._root))
        if not include_hidden:
            names = [n for n in names if not n.startswith(".")]
        return names

    def exists(self, path: str) -> bool:
        return os.path.exists(self._hostpath(path))

    def is_dir(self, path: str) -> bool:
        return os.path.isdir(self._hostpath(path))

    # ---- content (backs `cat FILE`) --------------------------------------
    def read_text(self, path: str) -> str:
        """The file's text, or '' for a missing path (no runtime errors by
        mechanism — a meaningless-but-valid empty read, like RAM OOB)."""
        hp = self._hostpath(path)
        if not os.path.isfile(hp):
            return ""
        with open(hp, "r", encoding="utf-8", newline="") as f:
            return f.read()

    def read_region(self, path: str) -> RamDevice:
        """An addressable RAM region holding the file's codepoints, so the
        substrate read head can scan it (the disk feeds RAM, then the substrate
        scans — the disk only changes WHERE the bytes come from)."""
        text = self.read_text(path)
        ram = RamDevice(self._vsa, size=max(8, len(text) + 2))
        ram.load_text(text, base=0, terminator=True)
        return ram, len(text)

    # ---- mutation (backs `cp` / `mv` / `rm`) -----------------------------
    def write_text(self, path: str, text: str) -> None:
        with open(self._hostpath(path), "w", encoding="utf-8", newline="") as f:
            f.write(text)

    def copy(self, src: str, dst: str) -> None:
        self.write_text(dst, self.read_text(src))

    def move(self, src: str, dst: str) -> None:
        os.replace(self._hostpath(src), self._hostpath(dst))

    def remove(self, path: str) -> None:
        hp = self._hostpath(path)
        if os.path.isfile(hp):
            os.remove(hp)
