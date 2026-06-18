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
    "if_classify": 100.0,  # classify(N) -> if N > 0 -> 100; true -> 200 end; classify(5)
    "tail_rec": 15.0,  # sum_to(Acc, N) -> if N == 0 -> Acc; true -> sum_to(Acc+N, N-1) end; sum_to(0, 5)
    "nontail_fact": 120.0,  # fac(N) -> if N == 0 -> 1; true -> N * fac(N-1) end; fac(5)  (CPS fold)
    "guard_dispatch": 150.0,  # grade(N) when N>90/when N>50/(_N) -> guarded dispatch; 95+70+20 = 100+50+0
    "case_dispatch": 119.0,  # pick(X) -> case X of 1 -> 10; 2 -> 20; _ -> 99 end; pick(2)+pick(7) = 20+99
    "map_axon": 13.0,  # sum2(P) -> maps:get(1,P) + maps:get(2,P); main() -> sum2(#{1 => 5, 2 => 8})  (map -> axon, maps:get -> realvec(item))
    "tuple_axon": 13.0,  # fst(P)=element(1,P)+element(2,P); main=fst({5,8})  (tuple -> positional-key axon, element 1-based -> _0)
    "record_axon": 13.0,  # -record(point,{x,y}); fst(P)=P#point.x+P#point.y; main=fst(#point{x=5,y=8})  (record -> named-field axon, name dropped)
    "tuple_param": 13.0,  # fst({A, B}) -> A + B; main() -> fst({5, 8})  (tuple-PATTERN param -> axon, A/B -> realvec(item _0/_1))
    "record_param": 13.0,  # -record(point,{x,y}); fst(#point{x=X, y=Y}) -> X + Y; main() -> fst(#point{x=5, y=8})  (record-PATTERN param -> axon, X/Y -> realvec(item x/y))
    "map_param": 13.0,  # getx(#{x := X, y := Y}) -> X + Y; main() -> getx(#{x => 5, y => 8})  (map-PATTERN param -> axon, X/Y -> realvec(item x/y))
    "match_bind_body": 13.0,  # fst(P) -> {A, B} = P, A + B; main() -> fst({5, 8})  (body = match destructure -> realvec(item _0/_1))
    "multiclause_fact": 120.0,  # fac(0) -> 1; fac(N) -> N * fac(N-1); main() -> fac(5)  (multi-clause pattern recursion -> synthesized (N==0) cond -> CPS fold loop)
    "multiclause_tailsum": 15.0,  # sum(0, Acc) -> Acc; sum(N, Acc) -> sum(N-1, Acc+N); main() -> sum(5, 0)  (multi-PARAM multi-clause tail recursion -> while_loop)
    "guarded_fact": 120.0,  # fac(N) when N == 0 -> 1; fac(N) -> N * fac(N-1); main() -> fac(5)  (GUARDED-base multi-clause recursion -> guard as cond -> CPS fold loop)
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
