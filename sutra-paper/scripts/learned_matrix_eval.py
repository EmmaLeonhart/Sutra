"""Learned-matrix binding evaluation on Wikidata relational triples.

For each Wikidata predicate (capital-of, country-of, etc.), pulls
(subject, object) pairs, embeds both via nomic-embed-text, and fits
four candidate role matrices:

  1. Displacement (rank-0): d = mean(v_obj - v_subj), predict v_subj + d
  2. Orthogonal Procrustes: R = argmin_R ||R @ S - O||, R^T R = I
  3. Low-rank regression: M = U V^T with rank r via truncated SVD of lstsq
  4. Ridge regression: M = O S^T (S S^T + λI)^{-1}

Evaluates each on held-out pairs: top-1 retrieval against per-predicate
object codebook, mean rank, mean cosine. Baselines: identity, constant
mean-object, random Gaussian.

Run:
    python sutra-paper/scripts/learned_matrix_eval.py --n 200

Requires Ollama running with nomic-embed-text pulled.
Results written to sutra-paper/scripts/learned_matrix_eval_results.json.
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import numpy as np
import requests
from scipy.linalg import orthogonal_procrustes

WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"
USER_AGENT = "sutra-learned-matrix-eval/1.0 (immanuelleleonhart@gmail.com)"

# Predicates with (subject_class, predicate, object description).
# Each query pulls pairs where subject --predicate--> object.
PREDICATES = {
    "capital-of": {
        "query": """
        SELECT ?sLabel ?oLabel WHERE {
          ?s wdt:P31/wdt:P279* wd:Q6256 .
          ?s wdt:P36 ?o .
          ?s rdfs:label ?sLabel . FILTER(LANG(?sLabel) = "en") .
          ?o rdfs:label ?oLabel . FILTER(LANG(?oLabel) = "en") .
        } LIMIT {n}
        """,
        "desc": "country → capital city",
    },
    "country-of-citizenship": {
        "query": """
        SELECT ?sLabel ?oLabel WHERE {
          ?s wdt:P31 wd:Q5 .
          ?s wdt:P27 ?o .
          ?s rdfs:label ?sLabel . FILTER(LANG(?sLabel) = "en") .
          ?o rdfs:label ?oLabel . FILTER(LANG(?oLabel) = "en") .
          ?s wikibase:sitelinks ?sl . FILTER(?sl > 20) .
        } LIMIT {n}
        """,
        "desc": "person → country of citizenship",
    },
    "located-in-country": {
        "query": """
        SELECT ?sLabel ?oLabel WHERE {
          ?s wdt:P31/wdt:P279* wd:Q515 .
          ?s wdt:P17 ?o .
          ?s rdfs:label ?sLabel . FILTER(LANG(?sLabel) = "en") .
          ?o rdfs:label ?oLabel . FILTER(LANG(?oLabel) = "en") .
        } LIMIT {n}
        """,
        "desc": "city → country it is in",
    },
    "author-of": {
        "query": """
        SELECT ?sLabel ?oLabel WHERE {
          ?o wdt:P31/wdt:P279* wd:Q7725634 .
          ?o wdt:P50 ?s .
          ?s rdfs:label ?sLabel . FILTER(LANG(?sLabel) = "en") .
          ?o rdfs:label ?oLabel . FILTER(LANG(?oLabel) = "en") .
          ?o wikibase:sitelinks ?sl . FILTER(?sl > 10) .
        } LIMIT {n}
        """,
        "desc": "author → literary work",
    },
    "instance-of": {
        "query": """
        SELECT ?sLabel ?oLabel WHERE {
          ?s wdt:P31 ?o .
          ?s rdfs:label ?sLabel . FILTER(LANG(?sLabel) = "en") .
          ?o rdfs:label ?oLabel . FILTER(LANG(?oLabel) = "en") .
          ?s wikibase:sitelinks ?sl . FILTER(?sl > 30) .
        } LIMIT {n}
        """,
        "desc": "entity → its type",
    },
}


def fetch_pairs(predicate: str, n: int) -> list[tuple[str, str]]:
    """Fetch (subject_label, object_label) pairs from Wikidata."""
    query_template = PREDICATES[predicate]["query"]
    q = query_template.replace("{n}", str(n))
    r = requests.get(
        WIKIDATA_SPARQL,
        params={"query": q, "format": "json"},
        headers={"User-Agent": USER_AGENT},
        timeout=90,
    )
    r.raise_for_status()
    pairs = []
    seen = set()
    for b in r.json()["results"]["bindings"]:
        s = b["sLabel"]["value"]
        o = b["oLabel"]["value"]
        key = (s, o)
        if key not in seen:
            seen.add(key)
            pairs.append((s, o))
    return pairs


_embed_cache: dict[str, np.ndarray] = {}


def embed(text: str, model: str = "nomic-embed-text") -> np.ndarray:
    """Embed text via Ollama, mean-centered + L2-normalized."""
    if text in _embed_cache:
        return _embed_cache[text]
    import ollama
    r = ollama.embed(model=model, input=text)
    v = np.array(r["embeddings"][0], dtype=np.float64)
    v = v - v.mean()
    n = np.linalg.norm(v)
    if n > 0:
        v = v / n
    _embed_cache[text] = v
    return v


def fit_displacement(S_train: np.ndarray, O_train: np.ndarray) -> np.ndarray:
    """Rank-0 baseline: predict v_subj + mean_displacement."""
    return (O_train - S_train).mean(axis=0)


def predict_displacement(S: np.ndarray, d: np.ndarray) -> np.ndarray:
    """Apply displacement to each row of S."""
    return S + d


def fit_procrustes(S_train: np.ndarray, O_train: np.ndarray) -> np.ndarray:
    """Orthogonal Procrustes: find R minimizing ||R @ S^T - O^T||."""
    R, _ = orthogonal_procrustes(S_train, O_train)
    return R  # shape (d, d), S @ R ≈ O


def predict_procrustes(S: np.ndarray, R: np.ndarray) -> np.ndarray:
    return S @ R


def fit_ridge(S_train: np.ndarray, O_train: np.ndarray, lam: float = 1.0) -> np.ndarray:
    """Ridge regression: M = O^T S (S^T S + λI)^{-1}, so predicted = S @ M."""
    d = S_train.shape[1]
    gram = S_train.T @ S_train + lam * np.eye(d)
    M = np.linalg.solve(gram, S_train.T @ O_train)
    return M  # shape (d, d), predict = S @ M


def predict_ridge(S: np.ndarray, M: np.ndarray) -> np.ndarray:
    return S @ M


def fit_lowrank(S_train: np.ndarray, O_train: np.ndarray, rank: int = 30, lam: float = 1.0) -> np.ndarray:
    """Low-rank regression: fit ridge M, then truncate to given rank via SVD."""
    M_full = fit_ridge(S_train, O_train, lam=lam)
    U, s, Vt = np.linalg.svd(M_full, full_matrices=False)
    # Truncate to rank
    U_r = U[:, :rank]
    s_r = s[:rank]
    Vt_r = Vt[:rank, :]
    return U_r * s_r[None, :] @ Vt_r  # shape (d, d)


def predict_lowrank(S: np.ndarray, M: np.ndarray) -> np.ndarray:
    return S @ M


def evaluate(predictions: np.ndarray, O_test: np.ndarray, codebook: np.ndarray) -> dict:
    """Evaluate predictions against test objects.

    predictions: (n_test, d) predicted object embeddings
    O_test: (n_test, d) true object embeddings
    codebook: (C, d) all unique object embeddings for this predicate
    """
    n = predictions.shape[0]
    if n == 0:
        return {"mean_cos": 0.0, "top1": 0.0, "mean_rank": 0.0, "n": 0}

    # Cosine similarities (embeddings are already L2-normalized)
    cosines = np.sum(predictions * O_test, axis=1)
    mean_cos = float(cosines.mean())

    # Top-1 retrieval
    # For each prediction, rank all codebook entries by cosine
    sims = predictions @ codebook.T  # (n_test, C)
    ranks = []
    top1_correct = 0
    for i in range(n):
        # Find the true object in the codebook
        true_cos = predictions[i] @ O_test[i]
        # How many codebook entries have higher similarity?
        rank = int((sims[i] > true_cos - 1e-9).sum())  # 1-indexed
        # More precise: find which codebook entry matches O_test[i]
        cb_sims_to_true = codebook @ O_test[i]
        true_idx = int(np.argmax(cb_sims_to_true))
        pred_ranking = np.argsort(-sims[i])
        rank_of_true = int(np.where(pred_ranking == true_idx)[0][0]) + 1
        ranks.append(rank_of_true)
        if rank_of_true == 1:
            top1_correct += 1

    return {
        "mean_cos": round(mean_cos, 4),
        "top1": round(top1_correct / n, 4),
        "mean_rank": round(np.mean(ranks), 2),
        "n": n,
    }


def run_predicate(predicate: str, pairs: list[tuple[str, str]], n_folds: int = 5) -> dict:
    """Run all methods on one predicate with cross-validation."""
    print(f"\n{'='*60}")
    print(f"Predicate: {predicate} ({PREDICATES[predicate]['desc']})")
    print(f"  Pairs fetched: {len(pairs)}")

    if len(pairs) < 20:
        print(f"  SKIP: too few pairs ({len(pairs)})")
        return {"predicate": predicate, "skipped": True, "n_pairs": len(pairs)}

    # Embed all subjects and objects
    print("  Embedding...", end="", flush=True)
    subjects = [p[0] for p in pairs]
    objects = [p[1] for p in pairs]
    S = np.array([embed(s) for s in subjects])
    O = np.array([embed(o) for o in objects])
    print(f" done ({S.shape[0]} × {S.shape[1]})")

    # Build codebook: unique object embeddings
    unique_objects = list(set(objects))
    codebook = np.array([embed(o) for o in unique_objects])
    print(f"  Codebook size: {codebook.shape[0]} unique objects")

    # Cross-validation
    n = len(pairs)
    indices = np.arange(n)
    rng = np.random.default_rng(42)
    rng.shuffle(indices)
    fold_size = n // n_folds

    methods = {
        "identity": {},
        "mean_object": {},
        "displacement": {},
        "procrustes": {},
        "ridge_1.0": {},
        "ridge_0.1": {},
        "lowrank_10": {},
        "lowrank_30": {},
        "lowrank_50": {},
        "random_gaussian": {},
    }
    # Accumulate per-fold results
    for m in methods:
        methods[m] = {"cosines": [], "top1s": [], "ranks": [], "ns": []}

    for fold in range(n_folds):
        test_idx = indices[fold * fold_size : (fold + 1) * fold_size]
        train_idx = np.array([i for i in indices if i not in test_idx])

        S_train, O_train = S[train_idx], O[train_idx]
        S_test, O_test = S[test_idx], O[test_idx]

        # Identity baseline
        ev = evaluate(S_test, O_test, codebook)
        methods["identity"]["cosines"].append(ev["mean_cos"])
        methods["identity"]["top1s"].append(ev["top1"])
        methods["identity"]["ranks"].append(ev["mean_rank"])
        methods["identity"]["ns"].append(ev["n"])

        # Mean-object baseline
        mean_obj = O_train.mean(axis=0, keepdims=True)
        mean_obj = mean_obj / (np.linalg.norm(mean_obj) + 1e-12)
        pred_mean = np.tile(mean_obj, (len(S_test), 1))
        ev = evaluate(pred_mean, O_test, codebook)
        methods["mean_object"]["cosines"].append(ev["mean_cos"])
        methods["mean_object"]["top1s"].append(ev["top1"])
        methods["mean_object"]["ranks"].append(ev["mean_rank"])
        methods["mean_object"]["ns"].append(ev["n"])

        # Displacement
        d = fit_displacement(S_train, O_train)
        pred = predict_displacement(S_test, d)
        pred = pred / (np.linalg.norm(pred, axis=1, keepdims=True) + 1e-12)
        ev = evaluate(pred, O_test, codebook)
        methods["displacement"]["cosines"].append(ev["mean_cos"])
        methods["displacement"]["top1s"].append(ev["top1"])
        methods["displacement"]["ranks"].append(ev["mean_rank"])
        methods["displacement"]["ns"].append(ev["n"])

        # Procrustes
        R = fit_procrustes(S_train, O_train)
        pred = predict_procrustes(S_test, R)
        pred = pred / (np.linalg.norm(pred, axis=1, keepdims=True) + 1e-12)
        ev = evaluate(pred, O_test, codebook)
        methods["procrustes"]["cosines"].append(ev["mean_cos"])
        methods["procrustes"]["top1s"].append(ev["top1"])
        methods["procrustes"]["ranks"].append(ev["mean_rank"])
        methods["procrustes"]["ns"].append(ev["n"])

        # Ridge λ=1.0
        M = fit_ridge(S_train, O_train, lam=1.0)
        pred = predict_ridge(S_test, M)
        pred = pred / (np.linalg.norm(pred, axis=1, keepdims=True) + 1e-12)
        ev = evaluate(pred, O_test, codebook)
        methods["ridge_1.0"]["cosines"].append(ev["mean_cos"])
        methods["ridge_1.0"]["top1s"].append(ev["top1"])
        methods["ridge_1.0"]["ranks"].append(ev["mean_rank"])
        methods["ridge_1.0"]["ns"].append(ev["n"])

        # Ridge λ=0.1
        M = fit_ridge(S_train, O_train, lam=0.1)
        pred = predict_ridge(S_test, M)
        pred = pred / (np.linalg.norm(pred, axis=1, keepdims=True) + 1e-12)
        ev = evaluate(pred, O_test, codebook)
        methods["ridge_0.1"]["cosines"].append(ev["mean_cos"])
        methods["ridge_0.1"]["top1s"].append(ev["top1"])
        methods["ridge_0.1"]["ranks"].append(ev["mean_rank"])
        methods["ridge_0.1"]["ns"].append(ev["n"])

        # Low-rank 10
        M = fit_lowrank(S_train, O_train, rank=10)
        pred = predict_lowrank(S_test, M)
        pred = pred / (np.linalg.norm(pred, axis=1, keepdims=True) + 1e-12)
        ev = evaluate(pred, O_test, codebook)
        methods["lowrank_10"]["cosines"].append(ev["mean_cos"])
        methods["lowrank_10"]["top1s"].append(ev["top1"])
        methods["lowrank_10"]["ranks"].append(ev["mean_rank"])
        methods["lowrank_10"]["ns"].append(ev["n"])

        # Low-rank 30
        M = fit_lowrank(S_train, O_train, rank=30)
        pred = predict_lowrank(S_test, M)
        pred = pred / (np.linalg.norm(pred, axis=1, keepdims=True) + 1e-12)
        ev = evaluate(pred, O_test, codebook)
        methods["lowrank_30"]["cosines"].append(ev["mean_cos"])
        methods["lowrank_30"]["top1s"].append(ev["top1"])
        methods["lowrank_30"]["ranks"].append(ev["mean_rank"])
        methods["lowrank_30"]["ns"].append(ev["n"])

        # Low-rank 50
        M = fit_lowrank(S_train, O_train, rank=50)
        pred = predict_lowrank(S_test, M)
        pred = pred / (np.linalg.norm(pred, axis=1, keepdims=True) + 1e-12)
        ev = evaluate(pred, O_test, codebook)
        methods["lowrank_50"]["cosines"].append(ev["mean_cos"])
        methods["lowrank_50"]["top1s"].append(ev["top1"])
        methods["lowrank_50"]["ranks"].append(ev["mean_rank"])
        methods["lowrank_50"]["ns"].append(ev["n"])

        # Random Gaussian
        d_dim = S.shape[1]
        M_rand = rng.standard_normal((d_dim, d_dim)) / np.sqrt(d_dim)
        pred = S_test @ M_rand
        pred = pred / (np.linalg.norm(pred, axis=1, keepdims=True) + 1e-12)
        ev = evaluate(pred, O_test, codebook)
        methods["random_gaussian"]["cosines"].append(ev["mean_cos"])
        methods["random_gaussian"]["top1s"].append(ev["top1"])
        methods["random_gaussian"]["ranks"].append(ev["mean_rank"])
        methods["random_gaussian"]["ns"].append(ev["n"])

    # Aggregate
    results = {"predicate": predicate, "n_pairs": len(pairs),
               "codebook_size": codebook.shape[0], "methods": {}}
    print(f"\n  {'Method':<20} {'MeanCos':>8} {'Top1':>8} {'MeanRank':>10} {'Chance':>8}")
    print(f"  {'-'*56}")
    chance = round(1.0 / codebook.shape[0], 4)
    for m_name, m_data in methods.items():
        mean_cos = round(np.mean(m_data["cosines"]), 4)
        mean_top1 = round(np.mean(m_data["top1s"]), 4)
        mean_rank = round(np.mean(m_data["ranks"]), 2)
        results["methods"][m_name] = {
            "mean_cos": mean_cos, "top1": mean_top1,
            "mean_rank": mean_rank, "chance_top1": chance,
        }
        print(f"  {m_name:<20} {mean_cos:>8.4f} {mean_top1:>8.4f} {mean_rank:>10.2f} {chance:>8.4f}")

    return results


def main():
    parser = argparse.ArgumentParser(description="Learned-matrix binding eval on Wikidata triples")
    parser.add_argument("--n", type=int, default=200, help="Max pairs per predicate")
    parser.add_argument("--folds", type=int, default=5, help="CV folds")
    parser.add_argument("--predicates", nargs="*", default=None,
                        help="Subset of predicates to run (default: all)")
    args = parser.parse_args()

    preds = args.predicates or list(PREDICATES.keys())
    all_results = []

    for pred in preds:
        if pred not in PREDICATES:
            print(f"Unknown predicate: {pred}")
            continue
        print(f"\nFetching Wikidata pairs for '{pred}'...")
        try:
            pairs = fetch_pairs(pred, args.n)
        except Exception as e:
            print(f"  ERROR fetching {pred}: {e}")
            all_results.append({"predicate": pred, "error": str(e)})
            continue
        time.sleep(2)  # respect Wikidata rate limits

        result = run_predicate(pred, pairs, n_folds=args.folds)
        all_results.append(result)

    # Save results
    out_path = Path(__file__).parent / "learned_matrix_eval_results.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to {out_path}")


if __name__ == "__main__":
    main()
