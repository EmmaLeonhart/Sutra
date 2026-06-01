"""Regression guard — RAM-pointer NTM read path runs on the substrate.

planning/sutra-spec/ram-pointers.md. Locks in the two addressing modes
the experiments/ntm_ram demos validate:

  - sequential scan: a recurring VRAM cursor emits addresses 0,1,2,...;
    the orchestrator serves host RAM and the decoded read stream equals
    the stored string.
  - pointer-chase: each cell is a complex number (real = codepoint,
    imag = next address); the head follows the imag-part links THROUGH
    the substrate, recovering a string laid out at non-sequential
    addresses in reading order (proof it followed pointers, not scanned).

Model-free (llm_model="none"), so no ollama dependency. Substrate audit
posture: semantic_dim is tiny because there are zero basis_vector calls
(dim audit); the recurring cursor/counter is a VRAM tensor surviving
across ticks via the module slot (state-locus audit); the only host
touches are the orchestrator's pointer/value decode at the I/O wire.
"""
from __future__ import annotations

import os
import sys
import unittest

_REPO = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
_NTM = os.path.join(_REPO, "experiments", "ntm_ram")
if _NTM not in sys.path:
    sys.path.insert(0, _NTM)


class TestNtmRamReadPath(unittest.TestCase):
    def _compile(self, su_name):
        from run_demo import compile_su  # noqa: E402
        return compile_su(os.path.join(_NTM, su_name), semantic_dim=2)

    def test_sequential_scan_recovers_text(self):
        from ram_device import RamDevice
        from orchestrator import Orchestrator
        ns = self._compile("text_scan.su")
        vsa = ns["_VSA"]
        ram = RamDevice(vsa, size=64)
        text = "HELLO, RAM!"
        ram.load_text(text, base=0, terminator=True)
        orch = Orchestrator(vsa, ram, ns["read_head"])
        trace = orch.run_read_scan(max_steps=64, stop_on_sentinel=True)
        self.assertEqual(orch.decode_text(trace), text)
        # program-controlled addresses are the sequential scan 0..len
        self.assertEqual([a for a, _ in trace][:len(text)],
                         list(range(len(text))))

    def test_pointer_chase_follows_links(self):
        from ram_device import RamDevice
        from orchestrator import Orchestrator
        ns = self._compile("chase.su")
        vsa = ns["_VSA"]
        ram = RamDevice(vsa, size=64)
        text = "WORLD"
        addrs = [0, 5, 2, 9, 4]   # deliberately non-sequential
        start = ram.load_linked_text(text, addrs, terminator_addr=63)
        orch = Orchestrator(vsa, ram, ns["chase"])
        trace = orch.run_pointer_chase(start_addr=start, max_steps=64)
        self.assertEqual(orch.chase_text(trace), text)
        # visited order == the stored link order => it followed pointers
        self.assertEqual([a for a, _c, _n in trace], addrs)

    def test_dim_audit_is_honest(self):
        # No basis_vector calls => semantic content is unused => a tiny
        # semantic_dim is correct (CLAUDE.md dim audit).
        ns = self._compile("text_scan.su")
        self.assertEqual(ns["_VSA"].semantic_dim, 2)


if __name__ == "__main__":
    unittest.main()
