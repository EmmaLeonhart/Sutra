"""Probe for a learnable 'object-of-sentence' role matrix in nomic.

Goal: test whether there exists a clean linear map M such that for
simple subject-verb-object sentences, M @ sentence_emb ~ object_emb.

If there is (high cosine, high top-1 on held-out), that supports the
Sutra spec's position that roles are learned matrices. If there isn't
(no better than random or degenerate solutions), that's a strike
against the matrix-for-a-role framing on this particular substrate.

Method:
- 30 simple SVO sentences with unambiguous direct objects.
- Embed both sentence and object with nomic-embed-text via Ollama,
  mean-centered + L2-normalized (matching codegen_numpy.embed).
- 5-fold cross-validation: fit M by least-squares on train,
  evaluate on held-out test.
- Report: mean cosine(M @ s_test, o_test), top-1 retrieval rank
  against the 30-object codebook, and baselines:
  * identity (M = I): just use sentence emb directly
  * mean-object: always predict the mean object embedding
  * random gaussian matrix

Run: python planning/exploratory/object_matrix_probe.py
"""
from __future__ import annotations

import sys
import numpy as np

try:
    import ollama
except ImportError:
    sys.stderr.write("ollama python package required\n")
    sys.exit(1)

MODEL = "nomic-embed-text"
RNG = np.random.default_rng(42)

PAIRS = [
    ("The cat chased the mouse.",            "mouse"),
    ("Alice met Bob at the cafe.",           "Bob"),
    ("The chef prepared the soup.",          "soup"),
    ("The dog bit the postman.",             "postman"),
    ("She wrote a letter to her mother.",    "letter"),
    ("He read the book last night.",         "book"),
    ("The boy kicked the ball.",             "ball"),
    ("The girl painted a picture.",          "picture"),
    ("He drove the car to work.",            "car"),
    ("The teacher graded the papers.",       "papers"),
    ("She played the piano beautifully.",    "piano"),
    ("The farmer harvested the corn.",       "corn"),
    ("He drank the water quickly.",          "water"),
    ("The chef cooked the steak.",           "steak"),
    ("The singer performed the song.",       "song"),
    ("The baker baked the bread fresh.",     "bread"),
    ("The painter painted the wall white.",  "wall"),
    ("The writer finished the novel.",       "novel"),
    ("The scientist discovered a particle.", "particle"),
    ("The detective solved the mystery.",    "mystery"),
    ("The athlete won the race.",            "race"),
    ("The pilot flew the plane.",            "plane"),
    ("The sailor sailed the boat.",          "boat"),
    ("The driver parked the truck.",         "truck"),
    ("The child broke the window.",          "window"),
    ("The woman read the newspaper.",        "newspaper"),
    ("The man fixed the chair.",             "chair"),
    ("The student answered the question.",   "question"),
    ("The doctor examined the patient.",     "patient"),
    ("The judge sentenced the criminal.",    "criminal"),
]


def embed(text: str) -> np.ndarray:
    r = ollama.embed(model=MODEL, input=text)
    v = np.array(r["embeddings"][0], dtype=np.float64)
    # match codegen_numpy.embed: scalar mean-center then L2 normalize
    v = v - np.mean(v)
    n = np.linalg.norm(v)
    return v / n if n > 0 else v


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    na = np.linalg.norm(a)
    nb = np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def fit_lstsq_matrix(S_train: np.ndarray, O_train: np.ndarray) -> np.ndarray:
    """Fit M such that M @ s ~ o for (s, o) pairs. rows are samples."""
    # We want M (d x d) with M @ s = o, i.e. S @ M.T = O in row form.
    # So M.T = lstsq(S, O); M = (lstsq(S, O)).T
    M_T, *_ = np.linalg.lstsq(S_train, O_train, rcond=None)
    return M_T.T


def evaluate(M: np.ndarray, S_test: np.ndarray, O_test: np.ndarray,
             O_codebook: np.ndarray, correct_idx: list[int]) -> dict:
    preds = S_test @ M.T  # (n_test, d)
    cos_true = []
    top1 = 0
    ranks = []
    for i, (p, o_true, true_idx) in enumerate(zip(preds, O_test, correct_idx)):
        cos_true.append(cosine(p, o_true))
        sims = O_codebook @ p / (np.linalg.norm(O_codebook, axis=1) * np.linalg.norm(p) + 1e-12)
        order = np.argsort(-sims)
        rank = int(np.where(order == true_idx)[0][0]) + 1  # 1-indexed
        ranks.append(rank)
        if rank == 1:
            top1 += 1
    return {
        "mean_cos_true": float(np.mean(cos_true)),
        "top1": top1,
        "n": len(preds),
        "mean_rank": float(np.mean(ranks)),
        "ranks": ranks,
    }


