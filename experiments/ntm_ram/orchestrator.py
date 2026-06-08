"""Orchestrator — the first external `await` producer for Sutra.

planning/sutra-spec/axon-io.md specced the slot protocol (a slot starts
at the zero vector, becomes non-zero when a producer writes it) and
explicitly left "who writes the slot" as a Yantra-side question. The
orchestrator is that producer, specialised to a RAM I/O device.

It drives a compiled non-halting Sutra module (`recur` loop) tick by
tick. Each tick:
  - the program emits a REQUEST on its output axon (a pointer vector);
  - the orchestrator decodes the pointer to a host address (monitoring
    decode at the wire), reads the RAM cell, and serves that VRAM
    vector back as the program's input on the NEXT tick (the RESPONSE
    slot becoming non-zero == axon-io.md "arrived").

What runs where (ram-pointers.md honesty line): the program's emit /
recurring-cursor advance / consume-input are all substrate tensor ops
inside the compiled module. The orchestrator only moves vectors between
the program's I/O and the RAM device and translates pointer<->address
at the boundary. It performs NO arithmetic the program claims the
substrate did.
"""
from __future__ import annotations

def _real_axis(vsa, v):
    # Orchestrator I/O-wire decode: a pointer/value vector's real axis to a
    # host number. The `real()` runtime method was removed (no scalar accessor
    # in the language); the orchestrator is host I/O (ram-pointers.md), so it
    # reads the axis directly. NOT a substrate op.
    return float(v[vsa.semantic_dim + vsa.AXIS_REAL])


class Orchestrator:
    def __init__(self, vsa, ram, tick_fn):
        self._vsa = vsa
        self._ram = ram
        self._tick = tick_fn  # ns["<nonhalting_fn>"], called once per tick

    def _decode_pointer(self, ptr_vec) -> int:
        """pointer-vector -> host address. The real-part readout is the
        same host accessor `recur`-state debugging uses (Audit.md
        LEGITIMATE) — a monitoring decode at the I/O wire, not an op
        inside the substrate computation."""
        return int(round(_real_axis(self._vsa, ptr_vec)))

    def run_read_scan(self, max_steps: int, stop_on_sentinel: bool = True):
        """Drive the read head for up to `max_steps` ticks. Returns the
        list of (address, served_vector) the program addressed, in order.

        The program controls the address sequence via its recurring
        substrate cursor; the orchestrator serves RAM and records the
        read stream — that stream IS the retrieved content (the NTM read
        result). Decoding to characters is left to the caller (more
        monitoring)."""
        served = self._vsa.zero_vector()  # response slot before any read
        trace = []
        for _ in range(max_steps):
            # One substrate tick: program consumes `served`, emits the
            # next pointer it wants to read.
            ptr_vec = self._tick(served)
            addr = self._decode_pointer(ptr_vec)
            served = self._ram.read_vector(addr)   # host RAM I/O
            trace.append((addr, served))
            if stop_on_sentinel:
                # Sentinel == the cell is the zero vector (norm ~ 0):
                # axon-io.md "not arrived / no value". For a forward scan
                # of laid-out text this is the end-of-string terminator.
                import torch as _torch
                if float(_torch.linalg.vector_norm(served).item()) <= 1e-7:
                    break
        return trace

    def run_pointer_chase(self, start_addr: int, max_steps: int):
        """Data-dependent addressing — the NTM read capability. Each RAM
        cell is a complex number (real = codepoint, imag = next address).
        Read the cell at `addr`, pass it THROUGH the substrate program,
        then decode the payload (real) and the next address (imag) from
        the program's OUTPUT — so the cell genuinely transited the
        substrate before its link is followed. Follow `imag` until a
        zero / non-positive cell (the end sentinel).

        Returns a list of (address, codepoint, next_address). The
        next-address comes from RAM via the substrate, so the visited
        address sequence is determined by RAM contents, not a host
        counter."""
        import torch as _torch
        addr = start_addr
        trace = []
        for _ in range(max_steps):
            cell = self._ram.read_vector(addr)       # host RAM I/O
            out = self._tick(cell)                    # carry through substrate
            if float(_torch.linalg.vector_norm(out).item()) <= 1e-7:
                break                                 # zero cell == sentinel
            code = int(round(_real_axis(self._vsa, out)))    # payload, at the wire
            # `imag` accessor removed in the substrate-purity purge (87cfa407);
            # read the imag axis directly here (orchestrator/terminal boundary,
            # monitoring — same wire as `real` above).
            nxt = int(round(float(
                out[self._vsa.semantic_dim + self._vsa.AXIS_IMAG].item())))  # link
            if code <= 0:
                break
            trace.append((addr, code, nxt))
            addr = nxt
        return trace

    def run_write_stream(self, n_steps: int):
        """Drive a write head that emits an Axon{ptr, data} mailbox each
        tick (ram-pointers.md § "Mailbox representation", Emma's
        2026-06-01 decision). Read the two fields with axon_item (the
        substrate unbind — the consumer side of the mailbox), decode the
        pointer at the wire, and store the data VRAM vector in host RAM.
        Returns [(addr, decoded_data)] in write order."""
        written = []
        for _ in range(n_steps):
            req = self._tick()                          # program emits mailbox
            ptr_vec = self._vsa.axon_item(req, "ptr")   # substrate unbind
            data_vec = self._vsa.axon_item(req, "data")
            addr = int(round(_real_axis(self._vsa, ptr_vec)))  # decode at the wire
            self._ram.write_vector(addr, data_vec)      # host RAM I/O
            written.append((addr, int(round(_real_axis(self._vsa, data_vec)))))
        return written

    def chase_text(self, trace) -> str:
        """Decode a pointer-chase trace's codepoints to a string."""
        return "".join(chr(code) for _addr, code, _nxt in trace if code > 0)

    def decode_text(self, trace) -> str:
        """Decode a read trace's served values to a string (monitoring).
        Zero-vector cells (sentinel / empty) are dropped."""
        import torch as _torch
        out = []
        for _addr, vec in trace:
            if float(_torch.linalg.vector_norm(vec).item()) <= 1e-7:
                continue
            code = int(round(_real_axis(self._vsa, vec)))
            if code > 0:
                out.append(chr(code))
        return "".join(out)
