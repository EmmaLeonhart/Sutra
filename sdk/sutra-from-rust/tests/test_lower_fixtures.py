"""Rust→Sutra fixture tests. Modeled on the OCaml/Scala frontend harnesses: each
fixture is lowered, compiled through the Sutra compiler, and (for runnable fixtures
with a callable `main`) RUN on the real substrate with the result compared to ground
truth — the compile-AND-run bar, not compile-only."""
from __future__ import annotations

import pathlib
import subprocess
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent
_PKG = HERE.parent
if str(_PKG) not in sys.path:
    sys.path.insert(0, str(_PKG))
from sutra_from_rust.lower import lower  # noqa: E402

FIXTURE_DIR = HERE / "fixtures"
_REPO = HERE.parents[2]

# Fixtures with a callable `main` and a known substrate result.
_RUNNABLE = {
    "add_main": 16.0,  # fn add(a, b) { a + b }; main = add(7, 9)
    "if_classify": 100.0,  # if n > 0 { 100 } else { 200 }; classify(5)  (if -> defuzz blend)
    "let_block": 17.0,  # let y = x + 1; let z = y * 2; z + x  at x=5
    "enum_match": 2.0,  # enum Expr -> tagged axon; eval(Lit 7)=7 + eval(Neg 5)=-5
    "if_let_enum": 13.0,  # if let Shape::Circle(r) = s { r+1 } else { 0 }; radius(Circle(12))  (if-let enum destructure -> int _vtag tag test [crisp at 0] + _val0 bind)
    "nested_match_tail_arm": 5.0,  # match e { A(x) => match n { 0 => x, _ => x+1 }, B(y) => y }; f(A(5),0)=5  (LITERAL inner match in a tail-match arm -> inline blend)
    "tail_rec": 15.0,  # fn sum_to(acc, n) { if n==0 { acc } else { sum_to(acc+n, n-1) } }; sum_to(0, 5)
    "nontail_fact": 120.0,  # fn fact(n) { if n==0 { 1 } else { n * fact(n-1) } }; fact(5)  (CPS fold)
    "struct_axon": 12.0,  # struct Point -> axon; getx(a{7,9})=7 + sum2(Point{2,3})=5
    "while_sum": 15.0,  # let mut acc/i; while i < n { i+=1; acc+=i }; sum_to(5)=15  (while -> substrate loop)
    "while_compound": 15.0,  # same via compound assignment: i += 1; acc += i  (op= desugars to x = x op rhs)
    "loop_break": 15.0,  # loop { if i >= n { break; } acc += i; i += 1 }; sum_to(6)=0+..+5=15  (unbounded loop+break -> while !cond)
    "struct_shorthand": 13.0,  # let x=5; let y=8; sum2(Point { x, y })  (field-init shorthand -> S { x: x, y: y })
    "nested_match": 202.0,  # evalE e = 100 + match e {Lit n=>n, Neg n=>0-n}; evalE(Lit 7)=107 + evalE(Neg 5)=95  (match in expression position -> hoisted)
    "struct_spread": 17.0,  # let q = Point { x: 9, ..base }; q.x+q.y; base={1,8} -> q={9,8} = 17  (..base functional-update copies y)
    "tuple_axon": 13.0,  # fst(p: (i64,i64)) = p.0 + p.1; main = fst((5, 8))  (tuple -> positional-key axon, p.0 -> realvec(item _0))
    "tuple_destructure": 13.0,  # add_pair(t) { let (a, b) = t; a + b }; main = add_pair((5, 8))  (let-tuple-pattern -> realvec(item _0/_1))
    "nested_tuple_destructure": 16.0,  # f(t: (i64,(i64,i64))) { let (a,(b,c)) = t; a+b+c }; main = f((5,(8,3)))  (NESTED tuple pattern -> Axon temp for the _1 prefix, then realvec(item _0/_1))
    "struct_destructure": 13.0,  # sum(p: Point) { let Point { x, y } = p; x + y }; main = sum(Point{5,8})  (let-struct-pattern -> realvec(item x/y))
    "nested_struct_destructure": 13.0,  # f(o: Outer) { let Outer { a, inner: Inner { v } } = o; a + v }; main = f(Outer{a:5,inner:Inner{v:8}})  (NESTED struct pattern -> Axon temp for the inner-struct prefix)
    "nullary_variant": 20.0,  # enum Dir{North,South}; code(d) = match d { Dir::North=>10, Dir::South=>20 }; main = code(Dir::South)  (nullary variant value -> {_tag} axon; scoped match patterns NOT mis-hoisted)
    "nullary_variant_let": 20.0,  # ... main = { let d = Dir::South; code(d) }  (nullary variant let-value -> Axon-typed local, not int-bound-to-axon)
}


def _cases():
    if not FIXTURE_DIR.exists():
        return []
    return [(d.name, d) for d in sorted(FIXTURE_DIR.iterdir())
            if d.is_dir() and (d / "input.rs").exists()]


@pytest.mark.parametrize("name,fix", _cases(), ids=[c[0] for c in _cases()])
def test_lowers_without_unsupported(name, fix):
    src = (fix / "input.rs").read_text(encoding="utf-8")
    out = lower(src)
    assert "UNSUPPORTED" not in out, f"{name} lowered with UNSUPPORTED:\n{out}"


@pytest.mark.parametrize("name,expected",
                         sorted(_RUNNABLE.items()), ids=sorted(_RUNNABLE))
def test_runs_on_substrate(name, expected, tmp_path):
    pytest.importorskip("torch", reason="substrate run needs torch")
    fix = FIXTURE_DIR / name / "input.rs"
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
