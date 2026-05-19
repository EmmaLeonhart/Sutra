"""Multi-seed replication of the §3.6 differentiable-training experiment.

Runs the IDENTICAL experiment as `differentiable_training.py` (same
data pipeline, same fuzzy-rule forward pass via the imported
`classify_batch`/`evaluate`, same Adam lr=0.005, same 300 epochs,
same temperature) across 5 seeds, varying ONLY `torch.manual_seed`
(which controls prototype initialization — the sole seed-dependent
part of the original, line 424).

`differentiable_training.py` is imported and left untouched, so the
paper's existing single-seed-42 reproduction line stays exactly
valid. This script is an additive artifact: it writes a NEW
aggregate JSON and prints TikZ coordinates generated from the real
per-epoch means/stds (no hand-typed numbers).

Numbers are measurements, not targets (CLAUDE.md). Whatever the
5-seed aggregate is, that is what gets reported.

Usage:  py experiments/differentiable_training_multiseed.py
Outputs: experiments/differentiable_training_multiseed_results.json
"""
from __future__ import annotations

import json
import os
import statistics

import torch
import torch.nn.functional as F

import differentiable_training as dt

SEEDS = [0, 1, 2, 3, 4]
EPOCHS = 300
LR = 0.005
HERE = os.path.dirname(os.path.abspath(__file__))


def build_data():
    all_words = [w for _, words in dt.CATEGORIES for w in words]
    cache = os.path.join(HERE, ".diff_train_embeddings.pt")
    vecs = dt.embed_all(all_words, cache_path=cache)
    dim = next(iter(vecs.values())).shape[0]
    data = []
    for cat_idx, (_, words) in enumerate(dt.CATEGORIES):
        for w in words:
            data.append((vecs[w], cat_idx))
    return data, dim


def run_once(seed, data, dim):
    """Faithful copy of differentiable_training.main()'s train path."""
    torch.manual_seed(seed)                       # original line 424
    prototypes = []
    for _ in range(len(dt.CATEGORIES)):           # original 425-430
        p = torch.randn(dim)
        p = p / p.norm()
        p = p.clone().requires_grad_(True)
        prototypes.append(p)

    acc_before = dt.evaluate(data, prototypes)
    optimizer = torch.optim.Adam(prototypes, lr=LR)
    X = torch.stack([x for x, _ in data])
    y = torch.tensor([lbl for _, lbl in data])

    acc_hist, loss_hist = [], []
    for _ in range(EPOCHS):                        # original 456-470
        optimizer.zero_grad()
        logits = dt.classify_batch(X, prototypes)
        loss = F.cross_entropy(logits, y)
        loss.backward()
        optimizer.step()
        with torch.no_grad():
            acc = (logits.argmax(dim=1) == y).float().mean().item()
        acc_hist.append(acc)
        loss_hist.append(loss.item())

    acc_after = dt.evaluate(data, prototypes)

    # gradient-flow check: per-prototype grad norm (original 499-511)
    gns = []
    offset = 0
    for i, (_, words) in enumerate(dt.CATEGORIES):
        optimizer.zero_grad()
        x, lbl = data[offset]
        F.cross_entropy(
            dt.classify(x, prototypes).unsqueeze(0), torch.tensor([lbl])
        ).backward()
        gns.append(prototypes[i].grad.norm().item())
        offset += len(words)

    return {
        "seed": seed,
        "acc_before": acc_before,
        "acc_after": acc_after,
        "acc_hist": acc_hist,
        "loss_hist": loss_hist,
        "grad_norm_min": min(gns),
        "grad_norm_max": max(gns),
    }


