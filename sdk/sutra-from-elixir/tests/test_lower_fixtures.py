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
    "bool_case": 10.0,  # f(b) = case b do true -> 10; false -> 20 end; main = f(true)  (Bool case pattern -> (b == true/false) blend)
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
    "string_map_param": 13.0,  # sum2(%{"x" => a, "y" => b}) = a + b; main = sum2(%{"x" => 5, "y" => 8})  (STRING-key arrow-map PATTERN param -> realvec(item x/y), via _map_fields)
    "match_bind_body": 13.0,  # sum2(t) = ( {a, b} = t; a + b ); main = sum2({5, 8})  (do-block = pattern-match destructure -> realvec(item _0/_1))
    "multiclause_bind_body": 13.0,  # def sel(flag,t) when flag>0 do {a,b}=t; a+b end; def sel(_,_) do 0; sel(1,{5,8})  (MULTI-CLAUSE guarded body with a = destructure binding)
    "multiclause_fact": 120.0,  # def fac(0), do: 1; def fac(n), do: n * fac(n-1); main = fac(5)  (multi-clause pattern recursion -> synthesized (n==0) cond -> CPS fold loop)
    "struct_param": 13.0,  # sum2(%Point{x: a, y: b}) = a + b; main = sum2(%Point{x: 5, y: 8})  (struct-PATTERN param -> axon, alias dropped, a/b -> realvec(item x/y))
    "multiclause_tailsum": 15.0,  # def sum(0, acc), do: acc; def sum(n, acc), do: sum(n-1, acc+n); main = sum(5, 0)  (multi-PARAM multi-clause tail recursion -> while_loop)
    "guarded_fact": 120.0,  # def fac(n) when n == 0, do: 1; def fac(n), do: n * fac(n-1); main = fac(5)  (GUARDED-base multi-clause recursion -> guard as cond -> CPS fold loop)
    "multibase_tailsum": 105.0,  # def f(0,acc),do: acc; def f(1,acc),do: acc+100; def f(n,acc),do: f(n-1,acc+n); f(3,0)=105  (>2-CLAUSE multi-literal-base tail recursion: continue = (n!=0)&&(n!=1) compound halt [§0.3], post-loop = nested blend of base bodies on final state)
    "guarded_rec_clause": 15.0,  # def f(n,acc) when n>0,do: f(n-1,acc+n); def f(_,acc),do: acc; f(5,0)=15  (Mode C: GUARDED RECURSIVE clause + catch-all base -> continue = the recursive guard, base is post-loop value)
    "multibase_nontail_fact": 600.0,  # def f(0),do: 1; def f(1),do: 5; def f(n),do: n*f(n-1); f(5)=5*4*3*2*f(1)=120*5=600  (>2-CLAUSE multi-literal-base NON-TAIL recursion -> CPS fold: acc seeded to OP identity, leaf folded each step, post-loop acc*base_blend on final state)
    "multiarg_nontail_multibase": 115.0,  # def f(0,b),do: b; def f(1,b),do: b+100; def f(a,b),do: a+f(a-1,b); f(3,10)=3+2+(10+100)=115  (MULTI-ARG non-tail multibase fold: loop carries (a,b,_acc), folds _acc+a each step, base blend keyed on final (a,b); _foldable_step_multi)
    "guarded_multibase": 9114.0,  # def f(0,acc)->acc; f(1,acc)->acc+100; f(n,acc) when n>50 -> acc+9000; f(n,acc)->f(n-1,acc+n); f(5,0)+f(60,0)=114+9000  (MIXED literal + `when`-guard >2-clause multibase tail recursion: continue = (n!=0)&&(n!=1)&&(n<=50) compound halt with guard term, post-loop = source-order blend keyed by (n==k)/guard)
    "string_case": 60.0,  # case s do "foo"->10; "bar"->20; _->30 end; classify("foo")+("bar")+("baz") = 60  (string literal + case string pattern -> eq_synthetic)
    "string_eq": 30.0,  # classify(s) = if s == "foo" do 10 else 20; classify("foo")+classify("bar") = 10+20  (string literal + `==` -> eq_synthetic via the literal operand; one-line `do:/else:` if mis-parses, multi-line works)
    "string_concat": 100.0,  # cat(a,b) = a <> b; classify(s) = if s == "foobar" do 100 else 200; classify(cat("foo","bar"))  (`<>` -> substrate string concat; `<>`-operand params inferred String so `+` routes to concat)
    "type_test_guard": 12.0,  # def kind(x) when is_binary(x),do: 1; def kind(_x),do: 2; main = kind("a")*10 + kind(5) = 12  (is_binary->is_string_truth [AXIS_STRING_FLAG]: "a"->1, 5->catch-all 2; a substrate-pure truth scatter blended in the clause dispatch. 2-way: is_list/is_map/is_tuple need an axon tag that was reverted — see the finding)
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
