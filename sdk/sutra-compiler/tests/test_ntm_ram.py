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

    def test_neural_uniq_adjacent_dedup(self):
        # Unix rung 8 (Tier B entry): uniq collapses ADJACENT identical lines. The
        # prev-vs-current line-equality test runs on the substrate — a recurring
        # mismatch accumulator over exact per-position char indicators, with the
        # shorter line padded so length differences register.
        from run_uniq import neural_uniq
        self.assertEqual(neural_uniq("a\na\nb\nb\nb\nc\na\n"), "a\nb\nc\na\n")
        self.assertEqual(neural_uniq("same\nsame\nsame\n"), "same\n")
        self.assertEqual(neural_uniq("ab\nabc\nabc\nab\n"), "ab\nabc\nab\n")
        self.assertEqual(neural_uniq("all\ndistinct\n"), "all\ndistinct\n")
        self.assertEqual(neural_uniq("trailing\ntrailing"), "trailing\n")
        self.assertEqual(neural_uniq(""), "")

    def test_neural_cut_c_column_gated_emit(self):
        # Unix rung 7: cut -c = per-column gated emit. A recurring column counter
        # resets at each newline; each char is emitted iff its column is in the
        # selected range set (exact ge1 integer steps). Closes Tier A.
        from run_cut import neural_cut
        self.assertEqual(neural_cut("abcdef\nghijkl\n", "2-4"), "bcd\nhij\n")
        self.assertEqual(neural_cut("abcdefgh\n", "3-"), "cdefgh\n")
        self.assertEqual(neural_cut("abcdefgh\n", "-3"), "abc\n")
        self.assertEqual(neural_cut("columns\n", "1,3,5"), "clm\n")
        self.assertEqual(neural_cut("one\ntwo\n", "2"), "n\nw\n")
        self.assertEqual(neural_cut("", "1-3"), "")

    def test_neural_rev_tac_reverse_permutation(self):
        # Unix rung 6: rev/tac = reverse permutations over a RAM buffer, computed
        # on the substrate (pointer = limit - cursor emits addresses in reverse).
        # rev reverses chars per line; tac reverses line order.
        from run_rev import neural_rev, neural_tac
        self.assertEqual(neural_rev("hello\nworld\n"), "olleh\ndlrow\n")
        self.assertEqual(neural_rev("abcdef\n"), "fedcba\n")
        self.assertEqual(neural_rev("tail no nl"), "ln on liat")
        self.assertEqual(neural_rev(""), "")
        self.assertEqual(neural_tac("a\nb\nc\n"), "c\nb\na\n")
        self.assertEqual(neural_tac("one\ntwo\nthree\n"), "three\ntwo\none\n")
        self.assertEqual(neural_tac(""), "")

    def test_neural_tr_codebook_translate_and_delete(self):
        # Unix rung 5: tr = a substrate codebook map. Each byte's output is a
        # weighted sum of EXACT codepoint indicators — matched codepoints become
        # their paired value, unmatched pass through; delete masks matches to 0.
        from run_tr import neural_tr
        self.assertEqual(neural_tr("hello world\n", "a-z", "A-Z"), "HELLO WORLD\n")
        self.assertEqual(neural_tr("Hello\n", "A-Z", "a-z"), "hello\n")
        self.assertEqual(neural_tr("abcdef\n", "abc", "xyz"), "xyzdef\n")
        self.assertEqual(neural_tr("a1b2c3\n", "abc", delete=True), "123\n")
        self.assertEqual(neural_tr("phone 555\n", "0-9", delete=True), "phone \n")
        self.assertEqual(neural_tr("map it\n", "a-z", "X"), "XXX XX\n")  # SET2 padding

    def test_neural_head_tail_line_gated_filters(self):
        # Unix rung 4: head/tail = substrate line-gated stream filters. A recurring
        # line accumulator + an EXACT integer gate mask each emitted codepoint by
        # line index; tail counts the total on the substrate first. Checked against
        # known head/tail outputs (model-free).
        from run_head_tail import neural_head, neural_tail
        text = "a\nb\nc\nd\ne\n"
        self.assertEqual(neural_head(text, 2), "a\nb\n")
        self.assertEqual(neural_head(text, 0), "")
        self.assertEqual(neural_head(text, 9), text)          # N > lines => all
        self.assertEqual(neural_tail(text, 2), "d\ne\n")
        self.assertEqual(neural_tail(text, 3), "c\nd\ne\n")
        self.assertEqual(neural_tail(text, 9), text)
        # final line with no trailing newline (the +1 boundary correction)
        self.assertEqual(neural_tail("x\ny\nz", 2), "y\nz")
        self.assertEqual(neural_head("x\ny\nz", 2), "x\ny\n")

    def test_neural_wc_counts_match_coreutils_exactly(self):
        # Unix rung 3: wc = the first REAL transform. Substrate streaming
        # accumulators (recurring VRAM vectors) count (lines, words, bytes) via
        # EXACT codepoint indicators (relu(1-|c-center|), 0 leakage), so the
        # counts are exact integers. Checked against known wc values (model-free;
        # the coreutils comparison lives in run_wc.py's self-test).
        from run_wc import neural_wc
        expected = {
            "hello world\n": (1, 2, 12),
            "one two three\nfour five\n": (2, 5, 24),
            "  spaced  out  \n": (1, 2, 16),
            "single": (0, 1, 6),
            "a\nb\nc\n": (3, 3, 6),
            "": (0, 0, 0),
            "tab\tsep\ttext\n": (1, 3, 13),
            "no newline at end": (0, 4, 17),
        }
        for text, want in expected.items():
            self.assertEqual(neural_wc(text), want, repr(text))

    def test_neural_cat_streams_stdin_passthrough(self):
        # Unix rung 2: `cat` = streamed stdin -> substrate scan/emit -> stdout.
        # The decoded emit stream must equal the piped input byte-for-byte across
        # multi-line, empty, and multi-chunk-boundary content (the streamed loader
        # feeds RAM in 8-byte chunks). Model-free; the coreutils cat.exe
        # comparison lives in run_cat.py's own self-test.
        from run_cat import neural_cat
        for data in ("hello world\n", "one\ntwo\nthree\n", "no trailing newline",
                     "", "spans several eight-byte chunk boundaries here.\n"):
            self.assertEqual(neural_cat(data), data, repr(data))

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
