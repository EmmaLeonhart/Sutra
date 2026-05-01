"""Rotation binding capacity on bioinformatics embeddings (ESM-2 protein LM).

Why this experiment exists:
    Sutra's substrate-purity story is that the runtime works on
    *any* dense vector embedding, not just frozen LLM text
    embeddings. The §3.1 capacity tables in the paper run on three
    LLM substrates (nomic-embed-text, all-minilm, mxbai-embed-large)
    — that demonstrates the claim within one modality. To
    demonstrate substrate-agnosticism across modalities, we run the
    *same* rotation-binding capacity test on protein embeddings
    produced by ESM-2 (Lin et al., Science 2023), Meta's protein
    language model.

What this experiment measures:
    Same protocol as `rotation_binding_capacity_llm.py`. We embed a
    fixed vocabulary of 84 short amino-acid sequences with ESM-2's
    smallest variant (`facebook/esm2_t6_8M_UR50D`, 320-d hidden
    state, ~30MB, runs on CPU). We mean-pool over residue positions
    to produce a fixed-dimension sequence embedding. We then sweep
    bundle width k in {2, 4, 8, 16, 24, 32, 48} and compare rotation
    binding (Haar-orthogonal R_role @ filler) against Hadamard
    binding (role .* filler) head-to-head, exactly as in §3.1.

    The vocabulary is a deterministic 84-sequence sample of canonical
    short peptides + random valid 10-residue k-mers. Protein
    embedding spaces are anisotropic in their own way (driven by
    amino-acid composition + residue context), and like LLM text
    embeddings they cluster on the unit sphere. The point of the
    experiment is to confirm that the *shape* of the rotation-vs-
    Hadamard tradeoff carries over: rotation degrades gracefully,
    Hadamard collapses fast.

Reproducible: seeded RNG, fixed vocabulary, ESM-2 weights are
deterministic for a given input.

Usage:
    pip install transformers torch
    python experiments/rotation_binding_capacity_bioinformatics.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

# ---------------------------------------------------------------------
# Vocabulary: 84 short amino-acid sequences spanning canonical
# motifs + deterministic k-mers so the codebook has biological
# diversity rather than clumping in one cluster.
# ---------------------------------------------------------------------

# Canonical short peptides (signal peptides, antimicrobial peptides,
# cell-penetrating peptides, classic motifs). All <= 30 residues.
CANONICAL_PEPTIDES = [
    # Signal peptides
    "MKWVTFISLLFLFSSAYS",       # bovine serum albumin signal
    "MKQSTIALALLPLLFTPVTKA",    # E. coli OmpA signal
    "MKLKLLFTSALCFSLLTAVPVQA",  # E. coli MalE signal
    "MKKTAIAIAVALAGFATVAQA",    # E. coli PhoA signal
    # Cell-penetrating peptides
    "GRKKRRQRRRPQ",             # HIV TAT(48-60)
    "RQIKIWFQNRRMKWKK",         # Penetratin
    "KETWWETWWTEWSQPKKKRKV",    # Pep-1
    "RRRRRRRRRR",               # Polyarginine R10
    # Antimicrobial peptides
    "GIGKFLHSAKKFGKAFVGEIMNS",  # Magainin II
    "FLPLIGRVLSGIL",            # Cecropin
    "ILPWKWPWWPWRR",            # Indolicidin
    "KWKLFKKIEKVGQNVRDGIIKAGPAVAVVGQATQIAK",  # Buforin
    # Classic motifs / reporter tags
    "DYKDDDDK",                 # FLAG tag
    "EQKLISEEDL",               # c-myc tag
    "YPYDVPDYA",                # HA tag
    "WSHPQFEK",                 # Strep-tag II
    "HHHHHH",                   # His6 tag
    "GGGGS",                    # GS linker
    # Canonical short bioactive peptides
    "YGGFM",                    # Met-enkephalin
    "YGGFL",                    # Leu-enkephalin
    "RPKPQQFFGLM",              # Substance P
    "CYIQNCPLG",                # Oxytocin (linear)
    "CYFQNCPRG",                # Vasopressin (linear)
    "QRLGNQWAVGHLM",            # Bombesin
    # Disulfide loops (linear forms shown)
    "GIVEQCCTSICSLYQLENYCN",    # Insulin A-chain (human)
    "FVNQHLCGSHLVEALYLVCGERGFFYTPKT",  # Insulin B-chain (human)
    # Histone tail residues (well-characterized PTM substrates)
    "ARTKQTARKSTGGKAPRKQL",     # H3 1-20
    "SGRGKGGKGLGKGGAKRHRK",     # H4 1-20
    # Beta-amyloid / disease-related
    "DAEFRHDSGYEVHHQK",         # Aβ 1-16
    "GSNKGAIIGLM",              # Aβ 29-39
    # Ribosome binding / SD-like (translated)
    "MAGGKAGKDSGKAKAKAVSRSQ",
]


def _generate_kmers(n: int, length: int, seed: int = 1729) -> list[str]:
    """Deterministic random valid amino-acid k-mers."""
    aa = list("ACDEFGHIKLMNPQRSTVWY")
    rng = np.random.default_rng(seed)
    seqs = []
    for _ in range(n):
        seqs.append("".join(rng.choice(aa, size=length)))
    return seqs


# Pad to 84 with random k-mers (80% length 12, 20% length 20 for diversity).
_TARGET_VOCAB_SIZE = 84
_remaining = _TARGET_VOCAB_SIZE - len(CANONICAL_PEPTIDES)
_KMER_12 = _generate_kmers(int(_remaining * 0.8), length=12, seed=1729)
_KMER_20 = _generate_kmers(_remaining - len(_KMER_12), length=20, seed=2718)

VOCAB = sorted(set(CANONICAL_PEPTIDES + _KMER_12 + _KMER_20))[:_TARGET_VOCAB_SIZE]

ESM2_MODEL_NAME = "facebook/esm2_t6_8M_UR50D"  # smallest ESM-2 (~30MB), 320-d
EXPECTED_DIM = 320

BUNDLE_WIDTHS = [2, 4, 8, 16, 24, 32, 48]
TRIALS_PER_K = 10
SEED = 42


# ---------------------------------------------------------------------
# ESM-2 embedding helper
# ---------------------------------------------------------------------

CACHE_DIR = Path(__file__).parent / "_embedding_cache"


def build_codebook_esm2() -> tuple[np.ndarray, list[str]]:
    """Embed the protein vocabulary with ESM-2 (smallest variant).
    Mean-pools residue-level representations into one vector per
    sequence. Disk-caches per (model, vocab_hash)."""
    import hashlib
    CACHE_DIR.mkdir(exist_ok=True)
    vocab_hash = hashlib.sha256("\n".join(VOCAB).encode()).hexdigest()[:16]
    cache_key = f"esm2-t6-8m_{vocab_hash}.npz"
    cache_path = CACHE_DIR / cache_key

    if cache_path.exists():
        print(f"  cache hit: {cache_path.name}")
        z = np.load(cache_path)
        cb = z["cb"]
    else:
        print(f"  embedding {len(VOCAB)} protein sequences via {ESM2_MODEL_NAME} "
              f"(no cache, ~30MB model download on first call)...")
        t0 = time.monotonic()
        import torch
        from transformers import AutoTokenizer, AutoModel
        tokenizer = AutoTokenizer.from_pretrained(ESM2_MODEL_NAME)
        model = AutoModel.from_pretrained(ESM2_MODEL_NAME)
        model.eval()
        rows = []
        with torch.no_grad():
            for i, seq in enumerate(VOCAB):
                # Tokenize, run, mean-pool over residue positions
                # (excluding the [CLS] / [EOS] special tokens).
                tok = tokenizer(seq, return_tensors="pt")
                out = model(**tok).last_hidden_state[0]  # (L, D)
                # Strip special tokens (ESM uses <cls> at 0 and <eos> at L-1)
                if out.shape[0] > 2:
                    out = out[1:-1]
                vec = out.mean(dim=0).cpu().numpy().astype(np.float64)
                rows.append(vec)
                if (i + 1) % 20 == 0:
                    print(f"    {i+1}/{len(VOCAB)}  "
                          f"({time.monotonic()-t0:.0f}s elapsed)")
        cb = np.stack(rows, axis=0)
        np.savez(cache_path, cb=cb)
        print(f"  done in {time.monotonic() - t0:.1f}s, cached to "
              f"{cache_path.name}")

    if cb.shape[1] != EXPECTED_DIM:
        print(f"    WARNING: expected dim {EXPECTED_DIM}, got {cb.shape[1]}",
              file=sys.stderr)
    # Mean-center (same treatment we apply to nomic; pulls the cluster
    # off whatever bias direction ESM-2 has so binding sees the
    # filler-discriminative direction).
    cb = cb - cb.mean(axis=0, keepdims=True)
    cb /= np.linalg.norm(cb, axis=1, keepdims=True) + 1e-12
    print(f"  shape={cb.shape}")
    return cb, list(VOCAB)


# ---------------------------------------------------------------------
# Reuse the binding scheme code from the LLM capacity script.
# ---------------------------------------------------------------------

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from rotation_binding_capacity_llm import (  # noqa: E402
    haar_rotation,
    trial_rotation,
    trial_hadamard,
)


def main() -> int:
    print("=" * 78)
    print(f"Substrate: {ESM2_MODEL_NAME}  (expected dim {EXPECTED_DIM})")
    print("=" * 78)
    codebook, _vocab = build_codebook_esm2()
    n, actual_dim = codebook.shape

    results = {"substrate": ESM2_MODEL_NAME, "dim": actual_dim, "n_codebook": n,
               "rotation": {}, "hadamard": {}}

    print(f"\n{'k':>4}  {'rotation acc':>12}  {'rot signal':>10}  "
          f"{'hadamard acc':>12}  {'had signal':>10}")
    print("-" * 70)
    t0 = time.monotonic()
    for k in BUNDLE_WIDTHS:
        if k >= n:
            continue
        rot_accs, rot_sigs = [], []
        had_accs, had_sigs = [], []
        for t in range(TRIALS_PER_K):
            rng_r = np.random.default_rng(SEED + 1000 * t + k)
            rng_h = np.random.default_rng(SEED + 2000 * t + k)
            ra, rs, _ = trial_rotation(k, codebook, rng_r)
            ha, hs, _ = trial_hadamard(k, codebook, rng_h)
            rot_accs.append(ra); rot_sigs.append(rs)
            had_accs.append(ha); had_sigs.append(hs)
        rot_acc = float(np.mean(rot_accs))
        rot_sig = float(np.mean(rot_sigs))
        had_acc = float(np.mean(had_accs))
        had_sig = float(np.mean(had_sigs))
        results["rotation"][k] = {"accuracy": rot_acc, "signal_cos": rot_sig}
        results["hadamard"][k] = {"accuracy": had_acc, "signal_cos": had_sig}
        print(f"{k:>4}  {rot_acc:>11.1%}  {rot_sig:>+10.4f}  "
              f"{had_acc:>11.1%}  {had_sig:>+10.4f}")

    print(f"\nTotal time: {time.monotonic() - t0:.1f}s")

    out_path = HERE / "rotation_binding_capacity_bioinformatics_results.json"
    out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"Results written to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
