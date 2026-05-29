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


if __name__ == "__main__":
    unittest.main()
