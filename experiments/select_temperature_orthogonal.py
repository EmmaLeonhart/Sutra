"""Select temperature — orthogonal-prototypes constrain-train task.

Follow-on to `experiments/select_temperature_adjustment.py` (`fe274d3c`).
That K=5 embed-protos run produced a NEGATIVE TASK-FIT result: the
mechanism trained but the embed(category-name) prototype set had too
narrow a similarity gap for select-T's softmax-temperature lever to
help. The synthesis doc named the next ship as either target 3
(`bundle` weights, 4-6h, needs parser change) OR a cheap non-flat
select-T task (~1h, no parser change) to push the select-T ship from
"mechanism trainable" to "mechanism trainable + non-trivial task win."

This is the cheap ship.

Task:
- K random orthonormal prototypes in 768-d (gram-schmidt on random
  normal vectors; not embeddings — controlled similarity geometry).
- Per class: N queries of the form
      x = alpha * p_y + Sum_{j != y} eps_j * p_j
      where eps_j ~ Uniform(-noise, +noise) per dimension of class.
  alpha controls signal; noise controls SNR.
- Substrate function: `pick(x, p_0..p_K-1, T) = select(scores/T, protos)`.
- Loss: cross-entropy on class logits = dot(out, p_i).
- Train T from 1.0; bake back; round-trip check.

Expected (verified 2026-05-28):
- At T=1, raw similarities sim(x, p_y) ~ alpha = 0.7 vs
  sim(x, p_{j != y}) ~ noise * sqrt(K-1) ~ 0.2. Softmax weights
  concentrate on correct class but not strongly: baseline margin
  ~ +0.4 (positive, well-separated).
- T trains toward small positive (sharpens softmax further); margin
  improves by a multiplicative factor.
- Round-trip bit-exact (within float32 noise).

Distinguishes mechanism (trainable substrate path, bake-back) from
task fit (controlled signal geometry, gap actually present).

Usage:
    py experiments/select_temperature_orthogonal.py [--k K] [--per-class N]
        [--epochs E] [--seeds 0,1,2] [--lr LR] [--alpha A] [--noise eps]
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

from sutra_compiler.codegen_pytorch import translate_module as translate_pytorch
from sutra_compiler.lexer import Lexer
from sutra_compiler.parser import Parser
from sutra_compiler.validator import validate_file


def _su(k: int, t_literal: float | None) -> str:
    """Same as select_temperature_adjustment._su — kept inline so this
    file is self-contained for the negative-result follow-on."""
    oth = [f"o{j}" for j in range(k - 1)]
    if t_literal is None:
        sig = (
            "vector x, vector own, "
            + ", ".join(f"vector {o}" for o in oth)
            + ", number T"
        )
        g = "T"
    else:
        sig = "vector x, vector own, " + ", ".join(
            f"vector {o}" for o in oth
        )
        g = f"({t_literal:.8f})"
    score_list = (
        f"similarity(x, own) / {g}, "
        + ", ".join(f"similarity(x, {o}) / {g}" for o in oth)
    )
    opt_list = "own, " + ", ".join(oth)
    return (
        "// Select softmax temperature — orthogonal-prototype task.\n"
        f"function vector pick({sig}) {{\n"
        f"    return select([{score_list}], [{opt_list}]);\n"
        f"}}\n\n"
        f"function string main() {{ return \"ok\"; }}\n"
    )


def _compile(su_text: str, tag: str):
    path = os.path.join(HERE, f".selT_orth_{tag}.su")
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
        ast, runtime_dim=768, runtime_seed=42, loop_max_iterations=50
    )
    m = types.ModuleType(f"_selT_orth_{tag}")
    m.__file__ = f"<selT_orth {tag}>"
    exec(compile(py, m.__file__, "exec"), m.__dict__)
    return m


def make_orthonormal_protos(k: int, dim: int, seed: int, dev):
    """K random orthonormal prototypes via QR on a Gaussian matrix."""
    g = torch.Generator(device="cpu").manual_seed(seed)
    raw = torch.randn(dim, k, generator=g, dtype=torch.float32)
    Q, _ = torch.linalg.qr(raw, mode="reduced")  # dim x k, orthonormal cols
    return [Q[:, i].to(dev) for i in range(k)]


def make_queries(protos, per_class, alpha, noise, seed, dev):
    """Per class y, generate per_class queries
        x = alpha * p_y + Sum_{j != y} eps_j * p_j   (eps_j ~ U(-noise, +noise))
    Normalize x to unit norm (so cosine == dot in the substrate)."""
    g = torch.Generator(device="cpu").manual_seed(seed + 7919)
    k = len(protos)
    data = []
    for y in range(k):
        for _ in range(per_class):
            x = alpha * protos[y]
            for j in range(k):
                if j == y:
                    continue
                eps = float(torch.rand(1, generator=g)) * (2 * noise) - noise
                x = x + eps * protos[j]
            x = x / x.norm()
            data.append((x.to(dev), y))
    return data


def class_logits(out_vec, protos):
    return torch.stack([torch.dot(out_vec, p) for p in protos])


def per_sample_logits(m, protos, T, x, k):
    out = m.pick(x, protos[0], *protos[1:], T)
    return class_logits(out, protos)


def per_sample_logits_baked(baked, protos, x, k):
    out = baked.pick(x, protos[0], *protos[1:])
    return class_logits(out, protos)


def margin(logits, y):
    K = logits.shape[-1]
    correct = logits[..., y]
    mask = torch.ones(K, dtype=torch.bool)
    mask[y] = False
    wrong_max = logits[..., mask].max()
    return float(correct - wrong_max)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--per-class", type=int, default=10)
    ap.add_argument("--epochs", type=int, default=80)
    ap.add_argument("--seeds", default="0,1,2")
    # Default lr=0.005 (not 0.05 as in equality_cosine_adjustment) — the
    # CE surface is bimodal in T for this select operator: global min at
    # small +T (sharpens softmax), spurious basin at moderate -T (inverts
    # softmax). lr=0.05 starting from T=1 overshoots zero into the wrong
    # basin; lr=0.005 stays in the correct basin. See
    # planning/findings/2026-05-28-select-T-bimodal-T-surface.md.
    ap.add_argument("--lr", type=float, default=0.005)
    ap.add_argument("--alpha", type=float, default=0.7)
    ap.add_argument("--noise", type=float, default=0.15)
    a = ap.parse_args()
    seeds = [int(s) for s in a.seeds.split(",") if s.strip()]
    k = a.k

    mod = _compile(_su(k, None), "param")
    dev = mod._VSA.device
    dim = mod._VSA.dim
    protos = make_orthonormal_protos(k, dim, seed=314, dev=dev)
    print(
        f"compiled select-T orthogonal-protos .su via PyTorch codegen; "
        f"k={k} per_class={a.per_class} dim={dim} epochs={a.epochs} "
        f"seeds={seeds} lr={a.lr} alpha={a.alpha} noise={a.noise}"
    )
    print(
        "  prototypes = K random orthonormal vectors (NOT embeddings);"
    )
    print(
        f"  queries = alpha*p_y + Σ_j≠y eps_j*p_j, eps ~ U(-{a.noise},+{a.noise})"
    )

    # Equivalence guard at T=1
    T_init = torch.tensor(1.0, device=dev)
    data0 = make_queries(protos, a.per_class, a.alpha, a.noise, seed=0, dev=dev)
    with torch.no_grad():
        lp_ref = [per_sample_logits(mod, protos, T_init, x, k) for x, _ in data0]
        recomputed = [per_sample_logits(mod, protos, T_init, x, k) for x, _ in data0]
        dmax = max(
            float((a_t - b_t).abs().max())
            for a_t, b_t in zip(lp_ref, recomputed)
        )
    if dmax >= 1e-4:
        raise SystemExit(
            f"DETERMINISM GUARD FAILED at T=1 (max|Δ|={dmax:.2e})"
        )
    print(f"  determinism guard PASSED (max|Δ|={dmax:.2e})")

    baseline_margins, trained_margins, ts, rt_oks, rt_dmax = (
        [],
        [],
        [],
        [],
        [],
    )
    t0 = time.time()
    for s in seeds:
        torch.manual_seed(s)
        data = make_queries(protos, a.per_class, a.alpha, a.noise, seed=s, dev=dev)

        T = torch.tensor(1.0, requires_grad=True, device=dev)
        opt = torch.optim.Adam([T], lr=a.lr)

        # baseline margin
        with torch.no_grad():
            ms_b = [
                margin(per_sample_logits(mod, protos, T_init, x, k), y)
                for x, y in data
            ]
        bm = statistics.mean(ms_b)

        # train T
        for _ in range(a.epochs):
            opt.zero_grad()
            losses = []
            for x, y in data:
                logits = per_sample_logits(mod, protos, T, x, k)
                losses.append(
                    F.cross_entropy(
                        (logits * 10.0).unsqueeze(0),
                        torch.tensor([y], device=dev),
                    )
                )
            loss = torch.stack(losses).mean()
            loss.backward()
            opt.step()
        T_star = float(T.detach())

        with torch.no_grad():
            ms_t = [
                margin(
                    per_sample_logits(mod, protos, T.detach(), x, k),
                    y,
                )
                for x, y in data
            ]
        tm = statistics.mean(ms_t)

        baked = _compile(_su(k, round(T_star, 6)), f"baked_s{s}")
        with torch.no_grad():
            md = 0.0
            for x, y in data:
                lp_ = per_sample_logits(mod, protos, T.detach(), x, k)
                lb_ = per_sample_logits_baked(baked, protos, x, k)
                md = max(md, float((lp_ - lb_).abs().max()))
        rt_ok = md < 1e-4
        print(
            f"  seed {s}: baseline margin = {bm:+.4f}  ->  trained margin = "
            f"{tm:+.4f}  T*={T_star:.4f}  round-trip max|Δ|={md:.2e}  "
            f"round_trip_ok={rt_ok}"
        )
        baseline_margins.append(bm)
        trained_margins.append(tm)
        ts.append(T_star)
        rt_oks.append(rt_ok)
        rt_dmax.append(md)

    def ms(v):
        return (
            statistics.mean(v),
            statistics.stdev(v) if len(v) > 1 else 0.0,
        )

    bm_mean, bm_sd = ms(baseline_margins)
    tm_mean, tm_sd = ms(trained_margins)
    t_mean, t_sd = ms(ts)
    print(
        f"\n=== SELECT TEMPERATURE — ORTHOGONAL PROTOTYPE TASK MEASURED "
        f"(real compiled graph, T trained, prototypes FROZEN random "
        f"orthonormal) in {time.time() - t0:.1f}s ==="
    )
    print(f"k={k} per_class={a.per_class} epochs={a.epochs} alpha={a.alpha} noise={a.noise}")
    print(
        f"baseline margin (T=1): {bm_mean:+.4f} ± {bm_sd:.4f}  "
        f"(n={len(seeds)})"
    )
    print(
        f"trained  margin (T=T*): {tm_mean:+.4f} ± {tm_sd:.4f}  "
        f"(n={len(seeds)})"
    )
    print(f"trained T*: {t_mean:.4f} ± {t_sd:.4f}")
    if abs(bm_mean) > 1e-9:
        ratio = tm_mean / bm_mean
        print(f"trained / baseline margin ratio: {ratio:+.2f}x")
    print(
        f"round_trip_ok(all): {all(rt_oks)}  max|Δ| over all seeds: "
        f"{max(rt_dmax):.2e}"
    )


if __name__ == "__main__":
    main()