def main():
    data, dim = build_data()
    print(f"data: {len(data)} (word, label) pairs, dim={dim}, "
          f"{len(dt.CATEGORIES)} classes, chance={1/len(dt.CATEGORIES):.1%}")
    runs = []
    for s in SEEDS:
        r = run_once(s, data, dim)
        runs.append(r)
        print(f"  seed {s}: before={r['acc_before']:.4f} "
              f"after={r['acc_after']:.4f} "
              f"acc@50={r['acc_hist'][50]:.4f} "
              f"acc@299={r['acc_hist'][299]:.4f} "
              f"gradnorm=[{r['grad_norm_min']:.3f},{r['grad_norm_max']:.3f}]")

    def ms(xs):
        return statistics.mean(xs), (statistics.stdev(xs) if len(xs) > 1 else 0.0)

    n = len(runs)
    mean_curve, std_curve = [], []
    for e in range(EPOCHS):
        col = [r["acc_hist"][e] for r in runs]
        m, sd = ms(col)
        mean_curve.append(m)
        std_curve.append(sd)

    before_m, before_s = ms([r["acc_before"] for r in runs])
    after_m, after_s = ms([r["acc_after"] for r in runs])
    e50_m, e50_s = ms([r["acc_hist"][50] for r in runs])
    e299_m, e299_s = ms([r["acc_hist"][299] for r in runs])
    loss299_m, loss299_s = ms([r["loss_hist"][299] for r in runs])

    # "knee": first epoch where the mean curve is within 1pp of the
    # final mean; report std over the post-knee tail.
    final = mean_curve[-1]
    knee = next((e for e in range(EPOCHS) if mean_curve[e] >= final - 0.01),
                EPOCHS - 1)
    postknee_std = statistics.mean(std_curve[knee:])
    gmin = min(r["grad_norm_min"] for r in runs)
    gmax = max(r["grad_norm_max"] for r in runs)

    # TikZ coords from REAL data: epoch 0, then every 15, plus 299.
    pts = sorted(set(list(range(0, EPOCHS, 15)) + [50, EPOCHS - 1]))
    mean_co = " ".join(f"({e},{mean_curve[e]*100:.2f})" for e in pts)
    up_co = " ".join(
        f"({e},{min(1.0, mean_curve[e]+std_curve[e])*100:.2f})" for e in pts)
    dn_co = " ".join(
        f"({e},{max(0.0, mean_curve[e]-std_curve[e])*100:.2f})"
        for e in reversed(pts))

    summary = {
        "experiment": "differentiable training — multi-seed replication",
        "seeds": SEEDS,
        "epochs": EPOCHS,
        "lr": LR,
        "classes": len(dt.CATEGORIES),
        "n_word_label_pairs": len(data),
        "chance": round(1 / len(dt.CATEGORIES), 4),
        "accuracy_before_mean": round(before_m, 4),
        "accuracy_before_std": round(before_s, 4),
        "accuracy_epoch50_mean": round(e50_m, 4),
        "accuracy_epoch50_std": round(e50_s, 4),
        "accuracy_epoch299_mean": round(e299_m, 4),
        "accuracy_epoch299_std": round(e299_s, 4),
        "accuracy_after_mean": round(after_m, 4),
        "accuracy_after_std": round(after_s, 4),
        "loss_epoch299_mean": round(loss299_m, 4),
        "loss_epoch299_std": round(loss299_s, 4),
        "knee_epoch": knee,
        "post_knee_mean_std": round(postknee_std, 4),
        "grad_norm_min": round(gmin, 6),
        "grad_norm_max": round(gmax, 6),
        "per_seed": [
            {k: r[k] for k in ("seed", "acc_before", "acc_after",
                               "grad_norm_min", "grad_norm_max")}
            for r in runs
        ],
        "tikz_mean_coords": mean_co,
        "tikz_upper_coords": up_co,
        "tikz_lower_coords_reversed": dn_co,
        "mean_curve": [round(v, 4) for v in mean_curve],
        "std_curve": [round(v, 4) for v in std_curve],
    }
    out = os.path.join(HERE, "differentiable_training_multiseed_results.json")
    with open(out, "w") as f:
        json.dump(summary, f, indent=2)

    print("\n=== 5-SEED AGGREGATE (measured) ===")
    print(f"before        : {before_m*100:.2f} ± {before_s*100:.2f} %")
    print(f"epoch 50      : {e50_m*100:.2f} ± {e50_s*100:.2f} %")
    print(f"epoch 299     : {e299_m*100:.2f} ± {e299_s*100:.2f} %")
    print(f"after (eval)  : {after_m*100:.2f} ± {after_s*100:.2f} %")
    print(f"loss @299     : {loss299_m:.4f} ± {loss299_s:.4f}")
    print(f"knee epoch    : {knee}  | mean post-knee std: {postknee_std*100:.2f} pp")
    print(f"grad norm rng : [{gmin:.4f}, {gmax:.4f}]  (all nonzero)")
    print(f"\nsaved -> {out}")
    print("\nTikZ mean coords:\n" + mean_co)


if __name__ == "__main__":
    main()
