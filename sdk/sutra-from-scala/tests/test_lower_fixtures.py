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
    "case_class": 12.0,  # case class Point -> axon; getx(mk(7,9))=7 + sum2(Point(2,3))=5
    "tail_rec": 15.0,  # def sumTo(acc,n) = if (n==0) acc else sumTo(acc+n, n-1); sumTo(0,5)
    "match_guard": 60.0,  # case 0 => 100; case x if x > 0 => x*10; case _ => 300; classify(6)
    "nontail_fact": 120.0,  # def fact(n) = if (n==0) 1 else n * fact(n-1); fact(5)  (CPS fold)
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
    fix = FIXTURE_DIR / name / "input.scala"
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
