"""Wikidata-scale evaluation of sign-flip binding.

Pulls N item-class pairs from Wikidata via SPARQL, embeds via Ollama
(nomic-embed-text by default), bundles each item into a k-role
record, unbinds and snaps every role, reports per-role and overall
accuracy across the corpus.

Replaces the 10/10 chained-step number that AI peer reviewers
flagged as statistically insignificant. With N = 200 items × 5 roles
= 1000 unbind+snap trials this puts a real number on capacity.

Run:
    python sutra-paper/scripts/wikidata_scale_eval.py --n 200 --k 5

Requires Ollama running with the embedding model pulled. Results are
written to sutra-paper/scripts/wikidata_scale_eval_results.json.
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


WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"

# Five well-populated, semantically distinct role classes. Pull the
# top-N most-linked instances of each. The "role" each query embodies
# is the class itself; the "filler" is the instance label.
ROLE_QUERIES = {
    "country":   ("Q6256",     "country"),
    "city":      ("Q515",      "city"),
    "river":     ("Q4022",     "river"),
    "mountain":  ("Q8502",     "mountain"),
    "language":  ("Q34770",    "language"),
}


def fetch_instances(class_qid: str, n: int) -> list[str]:
    q = f"""
    SELECT ?itemLabel WHERE {{
      ?item wdt:P31/wdt:P279* wd:{class_qid} .
      ?item rdfs:label ?itemLabel . FILTER(LANG(?itemLabel) = "en") .
    }} LIMIT {n}
    """
    r = requests.get(
        WIKIDATA_SPARQL, params={"query": q, "format": "json"},
        headers={"User-Agent": "sutra-eval/1.0 (immanuelleleonhart@gmail.com)"},
        timeout=60,
    )
    r.raise_for_status()
    return [b["itemLabel"]["value"]
            for b in r.json()["results"]["bindings"]]


def ollama_embed(model: str, text: str, cache: dict) -> np.ndarray:
    if text in cache:
        return cache[text]
    import ollama
    r = ollama.embed(model=model, input=text)
    v = np.array(r["embeddings"][0], dtype=np.float64)
    v = v - v.mean()
    n = np.linalg.norm(v)
    if n > 0:
        v = v / n
    cache[text] = v
    return v


def sign_flip_bind(filler: np.ndarray, role: np.ndarray) -> np.ndarray:
    s = np.sign(role)
    s[s == 0] = 1
    return filler * s


def bundle(vectors: list[np.ndarray]) -> np.ndarray:
    s = np.sum(vectors, axis=0)
    n = np.linalg.norm(s)
    return s / n if n > 0 else s


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def argmax_cosine(query: np.ndarray, codebook: list[np.ndarray]) -> int:
    sims = [cosine(query, c) for c in codebook]
    return int(np.argmax(sims))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=200,
                    help="Items per role class.")
    ap.add_argument("--k", type=int, default=5,
                    help="Roles bundled per record (capped by ROLE_QUERIES).")
    ap.add_argument("--model", default="nomic-embed-text")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    role_names = list(ROLE_QUERIES)[:args.k]
    print(f"Pulling {args.n} instances each for roles: {role_names}",
          flush=True)
    rng = np.random.RandomState(args.seed)

    instances: dict[str, list[str]] = {}
    for rn in role_names:
        qid, _ = ROLE_QUERIES[rn]
        items = fetch_instances(qid, args.n)
        # Stable shuffle for reproducibility.
        rng.shuffle(items)
        instances[rn] = items[:args.n]
        print(f"  {rn}: {len(instances[rn])} items "
              f"(first 3: {instances[rn][:3]})", flush=True)

    print(f"\nEmbedding {sum(len(v) for v in instances.values())} "
          f"item labels + {len(role_names)} role names via {args.model}...",
          flush=True)
    cache: dict[str, np.ndarray] = {}
    # Embed items first to establish dim, then generate random Gaussian
    # roles at that dim. Per EmbeddingSubstrate.random_roles() in
    # sutra_runtime.py: structural keys must be near-orthogonal, which
    # embedded role names are not — they cluster semantically and
    # collapse sign-flip binding. Content comes from the LLM; roles
    # come from a seeded RNG.
    item_vecs = {}
    for rn in role_names:
        item_vecs[rn] = [ollama_embed(args.model, lbl, cache)
                         for lbl in instances[rn]]
    dim = item_vecs[role_names[0]][0].shape[0]
    role_rng = np.random.RandomState(args.seed + 1)
    role_vecs = {}
    for rn in role_names:
        v = role_rng.standard_normal(dim).astype(np.float64)
        v = v / np.linalg.norm(v)
        role_vecs[rn] = v

    # Per-role codebooks. To recover filler given (bundle, role), snap
    # the unbound vector against the codebook of all candidate fillers
    # for that role.
    codebooks = {rn: item_vecs[rn] for rn in role_names}

    # Sweep: vary number of bundled roles k and codebook size C. For
    # each (k, C) config, for every i in [0, C), build a bundled record
    # from item[i] across k roles, unbind each role, snap against the
    # C-sized per-role codebook. Report accuracy per role and overall.
    k_values = [2, 3, 5]
    c_values = [10, 50, 200]
    t0 = time.perf_counter()
    sweep = []
    print(f"\n{'k':>3} {'C':>5} {'trials':>8} {'correct':>8} {'acc':>8}")
    print("-" * 40)
    for k in k_values:
        roles_used = role_names[:k]
        for C in c_values:
            correct = 0
            total = 0
            for i in range(C):
                bound = [sign_flip_bind(item_vecs[rn][i], role_vecs[rn])
                         for rn in roles_used]
                record = bundle(bound)
                for rn in roles_used:
                    recovered = sign_flip_bind(record, role_vecs[rn])
                    idx = argmax_cosine(recovered, codebooks[rn][:C])
                    total += 1
                    if idx == i:
                        correct += 1
            acc = correct / total
            sweep.append({"k": k, "C": C, "correct": correct,
                          "total": total, "acc": acc})
            print(f"{k:>3} {C:>5} {total:>8} {correct:>8} {acc:>7.2%}")
    elapsed = time.perf_counter() - t0
    print("-" * 40)
    print(f"Elapsed: {elapsed:.1f}s")

    out = {
        "model": args.model,
        "n": args.n,
        "roles": role_names,
        "elapsed_s": elapsed,
        "sweep": sweep,
    }
    out_path = Path(__file__).parent / "wikidata_scale_eval_results.json"
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nWrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
