"""Equality cosine-similarity adjustment — isolate the cosine-temperature lever.

Stage-B (`differentiable_training_weighted.py`) trained (w, prototypes)
jointly on K=3 / K=5 classification; the task saturated at 100% so the
trained gain w*'s effect on the cosine output was not directly visible.
This experiment isolates the cosine-temperature effect:

  - prototypes FROZEN at embed(category-name-word) -- not learned
  - ONLY the scalar T (formerly Stage-B's w) is trained
  - reported metric: logit margin (logit_correct - max logit_wrong) before
    training (T=1) and after (T=T*); the metric is the *equality
    discrimination headroom*, not just classification accuracy

The rule is the same shape as Stage-B:
    rule(x, own, others..., number T) = (T*sim(x,own)) && !(T*sim(x,o_j)) ...

Equivalence guard (per agenda): batched (vmap) logits == per-sample logits
within 1e-4 BEFORE training begins; otherwise the run is aborted.

Bake-back round-trip: the trained T* is substituted as a numeric literal
into a fresh .su with no T param; recompile via the real PyTorch codegen;
assert max-logit Delta between the param-T model and the baked-literal
model < 1e-4.

Usage:
    py experiments/equality_cosine_adjustment.py [--k K] [--per-class N]
        [--epochs E] [--seeds 0,1,2] [--lr LR]
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

import differentiable_training as dt


def _su(k: int, t_literal: float | None) -> str:
    """Generate the .su. If t_literal is None, T is a `number` param
    (trainable). Else the trained T* is inlined as a literal and the
    param is dropped -- the trained model AS source."""
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
        g = f"({t_literal!r})"
    nots = " ".join(f"&& !({g} * similarity(x, {o}))" for o in oth)
    return (
        "// Equality cosine-similarity adjustment — T is the cosine "
        "temperature.\n"
        f"function fuzzy rule({sig}) {{\n"
        f"    return ({g} * similarity(x, own)) {nots};\n"
        f"}}\n\n"
        f"function string main() {{ return \"ok\"; }}\n"
    )


def _compile(su_text: str, tag: str):
    path = os.path.join(HERE, f".eqcos_{tag}.su")
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
    m = types.ModuleType(f"_eqcos_{tag}")
    m.__file__ = f"<eqcos {tag}>"
    exec(compile(py, m.__file__, "exec"), m.__dict__)
    return m


def build_data(k, per_class):
    """K categories; one frozen prototype per category = embed(category-name).
    Data points = embed(words in that category), one per word."""
    cache = os.path.join(HERE, ".diff_train_embeddings.pt")
    cats = dt.CATEGORIES[:k]
    cat_names = [name for name, _ in cats]
    words = [w for _, ws in cats for w in ws]
    needed = sorted(set(words + cat_names))
    vecs = dt.embed_all(needed, cache_path=cache)
    protos = [vecs[name].detach() for name in cat_names]
    data = []
    for ci, (_, ws) in enumerate(cats):
        for w in ws[:per_class]:
            if w in cat_names:
                continue
            data.append((vecs[w].detach(), ci))
    return data, protos, next(iter(vecs.values())).shape[0]


def logits_per_sample(m, protos, T, x, k):
    return torch.stack(
        [
            m.rule(
                x,
                protos[i],
                *[protos[j] for j in range(k) if j != i],
                T,
            )
            for i in range(k)
        ]
    )


def logits_baked_per_sample(baked, protos, x, k):
    return torch.stack(
        [
            baked.rule(
                x,
                protos[i],
                *[protos[j] for j in range(k) if j != i],
            )
            for i in range(k)
        ]
    )


def margin(logits, y):
    """logit_correct − max logit_wrong (over the wrong classes)."""
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
    ap.add_argument("--lr", type=float, default=0.05)
    a = ap.parse_args()
    seeds = [int(s) for s in a.seeds.split(",") if s.strip()]
    k = a.k

    mod = _compile(_su(k, None), "param")
    data, protos, dim = build_data(k, a.per_class)
    print(
        f"compiled equality-cosine .su (param T) via PyTorch codegen; "
        f"k={k} N={len(data)} dim={dim} epochs={a.epochs} "
        f"seeds={seeds} lr={a.lr}"
    )
    print(
        "  prototypes FROZEN at embed(category-name); only T is trained."
    )

    # --- Equivalence guard: batched (vmap) vs per-sample at T=1 -----
    T_init = torch.tensor(1.0)

    def single(x, T):
        return logits_per_sample(mod, protos, T, x, k)

    vlogits = torch.vmap(lambda xx: single(xx, T_init))
    X = torch.stack([x for x, _ in data])
    with torch.no_grad():
        lp = torch.stack([single(x, T_init) for x, _ in data])
        lb = vlogits(X)
        dmax = float((lp - lb).abs().max())
    if dmax >= 1e-4:
        raise SystemExit(
            f"EQUIVALENCE GUARD FAILED: batched != per-sample "
            f"(max|Δ|={dmax:.2e}). Abort -- not the same compiled computation."
        )
    print(f"  equivalence guard PASSED (max|Δ|={dmax:.2e} < 1e-4)")

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
        T = torch.tensor(1.0, requires_grad=True)
        opt = torch.optim.Adam([T], lr=a.lr)

        # --- baseline margin (T=1, frozen protos) ---
        with torch.no_grad():
            ms_b = [
                margin(logits_per_sample(mod, protos, T_init, x, k), y)
                for x, y in data
            ]
        bm = statistics.mean(ms_b)

        # --- train T only ---
        for _ in range(a.epochs):
            opt.zero_grad()
            losses = []
            for x, y in data:
                logits = logits_per_sample(mod, protos, T, x, k)
                losses.append(
                    F.cross_entropy(
                        (logits * 10.0).unsqueeze(0),
                        torch.tensor([y]),
                    )
                )
            loss = torch.stack(losses).mean()
            loss.backward()
            opt.step()
        T_star = float(T.detach())

        # --- trained margin (T=T*, frozen protos) ---
        with torch.no_grad():
            ms_t = [
                margin(
                    logits_per_sample(mod, protos, T.detach(), x, k),
                    y,
                )
                for x, y in data
            ]
        tm = statistics.mean(ms_t)

        # --- bake T* as a .su literal, recompile, round-trip ---
        baked = _compile(_su(k, round(T_star, 6)), "baked")
        with torch.no_grad():
            md = 0.0
            for x, y in data:
                lp_ = logits_per_sample(mod, protos, T.detach(), x, k)
                lb_ = logits_baked_per_sample(baked, protos, x, k)
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
        f"\n=== EQUALITY COSINE ADJUSTMENT MEASURED "
        f"(real compiled graph, T trained, prototypes FROZEN at "
        f"embed(category-name)) in {time.time() - t0:.1f}s ==="
    )
    print(
        f"k={k} N={len(data)} per_class={a.per_class}  epochs={a.epochs}"
    )
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
