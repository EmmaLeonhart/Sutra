"""CPS + trampolining — approach 2 to non-tail recursion on the substrate.

The raw non-tail recursion `fact n = n * fact (n-1)` has pending work (`n *`) and never
halts on Sutra's both-branches blend (no call stack) — it lowers to UNSUPPORTED. The CPS /
accumulator rewrite `fact n acc = if n=0 then acc else fact (n-1) (acc*n)` makes the
recursion tail-recursive, reifying the continuation as `acc`; the OCaml frontend lowers it
to a Sutra `while_loop` — the trampoline — and it runs on the substrate.

This harness lowers both OCaml sources through the frontend, confirms the raw form is
UNSUPPORTED and the CPS form compiles, then RUNS the CPS form on the real substrate
(`sutrac --run`) and checks the result against the host factorial.
"""
from __future__ import annotations

import math
import pathlib
import subprocess
import sys
import tempfile

_REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "sdk" / "sutra-from-ocaml"))
sys.path.insert(0, str(_REPO / "sdk" / "sutra-compiler"))
HERE = pathlib.Path(__file__).resolve().parent


def _lower(ml_name: str) -> str:
    from sutra_from_ocaml.lower import lower
    return lower((HERE / ml_name).read_text(encoding="utf-8"))


def raw_is_unsupported() -> bool:
    """The raw non-tail factorial lowers to UNSUPPORTED (no stack on the substrate)."""
    return "UNSUPPORTED" in _lower("cps_factorial_raw.ml")


def run_cps_on_substrate() -> float:
    """Lower the CPS/accumulator factorial and run it on the real substrate."""
    su = _lower("cps_factorial.ml")
    assert "while_loop" in su, "CPS form should lower to a while_loop (the trampoline)"
    assert "UNSUPPORTED" not in su, su
    path = pathlib.Path(tempfile.gettempdir()) / "cps_factorial_eval.su"
    path.write_text(su, encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, "-m", "sutra_compiler", "--run", str(path)],
        capture_output=True, text=True, cwd=str(_REPO),
    )
    out = (proc.stdout + proc.stderr).strip()
    assert proc.returncode == 0, out
    # result printed either as a decoded float or as a tensor repr like
    # "tensor(120., device='cuda:0')" — extract the value, ignoring the device suffix.
    import re
    m = re.search(r"tensor\(\s*(-?\d+\.?\d*)", out)
    if m:
        return float(m.group(1))
    cleaned = re.sub(r"device='[^']*'", "", out)        # drop cuda:0 etc.
    nums = re.findall(r"-?\d+\.?\d*", cleaned)
    return float(nums[-1]) if nums else float("nan")


def main() -> int:
    raw_unsup = raw_is_unsupported()
    got = run_cps_on_substrate()
    want = float(math.factorial(5))
    match = abs(got - want) < 1e-5
    print(f"raw non-tail factorial -> UNSUPPORTED: {raw_unsup}")
    print(f"CPS factorial on substrate = {got} (host 5! = {want}) match={match}")
    ok = raw_unsup and match
    print("CPS+TRAMPOLINE APPROACH:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
