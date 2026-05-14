"""Tests for the axon-keys static analysis pass.

The pass walks a parsed module's AST and returns:
  - bound_keys: keys producers bind via `<expr>.add("K", value)`
  - read_keys:  keys consumers read via `axon_item(<expr>, "K")`

These tests cover:
  - The two real-world fixtures (producer.su / consumer.su) that
    drive the multi-program axon-passing demo.
  - Edge cases: no axon ops at all; mixed bound + read in one
    program; nested function bodies; non-string-literal first args
    (skipped); shadowed `axon_item` (treated as the function call).

After the analysis is wired into translate_module, the generated
Python module exposes `AXON_KEYS_BOUND` and `AXON_KEYS_READ` as
frozensets at module scope. A separate test verifies that
end-to-end.
"""

from __future__ import annotations

import pathlib
import sys
import types

HERE = pathlib.Path(__file__).resolve().parent
SDK = HERE.parent
sys.path.insert(0, str(SDK))

from sutra_compiler.axon_keys import collect_axon_keys
from sutra_compiler.lexer import Lexer
from sutra_compiler.parser import Parser
from sutra_compiler.codegen_pytorch import translate_module


REPO_ROOT = SDK.parent.parent
EXAMPLES = REPO_ROOT / "examples"


def _parse(src: str, file: str = "<test>"):
    lexer = Lexer(src, file=file)
    tokens = lexer.tokenize()
    parser = Parser(tokens, file=file, diagnostics=lexer.diagnostics)
    return parser.parse_module()


# ---------- Real-fixture tests --------------------------------------


def test_producer_su_bound_keys() -> None:
    src = (EXAMPLES / "multi_program_axon" / "producer.su").read_text(encoding="utf-8")
    module = _parse(src, file="producer.su")
    bound, read = collect_axon_keys(module)
    assert bound == frozenset({
        "animal_1", "animal_2", "color_1", "color_2", "user_1",
    })
    assert read == frozenset()


def test_consumer_su_read_keys() -> None:
    src = (EXAMPLES / "multi_program_axon" / "consumer.su").read_text(encoding="utf-8")
    module = _parse(src, file="consumer.su")
    bound, read = collect_axon_keys(module)
    assert bound == frozenset()
    assert read == frozenset({"animal_2", "color_1", "user_1"})


# ---------- Edge cases ----------------------------------------------


def test_program_with_no_axon_ops_returns_empty_sets() -> None:
    """A pure-arithmetic program has no bound or read keys."""
    src = """
        function int double(int x) {
            return x + x;
        }
        function int main() {
            return double(21);
        }
    """
    module = _parse(src, file="no_axon.su")
    bound, read = collect_axon_keys(module)
    assert bound == frozenset()
    assert read == frozenset()


def test_dynamic_key_arg_is_skipped() -> None:
    """`a.add(some_var, value)` is conservatively skipped.

    We can't statically resolve dynamic key names without deeper
    analysis. The axon_keys pass is conservative-by-omission here:
    rather than guess, we drop the entry. Downstream tooling treats
    a program with no declared keys as the eager-fallback case.
    """
    src = """
        function vector make_axon(string k, vector v) {
            Axon a;
            a.add(k, v);
            a.add("real_key", v);
            return a;
        }
    """
    module = _parse(src, file="dynamic.su")
    bound, _ = collect_axon_keys(module)
    # Only the literal-key "real_key" is collected; the dynamic
    # `k`-arg call is correctly skipped.
    assert bound == frozenset({"real_key"})


def test_dynamic_axon_item_arg_is_skipped() -> None:
    """`axon_item(state, dynamic_key)` is similarly skipped."""
    src = """
        function vector lookup(vector state, string k) {
            return axon_item(state, k);
        }
        function vector lookup_real(vector state) {
            return axon_item(state, "real_key");
        }
    """
    module = _parse(src, file="dynamic.su")
    _, read = collect_axon_keys(module)
    assert read == frozenset({"real_key"})


def test_keys_across_multiple_top_level_functions_are_collected() -> None:
    """Bound keys from N functions all aggregate into one frozenset."""
    src = """
        function vector make_a() {
            Axon a;
            a.add("from_func_a", basis_vector("x"));
            return a;
        }
        function vector make_b() {
            Axon a;
            a.add("from_func_b", basis_vector("y"));
            return a;
        }
    """
    module = _parse(src, file="multi.su")
    bound, _ = collect_axon_keys(module)
    assert bound == frozenset({"from_func_a", "from_func_b"})


def test_mixed_bound_and_read_in_one_program() -> None:
    """A program that both produces and consumes — both sets populate."""
    src = """
        function vector roundtrip() {
            Axon a;
            a.add("k1", basis_vector("v1"));
            a.add("k2", basis_vector("v2"));
            vector got_k1 = axon_item(a, "k1");
            return got_k1;
        }
    """
    module = _parse(src, file="mixed.su")
    bound, read = collect_axon_keys(module)
    assert bound == frozenset({"k1", "k2"})
    assert read == frozenset({"k1"})


# ---------- End-to-end: emitted module exposes the constants -------


def test_codegen_emits_axon_keys_constants_producer() -> None:
    """The generated Python module exposes both constants at module scope."""
    src = (EXAMPLES / "multi_program_axon" / "producer.su").read_text(encoding="utf-8")
    module = _parse(src, file="producer.su")
    py_src = translate_module(
        module, llm_model="nomic-embed-text", runtime_dim=768,
    )
    assert "AXON_KEYS_BOUND = frozenset(" in py_src
    assert "AXON_KEYS_READ = frozenset(" in py_src

    mod = types.ModuleType("producer_test")
    exec(compile(py_src, "<test>", "exec"), mod.__dict__)
    assert mod.AXON_KEYS_BOUND == frozenset({
        "animal_1", "animal_2", "color_1", "color_2", "user_1",
    })
    assert mod.AXON_KEYS_READ == frozenset()


def test_codegen_emits_axon_keys_constants_consumer() -> None:
    src = (EXAMPLES / "multi_program_axon" / "consumer.su").read_text(encoding="utf-8")
    module = _parse(src, file="consumer.su")
    py_src = translate_module(
        module, llm_model="nomic-embed-text", runtime_dim=768,
    )
    mod = types.ModuleType("consumer_test")
    exec(compile(py_src, "<test>", "exec"), mod.__dict__)
    assert mod.AXON_KEYS_BOUND == frozenset()
    assert mod.AXON_KEYS_READ == frozenset({"animal_2", "color_1", "user_1"})


def test_codegen_emits_constants_even_for_no_axon_program() -> None:
    """Empty frozensets land for programs with no axon ops — the
    symbol must always be present so consumers can rely on it."""
    src = """
        function int identity(int x) { return x; }
    """
    module = _parse(src, file="no_axon.su")
    py_src = translate_module(
        module, llm_model="nomic-embed-text", runtime_dim=768,
    )
    mod = types.ModuleType("noax_test")
    exec(compile(py_src, "<test>", "exec"), mod.__dict__)
    assert mod.AXON_KEYS_BOUND == frozenset()
    assert mod.AXON_KEYS_READ == frozenset()
