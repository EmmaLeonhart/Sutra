"""RAM device — the external host memory a Sutra NTM program addresses.

Per planning/sutra-spec/ram-pointers.md: RAM is host memory, distinct
from the VRAM the program runs on. This is the I/O device. It is host
code ON PURPOSE — the honesty line in the spec says the RAM access
itself is I/O, never a Sutra operation. What must transit the substrate
(the pointer, the value) does so as VRAM vectors; this device only
stores/returns vectors and does integer addressing.

A cell stores one Sutra `number` vector (the first-class complex-
hypervector number: value in v[semantic_dim + AXIS_REAL]). Encoding a
host int into a cell and decoding a cell back to an int are the
producer-side slot translations every axon producer performs — they
live at the wire, not inside any Sutra operation.
"""
from __future__ import annotations


class RamDevice:
    """A flat host memory of `size` cells, each holding a number-vector.

    Bound to a compiled module's `_VSA` so encode/decode use the same
    canonical layout the substrate uses. Out-of-bounds reads return the
    zero vector (Sutra's "no runtime errors by mechanism" — a
    meaningless-but-valid value, not a raised exception; ram-pointers.md
    open question 4).
    """

    def __init__(self, vsa, size: int):
        self._vsa = vsa
        self._size = size
        # Each cell is a VRAM-layout vector. Empty cells are the zero
        # vector (== the "no value" sentinel, axon-io.md).
        self._cells = [vsa.zero_vector() for _ in range(size)]

    @property
    def size(self) -> int:
        return self._size

    def write_number(self, addr: int, value: float) -> None:
        """Host-side store: encode `value` as a number-vector at `addr`."""
        if 0 <= addr < self._size:
            self._cells[addr] = self._vsa.make_real(float(value))

    def write_vector(self, addr: int, vec) -> None:
        """Store a pre-encoded VRAM vector (what the orchestrator hands
        over from the write mailbox — already a substrate vector)."""
        if 0 <= addr < self._size:
            self._cells[addr] = vec

    def read_vector(self, addr: int):
        """Return the cell's VRAM vector. OOB -> zero vector."""
        if 0 <= addr < self._size:
            return self._cells[addr]
        return self._vsa.zero_vector()

    def load_text(self, text: str, base: int = 0, terminator: bool = True) -> int:
        """Lay a string out across consecutive cells, one codepoint per
        cell starting at `base`. Returns the address one past the last
        char. If `terminator`, leaves the following cell as the zero
        vector (codepoint 0) — the end-of-string sentinel the reader
        program detects."""
        addr = base
        for ch in text:
            self.write_number(addr, float(ord(ch)))
            addr += 1
        # Cells beyond are already zero_vector() == sentinel.
        return addr
