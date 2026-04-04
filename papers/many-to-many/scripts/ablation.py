"""Alpha/beta ablation study for the structured matching primitive."""
import sys, io, json, numpy as np

# Import from structured_matching
from scripts.structured_matching import (
    get_embedder, get_countries_dataset, get_occupations_dataset,
    get_animals_dataset, compute_direction, structured_match
)

embed_fn, model_name = get_embedder("mxbai-embed-large")
datasets = [get_countries_dataset(), get_occupations_dataset(), get_animals_dataset()]

configs = [
    (0.0, 1.0, "selection only (β=1)"),
    (0.25, 0.75, "selection heavy"),
    (0.5, 0.5, "equal (α=β=0.5)"),
    (0.75, 0.25, "residual heavy"),
    (1.0, 0.0, "residual only (α=1)"),
]

# Pre-embed all datasets once
dataset_cache = []
for ds in datasets:
    all_texts = (ds["target_exemplars_positive"] + ds["target_exemplars_negative"] +
                 ds["confounder_group_a"] + ds["confounder_group_b"] +
                 [ds["query"]] + [ds["label_fn"](c) for c in ds["candidates"]])
    embs = embed_fn(all_texts)
    idx = 0
    n = [len(ds["target_exemplars_positive"]), len(ds["target_exemplars_negative"]),
         len(ds["confounder_group_a"]), len(ds["confounder_group_b"])]
    tp = embs[idx:idx+n[0]]; idx += n[0]
    tn = embs[idx:idx+n[1]]; idx += n[1]
    ca = embs[idx:idx+n[2]]; idx += n[2]
    cb = embs[idx:idx+n[3]]; idx += n[3]
    q = embs[idx]; idx += 1
    ce = embs[idx:]
    td = compute_direction(tp, tn)
    cv = compute_direction(ca, cb)
    cm = np.array([ds["correct_fn"](c) for c in ds["candidates"]])
    dataset_cache.append((q, ce, td, cv, cm, ds["name"]))

print("Alpha/Beta Ablation - mxbai-embed-large")
print(f"{'Config':<25} {'Countries':>10} {'Occupations':>12} {'Animals':>10} {'Mean':>8}")
print("-" * 70)

results = []
for alpha, beta, label in configs:
    mrrs = []
    for q, ce, td, cv, cm, name in dataset_cache:
        scores = structured_match(q, ce, td, [cv], alpha=alpha, beta=beta)
        ranking = np.argsort(-scores)
        ranks = np.where(cm[ranking])[0] + 1
        mrr = float(np.mean(1.0 / ranks)) if len(ranks) > 0 else 0
        mrrs.append(mrr)
    mean_mrr = sum(mrrs) / len(mrrs)
    print(f"a={alpha:.2f} b={beta:.2f} ({label:<17}) {mrrs[0]:10.4f} {mrrs[1]:12.4f} {mrrs[2]:10.4f} {mean_mrr:8.4f}")
    results.append({"alpha": alpha, "beta": beta, "label": label, "mrrs": mrrs, "mean": mean_mrr})

# Also test naive cosine for reference
from scripts.structured_matching import naive_cosine_ranking
print(f"\n{'Naive cosine':<25}", end="")
for q, ce, td, cv, cm, name in dataset_cache:
    scores = naive_cosine_ranking(q, ce)
    ranking = np.argsort(-scores)
    ranks = np.where(cm[ranking])[0] + 1
    mrr = float(np.mean(1.0 / ranks))
    print(f" {mrr:10.4f}", end="")
print()

with open("data/ablation_results.json", "w") as f:
    json.dump(results, f, indent=2)
print("\nSaved to data/ablation_results.json")
