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
    "struct_axon": 13.0,  # sum2(%Point{x: 6, y: 7})  (struct literal -> same named-field axon, alias dropped)
    "string_map_axon": 13.0,  # sum2(%{"x" => 5, "y" => 8}); p["x"] + p["y"]  (arrow-form string-key map -> axon, m["k"] -> realvec(item))
    "numkey_map_axon": 13.0,  # sum2(%{1 => 5, 2 => 8}); p[1] + p[2]  (numeric arrow-key map -> axon field "1"/"2", m[1] -> realvec(item))
    "tuple_axon": 13.0,  # fst(p)=elem(p,0)+elem(p,1); main=fst({5,8})  (tuple -> positional-key axon, elem -> realvec(item))
    "tuple_param": 13.0,  # add_pair({a, b}) = a + b; main = add_pair({5, 8})  (tuple-PATTERN param -> axon, a/b -> realvec(item _0/_1))
    "map_param": 13.0,  # sum2(%{x: a, y: b}) = a + b; main = sum2(%{x: 5, y: 8})  (map-PATTERN param -> axon, a/b -> realvec(item x/y))
    "match_bind_body": 13.0,  # sum2(t) = ( {a, b} = t; a + b ); main = sum2({5, 8})  (do-block = pattern-match destructure -> realvec(item _0/_1))
    "multiclause_fact": 120.0,  # def fac(0), do: 1; def fac(n), do: n * fac(n-1); main = fac(5)  (multi-clause pattern recursion -> synthesized (n==0) cond -> CPS fold loop)
    "struct_param": 13.0,  # sum2(%Point{x: a, y: b}) = a + b; main = sum2(%Point{x: 5, y: 8})  (struct-PATTERN param -> axon, alias dropped, a/b -> realvec(item x/y))
    "multiclause_tailsum": 15.0,  # def sum(0, acc), do: acc; def sum(n, acc), do: sum(n-1, acc+n); main = sum(5, 0)  (multi-PARAM multi-clause tail recursion -> while_loop)
    "guarded_fact": 120.0,  # def fac(n) when n == 0, do: 1; def fac(n), do: n * fac(n-1); main = fac(5)  (GUARDED-base multi-clause recursion -> guard as cond -> CPS fold loop)
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
