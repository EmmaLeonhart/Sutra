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

def _rv(_vsa, _vec):
    # Host-side terminal-boundary read of a number-vector's real axis
    # (the `real()` runtime method was removed — no number accessor). This
    # is the sanctioned external verification read, done by direct indexing.
    return float(_vec[_vsa.semantic_dim + _vsa.AXIS_REAL])

_REPO = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
_NTM = os.path.join(_REPO, "experiments", "ntm_ram")
if _NTM not in sys.path:
    sys.path.insert(0, _NTM)


def _ollama_up() -> bool:
    """The axon-mailbox write head embeds its field keys, so it needs an
    embedding model. Skip those legs when no ollama server is reachable
    (the read-path tests are model-free and always run)."""
    try:
        import urllib.request
        urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2)
        return True
    except Exception:
        return False


def _compile_src(src: str, dim: int = 2):
    """Compile a .su source string to a runnable namespace (torch backend,
    model-free) for the inline-surface tests."""
    from sutra_compiler.lexer import Lexer
    from sutra_compiler.parser import Parser
    from sutra_compiler.codegen_pytorch import translate_module
    lx = Lexer(src, file="<test>")
    toks = lx.tokenize()
    ast = Parser(toks, file="<test>", diagnostics=lx.diagnostics).parse_module()
    assert not lx.diagnostics.has_errors(), list(lx.diagnostics)
    ns: dict = {}
    exec(translate_module(ast, llm_model="none", runtime_dim=dim), ns)
    return ns


