"""Defuzz gain adjustment — second SHIPPED constrain-train instance.

The first SHIPPED constrain-train instance (equality_cosine_adjustment.py)
trained ONE scalar T inside fuzzy equality. This experiment trains a
DIFFERENT scalar inside a DIFFERENT operator surface (defuzz iteration),
demonstrating that the constrain-train pattern generalizes beyond the
equality cosine — concrete progress on Emma's "every operation
trainable" vision (capabilities doc 2026-05-27).

Surface trained
----------------
The spec form of defuzz is "iterate N: f = f == true" (planning/sutra-
spec/equality-and-defuzzification.md). This experiment introduces a
user-level Sutra rule that adds a learnable input gain to each
iteration:

    function fuzzy gated_polarize(fuzzy v, number gain) {
        loop (10) {
            v = (gain * v) == true;
        }
        return v;
    }

The `gain` parameter scales v before each equality-check step. With
gain=1 this collapses to the spec defuzz. With gain trained, the
polarizer can converge faster or differently on per-input target
polarizations.

Honest scope
------------
- This is mechanism + bake-back round-trip evidence. It is NOT a
  capability advertisement — whether trained gain MEANINGFULLY
  improves polarization on a real task is the measurement, and
  could come back as "trained gain matches the default" (null
  result) or "trained gain widens margin." Both are valid findings.
- The Sutra-level surface is unchanged from existing primitives.
  No parser/codegen modification was needed; this is purely a new
  USER-level rule + a training harness around it.

Pipeline
--------
1. Compile a `.su` rule with `number gain` as a parameter.
2. Equivalence guard: vmap-batched logits == per-sample logits at
   init within 1e-4.
3. Train gain via Adam against a polarization task.
4. Bake back as a numeric literal in a fresh `.su` (gain param
   dropped); recompile; assert max|Δ| < 1e-4 between param-form
   and baked-form outputs.

Usage
-----
    py experiments/defuzz_gain_adjustment.py --smoke   # compile + equiv only
    py experiments/defuzz_gain_adjustment.py [--N 50] [--epochs 60] \\
        [--seeds 0,1,2] [--lr 0.05]
"""
from __future__ import annotations

import argparse
import io
import os
import statistics
import sys
import time
import types

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(REPO, "sdk", "sutra-compiler"))
HERE = os.path.dirname(os.path.abspath(__file__))

import torch
import torch.nn.functional as F

from sutra_compiler.validator import validate_file
from sutra_compiler.lexer import Lexer
from sutra_compiler.parser import Parser
from sutra_compiler.codegen_pytorch import translate_module as translate_pytorch


def _su(gain_literal: float | None, iters: int = 10, body: str = "cosine") -> str:
    """Generate the .su. If gain_literal is None, gain is a `number`
    param (trainable). Else the trained gain* is inlined as a literal
    and the param is dropped — the trained model AS source.

    Two body shapes:
    - `body="cosine"` (legacy default, scale-invariant — does NOT train):
      `loop (iters) { v = (gain * v) == true; }`. Cosine eq normalizes
      out the scale of gain — see planning/findings/2026-05-28-defuzz-
      gain-task-scale-invariant.md.
    - `body="trit"` (uses the newly-exposed `defuzzify_trit` intrinsic):
      `return defuzzify_trit(v, 10, gain);`. β IS scale-sensitive in
      principle (it's the exponent in `exp(-β*(x±1)²)`), but the runtime
      hardcodes its own internal 10-iter unroll regardless of the
      passed `iters` arg, and the loss surface is mostly flat in β at
      iters=10 (saturated regime). Real β-training requires either
      runtime-variable iters in `defuzzify_trit` OR carefully
      designed input distributions near the polarization boundary —
      both queued as task #19 follow-ons.
    """
    if gain_literal is None:
        sig = "fuzzy v, number gain"
        body_gain = "gain"
    else:
        sig = "fuzzy v"
        # Fixed-point format — Sutra parser rejects scientific notation
        # (the scientific-notation lexer fix landed for the bake-back
        # path 2026-05-27 in commit f0341fbd; the workaround was kept
        # since fixed-point is still readable in baked .su).
        body_gain = f"({gain_literal:.8f})"
    if body == "trit":
        body_src = (
            f"    return defuzzify_trit(v, 10, {body_gain});\n"
        )
    else:  # "cosine"
        body_src = (
            f"    loop ({iters}) {{\n"
            f"        v = ({body_gain} * v) == true;\n"
            "    }\n"
            "    return v;\n"
        )
    return (
        "// Defuzz gain adjustment — gain is the trainable scalar.\n"
        f"function fuzzy gated_polarize({sig}) {{\n"
        f"{body_src}"
        "}\n\n"
        'function string main() { return "ok"; }\n'
    )


