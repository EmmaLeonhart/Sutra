"""Haskell→Sutra fixture tests. Modeled on the OCaml/Scala frontend harnesses: each
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
from sutra_from_haskell.lower import lower  # noqa: E402

FIXTURE_DIR = HERE / "fixtures"
_REPO = HERE.parents[2]

# Fixtures with a callable `main` and a known substrate result.
_RUNNABLE = {
    "add_main": 16.0,  # add a b = a + b; main = add 7 9
    "if_classify": 100.0,  # classify n = if n > 0 then 100 else 200; main = classify 5
    "tail_rec": 15.0,  # sumTo acc n = if n == 0 then acc else sumTo (acc+n) (n-1); main = sumTo 0 5
    "nontail_fact": 120.0,  # fact n = if n == 0 then 1 else n * fact (n-1); main = fact 5  (CPS fold)
    "pattern_eq": 120.0,  # classify 0/1/n equations -> dispatch fn; classify 0 + classify 2 = 100+20
    "guards": 120.0,  # classify n | n==0 | n==1 | otherwise -> guard blend; classify 0 + classify 2
    "where_block": 31.0,  # f x = y + z where y = x+1; z = x*2; main = f 10 = 11+20
    "let_block": 18.0,  # g x = let a = x+1; b = a*2 in a + b; main = g 5 = 6+12 (sequential bind)
    "data_adt": 2.0,  # data Expr = Lit Int | Neg Int; evalE via case; evalE(Lit 7)+evalE(Neg 5) = 7+(-5)  (ADT -> tagged axon)
}


def _cases():
    if not FIXTURE_DIR.exists():
        return []
    return [(d.name, d) for d in sorted(FIXTURE_DIR.iterdir())
            if d.is_dir() and (d / "input.hs").exists()]


@pytest.mark.parametrize("name,fix", _cases(), ids=[c[0] for c in _cases()])
def test_lowers_without_unsupported(name, fix):
    src = (fix / "input.hs").read_text(encoding="utf-8")
    out = lower(src)
    assert "UNSUPPORTED" not in out, f"{name} lowered with UNSUPPORTED:\n{out}"


@pytest.mark.parametrize("name,expected",
                         sorted(_RUNNABLE.items()), ids=sorted(_RUNNABLE))
def test_runs_on_substrate(name, expected, tmp_path):
    pytest.importorskip("torch", reason="substrate run needs torch")
    fix = FIXTURE_DIR / name / "input.hs"
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