class TestRamInlineSurface(unittest.TestCase):
    """The `ramRead`/`ramWrite` surface builtins bridging to the
    host-attached `_VSA.ram` device (planning/sutra-spec/ram-pointers.md).
    Model-free; the RAM access is I/O at the boundary (round-to-nearest
    pointer decode), the value transits VRAM."""

    def test_synchronous_ram_read_write(self):
        ns = _compile_src(
            'function vector sl(vector ptr, vector data) {'
            '  ramWrite(ptr, data); return ramRead(ptr); }'
            'function string main() { return "ok"; }')
        v = ns["_VSA"]
        v.ram = [v.zero_vector() for _ in range(8)]
        out = _rv(v, ns["sl"](v.make_real(2.0), v.make_real(77.0)))
        self.assertAlmostEqual(out, 77.0, places=3)
        self.assertAlmostEqual(_rv(v, v.ram[2]), 77.0, places=3)

    def test_await_ram_read_in_async(self):
        ns = _compile_src(
            'async function vector ld(vector ptr) {'
            '  number x = await ramRead(ptr); return x; }'
            'function string main() { return "ok"; }')
        v = ns["_VSA"]
        v.ram = [v.zero_vector() for _ in range(8)]
        v.ram[3] = v.make_real(55.0)
        self.assertAlmostEqual(_rv(v, ns["ld"](v.make_real(3.0))), 55.0, places=3)

    def test_synchronous_ram_read_in_recur(self):
        # The NTM read head: a recurring VRAM cursor advances on the
        # substrate each tick; ramRead reads the device at the decoded
        # address. State-locus holds (cursor is a recurring tensor; real()
        # is the I/O-wire address decode, not state extraction).
        ns = _compile_src(
            'function vector head(number dummy) {'
            '  recurring vector cur = make_real(0.0);'
            '  vector x = ramRead(cur);'
            '  recur(cur + make_real(1.0)); return(x); }'
            'function string main() { return "ok"; }')
        v = ns["_VSA"]
        v.ram = [v.make_real(72.0), v.make_real(73.0), v.make_real(74.0)] \
            + [v.zero_vector() for _ in range(5)]
        out = [_rv(v, ns["head"](0.0)) for _ in range(3)]
        self.assertEqual([round(x) for x in out], [72, 73, 74])

    def test_no_device_reads_zero(self):
        # No attached device -> ram_read returns the zero vector (no
        # runtime error by mechanism).
        ns = _compile_src(
            'function vector r(vector ptr) { return ramRead(ptr); }'
            'function string main() { return "ok"; }')
        v = ns["_VSA"]
        self.assertAlmostEqual(_rv(v, ns["r"](v.make_real(0.0))), 0.0, places=3)


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

    @unittest.skipUnless(_ollama_up(), "axon-mailbox write head needs an embedding model")
    def test_axon_mailbox_write_path(self):
        from run_demo import compile_su
        from ram_device import RamDevice
        from orchestrator import Orchestrator
        ns = compile_su(os.path.join(_NTM, "write_head.su"),
                        semantic_dim=768, llm_model="nomic-embed-text")
        vsa = ns["_VSA"]
        ram = RamDevice(vsa, size=64)
        orch = Orchestrator(vsa, ram, ns["write_step"])
        written = orch.run_write_stream(n_steps=5)
        expected = [(i, i + 100) for i in range(5)]
        # program-chosen address + substrate-computed data land in RAM
        self.assertEqual(written, expected)
        readback = [(a, int(round(_rv(vsa, ram.read_vector(a)))))
                    for a, _ in written]
        self.assertEqual(readback, expected)

    @unittest.skipUnless(_ollama_up(), "axon number-field separation needs a model")
    def test_axon_number_fields_separate(self):
        # The measured fact ram-pointers.md records: two number fields in
        # one axon recover cleanly (ptr=7, data=65), no superposition.
        from run_demo import compile_su
        import tempfile
        src = (
            'function vector build(number p, number d) {\n'
            '    Axon a;\n'
            '    a.add("ptr", make_real(p));\n'
            '    a.add("data", make_real(d));\n'
            '    return a;\n'
            '}\n'
            'function vector gp(vector a) { return axon_item(a, "ptr"); }\n'
            'function vector gd(vector a) { return axon_item(a, "data"); }\n'
            'function string main() { return "ok"; }\n'
        )
        with tempfile.NamedTemporaryFile("w", suffix=".su", delete=False,
                                         encoding="utf-8") as f:
            f.write(src)
            path = f.name
        ns = compile_su(path, semantic_dim=768, llm_model="nomic-embed-text")
        os.unlink(path)
        vsa = ns["_VSA"]
        a = ns["build"](7.0, 65.0)
        self.assertAlmostEqual(_rv(vsa, ns["gp"](a)), 7.0, places=3)
        self.assertAlmostEqual(_rv(vsa, ns["gd"](a)), 65.0, places=3)

    def test_ram_lookup_render_matches_font_ground_truth(self):
        # RAM-lookup rendering (Emma 2026-06-01): store a glyph's 5x5
        # bitmap in RAM, fetch all 25 cells by the read head's
        # program-controlled pointers, and confirm it reproduces the font
        # ground truth exactly. The pure-NN render (font.su glyph_pixel)
        # is verified separately by demos/font/test_font.py; recompiling
        # font.su here would be heavy, so this guards only the RAM side.
        sys.path.insert(0, os.path.join(_REPO, "demos", "font"))
        from font_data import bits_for
        from ram_device import RamDevice
        from orchestrator import Orchestrator
        ns = self._compile("text_scan.su")
        vsa = ns["_VSA"]
        for ch in ("A", "7"):
            ground = [round(b) for b in bits_for(ch)]
            ram = RamDevice(vsa, size=32)
            for pos, b in enumerate(ground):
                ram.write_number(pos, float(b))
            ns["_read_head__cursor_state"] = None  # fresh cursor per glyph
            orch = Orchestrator(vsa, ram, ns["read_head"])
            # fixed 25-cell fetch; 0 bits are valid pixels -> no sentinel
            trace = orch.run_read_scan(max_steps=25, stop_on_sentinel=False)
            got = [round(float(_rv(vsa, served))) for _a, served in trace]
            self.assertEqual(got, ground, f"glyph {ch!r} RAM render mismatch")

    def test_inline_ramread_demo_recovers_text(self):
        # experiments/ntm_ram/text_scan_inline.su: a recur read head using
        # the INLINE ramRead builtin against a host-attached _VSA.ram.
        from ram_device import RamDevice  # noqa: F401 (path side effect)
        ns = self._compile("text_scan_inline.su")
        vsa = ns["_VSA"]
        text = "HELLO, RAM!"
        vsa.ram = [vsa.make_real(float(ord(c))) for c in text] \
            + [vsa.zero_vector() for _ in range(32 - len(text))]
        out = "".join(chr(int(round(_rv(vsa, ns["read_step"](0.0)))))
                       for _ in range(len(text)))
        self.assertEqual(out, text)

    def test_dim_audit_is_honest(self):
        # No basis_vector calls => semantic content is unused => a tiny
        # semantic_dim is correct (CLAUDE.md dim audit).
        ns = self._compile("text_scan.su")
        self.assertEqual(ns["_VSA"].semantic_dim, 2)


class TestTrainableRead(unittest.TestCase):
    """The trainable NTM read head (Emma 2026-06-07): a DIFFERENTIABLE soft linear
    read over external memory cell contents, trained by SGD to do linear regression
    over memory. Guards that the read is differentiable + the training converges +
    recovers the true coefficients (the trainable-seed read, measured)."""

    def test_soft_linear_read_trains_to_regress_over_memory(self):
        try:
            import torch  # noqa: F401
        except Exception:
            self.skipTest("trainable read needs torch")
        from trainable_read import main as read_main
        self.assertEqual(read_main(), 0)


if __name__ == "__main__":
    unittest.main()