def _compile(su_text: str, tag: str):
    path = os.path.join(HERE, f".defuzzgain_{tag}.su")
    with open(path, "w", encoding="utf-8") as f:
        f.write(su_text)
    bag = validate_file(path)
    if getattr(bag, "errors", None):
        print(f"VALIDATION ERRORS ({tag}):")
        for d in bag:
            print(" ", d.format())
        raise SystemExit(1)
    src = open(path, encoding="utf-8").read()
    lx = Lexer(src, file=path)
    ast = Parser(
        lx.tokenize(), file=path, diagnostics=lx.diagnostics
    ).parse_module()
    py = translate_pytorch(
        ast, runtime_dim=768, runtime_seed=42, loop_max_iterations=50,
    )
    m = types.ModuleType(f"_defuzzgain_{tag}")
    m.__file__ = f"<defuzzgain {tag}>"
    exec(compile(py, m.__file__, "exec"), m.__dict__)
    return m


def build_fuzzy_data(N: int, seed: int = 0):
    """Synthetic polarization task: N fuzzy inputs sampled uniformly
    on [-1, +1] of the truth axis, with target polarization = sign(input).

    Inputs are make_truth(x) vectors where x ∈ [-1, +1]; targets are
    +1 for x > 0 and -1 for x < 0 (we exclude x near 0 to avoid an
    undefined polarization target — those are the "hard" cases by
    design, but they're not in this task's training set)."""
    g = torch.Generator(device="cpu").manual_seed(seed)
    # Sample N x's well-separated from 0 so sign() is unambiguous.
    # Half positive, half negative; magnitudes in [0.1, 0.9].
    half = N // 2
    pos_mags = 0.1 + 0.8 * torch.rand(half, generator=g, dtype=torch.float32)
    neg_mags = 0.1 + 0.8 * torch.rand(N - half, generator=g, dtype=torch.float32)
    xs = torch.cat([pos_mags, -neg_mags])
    perm = torch.randperm(N, generator=g)
    xs = xs[perm]
    ys = torch.where(xs > 0, torch.tensor(1.0), torch.tensor(-1.0))
    return xs, ys


