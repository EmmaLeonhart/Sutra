"""echo — the smallest userspace utility, migrated from Yantra to Sutra
as a KERNEL-FREE demo (Phase-3 migration, 2026-05-29).

Yantra ran echo.su as a kernel-admitted SutraService routed over R_stdin/
R_stdout axon channels (apps/echo + apps/terminal). Here it is
re-architected to skip the kernel entirely: compile echo.su with
`compile_su`, call its `on_axon` function directly on a host-built axon,
and decode the result — exactly the pattern `demos/font` and `demos/gui`
use. No `kernel.Init`, no `Manifest`, no `admit`, no router.

The string round-trips on the substrate (rotation-bind into the axon,
echo re-binds under "stdout_text", the host unbinds + decodes); the
returned value is the SUBSTRATE's decode, not a host re-echo.

Substrate-honesty note: echo DOES touch the frozen LLM. The axon keys
"stdin_text"/"stdout_text" are embedded via `_VSA.embed(key)` (Ollama,
nomic-embed-text) — the runtime `embed` has no random fallback, so a real
model is required (the Yantra echo.toml's "LLM codebook never touched at
dim=16" describes the *source* having no explicit basis_vector calls, but
axon_add/axon_item embed their keys). What IS cheap is the dimension: the
string value rides one rotation binding, which inverts exactly, so the
round-trip is bit-exact even at small dim. Measured 5/5 exact for the demo
strings (incl. "echo world", 10 chars) at every runtime_dim in
{16, 32, 64, 128, 256} (2026-05-29), so dim=16 is the floor used here.

Requires Ollama with nomic-embed-text. Run: py demos/echo/echo_demo.py
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "sdk", "sutra-compiler"))

# Smallest dim that round-trips the demo strings exactly (measured 5/5 at
# dims 16..256; the string rides a single rotation binding, which inverts
# exactly). The two axon keys are embedded via the LLM (nomic).
RUNTIME_DIM = 16
LLM_MODEL = "nomic-embed-text"

_COMPILED: dict = {}


def _compile() -> dict:
    cached = _COMPILED.get("echo.su")
    if cached is not None:
        return cached
    from sutra_compiler import compile_su

    mod = compile_su(
        os.path.join(HERE, "echo.su"),
        llm_model=LLM_MODEL,
        runtime_dim=RUNTIME_DIM,
        verbose=False,
    )
    _COMPILED["echo.su"] = mod.__dict__
    return mod.__dict__


def echo(text: str) -> str:
    """Run `text` through echo.su on the substrate and return the decoded
    result (the substrate's decode, not a host re-echo of the input)."""
    ns = _compile()
    on_axon, vsa = ns["on_axon"], ns["_VSA"]
    inp = vsa.axon_add(vsa.zero_vector(), "stdin_text", vsa.make_string(text))
    out = on_axon(inp)
    return vsa.string_to_python(vsa.axon_item(out, "stdout_text"))


def main() -> None:
    print("echo.su — kernel-free substrate round-trip (Phase-3 migration)")
    ok = True
    for t in ["hello", "echo world", "Sutra", "42", "a"]:
        got = echo(t)
        match = got == t
        ok = ok and match
        print(f"  echo({t!r}) -> {got!r}  {'OK' if match else 'MISMATCH'}")
    print("all round-trips exact" if ok else "SOME MISMATCHES (see above)")


if __name__ == "__main__":
    main()
