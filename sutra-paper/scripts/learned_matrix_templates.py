"""Learned-matrix binding eval with sentence-template embeddings.

Follow-up to `learned_matrix_eval.py`, which gave a null result on bare
entity names (see planning/findings/2026-04-17-wikidata-learned-matrix-null.md
— nomic clusters names at cos > 0.95, destroying relational signal).

Hypothesis: embedding sentence templates that carry the relation in the
*subject side* increases between-pair variance enough for a learned
matrix M to recover a nontrivial mapping.

Per predicate, four text configurations tested:

  bare          s = "{s}",                  o = "{o}"            [reproduces null]
  typed         s = "{s} ({s_type})",       o = "{o}"            [type-qualified subject]
  rich          s = "{s_rich_context}",     o = "{o}"            [Wikipedia-style subject]
  relational    s = "{relation_template}",  o = "{o}"            [subject carries relation]

All four use a *relation-agnostic* object embedding (bare "{o}") so top-1
retrieval against a shared codebook is apples-to-apples across setups.
That keeps the matrix from trivially solving the task by pattern-matching
the template on the object side.

Run:
    python sutra-paper/scripts/learned_matrix_templates.py --n 200
    python sutra-paper/scripts/learned_matrix_templates.py --n 100 --predicates capital-of

Results saved to sutra-paper/scripts/learned_matrix_templates_results.json.
Requires Ollama with nomic-embed-text pulled.
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
USER_AGENT = "sutra-learned-matrix-templates/1.0 (immanuelleleonhart@gmail.com)"

# Each predicate spec: Wikidata query + four text configurations.
# Subject templates take {s}; object template takes {o}.
PREDICATES = {
    "capital-of": {
        "query": """
        SELECT ?sLabel ?oLabel ?sDesc ?oDesc WHERE {
          ?s wdt:P31/wdt:P279* wd:Q6256 .
          ?s wdt:P36 ?o .
          ?s rdfs:label ?sLabel . FILTER(LANG(?sLabel) = "en") .
          ?o rdfs:label ?oLabel . FILTER(LANG(?oLabel) = "en") .
          OPTIONAL { ?s schema:description ?sDesc . FILTER(LANG(?sDesc) = "en") }
          OPTIONAL { ?o schema:description ?oDesc . FILTER(LANG(?oDesc) = "en") }
        } LIMIT {n}
        """,
        "desc": "country -> capital city",
        "s_template_typed": "{s} (country)",
        "s_template_rich": "{s}, a country",
        "s_template_relational": "The capital city of {s} is",
        "o_template": "{o}",
    },
    "country-of-citizenship": {
        "query": """
        SELECT ?sLabel ?oLabel ?sDesc ?oDesc WHERE {
          ?s wdt:P31 wd:Q5 .
          ?s wdt:P27 ?o .
          ?s rdfs:label ?sLabel . FILTER(LANG(?sLabel) = "en") .
          ?o rdfs:label ?oLabel . FILTER(LANG(?oLabel) = "en") .
          ?s wikibase:sitelinks ?sl . FILTER(?sl > 20) .
          OPTIONAL { ?s schema:description ?sDesc . FILTER(LANG(?sDesc) = "en") }
          OPTIONAL { ?o schema:description ?oDesc . FILTER(LANG(?oDesc) = "en") }
        } LIMIT {n}
        """,
        "desc": "person -> country of citizenship",
        "s_template_typed": "{s} (person)",
        "s_template_rich": "{s}, a person",
        "s_template_relational": "{s} is a citizen of the country",
        "o_template": "{o}",
    },
    "located-in-country": {
        "query": """
        SELECT ?sLabel ?oLabel ?sDesc ?oDesc WHERE {
          ?s wdt:P31/wdt:P279* wd:Q515 .
          ?s wdt:P17 ?o .
          ?s rdfs:label ?sLabel . FILTER(LANG(?sLabel) = "en") .
          ?o rdfs:label ?oLabel . FILTER(LANG(?oLabel) = "en") .
          OPTIONAL { ?s schema:description ?sDesc . FILTER(LANG(?sDesc) = "en") }
          OPTIONAL { ?o schema:description ?oDesc . FILTER(LANG(?oDesc) = "en") }
        } LIMIT {n}
        """,
        "desc": "city -> country it is in",
        "s_template_typed": "{s} (city)",
        "s_template_rich": "{s}, a city",
        "s_template_relational": "The city {s} is located in the country",
        "o_template": "{o}",
    },
    "author-of": {
        "query": """
        SELECT ?sLabel ?oLabel ?sDesc ?oDesc WHERE {
          ?o wdt:P31/wdt:P279* wd:Q7725634 .
          ?o wdt:P50 ?s .
          ?s rdfs:label ?sLabel . FILTER(LANG(?sLabel) = "en") .
          ?o rdfs:label ?oLabel . FILTER(LANG(?oLabel) = "en") .
          ?o wikibase:sitelinks ?sl . FILTER(?sl > 10) .
          OPTIONAL { ?s schema:description ?sDesc . FILTER(LANG(?sDesc) = "en") }
          OPTIONAL { ?o schema:description ?oDesc . FILTER(LANG(?oDesc) = "en") }
        } LIMIT {n}
        """,
        "desc": "author -> literary work",
        "s_template_typed": "{s} (author)",
        "s_template_rich": "{s}, an author",
        "s_template_relational": "A book written by {s} is titled",
        "o_template": "{o}",
    },
    "continent-of": {
        # Continent is only 7 classes — well-separated, good low-entropy case.
        "query": """
        SELECT DISTINCT ?sLabel ?oLabel ?sDesc ?oDesc WHERE {
          ?s wdt:P31/wdt:P279* wd:Q6256 .
          ?s wdt:P30 ?o .
          ?s rdfs:label ?sLabel . FILTER(LANG(?sLabel) = "en") .
          ?o rdfs:label ?oLabel . FILTER(LANG(?oLabel) = "en") .
          OPTIONAL { ?s schema:description ?sDesc . FILTER(LANG(?sDesc) = "en") }
          OPTIONAL { ?o schema:description ?oDesc . FILTER(LANG(?oDesc) = "en") }
        } LIMIT {n}
        """,
        "desc": "country -> continent",
        "s_template_typed": "{s} (country)",
        "s_template_rich": "{s}, a country",
        "s_template_relational": "The country {s} is located on the continent of",
        "o_template": "{o}",
    },
}

# `descr` config: use the Wikidata description of the subject (typically a
# short phrase like "capital and largest city of France") instead of the
# bare label. Falls back to `bare` subject text if no description exists.
CONFIGS = ["bare", "typed", "rich", "relational", "descr"]


def fetch_pairs(predicate: str, n: int) -> list[dict]:
    """Returns list of {'s': str, 'o': str, 's_desc': str|None, 'o_desc': str|None}."""
    q = PREDICATES[predicate]["query"].replace("{n}", str(n))
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
        if key in seen:
            continue
        seen.add(key)
        pairs.append({
            "s": s,
            "o": o,
            "s_desc": b.get("sDesc", {}).get("value"),
            "o_desc": b.get("oDesc", {}).get("value"),
        })
    return pairs


_embed_cache: dict[str, np.ndarray] = {}
_st_model = None
_model_name = "nomic-embed-text"


def set_model(name: str):
    global _model_name, _st_model, _embed_cache
    _model_name = name
    _st_model = None
    _embed_cache = {}


def embed(text: str) -> np.ndarray:
    """Embed via Ollama (for nomic-*) or sentence-transformers (for others).
    Mean-center + L2-normalize."""
    if text in _embed_cache:
        return _embed_cache[text]
    if _model_name.startswith("nomic") or _model_name.startswith("mxbai"):
        import ollama
        r = ollama.embed(model=_model_name, input=text)
        v = np.array(r["embeddings"][0], dtype=np.float64)
    else:
        global _st_model
        if _st_model is None:
            from sentence_transformers import SentenceTransformer
            _st_model = SentenceTransformer(_model_name)
        v = _st_model.encode(text, convert_to_numpy=True).astype(np.float64)
    v = v - v.mean()
    n = np.linalg.norm(v)
    if n > 0:
        v = v / n
    _embed_cache[text] = v
    return v


def subject_text(predicate: str, pair: dict | str, config: str) -> str:
    """Accepts either a dict (with s/s_desc) or a bare string (legacy/EXAMPLE)."""
    p = PREDICATES[predicate]
    if isinstance(pair, str):
        s = pair
        s_desc = None
    else:
        s = pair["s"]
        s_desc = pair.get("s_desc")
    if config == "bare":
        return s
    if config == "typed":
        return p["s_template_typed"].format(s=s)
    if config == "rich":
        return p["s_template_rich"].format(s=s)
    if config == "relational":
        return p["s_template_relational"].format(s=s)
    if config == "descr":
        # Wikidata description as the subject text, or fall back to bare.
        if s_desc:
            return f"{s}: {s_desc}"
        return s
    raise ValueError(config)


def object_text(predicate: str, pair: dict | str) -> str:
    """Object text is always the bare label for codebook consistency."""
    if isinstance(pair, str):
        return PREDICATES[predicate]["o_template"].format(o=pair)
    return PREDICATES[predicate]["o_template"].format(o=pair["o"])


def fit_displacement(S_train, O_train):
    return (O_train - S_train).mean(axis=0)


def fit_procrustes(S_train, O_train):
    R, _ = orthogonal_procrustes(S_train, O_train)
    return R


def fit_ridge(S_train, O_train, lam=1.0):
    d = S_train.shape[1]
    gram = S_train.T @ S_train + lam * np.eye(d)
    return np.linalg.solve(gram, S_train.T @ O_train)


def fit_lowrank(S_train, O_train, rank=30, lam=1.0):
    M = fit_ridge(S_train, O_train, lam=lam)
    U, s, Vt = np.linalg.svd(M, full_matrices=False)
    return U[:, :rank] * s[:rank][None, :] @ Vt[:rank, :]


def evaluate(pred, O_test, codebook, obj_idx):
    """pred: (n,d), O_test: (n,d), codebook: (C,d), obj_idx: list[int] of true codebook indices."""
    n = pred.shape[0]
    if n == 0:
        return {"mean_cos": 0.0, "top1": 0.0, "mean_rank": 0.0, "n": 0}
    pred_n = pred / (np.linalg.norm(pred, axis=1, keepdims=True) + 1e-12)
    cosines = np.sum(pred_n * O_test, axis=1)
    sims = pred_n @ codebook.T
    ranks = []
    correct = 0
    for i in range(n):
        ranking = np.argsort(-sims[i])
        rank = int(np.where(ranking == obj_idx[i])[0][0]) + 1
        ranks.append(rank)
        if rank == 1:
            correct += 1
    return {
        "mean_cos": round(float(cosines.mean()), 4),
        "top1": round(correct / n, 4),
        "mean_rank": round(float(np.mean(ranks)), 2),
        "n": n,
    }


def run_config(predicate, pairs, config, n_folds=5):
    """Run all matrix methods under one text configuration.
    pairs is a list of dicts with s/o/s_desc/o_desc."""
    print(f"    [{config}] embedding...", end="", flush=True)
    t0 = time.time()
    S = np.array([embed(subject_text(predicate, p, config)) for p in pairs])
    O = np.array([embed(object_text(predicate, p)) for p in pairs])
    print(f" done in {time.time()-t0:.1f}s", flush=True)

    # Codebook: unique OBJECT TEXTS (always embedded the same way, from label)
    unique_objs = list(dict.fromkeys(p["o"] for p in pairs))
    codebook = np.array([embed(object_text(predicate, o)) for o in unique_objs])
    obj_to_idx = {o: i for i, o in enumerate(unique_objs)}
    obj_idx_all = [obj_to_idx[p["o"]] for p in pairs]

    n = len(pairs)
    indices = np.arange(n)
    rng = np.random.default_rng(42)
    rng.shuffle(indices)
    fold_size = n // n_folds

    methods = ["identity", "mean_object", "displacement", "procrustes",
               "ridge_1.0", "ridge_0.1", "lowrank_30", "random"]
    acc = {m: {"cos": [], "top1": [], "rank": []} for m in methods}

    d_dim = S.shape[1]
    for fold in range(n_folds):
        test_idx = indices[fold * fold_size : (fold + 1) * fold_size]
        train_idx = np.array([i for i in indices if i not in test_idx])
        S_tr, O_tr = S[train_idx], O[train_idx]
        S_te, O_te = S[test_idx], O[test_idx]
        obj_te = [obj_idx_all[i] for i in test_idx]

        # identity
        ev = evaluate(S_te, O_te, codebook, obj_te)
        _append(acc["identity"], ev)

        # mean_object
        mo = O_tr.mean(axis=0, keepdims=True)
        mo = mo / (np.linalg.norm(mo) + 1e-12)
        pred = np.tile(mo, (len(S_te), 1))
        ev = evaluate(pred, O_te, codebook, obj_te)
        _append(acc["mean_object"], ev)

        # displacement
        d = fit_displacement(S_tr, O_tr)
        ev = evaluate(S_te + d, O_te, codebook, obj_te)
        _append(acc["displacement"], ev)

        # procrustes
        R = fit_procrustes(S_tr, O_tr)
        ev = evaluate(S_te @ R, O_te, codebook, obj_te)
        _append(acc["procrustes"], ev)

        # ridge
        M = fit_ridge(S_tr, O_tr, lam=1.0)
        ev = evaluate(S_te @ M, O_te, codebook, obj_te)
        _append(acc["ridge_1.0"], ev)

        M = fit_ridge(S_tr, O_tr, lam=0.1)
        ev = evaluate(S_te @ M, O_te, codebook, obj_te)
        _append(acc["ridge_0.1"], ev)

        # lowrank
        M = fit_lowrank(S_tr, O_tr, rank=30)
        ev = evaluate(S_te @ M, O_te, codebook, obj_te)
        _append(acc["lowrank_30"], ev)

        # random
        M_r = rng.standard_normal((d_dim, d_dim)) / np.sqrt(d_dim)
        ev = evaluate(S_te @ M_r, O_te, codebook, obj_te)
        _append(acc["random"], ev)

    out = {}
    for m, a in acc.items():
        out[m] = {
            "mean_cos": round(float(np.mean(a["cos"])), 4),
            "top1": round(float(np.mean(a["top1"])), 4),
            "mean_rank": round(float(np.mean(a["rank"])), 2),
        }
    out["_codebook_size"] = len(unique_objs)
    out["_chance"] = round(1.0 / len(unique_objs), 4)
    return out


def _append(acc, ev):
    acc["cos"].append(ev["mean_cos"])
    acc["top1"].append(ev["top1"])
    acc["rank"].append(ev["mean_rank"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--predicates", nargs="*", default=None)
    ap.add_argument("--configs", nargs="*", default=None)
    ap.add_argument("--model", default="nomic-embed-text",
                    help="Embedding model. nomic-* or mxbai-* → Ollama; "
                         "otherwise sentence-transformers (e.g. thenlper/gte-large).")
    ap.add_argument("--out", default=None, help="Output JSON path.")
    args = ap.parse_args()
    set_model(args.model)
    print(f"Model: {args.model}")

    preds = args.predicates or list(PREDICATES.keys())
    configs = args.configs or CONFIGS

    all_results = {}
    for pred in preds:
        if pred not in PREDICATES:
            print(f"Unknown predicate: {pred}")
            continue
        print(f"\n{'='*72}")
        print(f"Predicate: {pred} ({PREDICATES[pred]['desc']})")
        try:
            pairs = fetch_pairs(pred, args.n)
        except Exception as e:
            print(f"  ERROR fetching: {e}")
            all_results[pred] = {"error": str(e)}
            continue
        print(f"  Fetched {len(pairs)} pairs")
        if len(pairs) < 20:
            print(f"  SKIP (<20)")
            all_results[pred] = {"skipped": True, "n_pairs": len(pairs)}
            continue
        time.sleep(2)

        pred_results = {"n_pairs": len(pairs), "configs": {}}
        for cfg in configs:
            print(f"\n  Config: {cfg}")
            print(f"    subj template: \"{subject_text(pred, 'EXAMPLE_SUBJ', cfg)}\"")
            print(f"    obj  template: \"{object_text(pred, 'EXAMPLE_OBJ')}\"")
            r = run_config(pred, pairs, cfg, n_folds=args.folds)
            pred_results["configs"][cfg] = r

            print(f"    {'Method':<16} {'Top1':>8} {'MeanCos':>9} {'MeanRank':>10} (chance {r['_chance']}, CB={r['_codebook_size']})")
            for m, vals in r.items():
                if m.startswith("_"):
                    continue
                print(f"    {m:<16} {vals['top1']:>8.4f} {vals['mean_cos']:>9.4f} {vals['mean_rank']:>10.2f}")

        all_results[pred] = pred_results

    out_path = Path(args.out) if args.out else (
        Path(__file__).parent / "learned_matrix_templates_results.json"
    )
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to {out_path}")


if __name__ == "__main__":
    main()