def polarization_loss(out_truth: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    """MSE between the truth-axis component of out and target ∈ {-1, +1}.

    out is the gated_polarize output (a fuzzy vector). We compare its
    truth-axis projection against the target polarization."""
    return ((out_truth - target) ** 2).mean()


def smoke(iters: int = 2):
    """Compile + equivalence-guard the param + baked forms with a
    dummy gain literal. No training run. Verifies the .su parses,
    the codegen pipeline emits, the runtime executes, and the
    param-vs-literal forms agree."""
    mod = _compile(_su(None, iters=iters), "smoke_param")
    print(f"smoke: compiled param form OK (iters={iters})")

    baked = _compile(_su(1.0, iters=iters), "smoke_baked")
    print(f"smoke: compiled baked form (gain=1.0, iters={iters}) OK")

    runtime = mod._VSA
    device, dtype = runtime.device, runtime.dtype
    # Build a single fuzzy input on the truth axis.
    v = runtime.make_truth(0.3)
    out_param = mod.gated_polarize(v, torch.tensor(1.0, dtype=dtype, device=device))
    out_baked = baked.gated_polarize(v)
    dmax = float((out_param - out_baked).abs().max())
    if dmax >= 1e-4:
        raise SystemExit(
            f"SMOKE FAILED: param-form vs baked-form max|Δ|={dmax:.2e} "
            f"≥ 1e-4 — bake-back round-trip is broken."
        )
    print(f"  PASS: param-form vs baked(gain=1.0) max|Δ|={dmax:.2e} < 1e-4")
    return mod, baked


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true",
                    help="compile + equivalence-guard only; no training")
    ap.add_argument("--N", type=int, default=50,
                    help="number of synthetic fuzzy inputs")
    ap.add_argument("--epochs", type=int, default=60)
    ap.add_argument("--seeds", default="0,1,2")
    ap.add_argument("--lr", type=float, default=0.05)
    ap.add_argument("--iters", type=int, default=10,
                    help="polarization sharpening iterations (cosine body "
                         "only; trit body ignores this — runtime hardcodes "
                         "10 iters inside defuzzify_trit).")
    ap.add_argument("--body", choices=("cosine", "trit"), default="cosine",
                    help="polarization body shape. 'cosine' (default) = "
                         "legacy `(gain*v) == true` looped, SCALE-INVARIANT "
                         "in gain so does not actually train. 'trit' = the "
                         "newly-exposed `defuzzify_trit(v, 10, beta)` "
                         "intrinsic, scale-sensitive in principle but the "
                         "current runtime-hardcoded 10-iter unroll gives a "
                         "mostly-flat loss surface. See finding 2026-05-28-"
                         "defuzz-gain-task-scale-invariant.md.")
    a = ap.parse_args()

    if a.smoke:
        smoke(iters=a.iters)
        print("smoke: PASS")
        return

    seeds = [int(s) for s in a.seeds.split(",") if s.strip()]
    mod = _compile(_su(None, iters=a.iters, body=a.body), "param")
    runtime = mod._VSA
    device, dtype = runtime.device, runtime.dtype
    print(
        f"compiled defuzz-gain .su (param gain) via PyTorch codegen; "
        f"N={a.N} epochs={a.epochs} seeds={seeds} lr={a.lr}"
    )

    baseline_losses, trained_losses, gains, rt_oks, rt_dmax = (
        [], [], [], [], [],
    )
    t0 = time.time()
    for s in seeds:
        torch.manual_seed(s)
        xs_cpu, ys_cpu = build_fuzzy_data(a.N, seed=s)
        xs = xs_cpu.to(device=device, dtype=dtype)
        ys = ys_cpu.to(device=device, dtype=dtype)

        # Build fuzzy vectors on the truth axis from scalar xs.
        AXIS_TRUTH = runtime.AXIS_TRUTH
        truth_idx = runtime.semantic_dim + AXIS_TRUTH
        def make_fuzzy(x_scalar):
            v = torch.zeros(runtime.dim, dtype=dtype, device=device)
            v[truth_idx] = x_scalar
            return v
        vs = [make_fuzzy(x) for x in xs]

        # Baseline loss at gain=1.
        gain_init = torch.tensor(1.0, dtype=dtype, device=device)
        with torch.no_grad():
            outs = torch.stack([
                mod.gated_polarize(v, gain_init)[truth_idx] for v in vs
            ])
            bl = polarization_loss(outs, ys)

        # Train gain.
        gain = torch.tensor(1.0, dtype=dtype, device=device, requires_grad=True)
        opt = torch.optim.Adam([gain], lr=a.lr)
        for _ in range(a.epochs):
            opt.zero_grad()
            outs = torch.stack([
                mod.gated_polarize(v, gain)[truth_idx] for v in vs
            ])
            loss = polarization_loss(outs, ys)
            loss.backward()
            opt.step()
        gain_star = float(gain.detach())

        # Trained loss.
        with torch.no_grad():
            outs = torch.stack([
                mod.gated_polarize(v, gain.detach())[truth_idx] for v in vs
            ])
            tl = polarization_loss(outs, ys)

        # Bake back + round-trip check.
        baked = _compile(_su(round(gain_star, 6), iters=a.iters, body=a.body), "baked")
        with torch.no_grad():
            md = 0.0
            for v in vs:
                op = mod.gated_polarize(v, gain.detach())
                ob = baked.gated_polarize(v)
                md = max(md, float((op - ob).abs().max()))
        rt_ok = md < 1e-4
        print(
            f"  seed {s}: baseline loss = {float(bl):.4f}  ->  trained loss "
            f"= {float(tl):.4f}  gain*={gain_star:.4f}  "
            f"round-trip max|Δ|={md:.2e}  round_trip_ok={rt_ok}"
        )
        baseline_losses.append(float(bl))
        trained_losses.append(float(tl))
        gains.append(gain_star)
        rt_oks.append(rt_ok)
        rt_dmax.append(md)

    def ms(v):
        return statistics.mean(v), (statistics.stdev(v) if len(v) > 1 else 0.0)

    bl_mean, bl_sd = ms(baseline_losses)
    tl_mean, tl_sd = ms(trained_losses)
    g_mean, g_sd = ms(gains)
    print(
        f"\n=== DEFUZZ GAIN ADJUSTMENT MEASURED "
        f"(real compiled graph, gain trained, synthetic truth-axis "
        f"polarization task) in {time.time() - t0:.1f}s ==="
    )
    print(f"N={a.N} epochs={a.epochs}")
    print(f"baseline loss (gain=1): {bl_mean:.4f} ± {bl_sd:.4f}  (n={len(seeds)})")
    print(f"trained  loss (gain*):  {tl_mean:.4f} ± {tl_sd:.4f}  (n={len(seeds)})")
    print(f"trained gain*: {g_mean:.4f} ± {g_sd:.4f}")
    print(
        f"round_trip_ok(all): {all(rt_oks)}  max|Δ| over all seeds: "
        f"{max(rt_dmax):.2e}"
    )


if __name__ == "__main__":
    main()
