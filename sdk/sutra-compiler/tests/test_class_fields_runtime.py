"""End-to-end runtime tests for object encapsulation — class fields + methods.

The encapsulation feature (`todo.md` § "Object encapsulation": axon-backed
immutable instance fields, `this.field`, instance-method dispatch, non-static
loops threading `this`) is fully implemented and parses (corpus
`22_class_with_fields.su`), but had NO end-to-end RUNTIME test — it could silently
regress. These compile each program, RUN it, and DECODE the result off the real
axis, comparing to ground truth (integrity discipline: verify the running
program, not just that it compiled).

Design (per `planning/sutra-spec/axons.md` class-field design): a field is an
immutable named slot set at construction; an instance is an axon; `new C(args)`
lowers to `axon_add` per field, `g.field` to `axon_item(g, "field")`.
"""
from __future__ import annotations

import types

import pytest

torch = pytest.importorskip("torch")

from sutra_compiler.codegen_pytorch import translate_module  # noqa: E402
from sutra_compiler.lexer import Lexer  # noqa: E402
from sutra_compiler.parser import Parser  # noqa: E402

_DIM = 64  # no codebook (numeric fields) → small semantic dim is fine


def _exec(src: str) -> types.ModuleType:
    lx = Lexer(src, file="<cf>")
    ps = Parser(lx.tokenize(), file="<cf>", diagnostics=lx.diagnostics)
    module = ps.parse_module()
    assert not lx.diagnostics.has_errors(), [str(d) for d in lx.diagnostics]
    py = translate_module(module, runtime_dim=_DIM)
    m = types.ModuleType("cf")
    exec(compile(py, "<cf>", "exec"), m.__dict__)
    return m


def _real(m, vec) -> float:
    """Decode the real-axis scalar of a number-vector."""
    return float(torch.dot(vec, m._VSA.make_real(1.0)))


def test_field_construction_and_read():
    m = _exec(
        "class Cat extends vector {\n"
        "    field int age;\n"
        "    field int weight;\n"
        "}\n"
        "function vector get_age() { Cat c = new Cat(5, 10); return c.age; }\n"
        "function vector get_weight() { Cat c = new Cat(5, 10); return c.weight; }\n"
        "function int main() { return 0; }\n"
    )
    assert _real(m, m.get_age()) == pytest.approx(5.0, abs=1e-2)
    assert _real(m, m.get_weight()) == pytest.approx(10.0, abs=1e-2)


def test_method_reads_this_field():
    m = _exec(
        "class Greeter extends vector {\n"
        "    field int base;\n"
        "    method int doubled() { return this.base + this.base; }\n"
        "}\n"
        "function vector run() { Greeter g = new Greeter(7); return g.doubled(); }\n"
        "function int main() { return 0; }\n"
    )
    assert _real(m, m.run()) == pytest.approx(14.0, abs=2e-2)


def test_non_static_loop_threads_this_field():
    # A non-static class loop reads this.field across iterations (A.3).
    m = _exec(
        "class Accum extends vector {\n"
        "    field int step;\n"
        "    method int run_to(int limit) {\n"
        "        int total = 0;\n"
        "        loop (3) { total = total + this.step; }\n"
        "        return total;\n"
        "    }\n"
        "}\n"
        "function vector go() { Accum a = new Accum(4); return a.run_to(3); }\n"
        "function int main() { return 0; }\n"
    )
    assert _real(m, m.go()) == pytest.approx(12.0, abs=2e-2)


def test_two_instances_are_independent():
    # Each `new` builds its own axon — instances don't share field state.
    m = _exec(
        "class Box extends vector {\n"
        "    field int v;\n"
        "    method int get() { return this.v; }\n"
        "}\n"
        "function vector a() { Box b = new Box(3); return b.get(); }\n"
        "function vector b() { Box b = new Box(99); return b.get(); }\n"
        "function int main() { return 0; }\n"
    )
    assert _real(m, m.a()) == pytest.approx(3.0, abs=1e-2)
    assert _real(m, m.b()) == pytest.approx(99.0, abs=1e-2)
