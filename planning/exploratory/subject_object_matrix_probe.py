"""Probe for distinguishable subject and object role matrices in nomic.

The previous probe (object_matrix_probe.py) found that the identity
baseline wins for 'object of sentence' because the object word is
lexically present. This probe asks the sharper question: does nomic
distinguish subject from object linearly?

Identity can return at most ONE content word when asked for either
role. If M_subject and M_object are genuinely different operators
that each recover the correct role word, that's positive evidence
that role matrices exist and differ — which is what the spec claims.

If M_subject ≈ M_object (both collapse to identity or mean), that's
strong negative evidence that nomic linearly distinguishes roles.

Setup: same 30 SVO sentences, but with both subject and object
labelled. Fit both matrices via 5-fold CV. Report per-role top-1,
and critically — per-role top-1 of the *wrong* matrix
(M_object applied to a subject query should be WORSE than
M_subject applied to a subject query).
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

# (sentence, subject, object)
TRIPLES = [
    ("The cat chased the mouse.",            "cat",       "mouse"),
    ("Alice met Bob at the cafe.",           "Alice",     "Bob"),
    ("The chef prepared the soup.",          "chef",      "soup"),
    ("The dog bit the postman.",             "dog",       "postman"),
    ("She wrote a letter to her mother.",    "she",       "letter"),
    ("He read the book last night.",         "he",        "book"),
    ("The boy kicked the ball.",             "boy",       "ball"),
    ("The girl painted a picture.",          "girl",      "picture"),
    ("He drove the car to work.",            "he",        "car"),
    ("The teacher graded the papers.",       "teacher",   "papers"),
    ("She played the piano beautifully.",    "she",       "piano"),
    ("The farmer harvested the corn.",       "farmer",    "corn"),
    ("He drank the water quickly.",          "he",        "water"),
    ("The chef cooked the steak.",           "chef",      "steak"),
    ("The singer performed the song.",       "singer",    "song"),
    ("The baker baked the bread fresh.",     "baker",     "bread"),
    ("The painter painted the wall white.",  "painter",   "wall"),
    ("The writer finished the novel.",       "writer",    "novel"),
    ("The scientist discovered a particle.", "scientist", "particle"),
    ("The detective solved the mystery.",    "detective", "mystery"),
    ("The athlete won the race.",            "athlete",   "race"),
    ("The pilot flew the plane.",            "pilot",     "plane"),
    ("The sailor sailed the boat.",          "sailor",    "boat"),
    ("The driver parked the truck.",         "driver",    "truck"),
    ("The child broke the window.",          "child",     "window"),
    ("The woman read the newspaper.",        "woman",     "newspaper"),
    ("The man fixed the chair.",             "man",       "chair"),
    ("The student answered the question.",   "student",   "question"),
    ("The doctor examined the patient.",     "doctor",    "patient"),
    ("The judge sentenced the criminal.",    "judge",     "criminal"),
]


def embed(text: str) -> np.ndarray:
    r = ollama.embed(model=MODEL, input=text)
    v = np.array(r["embeddings"][0], dtype=np.float64)
    v = v - np.mean(v)
    n = np.linalg.norm(v)
    return v / n if n > 0 else v


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    na = np.linalg.norm(a)
    nb = np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def fit_matrix(S_train: np.ndarray, T_train: np.ndarray) -> np.ndarray:
    M_T, *_ = np.linalg.lstsq(S_train, T_train, rcond=None)
    return M_T.T


def top1_against_codebook(preds: np.ndarray, codebook: np.ndarray,
                          correct_idx: list[int]) -> int:
    """How many preds retrieve the correct index from codebook by cosine."""
    cb_norms = np.linalg.norm(codebook, axis=1)
    correct = 0
    for i, ci in enumerate(correct_idx):
        p_norm = np.linalg.norm(preds[i])
        if p_norm == 0:
            continue
        sims = codebook @ preds[i] / (cb_norms * p_norm + 1e-12)
        if int(np.argmax(sims)) == ci:
            correct += 1
    return correct


def main() -> int:
    print(f"Embedding {len(TRIPLES)} (sentence, subject, object) triples via {MODEL}...")
    S = np.stack([embed(s) for s, _, _ in TRIPLES])
    Subj = np.stack([embed(s) for _, s, _ in TRIPLES])
    Obj = np.stack([embed(o) for _, _, o in TRIPLES])
    n, d = S.shape
    print(f"  shape: S={S.shape}  Subj={Subj.shape}  Obj={Obj.shape}")

    # Raw baselines: is subject-emb or object-emb nearer to sentence-emb?
    raw_subj = np.mean([cosine(S[i], Subj[i]) for i in range(n)])
    raw_obj = np.mean([cosine(S[i], Obj[i]) for i in range(n)])
    raw_subj_obj_conflict = np.mean([cosine(Subj[i], Obj[i]) for i in range(n)])
    print()
    print("Raw (no fit) cosines:")
    print(f"  mean cos(sentence, its subject) = {raw_subj:+.3f}")
    print(f"  mean cos(sentence, its object)  = {raw_obj:+.3f}")
    print(f"  mean cos(subject, object)       = {raw_subj_obj_conflict:+.3f}")

    # Identity baseline: for each sentence, which is nearest in the
    # full 2n-word codebook (subject + object of all sentences)? Also
    # measure: when asked for subject vs object, does identity give
    # the right answer for both, one, or neither?
    all_words = np.concatenate([Subj, Obj], axis=0)
    # indices: subj of sentence i is at position i; obj of sentence i is at n+i
    print()
    print("Identity baseline (prediction = sentence emb):")
    id_subj_top1 = top1_against_codebook(S, all_words, list(range(n)))
    id_obj_top1 = top1_against_codebook(S, all_words, list(range(n, 2 * n)))
    print(f"  top-1 retrieving SUBJECT of each sentence: {id_subj_top1}/{n}")
    print(f"  top-1 retrieving OBJECT of each sentence:  {id_obj_top1}/{n}")
    print("  (identity returns sentence emb for both queries — can at most")
    print("   be correct for one role per sentence)")

    # Key experiment: fit M_subj and M_obj via 5-fold CV.
    K = 5
    idx = np.arange(n)
    RNG.shuffle(idx)
    folds = np.array_split(idx, K)

    per_fold = {
        "subj_via_Msubj": [], "obj_via_Mobj": [],
        "subj_via_Mobj": [], "obj_via_Msubj": [],
        "subj_via_id": [],   "obj_via_id": [],
    }

    for k in range(K):
        test_idx = folds[k]
        train_idx = np.concatenate([folds[j] for j in range(K) if j != k])

        M_subj = fit_matrix(S[train_idx], Subj[train_idx])
        M_obj = fit_matrix(S[train_idx], Obj[train_idx])

        preds_subj = S[test_idx] @ M_subj.T
        preds_obj = S[test_idx] @ M_obj.T
        preds_id = S[test_idx]  # identity

        correct_subj = list(test_idx)              # subj indices in all_words
        correct_obj = [i + n for i in test_idx]    # obj indices in all_words

        t_ss = top1_against_codebook(preds_subj, all_words, correct_subj)
        t_oo = top1_against_codebook(preds_obj, all_words, correct_obj)
        t_so = top1_against_codebook(preds_obj, all_words, correct_subj)  # wrong matrix for role
        t_os = top1_against_codebook(preds_subj, all_words, correct_obj)  # wrong matrix for role
        t_id_s = top1_against_codebook(preds_id, all_words, correct_subj)
        t_id_o = top1_against_codebook(preds_id, all_words, correct_obj)

        nt = len(test_idx)
        per_fold["subj_via_Msubj"].append(t_ss / nt)
        per_fold["obj_via_Mobj"].append(t_oo / nt)
        per_fold["subj_via_Mobj"].append(t_so / nt)
        per_fold["obj_via_Msubj"].append(t_os / nt)
        per_fold["subj_via_id"].append(t_id_s / nt)
        per_fold["obj_via_id"].append(t_id_o / nt)
        print(f"  fold {k}: n={nt:>2}  "
              f"subj@Msubj={t_ss}/{nt}  obj@Mobj={t_oo}/{nt}  "
              f"subj@Mobj={t_so}/{nt}  obj@Msubj={t_os}/{nt}  "
              f"subj@I={t_id_s}/{nt}  obj@I={t_id_o}/{nt}")

    print()
    print("5-fold CV aggregate top-1 accuracy (against 60-word codebook, chance=1.7%):")
    print(f"  SUBJECT via M_subject         : {np.mean(per_fold['subj_via_Msubj'])*100:5.1f}%")
    print(f"  OBJECT  via M_object          : {np.mean(per_fold['obj_via_Mobj'])*100:5.1f}%")
    print(f"  SUBJECT via M_object (wrong!) : {np.mean(per_fold['subj_via_Mobj'])*100:5.1f}%")
    print(f"  OBJECT  via M_subject (wrong!): {np.mean(per_fold['obj_via_Msubj'])*100:5.1f}%")
    print(f"  SUBJECT via identity          : {np.mean(per_fold['subj_via_id'])*100:5.1f}%")
    print(f"  OBJECT  via identity          : {np.mean(per_fold['obj_via_id'])*100:5.1f}%")

    # Are M_subj and M_obj actually different? Fit on all 30 and compare.
    M_subj_full = fit_matrix(S, Subj)
    M_obj_full = fit_matrix(S, Obj)
    fro_diff = np.linalg.norm(M_subj_full - M_obj_full)
    fro_subj = np.linalg.norm(M_subj_full)
    fro_obj = np.linalg.norm(M_obj_full)
    print()
    print("Structural comparison of M_subject and M_object (fit on all 30):")
    print(f"  ||M_subj||_F = {fro_subj:.3f}")
    print(f"  ||M_obj||_F  = {fro_obj:.3f}")
    print(f"  ||M_subj - M_obj||_F = {fro_diff:.3f}")
    print(f"  relative diff = {fro_diff / (0.5 * (fro_subj + fro_obj)):.3f}")

    # Are they both near identity?
    I = np.eye(d)
    print(f"  ||M_subj - I||_F = {np.linalg.norm(M_subj_full - I):.3f}")
    print(f"  ||M_obj  - I||_F = {np.linalg.norm(M_obj_full - I):.3f}")
    print(f"  ||I||_F          = {np.linalg.norm(I):.3f}  (sqrt(d) = {np.sqrt(d):.3f})")

    return 0


if __name__ == "__main__":
    sys.exit(main())
