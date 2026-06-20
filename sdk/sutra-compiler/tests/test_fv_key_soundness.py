"""FV contract key-soundness (paper §3.1) — runtime key-usage
instrumentation gated against the static AXON_KEYS_* analysis.

Verifies the discharge of the previously-open half of the §3.1 contract
obligation: that `AXON_KEYS_READ`/`AXON_KEYS_BOUND` (the compiler's static
string-literal key analysis) are SOUND vs the keys touched at runtime.

The PyTorch runtime carries opt-in key tracing on `axon_add`/`axon_item`
(`_VSA._fv_key_trace`, off by default). `fv_key_soundness.check_key_soundness`
turns it on, runs the program's axon accesses, and gates
runtime_keys ⊆ static_keys. These tests show the check is NON-VACUOUS: a
program touching only its statically-collected keys is sound, and an
access that escapes the static set (a key not collected, or a non-str
'<dynamic>' key) is caught.
"""
from __future__ import annotations

import unittest

from sutra_compiler.codegen_pytorch import translate_module as torch_translate
from sutra_compiler.fv_key_soundness import check_key_soundness
from sutra_compiler.lexer import Lexer
from sutra_compiler.parser import Parser


# Source whose static analysis yields AXON_KEYS_BOUND = {animal, color}
# and AXON_KEYS_READ = {animal}. The .item("k")=v writes are the bound
# keys; axon_item(a,"k") is the read key.
SRC = (
    "function vector producer() {\n"
    "    Axon a = new Axon();\n"
    '    a.add("animal", basis_vector("dog"));\n'
    '    a.add("color", basis_vector("red"));\n'
    '    return axon_item(a, "animal");\n'
    "}\n"
    'function string main() { return "ok"; }\n'
)


def _compile(src: str) -> dict:
    lx = Lexer(src, file="<fvks>")
    ast = Parser(lx.tokenize(), file="<fvks>", diagnostics=lx.diagnostics).parse_module()
    assert not lx.diagnostics.has_errors(), list(lx.diagnostics)
    ns: dict = {}
    exec(torch_translate(ast), ns)
    return ns


class TestFVKeySoundness(unittest.TestCase):
    def setUp(self):
        self.ns = _compile(SRC)
        # sanity: the static sets are what we expect
        self.assertEqual(set(self.ns["AXON_KEYS_BOUND"]), {"animal", "color"})
        self.assertEqual(set(self.ns["AXON_KEYS_READ"]), {"animal"})

    def test_trace_off_by_default(self):
        # Zero hot-path cost / no behavior change when not verifying.
        self.assertIsNone(self.ns["_VSA"]._fv_key_trace)

    def test_sound_program_passes(self):
        # Touch only statically-collected keys: bound {animal,color},
        # read {animal}. The instrumented axon_add/axon_item are exactly
        # what the compiled program calls.
        def run(vsa):
            a = vsa.axon_add(vsa.zero_vector(), "animal", 1.0)
            a = vsa.axon_add(a, "color", 2.0)
            return vsa.axon_item(a, "animal")

        v = check_key_soundness(self.ns, run)
        self.assertTrue(v["sound"], v)
        self.assertEqual(v["runtime_bound"], {"animal", "color"})
        self.assertEqual(v["runtime_read"], {"animal"})
        self.assertEqual(v["read_escapes"], set())
        self.assertEqual(v["bound_escapes"], set())
        # trace restored to off afterwards
        self.assertIsNone(self.ns["_VSA"]._fv_key_trace)

    def test_read_escape_is_caught(self):
        # A read of a key NOT in AXON_KEYS_READ ({animal}) must be flagged
        # unsound — the static analysis did not account for it.
        def run(vsa):
            a = vsa.axon_add(vsa.zero_vector(), "animal", 1.0)
            return vsa.axon_item(a, "user")  # "user" not statically read

        v = check_key_soundness(self.ns, run)
        self.assertFalse(v["sound"], v)
        self.assertIn("user", v["read_escapes"])

    def test_bound_escape_is_caught(self):
        # A bind of a key NOT in AXON_KEYS_BOUND ({animal,color}).
        def run(vsa):
            return vsa.axon_add(vsa.zero_vector(), "secret", 9.0)

        v = check_key_soundness(self.ns, run)
        self.assertFalse(v["sound"], v)
        self.assertIn("secret", v["bound_escapes"])

    def test_dynamic_vector_key_is_caught(self):
        # A non-str (pre-embedded vector) key the static analysis cannot
        # name is recorded as '<dynamic>' and flagged as an escape.
        def run(vsa):
            a = vsa.axon_add(vsa.zero_vector(), "animal", 1.0)
            keyvec = vsa.embed("animal")  # pre-embedded -> non-str at runtime
            return vsa.axon_item(a, keyvec)

        v = check_key_soundness(self.ns, run)
        self.assertFalse(v["sound"], v)
        self.assertIn("<dynamic>", v["read_escapes"])


# A program whose 3 consecutive `.add`s the peephole fuses into ONE
# `axon_build` (make_real values → no Ollama, so it runs end-to-end). Its
# static AXON_KEYS_BOUND = {x, y, z}. This is the path that would go VACUOUS
# if axon_build did not record to _fv_key_trace.
FUSED_SRC = (
    "function vector build() {\n"
    "    Axon a;\n"
    '    a.add("x", make_real(5.0));\n'
    '    a.add("y", make_real(8.0));\n'
    '    a.add("z", make_real(3.0));\n'
    "    return a;\n"
    "}\n"
    'function string main() { return "ok"; }\n'
)


class TestFVKeySoundnessFusedPath(unittest.TestCase):
    """The axon_build peephole (consecutive .add → one batched bmm) must trace
    its bound keys, or the soundness check is vacuous for every fused program
    (records, structs — the common case). Verified on the REAL compiled entry
    point, not a hand-written proxy."""

    def test_axon_build_peephole_path_is_traced_end_to_end(self):
        ns = _compile(FUSED_SRC)
        self.assertEqual(set(ns["AXON_KEYS_BOUND"]), {"x", "y", "z"})
        # Run the actual compiled program; every bound key must be traced.
        v = check_key_soundness(ns, lambda vsa: ns["build"]())
        self.assertTrue(v["sound"], v)
        self.assertEqual(
            v["runtime_bound"], {"x", "y", "z"},
            "axon_build did not trace its keys — checker vacuous for fused programs",
        )

    def test_axon_build_bound_escape_is_caught(self):
        # Non-vacuous through the fused path: a key outside the static set is
        # flagged even when bound via axon_build.
        ns = _compile(FUSED_SRC)

        def run(vsa):
            return vsa.axon_build(vsa.zero_vector(), ["x", "secret"], [1.0, 2.0])

        v = check_key_soundness(ns, run)
        self.assertFalse(v["sound"], v)
        self.assertIn("secret", v["bound_escapes"])

    def test_axon_build_dynamic_key_is_caught(self):
        # A pre-embedded (non-str) key through axon_build records as '<dynamic>'.
        ns = _compile(FUSED_SRC)

        def run(vsa):
            kv = vsa.embed("x")
            return vsa.axon_build(vsa.zero_vector(), [kv], [1.0])

        v = check_key_soundness(ns, run)
        self.assertFalse(v["sound"], v)
        self.assertIn("<dynamic>", v["bound_escapes"])


if __name__ == "__main__":
    unittest.main()
