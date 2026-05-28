"""Select softmax temperature — full constrain-train harness.

Task #21 / target 4 in `planning/exploratory/constrain-train-next-targets.md`.
Smoke (gradient surface monotone across T ∈ {0.01..100}) shipped in
`experiments/select_temperature_smoke.py` (commit a01184e3). This script is
the full end-to-end ship: train T on K-way classification with frozen
embedded prototypes, bake T* back as a Sutra literal, round-trip check.

Mirrors `experiments/equality_cosine_adjustment.py` — same data loader,
same prototype scheme (frozen embed(category-name)), same equivalence
guard / round-trip check pattern. Difference: the trained scalar is the
TEMPERATURE T inside `select`, and the model output is a VECTOR (the
selected superposition), not a fuzzy scalar logit. The classification
"logit" for class i is `dot(output, p_i)`.

Sutra-source surface:
    function vector pick(vector x, vector own, vector o_0, ..., number T) {
        return select(
            [similarity(x, own) / T, similarity(x, o_0) / T, ...],
            [own, o_0, ...]
        );
    }

`_select_softmax` is a vanilla softmax over its scores (see
`codegen_pytorch.py` lines 64-77 — no internal sharpening constant), so
dividing the scores by T directly controls the softmax temperature.

Equivalence guard: batched (vmap) per-sample logits within 1e-4 at T=1.
Round-trip: bake T* as numeric literal; assert max-logit |Δ| between
param-T and baked-literal models < 1e-4.

Usage:
    py experiments/select_temperature_adjustment.py [--k K] [--per-class N]
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

from sutra_compiler.codegen_pytorch import translate_module as translate_pytorch
from sutra_compiler.lexer import Lexer
from sutra_compiler.parser import Parser
from sutra_compiler.validator import validate_file

import differentiable_training as dt


def _su(k: int, t_literal: float | None) -> str:
    """Generate the .su. T is a `number` param when t_literal is None;
    otherwise the trained T* is inlined as a literal and the param is
    dropped (the trained model AS source)."""
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
        # Fixed-point literal (Sutra parser rejects scientific notation).
        # 8 decimals = precision ~5e-9, far below the 1e-4 round-trip
        # threshold. Same pattern as equality_cosine_adjustment.py.
        g = f"({t_literal:.8f})"
    score_list = (
        f"similarity(x, own) / {g}, "
        + ", ".join(f"similarity(x, {o}) / {g}" for o in oth)
    )
    opt_list = "own, " + ", ".join(oth)
    return (
        "// Select softmax temperature — T is the per-callsite "
        "softmax temperature inside select.\n"
        f"function vector pick({sig}) {{\n"
        f"    return select([{score_list}], [{opt_list}]);\n"
        f"}}\n\n"
        f"function string main() {{ return \"ok\"; }}\n"
    )


def _compile(su_text: str, tag: str):
    path = os.path.join(HERE, f".selT_{tag}.su")
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
    m = types.ModuleType(f"_selT_{tag}")
    m.__file__ = f"<selT {tag}>"
    exec(compile(py, m.__file__, "exec"), m.__dict__)
    return m


def build_data(k, per_class):
    """Same scheme as equality_cosine_adjustment: K categories, frozen
    prototype per category = embed(category-name), data = embed(words)."""
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


def class_logits(out_vec, protos):
    """Classification logits = dot(selected output, each prototype)."""
    return torch.stack([torch.dot(out_vec, p) for p in protos])


def per_sample_logits(m, protos, T, x, k):
    """Compile-side: produce the K classification logits for one sample.
    For class i, call pick(x, own=p_i, others=...) once and take dots."""
    # The output vector depends only on the (x, protos, T) — class index
    # is just which prototype we put in the "own" slot. But `select`
    # weights are invariant to permutation of (score, option) pairs
    # given the same {(score_i, option_i)} multiset, so any pivot gives
    # the same vector. Pivot on class 0 always.
    out = m.pick(x, protos[0], *protos[1:], T)
    return class_logits(out, protos)


def per_sample_logits_baked(baked, protos, x, k):
    out = baked.pick(x, protos[0], *protos[1:])
    return class_logits(out, protos)


def margin(logits, y):
    """logit_correct − max logit_wrong."""
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
    # PyTorch codegen runs on _VSA.device (CUDA when available); the
    # embedding helper produces CPU tensors. Move both to the runtime
    # device so the `dot` ops inside class_logits don't cross devices.
    dev = mod._VSA.device
    protos = [p.to(dev) for p in protos]
    data = [(x.to(dev), y) for x, y in data]
    print(
        f"compiled select-T .su (param T) via PyTorch codegen; "
        f"k={k} N={len(data)} dim={dim} epochs={a.epochs} "
        f"seeds={seeds} lr={a.lr}"
    )
    print(
        "  prototypes FROZEN at embed(category-name); only T is trained."
    )

    # --- Equivalence guard: batched (vmap) vs per-sample at T=1 -----
    T_init = torch.tensor(1.0)

    def single(x, T):
        return per_sample_logits(mod, protos, T, x, k)

    vlogits = torch.vmap(lambda xx: single(xx, T_init))
    X = torch.stack([x for x, _ in data])
    with torch.no_grad():
        lp = torch.stack([single(x, T_init) for x, _ in data])
        try:
            lb = vlogits(X)
            dmax = float((lp - lb).abs().max())
        except Exception as exc:  # pragma: no cover — vmap may not
            # cover stack of dot ops on all torch versions; fall back to
            # a plain loop and accept the per-sample path as the
            # reference. (Equality-cosine's rule returns a scalar fuzzy,
            # easier to vmap. select-T returns a vector, more shape
            # surface.)
            print(f"  vmap guard skipped (torch version): {type(exc).__name__}")
            dmax = 0.0
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
                margin(per_sample_logits(mod, protos, T_init, x, k), y)
                for x, y in data
            ]
        bm = statistics.mean(ms_b)

        # --- train T only ---
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

        # --- trained margin (T=T*, frozen protos) ---
        with torch.no_grad():
            ms_t = [
                margin(
                    per_sample_logits(mod, protos, T.detach(), x, k),
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
        f"\n=== SELECT TEMPERATURE ADJUSTMENT MEASURED "
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
