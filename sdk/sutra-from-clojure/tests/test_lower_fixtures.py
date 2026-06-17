"""Clojure→Sutra fixture tests. Modeled on the OCaml/Scala frontend harnesses: each
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
from sutra_from_clojure.lower import grammar_available, lower  # noqa: E402

pytestmark = pytest.mark.skipif(
    not grammar_available(),
    reason="Clojure grammar DLL not built — run sdk/sutra-from-clojure/build_grammar.py (needs MSVC)",
)

FIXTURE_DIR = HERE / "fixtures"
_REPO = HERE.parents[2]

# Fixtures with a callable `main` and a known substrate result.
_RUNNABLE = {
    "add_main": 16.0,  # (defn add [a b] (+ a b)); (main) = (add 7 9)
    "if_classify": 100.0,  # (if (> n 0) 100 200); (classify 5)  (if -> defuzz blend)
    "nary_sum": 16.0,  # (+ a b c d) n-ary left-fold; (sum4 1 2 3 (* 2 5))
    "let_block": 17.0,  # (let [y (+ x 1) z (* y 2)] (+ z x)) at x=5  (sequential let subst)
    "cond_grade": 150.0,  # (cond (> n 90) 100 (> n 50) 50 :else 0); grade(95)=100 + grade(70)=50
    "tail_rec": 15.0,  # (defn sumTo [acc n] (if (= n 0) acc (recur (+ acc n) (- n 1)))); (sumTo 0 5)
    "nontail_fact": 120.0,  # (defn fact [n] (if (= n 0) 1 (* n (fact (- n 1))))); (fact 5)  (CPS fold)
    "loop_recur": 15.0,  # (loop [acc 0 i 0] (if (< i n) (recur (+ acc i) (+ i 1)) acc)); sumLoop(6)
    "case_dispatch": 119.0,  # (case x 1 10 2 20 3 30 99); (classify 2)=20 + (classify 7)=99 default
    "case_multilist": 300.0,  # (case x (1 3 5) 100 (2 4) 200 999); (classify 3)=100 + (classify 4)=200  (multi-constant test lists -> OR)
    "map_axon": 13.0,  # (defn sum2 [p] (+ (:x p) (:y p))); (sum2 {:x 5 :y 8})  (map -> axon, (:k m) -> realvec(item))
    "map_get": 13.0,  # (defn sum2 [p] (+ (get p :x) (get p :y))); (sum2 {"x" 6 "y" 7})  ((get m k) access + string-key map)
    "map_numkey": 13.0,  # (defn sum2 [p] (+ (get p 1) (get p 2))); (sum2 {1 5 2 8})  (numeric map keys -> axon field "1"/"2")
    "vector_axon": 13.0,  # (defn fst [v] (+ (nth v 0) (nth v 1))); (let [w [5 8]] (fst w))  (data vector -> positional-key axon; let binding-vec NOT hoisted as data)
    "vector_first_second": 13.0,  # (defn fst [v] (+ (first v) (second v))); (let [w [5 8]] (fst w))  (first/second -> _0/_1 vector accessors)
    "let_destructure": 13.0,  # (let [[a b] [5 8]] (+ a b))  (vector destructuring bind -> realvec(item _0/_1); inner pattern vec NOT hoisted)
    "map_destructure_keys": 13.0,  # (let [{:keys [a b]} {:a 5 :b 8}] (+ a b))  (:keys map destructuring -> realvec(item a/b); pattern map+vec NOT hoisted)
    "map_destructure_named": 13.0,  # (let [{a :x b :y} {:x 5 :y 8}] (+ a b))  ({local :field} map destructuring -> realvec(item x/y))
}


def _cases():
    if not FIXTURE_DIR.exists():
        return []
    return [(d.name, d) for d in sorted(FIXTURE_DIR.iterdir())
            if d.is_dir() and (d / "input.clj").exists()]


@pytest.mark.parametrize("name,fix", _cases(), ids=[c[0] for c in _cases()])
def test_lowers_without_unsupported(name, fix):
    src = (fix / "input.clj").read_text(encoding="utf-8")
    out = lower(src)
    assert "UNSUPPORTED" not in out, f"{name} lowered with UNSUPPORTED:\n{out}"


@pytest.mark.parametrize("name,expected",
                         sorted(_RUNNABLE.items()), ids=sorted(_RUNNABLE))
def test_runs_on_substrate(name, expected, tmp_path):
    pytest.importorskip("torch", reason="substrate run needs torch")
    fix = FIXTURE_DIR / name / "input.clj"
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
