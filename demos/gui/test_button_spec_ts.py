"""B5 — the JS→Sutra tie-in: the button render authored in TypeScript, transpiled to Sutra.

`button_spec.ts` expresses the trainable button's quartic-squircle render math in TypeScript;
`sutra-from-ts` lowers it to `button_spec.su`. This is the concrete "linked to the JS stuff"
path for the GUI/browser layer. These tests verify that the transpiled Sutra program COMPILES
and RUNS (its `main` lights the button centre = 1.0, matching the hand-written
button_frame.su), and — when the TS frontend is installed — that re-transpiling reproduces the
committed `.su`.

The committed `button_spec.su` lets CI verify the JS→Sutra artifact without needing `ts2su`
installed on the runner; only the Sutra compiler is required.
"""
from __future__ import annotations

import pathlib
import sys

import pytest

_DIR = pathlib.Path(__file__).resolve().parent
_REPO_ROOT = _DIR.parent.parent
_SUTRA_SDK = _REPO_ROOT / "sdk" / "sutra-compiler"
if str(_SUTRA_SDK) not in sys.path:
    sys.path.insert(0, str(_SUTRA_SDK))


def test_transpiled_button_spec_compiles_and_centre_is_lit():
    """The TS-authored, transpiled button render compiles and its `main` lights the button
    centre (= 1.0): centred button, page=0, fill=1 → centre channel = 0 − 0·1 + 1·1 = 1."""
    from sutra_compiler import compile_su
    su = _DIR / "button_spec.su"
    assert su.exists(), "button_spec.su (transpiled from button_spec.ts) is missing"
    mod = compile_su(su, llm_model="unused-no-basis-vectors", runtime_dim=8, verbose=False)
    result = mod.main()
    val = result.real if hasattr(result, "is_complex") and result.is_complex() else result
    # Numbers-on-substrate: `main`'s arithmetic returns a real-axis number-VECTOR
    # (the value on AXIS_REAL, zeros elsewhere), not a 0-d scalar — project it to
    # its real-axis scalar at the display boundary before reading out (the same
    # role as the font demos' `read_real`).
    val = mod._VSA._num_re(val)
    val = float(val.item()) if hasattr(val, "item") else float(val)
    assert abs(val - 1.0) < 1e-5, f"transpiled button centre = {val}, expected 1.0"


def test_button_spec_su_regenerates_from_ts():
    """If the TS frontend is installed, re-transpiling button_spec.ts reproduces the committed
    button_spec.su (modulo the generator header) — guards against drift between the TS source
    and the committed Sutra artifact."""
    pytest.importorskip("sutra_from_ts")
    import subprocess
    import tempfile

    ts = _DIR / "button_spec.ts"
    committed = (_DIR / "button_spec.su").read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory() as tmp:
        out = pathlib.Path(tmp) / "regen.su"
        r = subprocess.run([sys.executable, "-m", "sutra_from_ts", str(ts), "-o", str(out)],
                           capture_output=True, text=True)
        if r.returncode != 0:
            pytest.skip(f"ts2su not runnable here: {r.stderr.strip()[:200]}")
        regen = out.read_text(encoding="utf-8")

    def _body(s: str) -> str:
        # Drop the leading generator-comment header; compare the program body only.
        return "\n".join(l for l in s.splitlines() if not l.strip().startswith("//")).strip()

    assert _body(regen) == _body(committed), "button_spec.su is stale vs button_spec.ts — re-run ts2su"
