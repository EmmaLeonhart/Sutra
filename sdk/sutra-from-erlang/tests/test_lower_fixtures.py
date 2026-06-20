"""Erlang→Sutra fixture tests. Modeled on the Clojure/Elixir frontend harnesses:
each fixture is lowered, compiled through the Sutra compiler, and (for runnable
fixtures with a callable `main`) RUN on the real substrate with the result compared
to ground truth — the compile-AND-run bar, not compile-only.

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
from sutra_from_erlang.lower import grammar_available, lower  # noqa: E402

pytestmark = pytest.mark.skipif(
    not grammar_available(),
    reason="Erlang grammar DLL not built — run sdk/sutra-from-erlang/build_grammar.py (needs MSVC)",
)

FIXTURE_DIR = HERE / "fixtures"
_REPO = HERE.parents[2]

# Fixtures with a callable `main` and a known substrate result.
_RUNNABLE = {
    "add_main": 16.0,  # add(A, B) -> A + B; main() -> add(7, 9)
    "div_rem": 5.0,  # main() -> (17 div 5) + (17 rem 5) = 3 + 2  (div -> Math.trunc(A/B); rem -> % -> _VSA.fmod, sign of dividend)
    "if_classify": 100.0,  # classify(N) -> if N > 0 -> 100; true -> 200 end; classify(5)
    "tail_rec": 15.0,  # sum_to(Acc, N) -> if N == 0 -> Acc; true -> sum_to(Acc+N, N-1) end; sum_to(0, 5)
    "nontail_fact": 120.0,  # fac(N) -> if N == 0 -> 1; true -> N * fac(N-1) end; fac(5)  (CPS fold)
    "guard_dispatch": 150.0,  # grade(N) when N>90/when N>50/(_N) -> guarded dispatch; 95+70+20 = 100+50+0
    "case_dispatch": 119.0,  # pick(X) -> case X of 1 -> 10; 2 -> 20; _ -> 99 end; pick(2)+pick(7) = 20+99
    "bool_case": 10.0,  # f(B) -> case B of true -> 10; false -> 20 end; main() -> f(true)  (Bool atom case pattern -> (B == true/false) blend)
    "map_axon": 13.0,  # sum2(P) -> maps:get(1,P) + maps:get(2,P); main() -> sum2(#{1 => 5, 2 => 8})  (map -> axon, maps:get -> realvec(item))
    "tuple_axon": 13.0,  # fst(P)=element(1,P)+element(2,P); main=fst({5,8})  (tuple -> positional-key axon, element 1-based -> _0)
    "record_axon": 13.0,  # -record(point,{x,y}); fst(P)=P#point.x+P#point.y; main=fst(#point{x=5,y=8})  (record -> named-field axon, name dropped)
    "tuple_param": 13.0,  # fst({A, B}) -> A + B; main() -> fst({5, 8})  (tuple-PATTERN param -> axon, A/B -> realvec(item _0/_1))
    "record_param": 13.0,  # -record(point,{x,y}); fst(#point{x=X, y=Y}) -> X + Y; main() -> fst(#point{x=5, y=8})  (record-PATTERN param -> axon, X/Y -> realvec(item x/y))
    "map_param": 13.0,  # getx(#{x := X, y := Y}) -> X + Y; main() -> getx(#{x => 5, y => 8})  (map-PATTERN param -> axon, X/Y -> realvec(item x/y))
    "match_bind_body": 13.0,  # fst(P) -> {A, B} = P, A + B; main() -> fst({5, 8})  (body = match destructure -> realvec(item _0/_1))
    "multiclause_bind_body": 13.0,  # sel(Flag,T) when Flag>0 -> {A,B}=T, A+B; sel(_,_) -> 0; sel(1,{5,8})  (MULTI-CLAUSE guarded body with a = destructure binding)
    "multiclause_fact": 120.0,  # fac(0) -> 1; fac(N) -> N * fac(N-1); main() -> fac(5)  (multi-clause pattern recursion -> synthesized (N==0) cond -> CPS fold loop)
    "multiclause_tailsum": 15.0,  # sum(0, Acc) -> Acc; sum(N, Acc) -> sum(N-1, Acc+N); main() -> sum(5, 0)  (multi-PARAM multi-clause tail recursion -> while_loop)
    "guarded_fact": 120.0,  # fac(N) when N == 0 -> 1; fac(N) -> N * fac(N-1); main() -> fac(5)  (GUARDED-base multi-clause recursion -> guard as cond -> CPS fold loop)
    "multibase_tailsum": 105.0,  # f(0,Acc)->Acc; f(1,Acc)->Acc+100; f(N,Acc)->f(N-1,Acc+N); f(3,0)=105  (>2-CLAUSE multi-literal-base tail recursion: continue = (N!=0)&&(N!=1) compound halt [§0.3], post-loop = nested blend of base bodies on final state)
    "guarded_rec_clause": 15.0,  # f(N,Acc) when N>0 -> f(N-1,Acc+N); f(_,Acc) -> Acc; f(5,0)=15  (Mode C: GUARDED RECURSIVE clause + catch-all base -> continue = the recursive guard, base is post-loop value)
    "multibase_nontail_fact": 600.0,  # f(0)->1; f(1)->5; f(N)->N*f(N-1); f(5)=5*4*3*2*f(1)=120*5=600  (>2-CLAUSE multi-literal-base NON-TAIL recursion -> CPS fold: acc seeded to OP identity, leaf folded each step, post-loop acc*base_blend on final state)
    "guarded_multibase": 9114.0,  # f(0,Acc)->Acc; f(1,Acc)->Acc+100; f(N,Acc) when N>50 -> Acc+9000; f(N,Acc)->f(N-1,Acc+N); f(5,0)+f(60,0)=114+9000  (MIXED literal + `when`-guard >2-clause multibase tail recursion: continue = (N!=0)&&(N!=1)&&(N<=50) compound halt with guard term, post-loop = source-order blend keyed by (N==K)/guard)
    "string_case": 60.0,  # classify(S) -> case S of "foo"->10; "bar"->20; _->30 end; classify("foo")+("bar")+("baz") = 60  (Erlang string literal + case string pattern -> eq_synthetic)
    "string_concat": 100.0,  # cat(A,B) -> A ++ B; classify(S) -> case S of "foobar"->100; _->200; classify(cat("foo","bar"))  (`++` over charlists -> substrate string concat; `++`-operand params inferred String)
    "type_test_guard": 12.0,  # kind(X) when is_number(X)->1; kind(_X)->2; main = kind(5)*10 + kind("hello") = 12  (is_number->is_number_truth [= NOT-a-String]: 5->1, "hello"->catch-all 2; substrate-pure truth scatter in the clause blend. 2-way: is_tuple/is_list/is_map need an axon tag that was reverted — see the finding. is_binary excluded: Erlang strings are charlists)
}


def _cases():
    if not FIXTURE_DIR.exists():
        return []
    return [(d.name, d) for d in sorted(FIXTURE_DIR.iterdir())
            if d.is_dir() and (d / "input.erl").exists()]


@pytest.mark.parametrize("name,fix", _cases(), ids=[c[0] for c in _cases()])
def test_lowers_without_unsupported(name, fix):
    src = (fix / "input.erl").read_text(encoding="utf-8")
    out = lower(src)
    assert "UNSUPPORTED" not in out, f"{name} lowered with UNSUPPORTED:\n{out}"


@pytest.mark.parametrize("name,expected",
                         sorted(_RUNNABLE.items()), ids=sorted(_RUNNABLE))
def test_runs_on_substrate(name, expected, tmp_path):
    pytest.importorskip("torch", reason="substrate run needs torch")
    fix = FIXTURE_DIR / name / "input.erl"
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