def main() -> int:
    print(f"Embedding {len(PAIRS)} (sentence, object) pairs via {MODEL}...")
    S = np.stack([embed(s) for s, _ in PAIRS])
    O = np.stack([embed(o) for _, o in PAIRS])
    n, d = S.shape
    print(f"  shape: S={S.shape}, O={O.shape}")

    # Check baseline: what does similarity(sentence, its own object) look like
    # raw? If it's already high, the "matrix" isn't doing much work.
    print()
    print("Baseline 0 — raw cosine(sentence, its own object), no fit:")
    raw = [cosine(S[i], O[i]) for i in range(n)]
    print(f"  mean={np.mean(raw):+.3f}  min={np.min(raw):+.3f}  max={np.max(raw):+.3f}")

    # 5-fold CV
    print()
    print("Fitting M via 5-fold CV, eval against 30-object codebook:")
    K = 5
    idx = np.arange(n)
    RNG.shuffle(idx)
    folds = np.array_split(idx, K)

    agg = {"cos": [], "top1": [], "rank": []}
    for k in range(K):
        test_idx = folds[k]
        train_idx = np.concatenate([folds[j] for j in range(K) if j != k])
        S_train, O_train = S[train_idx], O[train_idx]
        S_test, O_test = S[test_idx], O[test_idx]
        M = fit_lstsq_matrix(S_train, O_train)
        # correct_idx: position of each test object in the full 30-object codebook O
        correct = [int(i) for i in test_idx]
        res = evaluate(M, S_test, O_test, O, correct)
        print(f"  fold {k}: n={res['n']:>2}  mean_cos={res['mean_cos_true']:+.3f}  "
              f"top1={res['top1']:>2}/{res['n']}  mean_rank={res['mean_rank']:.2f}")
        agg["cos"].append(res["mean_cos_true"])
        agg["top1"].append(res["top1"] / res["n"])
        agg["rank"].append(res["mean_rank"])

    print()
    print("Learned M (5-fold CV, aggregated):")
    print(f"  mean cos(M@s, o_true) = {np.mean(agg['cos']):+.3f}")
    print(f"  top-1 accuracy        = {np.mean(agg['top1'])*100:.1f}%  (chance = {100/n:.1f}%)")
    print(f"  mean rank             = {np.mean(agg['rank']):.2f}  (chance = {(n+1)/2:.1f})")

    # Comparison baselines (on the same test split structure)
    print()
    print("Comparison baselines (average across 5 folds):")
    for name, M_builder in [
        ("identity I",            lambda: np.eye(d)),
        ("mean-object const",     lambda: None),  # special-cased below
        ("random Gaussian",       lambda: RNG.standard_normal((d, d)) / np.sqrt(d)),
    ]:
        b_agg = {"cos": [], "top1": []}
        for k in range(K):
            test_idx = folds[k]
            train_idx = np.concatenate([folds[j] for j in range(K) if j != k])
            S_test, O_test = S[test_idx], O[test_idx]
            O_train = O[train_idx]
            if name == "mean-object const":
                # always predict the train-mean object embedding
                mean_o = O_train.mean(axis=0)
                preds = np.tile(mean_o, (len(test_idx), 1))
            else:
                Mb = M_builder()
                preds = S_test @ Mb.T
            cos_vals = [cosine(preds[i], O_test[i]) for i in range(len(test_idx))]
            top1 = 0
            for i, true_idx in enumerate(test_idx):
                sims = O @ preds[i] / (
                    np.linalg.norm(O, axis=1) * np.linalg.norm(preds[i]) + 1e-12
                )
                order = np.argsort(-sims)
                rank = int(np.where(order == true_idx)[0][0]) + 1
                if rank == 1:
                    top1 += 1
            b_agg["cos"].append(float(np.mean(cos_vals)))
            b_agg["top1"].append(top1 / len(test_idx))
        print(f"  {name:<22} mean_cos={np.mean(b_agg['cos']):+.3f}  "
              f"top1={np.mean(b_agg['top1'])*100:.1f}%")

    # Report M properties: how far from orthogonal, condition number, etc.
    print()
    print("Structure of the fitted M (trained on all 30):")
    M_full = fit_lstsq_matrix(S, O)
    print(f"  M shape: {M_full.shape}")
    print(f"  Frobenius norm ||M||_F = {np.linalg.norm(M_full):.3f}")
    u, sv, _ = np.linalg.svd(M_full)
    print(f"  singular values: top5={sv[:5].tolist()}  "
          f"min={sv[-1]:.3e}  cond={sv[0]/max(sv[-1],1e-12):.1e}")
    M_ortho = u @ _[:d, :]  # nearest orthogonal
    print(f"  distance to nearest orthogonal: {np.linalg.norm(M_full - M_ortho):.3f}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
