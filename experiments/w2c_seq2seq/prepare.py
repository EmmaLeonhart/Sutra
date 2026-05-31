"""Weight→code seq2seq data prep (Emma 2026-05-30 AskUserQuestion: source generation).

Turns the template weights↔code corpus into (input, target) pairs for a
model that GENERATES `.su` source from a program's weights + IO.

Two design calls that make the task real rather than a leak:

1. **Source normalization.** Each program references its weights via
   `load_matrix("<csv>")`, and that CSV filename encodes the answer
   (`linear_K4_gaussian_s0_M0.csv` literally names structure/K/kind/seed).
   A model that had to *reproduce* that filename would either be cheating
   (the answer is in the target it generates) or doomed (it can't know the
   per-program filename from weights alone). So we normalize the target:
   `load_matrix("<csv>")` → `load_matrix("<weight name>")`, e.g.
   `load_matrix("M0")`. The target becomes the program STRUCTURE plus
   canonical weight references; the actual weight VALUES are supplied
   separately as the model input. Eval re-substitutes the real CSV to
   compile + run on the substrate.

2. **Split by program id.** Held-out programs share no id with train, so
   "decompilation accuracy" measures generalization, not memorization.

This is host-side data prep over the corpus — analysis/training scaffolding,
NOT a Sutra substrate op (no embeddings, no substrate calls here; the
substrate enters only at the eval tick, on GENERATED source).

Output (under --out, default experiments/w2c_seq2seq/data/):
  train.jsonl / val.jsonl  — one record per program:
    {id, structure, K, weight_kind, target (normalized source),
     target_ids (BOS..EOS char ids), weights (loaded CSV values per matrix),
     io (input/output pairs)}
  vocab.json  — {char: id} including specials PAD/BOS/EOS.

Verifiable by experiments/w2c_seq2seq/test_prepare.py: tokenizer round-trips
(decode(encode(s)) == s) on every target, train/val ids are disjoint, the
vocab covers every target character, and the normalized target no longer
contains any raw `.csv` filename.
"""
from __future__ import annotations

import argparse
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
DEFAULT_CORPUS = os.path.join(REPO, "corpus")
DEFAULT_OUT = os.path.join(HERE, "data")

PAD, BOS, EOS = "\x00", "\x02", "\x03"  # specials (not used by Sutra source text)

# Discrete coefficient classes — must match weight_to_code_corpus.COEFFS. Used
# for the coefficient-head diagnostic (tick-3 follow-up #2): each coeff-family
# program carries `coeffs` {a, b}; we propagate them as class indices so the
# model can train an auxiliary head that predicts the coefficient from the
# encoder rep. -1 = slot absent for this program's family.
COEFF_CLASSES = [0.5, 1.0, 1.5, 2.0, 3.0]


def _coeff_class(value) -> int:
    """Map a coefficient value to its class index, or -1 if not a known class."""
    for i, c in enumerate(COEFF_CLASSES):
        if abs(float(value) - c) < 1e-9:
            return i
    return -1


def normalize_source(entry: dict) -> str:
    """Replace each per-program `load_matrix("<csv>")` with the canonical
    `load_matrix("<weight name>")`. Canonicalizes the unguessable filename
    (which encodes the answer) into a stable handle to the i-th weight."""
    src = entry["source"]
    for w in entry.get("weights", []):
        csv = w.get("csv")
        if csv:
            src = src.replace(f'load_matrix("{csv}")', f'load_matrix("{w["name"]}")')
    return src


def build_vocab(targets: list[str]) -> dict[str, int]:
    chars = set()
    for t in targets:
        chars.update(t)
    # specials first (stable ids), then sorted source chars
    vocab = {PAD: 0, BOS: 1, EOS: 2}
    for c in sorted(chars):
        if c not in vocab:
            vocab[c] = len(vocab)
    return vocab


def encode(target: str, vocab: dict[str, int]) -> list[int]:
    return [vocab[BOS]] + [vocab[c] for c in target] + [vocab[EOS]]


def decode(ids: list[int], vocab: dict[str, int]) -> str:
    inv = {i: c for c, i in vocab.items()}
    out = []
    for i in ids:
        c = inv[i]
        if c in (PAD, BOS, EOS):
            continue
        out.append(c)
    return "".join(out)


def _load_weights(entry: dict, corpus_dir: str) -> list[list[list[float]]]:
    """Load the actual matrix values for each of the program's weights."""
    mats = []
    for w in entry.get("weights", []):
        csv = w.get("csv")
        if not csv:
            continue
        path = os.path.join(corpus_dir, csv)
        rows = []
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    rows.append([float(x) for x in line.split(",")])
        mats.append(rows)
    return mats


def is_val(pid: str) -> bool:
    """Deterministic ~10% held-out split by program id (no host randomness)."""
    h = 0
    for ch in pid:
        h = (h * 131 + ord(ch)) & 0xFFFFFFFF
    return h % 10 == 0


def prepare(corpus_dir: str, out_dir: str, include_gemma: bool = False) -> dict:
    paths = [os.path.join(corpus_dir, "corpus.jsonl")]
    if include_gemma:
        g = os.path.join(corpus_dir, "gemma_corpus.jsonl")
        if os.path.isfile(g):
            paths.append(g)

    entries = []
    for p in paths:
        if not os.path.isfile(p):
            continue
        with open(p, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
    if not entries:
        raise SystemExit(f"no corpus entries found under {corpus_dir}")

    targets = [normalize_source(e) for e in entries]
    vocab = build_vocab(targets)

    os.makedirs(out_dir, exist_ok=True)
    counts = {"train": 0, "val": 0}
    fhs = {
        "train": open(os.path.join(out_dir, "train.jsonl"), "w", encoding="utf-8"),
        "val": open(os.path.join(out_dir, "val.jsonl"), "w", encoding="utf-8"),
    }
    try:
        for e, tgt in zip(entries, targets):
            pid = e["id"]
            cv = e.get("coeffs") or {}
            rec = {
                "id": pid,
                "structure": e.get("structure"),
                "K": e.get("K"),
                "weight_kind": e.get("weight_kind"),
                "target": tgt,
                "target_ids": encode(tgt, vocab),
                "weights": _load_weights(e, corpus_dir),
                "io": e.get("io", []),
                # coeff-head labels (-1 = slot absent for this family)
                "coeff_a": _coeff_class(cv["a"]) if "a" in cv else -1,
                "coeff_b": _coeff_class(cv["b"]) if "b" in cv else -1,
            }
            split = "val" if is_val(pid) else "train"
            fhs[split].write(json.dumps(rec) + "\n")
            counts[split] += 1
    finally:
        for fh in fhs.values():
            fh.close()

    with open(os.path.join(out_dir, "vocab.json"), "w", encoding="utf-8") as f:
        json.dump(vocab, f, ensure_ascii=True, indent=0)

    stats = {
        "entries": len(entries),
        "train": counts["train"],
        "val": counts["val"],
        "vocab_size": len(vocab),
        "max_target_len": max(len(t) for t in targets),
        "out_dir": out_dir,
    }
    return stats


def main() -> None:
    import io as _io
    import sys

    sys.stdout = _io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corpus", default=DEFAULT_CORPUS)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--include-gemma", action="store_true",
                    help="also include gemma_corpus.jsonl (inline-weight regime; off by default)")
    args = ap.parse_args()
    stats = prepare(args.corpus, args.out, include_gemma=args.include_gemma)
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
