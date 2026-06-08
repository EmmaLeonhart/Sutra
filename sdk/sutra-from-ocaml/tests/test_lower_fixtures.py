"""Fixture-driven tests for the OCaml → Sutra lowering pass.

Each fixture is a directory under `tests/fixtures/` containing:
  - `input.ml`   — the OCaml source.
  - `expected.su` — the expected lowered Sutra source.

Two complementary tests per fixture, mirroring `sutra-from-ts`:

1. **Lowering test** (`test_fixture_lowering`): compares `lower(input)`
   against `expected.su` after normalizing comments and whitespace.
   Locks the lowering output; does not check runnability.

2. **Compilation test** (`test_fixture_compiles`): feeds `lower(input)`
   through the Sutra compiler and asserts it produces parsable Python.
   This is the parse → codegen → Python-syntax bar the TS harness uses;
   true end-to-end execution (compile AND run AND compare output) is a
   dedicated follow-on item in the work queue, exercised separately by
   `test_arith_main_runs_on_substrate` below for the one fixture that
   has a callable entry point.
"""

from __future__ import annotations

import pathlib
import re
import sys

import pytest

from sutra_from_ocaml.lower import lower


FIXTURE_DIR = pathlib.Path(__file__).parent / "fixtures"

# Fixtures whose lowered output does not yet compile through the Sutra
# compiler. Empty today; add entries (name → reason) as harder OCaml
# constructs land ahead of their Sutra codegen support.
_COMPILE_KNOWN_FAILURES: dict[str, str] = {}


def _normalize(text: str) -> str:
    out_lines = []
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped:
            continue
        if stripped.startswith("//"):
            continue
        out_lines.append(re.sub(r"\s+", " ", stripped))
    return "\n".join(out_lines)


def _collect_cases():
    cases = []
    if not FIXTURE_DIR.exists():
        return cases
    for d in sorted(FIXTURE_DIR.iterdir()):
        if not d.is_dir():
            continue
        inputs = sorted(d.glob("input.*"))
        expected = d / "expected.su"
        if inputs and expected.exists():
            cases.append((d.name, inputs[0], expected))
    return cases


_CASES = _collect_cases()


@pytest.mark.parametrize(
    "name,input_path,expected_path",
    _CASES,
    ids=[c[0] for c in _CASES],
)
def test_fixture_lowering(name, input_path, expected_path):
    src = input_path.read_text(encoding="utf-8")
    got = lower(src, source_path=input_path)
    expected = expected_path.read_text(encoding="utf-8")
    got_norm = _normalize(got)
    exp_norm = _normalize(expected)
    if got_norm != exp_norm:
        msg = (
            f"\nFixture: {name}\n"
            f"\n--- got (normalized) ---\n{got_norm}\n"
            f"\n--- expected (normalized) ---\n{exp_norm}\n"
            f"\n--- got (raw) ---\n{got}\n"
        )
        raise AssertionError(msg)


def _compile_with_sutra(sutra_src: str):
    """Lazy-import the sister sutra_compiler package and run the front
    of the pipeline (lex → parse → codegen). Returns the emitted Python
    source on success; raises on any compile failure."""
    repo_root = pathlib.Path(__file__).resolve().parents[3]
    compiler_src = repo_root / "sdk" / "sutra-compiler"
    if str(compiler_src) not in sys.path:
        sys.path.insert(0, str(compiler_src))
    from sutra_compiler.codegen import translate_module  # noqa: WPS433
    from sutra_compiler.lexer import Lexer  # noqa: WPS433
    from sutra_compiler.parser import Parser  # noqa: WPS433

    lexer = Lexer(sutra_src, file="<fixture>")
    tokens = lexer.tokenize()
    parser = Parser(tokens, file="<fixture>", diagnostics=lexer.diagnostics)
    module = parser.parse_module()
    if lexer.diagnostics.has_errors():
        errs = "\n".join(d.format() for d in lexer.diagnostics.errors)
        raise AssertionError(f"sutra parse/validate errors:\n{errs}")
    py_src = translate_module(module)
    compile(py_src, "<fixture>", "exec")
    return py_src


@pytest.mark.parametrize(
    "name,input_path,expected_path",
    _CASES,
    ids=[c[0] for c in _CASES],
)
def test_fixture_compiles(name, input_path, expected_path):
    if name in _COMPILE_KNOWN_FAILURES:
        pytest.xfail(_COMPILE_KNOWN_FAILURES[name])
    src = input_path.read_text(encoding="utf-8")
    sutra_src = lower(src, source_path=input_path)
    _compile_with_sutra(sutra_src)


