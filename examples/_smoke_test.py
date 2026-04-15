"""Smoke test: compile + exec both demo .su files and print outputs.

Run from anywhere:
    python examples/_smoke_test.py

Exit code 0 on pass (outputs match hardcoded expected tables), 1 on fail.
"""
from __future__ import annotations

import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, ".."))
SDK_PATH = os.path.join(REPO_ROOT, "sdk", "sutra-compiler")
sys.path.insert(0, SDK_PATH)

from sutra_compiler.codegen_numpy import translate_module  # noqa: E402
from sutra_compiler.lexer import Lexer  # noqa: E402
from sutra_compiler.parser import Parser  # noqa: E402


def compile_to_module(src_path: str) -> types.ModuleType:
    with open(src_path, encoding="utf-8") as f:
        src = f.read()
    lexer = Lexer(src, file=src_path)
    tokens = lexer.tokenize()
    parser = Parser(tokens, file=src_path, diagnostics=lexer.diagnostics)
    module = parser.parse_module()
    py_src = translate_module(module)
    mod = types.ModuleType(os.path.basename(src_path))
    mod.__file__ = f"<generated from {src_path}>"
    exec(compile(py_src, mod.__file__, "exec"), mod.__dict__)
    return mod


def run_hello_world() -> bool:
    path = os.path.join(HERE, "hello_world.su")
    mod = compile_to_module(path)
    print("=" * 72)
    print("Example 0: hello_world.su (embed + retrieve — the minimal program)")
    print("=" * 72)
    got = mod.say()
    exp = "hello world"
    mark = "OK" if got == exp else "FAIL"
    print(f"  say() expected={exp!r} got={got!r} {mark}")
    print()
    return got == exp


def run_fuzzy_branching() -> bool:
    path = os.path.join(HERE, "fuzzy_branching.su")
    mod = compile_to_module(path)
    inputs = [
        ("vinegar + hungry", mod.smell_present, mod.hunger_hungry),
        ("vinegar + fed",    mod.smell_present, mod.hunger_fed),
        ("clean_air + hungry", mod.smell_absent, mod.hunger_hungry),
        ("clean_air + fed",    mod.smell_absent, mod.hunger_fed),
    ]
    expected = {
        "A": ["approach", "ignore",   "search",   "idle"],
        "B": ["search",   "idle",     "approach", "ignore"],
        "C": ["ignore",   "approach", "idle",     "search"],
        "D": ["idle",     "search",   "ignore",   "approach"],
    }
    fns = {"A": mod.program_A, "B": mod.program_B,
           "C": mod.program_C, "D": mod.program_D}

    print("=" * 72)
    print("Example 1: fuzzy_branching.su (weighted superposition conditionals)")
    print("=" * 72)
    total = 0
    correct = 0
    for prog in "ABCD":
        print(f"Program {prog}:")
        for i, (label, s, h) in enumerate(inputs):
            got = fns[prog](s, h)
            exp = expected[prog][i]
            mark = "OK" if got == exp else "FAIL"
            print(f"  {label:<22} expected={exp:<10} got={got:<10} {mark}")
            total += 1
            correct += got == exp
        print()
    print(f"{correct}/{total} decisions match expected")
    return correct == total


def run_role_filler() -> bool:
    path = os.path.join(HERE, "role_filler_record.su")
    mod = compile_to_module(path)
    records = [
        ("alice",  "red",   "circle",
         mod.f_alice, mod.f_red,  mod.f_circle),
        ("bob",    "blue",  "square",
         mod.f_bob,   mod.f_blue, mod.f_square),
    ]
    print("=" * 72)
    print("Example 2: role_filler_record.su (bind/bundle/unbind records)")
    print("=" * 72)
    total = 0
    correct = 0
    for name_lbl, color_lbl, shape_lbl, name_v, color_v, shape_v in records:
        rec = mod.make_record(name_v, color_v, shape_v)
        queries = [
            ("r_name",  mod.r_name,  name_lbl),
            ("r_color", mod.r_color, color_lbl),
            ("r_shape", mod.r_shape, shape_lbl),
        ]
        print(f"record = make_record({name_lbl}, {color_lbl}, {shape_lbl})")
        for role_lbl, role_v, exp in queries:
            got = mod.decode_field(rec, role_v)
            mark = "OK" if got == exp else "FAIL"
            print(f"  decode_field(record, {role_lbl:<8}) expected={exp:<8} got={got:<8} {mark}")
            total += 1
            correct += got == exp
        print()
    print(f"{correct}/{total} decodes match expected")
    return correct == total


def run_classifier() -> bool:
    path = os.path.join(HERE, "classifier.su")
    mod = compile_to_module(path)
    tests = [
        ("fruit_apple", mod.fruit_apple, "fruit"),
        ("fruit_pear",  mod.fruit_pear,  "fruit"),
        ("fruit_mango", mod.fruit_mango, "fruit"),
        ("veh_car",     mod.veh_car,     "vehicle"),
        ("veh_truck",   mod.veh_truck,   "vehicle"),
        ("veh_bike",    mod.veh_bike,    "vehicle"),
        ("tool_hammer", mod.tool_hammer, "tool"),
        ("tool_saw",    mod.tool_saw,    "tool"),
        ("tool_drill",  mod.tool_drill,  "tool"),
    ]
    print("=" * 72)
    print("Example 3: classifier.su (bundled prototype classifier)")
    print("=" * 72)
    total = 0
    correct = 0
    for label, vec, exp in tests:
        got = mod.classify(vec)
        mark = "OK" if got == exp else "FAIL"
        print(f"  classify({label:<12}) expected={exp:<8} got={got:<8} {mark}")
        total += 1
        correct += got == exp
    print()
    print(f"{correct}/{total} classifications match expected")
    return correct == total


def run_analogy() -> bool:
    path = os.path.join(HERE, "analogy.su")
    mod = compile_to_module(path)
    tests = [
        ("paris",  mod.paris,  "france"),
        ("tokyo",  mod.tokyo,  "japan"),
        ("london", mod.london, "uk"),
        ("rome",   mod.rome,   "italy"),
        ("cairo",  mod.cairo,  "egypt"),
    ]
    print("=" * 72)
    print("Example 4: analogy.su (associative pair memory: capital -> country)")
    print("=" * 72)
    total = 0
    correct = 0
    for lbl, v, exp in tests:
        got = mod.country_of(v)
        mark = "OK" if got == exp else "FAIL"
        print(f"  country_of({lbl:<6}) expected={exp:<8} got={got:<8} {mark}")
        total += 1
        correct += got == exp
    print()
    print(f"{correct}/{total} recalls match expected")
    return correct == total


def main() -> int:
    ok0 = run_hello_world()
    ok1 = run_fuzzy_branching()
    print()
    ok2 = run_role_filler()
    print()
    ok3 = run_classifier()
    print()
    ok4 = run_analogy()
    print()
    print("=" * 72)
    if ok0 and ok1 and ok2 and ok3 and ok4:
        print("PASS")
        return 0
    print("FAIL")
    return 1


if __name__ == "__main__":
    sys.exit(main())
