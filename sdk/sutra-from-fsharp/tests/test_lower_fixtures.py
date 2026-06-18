"""F#→Sutra fixture tests. Modeled on the OCaml/Scala frontend harnesses: each
fixture is lowered, compiled through the Sutra compiler, and (for runnable fixtures
with a callable `main`) RUN on the real substrate with the result compared to ground
truth — the compile-AND-run bar, not compile-only.

The grammar DLL is machine-local (built by build_grammar.py; no PyPI wheel exists);
the whole suite skips with a loud reason when it is absent."""
from __future__ import annotations

import pathlib
import subprocess
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent
_PKG = HERE.parent
if str(_PKG) not in sys.path:
    sys.path.insert(0, str(_PKG))
from sutra_from_fsharp.lower import grammar_available, lower  # noqa: E402

pytestmark = pytest.mark.skipif(
    not grammar_available(),
    reason="F# grammar DLL not built — run sdk/sutra-from-fsharp/build_grammar.py (needs MSVC)",
)

FIXTURE_DIR = HERE / "fixtures"
_REPO = HERE.parents[2]

# Fixtures with a callable `main` and a known substrate result.
_RUNNABLE = {
    "add_main": 16.0,  # let add a b = a + b; let main () = add 7 9
    "if_classify": 100.0,  # if n > 0 then 100 else 200; classify 5  (if -> defuzz blend)
    "paren_sum": 26.0,  # (add 7 9) + (double 5)  (parenthesized application + infix)
    "match_literal": 200.0,  # match n with | 1 -> 100 | 2 -> 200 | _ -> 300; classify 2
    "match_bind": 160.0,  # match n with | 0 -> 100 | x -> x * 10; (classify 0)+(classify 6) = 100+60
    "tail_rec": 15.0,  # let rec sumTo acc n = if n = 0 then acc else sumTo (acc+n) (n-1); sumTo 0 5
    "nontail_fact": 120.0,  # let rec fact n = if n = 0 then 1 else n * fact (n-1); fact 5  (CPS fold)
    "typed_params": 17.0,  # let add (a: int) (b: int) = a + b; add 8 9  (type-annotated params)
    "return_type": 13.0,  # let add (a: int) (b: int) : int = a + b; add 6 7  (return-type annotation, value_declaration_left path)
    "let_seq": 18.0,  # let f x = let a = x+1 \n let b = a*2 \n a+b; f 5 = 6+12  (let-sequence body, sequential subst)
    "record_axon": 13.0,  # type Point={x;y}; sum2 (p:Point)=p.x+p.y; main = sum2 {x=5;y=8}  (record -> axon, p.x -> realvec(item))
    "union_axon": 48.0,  # type Shape=Circle of int|Square of int; area via match; main = area (Circle 4) = 4*4*3  (DU -> tagged axon)
    "tuple_axon": 13.0,  # addPair (p: int*int) = (fst p)+(snd p); let t=(5,8) in addPair t  (tuple -> positional-key axon, fst/snd -> _0/_1)
    "tuple_destructure": 13.0,  # addPair (t: int*int) = let (a, b) = t in a + b; main = addPair (5,8)  (let-tuple-pattern -> realvec(item _0/_1))
    "nested_tuple_destructure": 16.0,  # f (t: int*(int*int)) = let (a,(b,c)) = t in a+b+c; main = f (5,(8,3))  (NESTED tuple pattern: nested-axon construction + Axon-temp chained item read)
    "record_destructure": 13.0,  # sum (p: Point) = let { x = a; y = b } = p in a + b; main = sum {x=5;y=8}  (let-record-pattern -> realvec(item x/y))
    "du_destructure": 13.0,  # type Shape=Circle of int|...; radius (s) = let (Circle r) = s in r + 1; main = radius (Circle 12)  (let-DU-pattern -> realvec(item _val0))
    "tuple_arg": 13.0,  # addPair (p: int*int) = fst p + snd p; main = addPair (5, 8)  (tuple construction DIRECTLY as arg -> hoisted to _ahN temp, F# arg-hoist parity)
    "nullary_variant": 20.0,  # type Dir=North|South; code (d) = match d with North->10|South->20; main = code South  (nullary DU variant in value position -> {_tag} axon)
    "record_update": 17.0,  # type Point={x;y}; bump (p) = let q = { p with x = 9 } in q.x+q.y; main = bump {x=1;y=8}  (record functional-update -> override x, copy y from p)
}


def _cases():
    if not FIXTURE_DIR.exists():
        return []
    return [(d.name, d) for d in sorted(FIXTURE_DIR.iterdir())
            if d.is_dir() and (d / "input.fsx").exists()]


@pytest.mark.parametrize("name,fix", _cases(), ids=[c[0] for c in _cases()])
def test_lowers_without_unsupported(name, fix):
    src = (fix / "input.fsx").read_text(encoding="utf-8")
    out = lower(src)
    assert "UNSUPPORTED" not in out, f"{name} lowered with UNSUPPORTED:\n{out}"


@pytest.mark.parametrize("name,expected",
                         sorted(_RUNNABLE.items()), ids=sorted(_RUNNABLE))
def test_runs_on_substrate(name, expected, tmp_path):
    pytest.importorskip("torch", reason="substrate run needs torch")
    fix = FIXTURE_DIR / name / "input.fsx"
    su = lower(fix.read_text(encoding="utf-8"))
    su_path = tmp_path / f"{name}.su"
    su_path.write_text(su, encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, "-m", "sutra_compiler", "--run", str(su_path)],
        capture_output=True, text=True, cwd=str(_REPO),
    )
    out = (proc.stdout + proc.stderr).strip()
    assert proc.returncode == 0, out
    import re
    m = re.search(r"tensor\(\s*(-?\d+\.?\d*)", out) or re.search(r"(-?\d+\.?\d*)\s*$", out)
    assert m, f"no numeric result in: {out}"
    assert abs(float(m.group(1)) - expected) < 0.5, f"{name}: got {out}, want {expected}"
