"""End-to-end: codegen'd fuzzy_conditional runs on the MB and matches
the expected 4-program x 4-input behavior table.

Same shape as test_codegen_e2e.py but points at fuzzy_conditional.su —
the spec-aligned replacement for permutation_conditional.su. Closes the
compile-to-brain loop for the branching form used in the paper.

    python fly-brain/test_codegen_e2e_fuzzy.py
    python fly-brain/test_codegen_e2e_fuzzy.py --hemibrain
"""

from __future__ import annotations

import os
import sys
import types


HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, ".."))
SDK_PATH = os.path.join(REPO_ROOT, "sdk", "sutra-compiler")
SOURCE_AK = os.path.join(HERE, "fuzzy_conditional.su")

sys.path.insert(0, SDK_PATH)
sys.path.insert(0, HERE)

from sutra_compiler.codegen_flybrain import translate_module  # noqa: E402
from sutra_compiler.lexer import Lexer  # noqa: E402
from sutra_compiler.parser import Parser  # noqa: E402


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


def compile_from_source(use_hemibrain=False):
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
    return translate_module(module, runtime_use_hemibrain=use_hemibrain)


def load_generated_module(py_src: str):
    mod = types.ModuleType("_e2e_generated_fuzzy_conditional")
    mod.__file__ = "<generated from fuzzy_conditional.su>"
    exec(compile(py_src, mod.__file__, "exec"), mod.__dict__)
    return mod


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--hemibrain', action='store_true')
    ap.add_argument('--dump', action='store_true',
                    help='print generated Python and exit')
    args = ap.parse_args()

    substrate = "HEMIBRAIN connectome" if args.hemibrain else "mushroom body"
    print(f"E2E: fuzzy_conditional.su -> codegen -> {substrate}")
    print("=" * 72)
    py_src = compile_from_source(use_hemibrain=args.hemibrain)
    print(f"Step 1: generated Python: {len(py_src.splitlines())} lines")

    if args.dump:
        print(py_src)
        return 0

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
