"""Content-based soft addressing IS a Sutra substrate primitive — and it's
differentiable on the substrate. (Emma 2026-06-08; NTM/DNC hard part.)

Discovery (grep-first, don't-invent): Sutra already has the content-addressed softmax
read. `select(scores, options)` (spec 26-select-and-gate.md; runtime `_select_softmax`)
is the softmax-weighted superposition; `similarity(q, k)` is the content match. So a
content-based addressing read is, on the substrate,
    select([similarity(q, K_0), …], [V_0, …])
exactly as `examples/fuzzy_dispatch.su` already does. No new softmax primitive is needed.

What this script measures, against the REAL emitted runtime ops (`_VSA.similarity`,
`_select_softmax` — not a hand-written torch softmax): that the content-addressed read is
DIFFERENTIABLE on the substrate, i.e. a query trained THROUGH the compiled substrate
select learns to address memory by content. This lifts the soft-vs-hard result
(content_addressed_read.py, raw torch) onto Sutra's actual primitive — the "logical
differentiable-ness that does stuff", on the substrate.

Soft (substrate `select`) should learn; a hard argmax pick over the same scores should be
inert (zero gradient to the query) — the same divergence, now through the compiled ops.

Training is the sanctioned compile-time fit role; the forward read uses substrate ops.
"""

from __future__ import annotations

import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str((REPO / "sdk" / "sutra-compiler").resolve()))

import torch  # noqa: E402

from sutra_compiler.lexer import Lexer  # noqa: E402
from sutra_compiler.parser import Parser  # noqa: E402
from sutra_compiler.codegen_pytorch import translate_module  # noqa: E402


def _compile_ns(runtime_dim: int = 16):
    """Compile a trivial module and return its namespace, so we can call the EXACT
    emitted runtime ops (`_VSA.similarity`, `_select_softmax`) the compiler produces."""
    src = 'function string main(){ return "ok"; }'
    lx = Lexer(src, file="<scr>")
    ast = Parser(lx.tokenize(), file="<scr>", diagnostics=lx.diagnostics).parse_module()
    ns: dict = {}
    exec(translate_module(ast, llm_model="none", runtime_dim=runtime_dim), ns)
    return ns


def _cos(a, b):
    return torch.dot(a, b) / (a.norm() * b.norm() + 1e-12)


def train_query(ns, mode: str, N: int = 6, target_row: int = 3, steps: int = 300,
                seed: int = 0, beta: float = 1.0):
    vsa = ns["_VSA"]
    select = ns["_select_softmax"]
    dim = vsa.dim
    g = torch.Generator(device="cpu").manual_seed(seed)
    # Memory: N content keys K_i and N value vectors V_i (distinct random vectors,
    # placed on the runtime device). These are the orchestrator-fetched cell contents.
    K = [torch.randn(dim, generator=g).to(dtype=vsa.dtype, device=vsa.device)
         for _ in range(N)]
    V = [torch.randn(dim, generator=g).to(dtype=vsa.dtype, device=vsa.device)
         for _ in range(N)]
    target = V[target_row]
    q = torch.randn(dim, generator=g).to(dtype=vsa.dtype, device=vsa.device)
    q.requires_grad_(True)
    opt = torch.optim.Adam([q], lr=0.1)
    grad0 = loss0 = None

    def read(qv):
        # Temperature via score-scaling: select() is a vanilla (fixed-T) softmax, so
        # multiplying the scores by beta IS the temperature control — the established
        # select-temperature pattern (similarity/T), here beta = 1/T. No primitive change.
        scores = [beta * vsa.similarity(qv, K[i]) for i in range(N)]  # substrate content match
        if mode == "soft":
            return select(scores, V)                            # substrate softmax read
        # hard: argmax over the scores, return that value (no gradient to q)
        st = torch.stack([s.detach() if torch.is_tensor(s) else torch.as_tensor(s)
                          for s in scores])
        return V[int(torch.argmax(st))]

    for step in range(steps):
        opt.zero_grad()
        r = read(q)
        loss = ((r - target) ** 2).mean()
        if loss.requires_grad:
            loss.backward()
            gnorm = float(q.grad.norm()) if q.grad is not None else 0.0
            opt.step()
        else:
            gnorm = 0.0
        if step == 0:
            grad0, loss0 = gnorm, float(loss.detach())
    with torch.no_grad():
        r = read(q)
        cos_target = float(_cos(r, target))
        # attention weight the substrate select puts on the target row (at this beta)
        scores = torch.stack([beta * vsa.similarity(q, K[i]) for i in range(N)])
        w = torch.softmax(scores - scores.amax(), dim=0)
        wt = float(w[target_row])
        lossN = float(((r - target) ** 2).mean())
    return {"mode": mode, "grad0": grad0, "loss0": loss0, "lossN": lossN,
            "cos_to_target": cos_target, "weight_on_target": wt}