# Fixtures with a callable `main ()` and a known ground-truth result.
# These get the full "compile AND run AND produce the expected output"
# treatment on the real substrate, beyond the parse/codegen syntax check.
_RUNNABLE_FIXTURES = {
    "arith_main": 7.0,   # main () = add 3 4
    "floatarith": 6.5,   # main () = addf 2.5 4.0
    "max": 5.0,          # main () = maxi 5 3  (if/then/else defuzz blend)
    "let_in": 10.0,      # main () = f 4  (let x = a+1 in x*2)
    "tail_rec_sum": 15.0,  # main () = sum_to 0 5  (tail rec -> while_loop)
    "tail_rec_swap": 7.0,  # main () = swaploop 7 9 2  (simultaneous update via temps)
    "match_lit": 200.0,    # main () = classify 1  (match -> nested defuzz blend)
    "record": 7.0,         # main () = getx (mk 7 9)  (record -> axon, field via .real())
    "variant": 200.0,      # main () = label Green  (nullary variant enum + ctor-pattern match)
    "bool_ops": 100.0,     # main () = test true false  (&& || not in a condition)
    "toplevel_const": 50.0,  # main () = (300 - mask) + bump  (top-level value bindings; hex 0xFF -> 255)
    "seq_mut": 15.0,  # main () = let r = ref 0 in r := !r+5; r := !r+10; !r  (sequence + ref mutation)
    "while_sum": 10.0,  # main () = while !i<5 do sum:=!sum+!i; i:=!i+1 done; !sum  (while -> substrate loop)
    "char_code": 65.0,  # main () = 'A'  (char literal -> codepoint int)
    "nested_fn": 16.0,  # main () = let dbl x = x*2 in dbl 5 + dbl 3  (closed nested fn hoisted)
    "tuple_fst_snd": 16.0,  # main () = sum2 (pair 7 9)  (tuple -> positional axon; fst/snd off Axon param)
    "match_bind": 6.0,  # classify 5 = match n with 0 -> 100 | x -> x+1  (catch-all name binding)
    "match_or": 300.0,  # classify 2 + 8 + 5 = match | 1|2|3 -> 100 | 7|8 -> 200 | _ -> 0  (or-pattern -> ||)
    "match_guard": 60.0,  # sign 7/0/-4 via | x when x>0 -> 1 | 0 -> 0 | _ -> -1  (guard -> && / blend test)
    "match_record": 16.0,  # sum (mk 7 9) via match p with {x; y} -> x + y  (record-destructure -> field reads)
    "record_arg": 16.0,  # sum2 { x = 7; y = 9 }  (record literal in arg position -> hoisted to a temp Axon)
    "tuple_arg": 16.0,  # sum2 (7, 9)  (tuple literal in arg position -> hoisted to a temp positional Axon)
    "tail_rec_bool": 15.0,  # f 0 5 = if (n=0)||(acc>100) then acc else f (acc+n) (n-1)  (boolean halt -> !(...) continue)
    "option_some": 42.0,  # get_or (mk 42) 0  (option Some/None -> tagged axon; match binds payload via int locals)
    "let_in_expr": 20.0,  # (let x = 5 in x + x) + 10  (let..in in expression position via substitution)
    "modulo": 2.0,  # 17 mod 5  (OCaml mod -> Sutra %)
    "tuple_local": 16.0,  # let p = pair 7 9 in fst p + snd p  (Axon-returning call -> local typed Axon)
    "bitwise": 1043.0,  # (255 land 12)+((3 lsl 8) lor 7)+(1024 lsr 2)  (land/lor->Bits, lsl/lsr->arith)
    "failwith_sentinel": 0.0,  # failwith "boom" -> 0 (no-runtime-error sentinel)
    # Attention-on-RAM parser (NTM-archetype track; design doc
    # planning/exploratory/codable-attention-on-ram-parser.md). One constructed
    # attention head reading a RAM tape; cross-language oracle = experiments/
    # attention_on_ram/reference.py. acc-in-RAM loop shape (scalar slot can't hold
    # a vector ramRead; O2 finding 2026-06-08-attention-on-ram-substrate.md).
    "attn_sum_tape": 10.0,      # sum_tape([1;2;3;4])  (q=ones -> Σ tape)
    "attn_dot_tape": -2.0,      # dot_tape([1;2;3],[1;0;-1])  (Σ wᵢxᵢ = lin. regression)
    "attn_select_field": 22.0,  # select_field([11;22;33],1)  (hard location read)
}


def _extract_result(out: str) -> float:
    """Pull the numeric result from `sutrac --run` output, which may be
    a bare float (`5.0`) or a tensor repr (`tensor(5., device='cuda:0')`)
    depending on backend/device."""
    last = out.splitlines()[-1].strip() if out else ""
    m = re.search(r"tensor\(\s*(-?\d+\.?\d*)", last) or re.search(
        r"(-?\d+\.\d+|-?\d+)", last
    )
    if m is None:
        raise AssertionError(f"no numeric result in output:\n{out}")
    return float(m.group(1))


@pytest.mark.parametrize("fixture_name,expected", sorted(_RUNNABLE_FIXTURES.items()))
def test_fixture_runs_on_substrate(tmp_path, fixture_name, expected):
    """Transpile a fixture with a callable entry → `.su`, then run it on
    the real Sutra substrate (PyTorch codegen via `sutrac --run`) and
    assert `main()` matches ground truth. The "compile AND run AND
    produce the expected output" bar.

    Skipped when torch is unavailable (the substrate runtime needs it),
    so CI without the heavy runtime stays green instead of failing.
    """
    pytest.importorskip("torch")
    import subprocess

    fixture = FIXTURE_DIR / fixture_name / "input.ml"
    sutra_src = lower(fixture.read_text(encoding="utf-8"), source_path=fixture)
    su_path = tmp_path / f"{fixture_name}.su"
    su_path.write_text(sutra_src, encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, "-m", "sutra_compiler", "--run", str(su_path)],
        capture_output=True,
        text=True,
    )
    out = (proc.stdout + proc.stderr).strip()
    assert proc.returncode == 0, f"sutrac --run failed:\n{out}"
    got = _extract_result(out)
    assert abs(got - expected) < 0.5, (
        f"{fixture_name}: expected ~{expected}, got {got}\n{out}"
    )
