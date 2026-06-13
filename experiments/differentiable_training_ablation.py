"""Ablation for the §3.7 weighted-Equals training: isolate the contribution of
the learned gain `w` vs the trained prototypes.

The full model (differentiable_training_weighted.py) trains BOTH the scalar gain
`w` and the three prototype vectors, reaching 100%. This ablation runs three
conditions through the SAME compiled `.su` graph, so the only difference is which
parameters carry gradients:

  - full         : w trainable + prototypes trainable        (the paper's result)
  - prototypes   : w FROZEN at 1.0, only prototypes trained  (is the gain needed?)
  - gain         : prototypes FROZEN at init, only w trained (can the scalar gain
                   alone separate classes? — w rescales sim BEFORE the nonlinear
                   Kleene AND/NOT, so its effect on argmax is not a no-op a priori)

Measured, not predicted — numbers are whatever the substrate produces. nomic-embed
-text (768-d, frozen), 3 classes × 8 words, full-batch CE, Adam lr 0.02, 30 epochs.

Usage: py experiments/differentiable_training_ablation.py [--epochs E] [--seeds 0,1]
"""
from __future__ import annotations

import argparse
import io
import os
import statistics
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import torch
import torch.nn.functional as F

import differentiable_training_weighted as W


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=3)
    ap.add_argument("--per-class", type=int, default=8)
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--seeds", default="0,1")
    ap.add_argument("--lr", type=float, default=0.02)
    a = ap.parse_args()
    seeds = [int(s) for s in a.seeds.split(",") if s.strip()]
    k = a.k

    mod = W._compile(W._su(k, None), "ablation")
    data, dim = W.build_data(k, a.per_class)
    print(f"compiled weighted .su (param w) via PyTorch codegen; k={k} "
          f"N={len(data)} dim={dim} epochs={a.epochs} seeds={seeds} lr={a.lr}\n")

    def logits(protos, w, x):
        return torch.stack([
            mod.rule(x, protos[i], *[protos[j] for j in range(k) if j != i], w)
            for i in range(k)])

    def acc(P, wv):
        c = 0
        with torch.no_grad():
            for x, y in data:
                if int(torch.argmax(logits(P, wv, x))) == y:
                    c += 1
        return c / len(data)

    conditions = ("full", "prototypes", "gain")
    results = {c: {"before": [], "after": [], "w": []} for c in conditions}

    t0 = time.time()
    for s in seeds:
        for cond in conditions:
            torch.manual_seed(s)
            protos = [(p := torch.randn(dim)) / p.norm() for _ in range(k)]
            train_protos = cond in ("full", "prototypes")
            train_gain = cond in ("full", "gain")
            protos = [p.clone().requires_grad_(train_protos) for p in protos]
            w = torch.tensor(1.0, requires_grad=train_gain)
            params = ([p for p in protos] if train_protos else []) \
                + ([w] if train_gain else [])
            opt = torch.optim.Adam(params, lr=a.lr)
            before = acc(protos, w)
            for _ in range(a.epochs):
                opt.zero_grad()
                loss = torch.stack([
                    F.cross_entropy((logits(protos, w, x) * 10.0).unsqueeze(0),
                                    torch.tensor([y])) for x, y in data]).mean()
                loss.backward()
                opt.step()
            after = acc(protos, w)
            results[cond]["before"].append(before)
            results[cond]["after"].append(after)
            results[cond]["w"].append(float(w.detach()))
            print(f"  seed {s} [{cond:>10}]: acc {before:.3f} -> {after:.3f}  "
                  f"w*={float(w.detach()):.4f}")

    def ms(v):
        return (statistics.mean(v), statistics.stdev(v) if len(v) > 1 else 0.0)

    print(f"\n=== ABLATION MEASURED (same compiled graph; n={len(seeds)} seeds) "
          f"in {time.time()-t0:.1f}s ===")
    print(f"k={k}  chance={100/k:.1f}%")
    print(f"{'condition':>12} | {'before %':>12} | {'after %':>12} | {'w*':>14}")
    print("-" * 60)
    for cond in conditions:
        bm, bs = ms(results[cond]["before"])
        am, asd = ms(results[cond]["after"])
        wm, wsd = ms(results[cond]["w"])
        print(f"{cond:>12} | {bm*100:6.1f} ± {bs*100:4.1f} | "
              f"{am*100:6.1f} ± {asd*100:4.1f} | {wm:7.4f} ± {wsd:.4f}")


if __name__ == "__main__":
    main()
