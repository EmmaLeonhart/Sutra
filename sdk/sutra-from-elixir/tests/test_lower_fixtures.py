"""Elixir→Sutra fixture tests. Modeled on the OCaml/Scala frontend harnesses: each
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
from sutra_from_elixir.lower import lower  # noqa: E402

FIXTURE_DIR = HERE / "fixtures"
_REPO = HERE.parents[2]

# Fixtures with a callable `main` and a known substrate result.
_RUNNABLE = {
    "add_main": 16.0,  # def add(a, b), do: a + b; main = add(7, 9)
    "if_classify": 100.0,  # if n > 0 do 100 else 200 end; classify(5)  (if -> defuzz blend)
    "tail_rec": 15.0,  # def sum_to(acc, n) do if n == 0 do acc else sum_to(acc+n, n-1) end end; sum_to(0, 5)
    "nontail_fact": 120.0,  # def fact(n) do if n == 0 do 1 else n * fact(n-1) end end; fact(5)  (CPS fold)
    "case_literal": 200.0,  # case n do 1 -> 100; 2 -> 200; _ -> 300 end; classify(2)  (nested blend)
    "case_bind": 60.0,  # case n do 0 -> 100; x -> x * 10 end; classify(6)  (name-binding pattern)
    "multiclause": 120.0,  # def classify(0)/( 1)/(n) heads -> dispatch fn; classify(0)+classify(2) = 100+20
    "guard_clause": 150.0,  # def grade(n) when n>90/when n>50/(_n) -> guarded dispatch; grade(95)+grade(70)+grade(20) = 100+50+0
    "pipe_chain": 16.0,  # 5 |> add(3) |> double() -> double(add(5,3)) = double(8) = 16
    "map_axon": 13.0,  # def sum2(p), do p.x + p.y; sum2(%{x: 5, y: 8})  (map -> axon, dot -> realvec(item))
}


def _cases():
    if not FIXTURE_DIR.exists():
        return []
    return [(d.name, d) for d in sorted(FIXTURE_DIR.iterdir())
            if d.is_dir() and (d / "input.ex").exists()]


@pytest.mark.parametrize("name,fix", _cases(), ids=[c[0] for c in _cases()])
def test_lowers_without_unsupported(name, fix):
    src = (fix / "input.ex").read_text(encoding="utf-8")
    out = lower(src)
    assert "UNSUPPORTED" not in out, f"{name} lowered with UNSUPPORTED:\n{out}"


@pytest.mark.parametrize("name,expected",
                         sorted(_RUNNABLE.items()), ids=sorted(_RUNNABLE))
def test_runs_on_substrate(name, expected, tmp_path):
    pytest.importorskip("torch", reason="substrate run needs torch")
    fix = FIXTURE_DIR / name / "input.ex"
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
