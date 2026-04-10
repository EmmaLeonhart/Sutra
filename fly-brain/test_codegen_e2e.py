"""End-to-end: the codegen'd permutation_conditional runs on the real
mushroom body and matches the expected program A/B/C/D behavior table.

Flow:
    1. Parse `fly-brain/permutation_conditional.ak` with the Akasha SDK.
    2. Run the AST -> FlyBrainVSA translator (codegen_flybrain).
    3. exec() the resulting Python in a private module namespace so the
       compile-time snap() calls fire on a live mushroom body.
    4. Call program_A / program_B / program_C / program_D on the four
       (smell, hunger) inputs and compare against the expected table
       from fly-brain/STATUS.md and fly-brain/DEMO.md.

This is the "compile to brain" pipeline end-to-end, in one file. If it
passes, the whole path from .ak source through parser, AST, codegen,
and spiking simulation is working.

Runs locally only — needs Brian2 installed. Not part of the SDK unit
test suite for that reason; run it explicitly:

    python fly-brain/test_codegen_e2e.py

Takes ~30-60 seconds because of 5 snap() calls against the Brian2 LIF
circuit (4 compile-time prototypes + 1 per decision * 16 decisions).
"""

from __future__ import annotations

import os
import sys
import types


HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, ".."))
SDK_PATH = os.path.join(REPO_ROOT, "sdk", "akasha-compiler")
SOURCE_AK = os.path.join(HERE, "permutation_conditional.ak")

# Make both the SDK package and the fly-brain helpers (vsa_operations,
# spike_vsa_bridge) importable.
sys.path.insert(0, SDK_PATH)
sys.path.insert(0, HERE)

from akasha_compiler.codegen_flybrain import translate_module  # noqa: E402
from akasha_compiler.lexer import Lexer  # noqa: E402
from akasha_compiler.parser import Parser  # noqa: E402


INPUT_LABELS = [
    "vinegar + hungry",
    "vinegar + fed",
    "clean_air + hungry",
    "clean_air + fed",
]

EXPECTED = {
    "A": ["approach", "ignore",   "search",   "idle"],
    "B": ["search",   "idle",     "approach", "ignore"],
    "C": ["ignore",   "approach", "idle",     "search"],
    "D": ["idle",     "search",   "ignore",   "approach"],
}


def compile_from_source():
    """Parse the .ak file and return the generated Python source string."""
    with open(SOURCE_AK, encoding="utf-8") as f:
        src = f.read()
    lexer = Lexer(src, file=SOURCE_AK)
    tokens = lexer.tokenize()
    parser = Parser(tokens, file=SOURCE_AK, diagnostics=lexer.diagnostics)
    module = parser.parse_module()
    if lexer.diagnostics.has_errors():
        for d in lexer.diagnostics:
            print(d.format(), file=sys.stderr)
        raise SystemExit(
            "refusing to codegen: source has parser/validator errors"
        )
    return translate_module(module)


def load_generated_module(py_src: str):
    """exec() the generated Python in a fresh module namespace.

    Module import is where the compile-time snap() calls fire, so this
    is a real mushroom-body workload, not a no-op.
    """
    mod = types.ModuleType("_e2e_generated_permutation_conditional")
    mod.__file__ = "<generated from permutation_conditional.ak>"
    exec(compile(py_src, mod.__file__, "exec"), mod.__dict__)
    return mod


def main() -> int:
    print("E2E: permutation_conditional.ak -> codegen -> mushroom body")
    print("=" * 72)
    print("Step 1: parse + translate")
    py_src = compile_from_source()
    print(f"  generated Python: {len(py_src.splitlines())} lines")

    print("Step 2: exec generated module (fires compile-time snap calls)")
    gen = load_generated_module(py_src)

    inputs = [
        (gen.smell_present, gen.hunger_hungry),
        (gen.smell_present, gen.hunger_fed),
        (gen.smell_absent,  gen.hunger_hungry),
        (gen.smell_absent,  gen.hunger_fed),
    ]
    program_fn = {
        "A": gen.program_A,
        "B": gen.program_B,
        "C": gen.program_C,
        "D": gen.program_D,
    }

    print("Step 3: run 16 decisions (4 programs x 4 inputs)")
    per_program = {}
    total = 0
    correct = 0
    for prog in ("A", "B", "C", "D"):
        row = []
        fn = program_fn[prog]
        for i, (smell, hunger) in enumerate(inputs):
            got = fn(smell, hunger)
            exp = EXPECTED[prog][i]
            total += 1
            if got == exp:
                correct += 1
            row.append((INPUT_LABELS[i], exp, got))
        per_program[prog] = row

    print()
    for prog in ("A", "B", "C", "D"):
        print(f"Program {prog}:")
        for label, exp, got in per_program[prog]:
            mark = "OK" if exp == got else "FAIL"
            print(f"  {label:<22} expected={exp:<10} got={got:<10} {mark}")
        print()

    distinct = len({
        tuple(r[2] for r in per_program[p]) for p in ("A", "B", "C", "D")
    })
    passed = correct == total and distinct == 4

    print("=" * 72)
    print(f"Decisions matching expected: {correct}/{total}")
    print(f"Distinct program mappings:   {distinct}/4")
    print(f"GATE: {'PASS' if passed else 'FAIL'}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
