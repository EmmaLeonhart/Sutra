"""Scala→Sutra fixture tests. Modeled on the OCaml frontend harness: each fixture is
lowered, compiled through the Sutra compiler, and (for runnable fixtures with a callable
`main`) RUN on the real substrate with the result compared to ground truth — the
compile-AND-run bar, not compile-only."""
from __future__ import annotations

import pathlib
import subprocess
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent
_PKG = HERE.parent
if str(_PKG) not in sys.path:
    sys.path.insert(0, str(_PKG))
from sutra_from_scala.lower import lower  # noqa: E402

FIXTURE_DIR = HERE / "fixtures"
_REPO = HERE.parents[2]

# Fixtures with a callable `main` and a known substrate result.
_RUNNABLE = {
    "add_main": 16.0,  # def add(a,b)=a+b; def main()=add(7,9)
    "if_classify": 100.0,  # if (n>0) 100 else 200; classify(5)  (if -> defuzz blend)
    "val_block": 17.0,  # { val y=x+1; val z=y*2; z+x } at x=5  (block val bindings -> Sutra locals)
    "match_literal": 200.0,  # n match {1=>100; 2=>200; _=>300} at n=2  (literal match -> nested blend)
    "bool_match": 10.0,  # f(b: Boolean) = b match { case true => 10; case false => 20 }; f(true)  (Bool match pattern -> (b == true/false) blend)
    "case_class": 12.0,  # case class Point -> axon; getx(mk(7,9))=7 + sum2(Point(2,3))=5
    "tuple_axon": 13.0,  # def fst(p: (Int,Int)) = p._1 + p._2; main = fst((5, 8))  (tuple -> positional-key axon, 1-based _1/_2 to match ._1 access)
    "tuple_destructure": 13.0,  # def addPair(t: (Int,Int)) = { val (a, b) = t; a + b }; main = addPair((5, 8))  (val-tuple-pattern -> realvec(item _1/_2), 1-based)
    # NESTED tuple pattern. (expected, runtime_dim): nested axons reusing 1-based keys (_1/_2)
    # cross-talk at low dims; run at 256 (measured clean across all nested fixtures; cross-talk
    # is non-monotonic — 100/128/196 each collide for some key set — finding 2026-06-17).
    "nested_tuple_destructure": (16.0, 256),  # def f(t: (Int,(Int,Int))) = { val (a,(b,c)) = t; a+b+c }; f((5,(8,3)))
    "caseclass_destructure": 13.0,  # case class Point(x,y); sum(p) = { val Point(a, b) = p; a + b }; main = sum(Point(5, 8))  (val-case-class-pattern -> realvec(item x/y) positionally)
    "caseclass_match": 13.0,  # case class Point(x,y); sum(p) = p match { case Point(a, b) => a + b }; main = sum(Point(5, 8))  (case-class MATCH pattern -> positional realvec(item x/y))
    "nested_caseclass_destructure": (16.0, 256),  # case class Inner(x,y), Outer(inner,z); sum(o) = { val Outer(Inner(a, b), c) = o; a+b+c }; sum(Outer(Inner(5,8),3))  (NESTED case-class val pattern -> Axon temp for the inner prefix; dim>=256, finding 2026-06-17)
    "caseclass_in_tuple": (13.0, 256),  # case class Box(v); f(t: (Int,Box)) = { val (a, Box(v)) = t; a+v }; f((5, Box(8)))  (MIXED: case class nested in a tuple pattern; _collect_scala_tuple_paths cross-calls _collect_caseclass_paths; dim>=256, finding 2026-06-17)
    "tuple_in_caseclass": (16.0, 256),  # case class Outer(a, pos: (Int,Int)); g(o) = { val Outer(a, (x, y)) = o; a+x+y }; g(Outer(5,(8,3)))  (MIXED: tuple nested in a case-class pattern; _collect_caseclass_paths cross-calls _collect_scala_tuple_paths; dim>=256, finding 2026-06-17)
    "tail_rec": 15.0,  # def sumTo(acc,n) = if (n==0) acc else sumTo(acc+n, n-1); sumTo(0,5)
    "match_guard": 60.0,  # case 0 => 100; case x if x > 0 => x*10; case _ => 300; classify(6)
    "nontail_fact": 120.0,  # def fact(n) = if (n==0) 1 else n * fact(n-1); fact(5)  (CPS fold)
    "object_dispatch": 26.0,  # object Calc { add, twice }; Calc.add(7,9)=16 + Calc.twice(5)=10
    "string_eq": 30.0,  # classify(s) = if (s == "foo") 10 else 20; classify("foo")+classify("bar") = 10+20  (Scala string LITERAL -> Sutra string; == routes to eq_synthetic via the String type)
    "string_concat": 100.0,  # cat(a,b)=a+b; f(s)=if (s=="foobar") 100 else 200; f(cat("foo","bar"))  (String `+` -> substrate string concat; result eq_synthetic-matches "foobar")
    "string_match": 60.0,  # classify(s) = s match { case "foo" => 10; case "bar" => 20; case _ => 30 }; classify("foo")+("bar")+("baz") = 10+20+30  (string-LITERAL case pattern -> scrut == "lit" nested blend, eq_synthetic dispatch)
}


def _cases():
    if not FIXTURE_DIR.exists():
        return []
    return [(d.name, d) for d in sorted(FIXTURE_DIR.iterdir())
            if d.is_dir() and (d / "input.scala").exists()]


@pytest.mark.parametrize("name,fix", _cases(), ids=[c[0] for c in _cases()])
def test_lowers_without_unsupported(name, fix):
    src = (fix / "input.scala").read_text(encoding="utf-8")
    out = lower(src)
    assert "UNSUPPORTED" not in out, f"{name} lowered with UNSUPPORTED:\n{out}"


@pytest.mark.parametrize("name,expected",
                         sorted(_RUNNABLE.items()), ids=sorted(_RUNNABLE))
def test_runs_on_substrate(name, expected, tmp_path):
    pytest.importorskip("torch", reason="substrate run needs torch")
    # A fixture value may be `expected` or `(expected, runtime_dim)` — nested-axon
    # fixtures need a higher dim than the CLI default (finding 2026-06-17).
    dim = None
    if isinstance(expected, tuple):
        expected, dim = expected
    fix = FIXTURE_DIR / name / "input.scala"
    su = lower(fix.read_text(encoding="utf-8"))
    su_path = tmp_path / f"{name}.su"
    su_path.write_text(su, encoding="utf-8")
    cmd = [sys.executable, "-m", "sutra_compiler", "--run"]
    if dim is not None:
        cmd += ["--runtime-dim", str(dim)]
    cmd.append(str(su_path))
    proc = subprocess.run(
        cmd, capture_output=True, text=True, cwd=str(_REPO),
    )
    out = (proc.stdout + proc.stderr).strip()
    assert proc.returncode == 0, out
    import re
    m = re.search(r"tensor\(\s*(-?\d+\.?\d*)", out) or re.search(r"(-?\d+\.?\d*)\s*$", out)
    assert m, f"no numeric result in: {out}"
    assert abs(float(m.group(1)) - expected) < 0.5, f"{name}: got {out}, want {expected}"