def run(verbose: bool = True) -> dict:
    ns = _compile_ns()
    soft = train_query(ns, "soft")
    hard = train_query(ns, "hard")
    if verbose:
        print("content-based addressing through the COMPILED substrate select/similarity\n")
        for r in (soft, hard):
            print(f"  [{r['mode']:>4}] loss {r['loss0']:.3f} -> {r['lossN']:.3e}  "
                  f"||grad||@0 = {r['grad0']:.3e}  cos(read,target) = {r['cos_to_target']:.4f}  "
                  f"weight_on_target = {r['weight_on_target']:.4f}")
        print("\n  SOFT (substrate `select`) learns to address by content — gradient flows "
              "through the compiled softmax read into q; the read moves toward the target.")
        print("  HARD (argmax over the same scores) is inert — zero gradient to q.")
        print("  NOTE: `select` uses a fixed-beta(=1) softmax, so with close similarity "
              "scores the soft read stays a DIFFUSE blend (weight_on_target < 1); it learns\n"
              "  directionally but does not sharpen to a clean one-hot read. Sharpening is a "
              "temperature/beta lever (cf. experiments/select_temperature_adjustment.py), not\n"
              "  a differentiability issue.")
    return {"soft": soft, "hard": hard}


def temperature_sweep(verbose: bool = True) -> dict:
    """Sharpening: with a temperature (score-scaling by beta = 1/T) the substrate soft
    read converges from a diffuse blend (beta=1) to crisp content retrieval, while the
    gradient keeps flowing. This is the established select-temperature lever, not a
    primitive change."""
    ns = _compile_ns()
    out = {}
    for beta in (1.0, 4.0, 16.0, 64.0):
        out[beta] = train_query(ns, "soft", beta=beta)
    if verbose:
        print("\ntemperature sweep (beta = 1/T) on the substrate soft read:")
        for beta, r in out.items():
            print(f"  beta={beta:>5}  cos(read,target) = {r['cos_to_target']:.4f}  "
                  f"weight_on_target = {r['weight_on_target']:.4f}  "
                  f"||grad||@0 = {r['grad0']:.3e}")
    return out


def main() -> int:
    r = run(verbose=True)
    temperature_sweep(verbose=True)
    soft, hard = r["soft"], r["hard"]
    # The claim that is actually true and load-bearing: the substrate content-addressed
    # read is DIFFERENTIABLE (gradient flows) and LEARNS directionally (loss drops, read
    # moves toward the target), while the hard argmax read is INERT (zero gradient) and
    # does not. NOT claimed: full one-hot convergence (blocked by select's fixed beta=1).
    soft_learns = (soft["grad0"] > 1e-4 and soft["lossN"] < soft["loss0"]
                   and soft["cos_to_target"] > 0.5)
    hard_inert = hard["grad0"] < 1e-9
    soft_beats_hard = soft["cos_to_target"] > hard["cos_to_target"] + 0.3
    ok = soft_learns and hard_inert and soft_beats_hard
    print("\n" + ("PASS: the content-addressed read is DIFFERENTIABLE on the substrate "
                  "(via `select`+`similarity`) and learns directionally; hard argmax is "
                  "inert. (Full sharpening is a beta/temperature lever, not differentiability.)"
                  if ok else "RESULT did not match expected soft-learns/hard-inert — "
                  "inspect numbers."))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
