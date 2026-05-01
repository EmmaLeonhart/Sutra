"""End-to-end differentiable training through Sutra's tensor-op graph.

Demonstrates that gradient descent can optimize parameters through
the exact operations the Sutra compiler emits to tensor normal form:
cosine similarity, Lagrange-interpolated fuzzy AND/OR/NOT polynomials,
scalar-vector multiply, and bundle (vector addition).

Task: 3-category word classification (animals / vehicles / foods)
using fuzzy if-then rules with learnable prototype embeddings.
Every operation in the forward pass is a Sutra primitive; every
primitive is differentiable.

Architecture:
  input word embedding (frozen, via Ollama)
    -> cosine similarity to each learnable prototype
    -> fuzzy AND/OR/NOT gates (Lagrange polynomials, C^inf)
    -> classification scores
    -> softmax cross-entropy loss
    -> backprop updates prototype embeddings

Called by: standalone experiment for the paper (Section 3.2).

Usage:
    py experiments/differentiable_training.py

Requires: torch, ollama (with nomic-embed-text model pulled)
Outputs:  experiments/differentiable_training_results.json
"""

from __future__ import annotations

import json
import os
import sys
import torch
import torch.nn.functional as F


# ---------------------------------------------------------------------------
# Sutra fuzzy-logic primitives — exact match to codegen_pytorch.py
# ---------------------------------------------------------------------------
# These are the Lagrange-interpolated polynomials that the Sutra compiler
# emits for Kleene three-valued logic gates. They are exact on the
# {-1, 0, +1}^2 grid and C^inf everywhere — no branches, no clamps,
# pure polynomial tensor ops.

def fuzzy_and(a: torch.Tensor, b: torch.Tensor) -> torch.Tensor:
    """Lagrange-interpolated min — exact on {-1, 0, +1}^2.

    Same polynomial as codegen_pytorch.py (lines 963-964):
      min(a, b) = (a + b + ab - a^2 - b^2 + a^2 b^2) / 2
    """
    return (a + b + a * b - a**2 - b**2 + a**2 * b**2) / 2


def fuzzy_or(a: torch.Tensor, b: torch.Tensor) -> torch.Tensor:
    """Lagrange-interpolated max — exact on {-1, 0, +1}^2.

    Same polynomial as codegen_pytorch.py (lines 965-966):
      max(a, b) = (a + b - ab + a^2 + b^2 - a^2 b^2) / 2
    """
    return (a + b - a * b + a**2 + b**2 - a**2 * b**2) / 2


def fuzzy_not(a: torch.Tensor) -> torch.Tensor:
    """Kleene strong negation: NOT(a) = -a."""
    return -a


# ---------------------------------------------------------------------------
# Embedding helpers — same pipeline as _TorchVSA.embed() / embed_batch()
# ---------------------------------------------------------------------------

def embed_all(
    words: list[str],
    model: str = "nomic-embed-text",
    cache_path: str | None = None,
) -> dict[str, torch.Tensor]:
    """Embed words via Ollama, mean-center, L2-normalize.

    Caches to a .pt file so the experiment can re-run without Ollama.
    Semantic-only vectors (no synthetic block) — the fuzzy logic
    operates on scalar truth values from cosine similarity, not on
    the synthetic axis directly.
    """
    if cache_path and os.path.exists(cache_path):
        cached = torch.load(cache_path, map_location="cpu", weights_only=True)
        # If all words are cached, return them
        if all(w in cached for w in words):
            return cached

    import ollama as _ollama

    r = _ollama.embed(model=model, input=words)
    vecs: dict[str, torch.Tensor] = {}
    for word, emb in zip(words, r["embeddings"]):
        v = torch.tensor(emb, dtype=torch.float32)
        v = v - v.mean()
        n = v.norm()
        if n > 0:
            v = v / n
        vecs[word] = v

    if cache_path:
        torch.save(vecs, cache_path)
    return vecs


# ---------------------------------------------------------------------------
# Training data
# ---------------------------------------------------------------------------

CATEGORIES = [
    ("animal",  ["dog", "cat", "bird", "fish", "horse"]),
    ("vehicle", ["car", "truck", "airplane", "boat", "bicycle"]),
    ("food",    ["apple", "bread", "cheese", "rice", "pasta"]),
]


# ---------------------------------------------------------------------------
# Forward pass — fuzzy rule-based classifier using Sutra operations
# ---------------------------------------------------------------------------

def classify(
    x: torch.Tensor,
    prototypes: list[torch.Tensor],
    temperature: float = 10.0,
) -> torch.Tensor:
    """Classify an input embedding using fuzzy if-then rules.

    For each class i, computes the fuzzy rule:

        sim_i   = cosine(x, prototype_i)
        rule_i  = AND(sim_i, AND(NOT(sim_j), NOT(sim_k)))

    where j, k are the other classes. This is the Sutra equivalent
    of:

        if (similar_to(x, proto_i)
            && !similar_to(x, proto_j)
            && !similar_to(x, proto_k)) -> class i

    except that every gate is a differentiable Lagrange polynomial
    and all three rules execute simultaneously (no branching).

    Returns logits (K,) — fuzzy rule scores * temperature.
    """
    K = len(prototypes)

    # Cosine similarity to each prototype (Sutra's similarity() op)
    sims = []
    for p in prototypes:
        s = torch.dot(x, p) / (x.norm() * p.norm() + 1e-12)
        sims.append(s)

    # Fuzzy classification rules using AND/NOT
    rules = []
    for i in range(K):
        others = [j for j in range(K) if j != i]
        # NOT similar to the other two classes
        neg_others = fuzzy_and(
            fuzzy_not(sims[others[0]]),
            fuzzy_not(sims[others[1]]),
        )
        # AND: similar to this class AND not similar to others
        rule = fuzzy_and(sims[i], neg_others)
        rules.append(rule)

    return torch.stack(rules) * temperature


def evaluate(
    data: list[tuple[torch.Tensor, int]],
    prototypes: list[torch.Tensor],
) -> float:
    """Evaluate classification accuracy (no grad)."""
    correct = 0
    for x, label in data:
        with torch.no_grad():
            logits = classify(x, prototypes)
            if logits.argmax().item() == label:
                correct += 1
    return correct / len(data)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 60)
    print("Sutra: End-to-end differentiable training")
    print("Backpropagation through Lagrange fuzzy-logic gates")
    print("=" * 60)
    print()

    # ---- Step 1: Embed all training words ----
    all_words = [w for _, words in CATEGORIES for w in words]
    cache_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        ".diff_train_embeddings.pt",
    )
    print("Step 1: Embedding training data via Ollama (nomic-embed-text)...")
    vecs = embed_all(all_words, cache_path=cache_path)
    dim = next(iter(vecs.values())).shape[0]
    print(f"  {len(vecs)} words embedded, dim={dim}")
    print()

    # ---- Step 2: Build dataset ----
    data: list[tuple[torch.Tensor, int]] = []
    for cat_idx, (_, words) in enumerate(CATEGORIES):
        for w in words:
            data.append((vecs[w], cat_idx))

    # True category centroids (for measuring prototype convergence)
    centroids = []
    for _, words in CATEGORIES:
        c = torch.stack([vecs[w] for w in words]).mean(0)
        c = c / (c.norm() + 1e-12)
        centroids.append(c)

    # ---- Step 3: Initialize learnable prototypes ----
    torch.manual_seed(42)
    prototypes = []
    for _ in range(len(CATEGORIES)):
        p = torch.randn(dim)
        p = p / p.norm()
        p = p.clone().requires_grad_(True)
        prototypes.append(p)

    # ---- Step 4: Evaluate BEFORE training ----
    acc_before = evaluate(data, prototypes)
    cos_before = [
        round(torch.dot(prototypes[i].detach(), centroids[i]).item(), 4)
        for i in range(len(CATEGORIES))
    ]
    print(f"Step 2: Accuracy BEFORE training: {acc_before:.0%} "
          f"(chance = {1/len(CATEGORIES):.0%})")
    print(f"  Proto<->centroid cosine: {cos_before}")
    print()

    # ---- Step 5: Train ----
    optimizer = torch.optim.Adam(prototypes, lr=0.005)
    epochs = 300
    history: list[dict] = []

    print(f"Step 3: Training ({epochs} epochs, Adam lr=0.005)...")
    for epoch in range(epochs):
        total_loss = 0.0
        correct = 0

        for x, label in data:
            optimizer.zero_grad()
            logits = classify(x, prototypes)
            loss = F.cross_entropy(
                logits.unsqueeze(0), torch.tensor([label])
            )
            loss.backward()
            optimizer.step()

            total_loss += loss.item()
            if logits.argmax().item() == label:
                correct += 1

        acc = correct / len(data)
        avg_loss = total_loss / len(data)
        history.append({
            "epoch": epoch,
            "loss": round(avg_loss, 6),
            "accuracy": round(acc, 4),
        })

        if epoch % 50 == 0 or epoch == epochs - 1:
            cos = [
                f"{torch.dot(prototypes[i].detach(), centroids[i]).item():.3f}"
                for i in range(len(CATEGORIES))
            ]
            print(f"  epoch {epoch:3d}: loss={avg_loss:.4f}  "
                  f"acc={acc:.0%}  proto<->centroid={cos}")

    # ---- Step 6: Evaluate AFTER training ----
    acc_after = evaluate(data, prototypes)
    cos_after = [
        round(torch.dot(prototypes[i].detach(), centroids[i]).item(), 4)
        for i in range(len(CATEGORIES))
    ]
    print()
    print(f"Step 4: Accuracy AFTER training: {acc_after:.0%}")
    print(f"  Proto↔centroid cosine: {cos_after}")
    print(f"  Improvement: {acc_before:.0%} -> {acc_after:.0%}")
    print()

    # ---- Step 7: Gradient flow verification ----
    print("Step 5: Gradient flow verification")
    print("  (nonzero gradient => backprop reaches the parameter)")
    grad_norms = {}
    for i, (cat_name, _) in enumerate(CATEGORIES):
        optimizer.zero_grad()
        x, label = data[i * 5]  # first word from this category
        logits = classify(x, prototypes)
        loss = F.cross_entropy(
            logits.unsqueeze(0), torch.tensor([label])
        )
        loss.backward()
        gn = prototypes[i].grad.norm().item()
        grad_norms[cat_name] = round(gn, 8)
        ok = "nonzero" if gn > 0 else "ZERO — gradient blocked!"
        print(f"  d(loss)/d(proto_{cat_name}) norm = {gn:.6f}  ({ok})")

    # ---- Step 8: Save results ----
    results = {
        "experiment": "end-to-end differentiable training through Sutra ops",
        "task": "3-category word classification (animals / vehicles / foods)",
        "sutra_operations_in_forward_pass": [
            "cosine_similarity (torch.dot / norm — Sutra's similarity())",
            "fuzzy_and (Lagrange min polynomial — Sutra's && operator)",
            "fuzzy_not (Kleene negation — Sutra's ! operator)",
            "scalar * temperature (element-wise — Sutra's scalar multiply)",
            "cross_entropy (softmax + NLL over fuzzy rule scores)",
        ],
        "embedding_model": "nomic-embed-text",
        "embedding_dim": dim,
        "training_words": len(data),
        "categories": [name for name, _ in CATEGORIES],
        "epochs": epochs,
        "accuracy_before": acc_before,
        "accuracy_after": acc_after,
        "proto_centroid_cosine_before": {
            name: cos_before[i]
            for i, (name, _) in enumerate(CATEGORIES)
        },
        "proto_centroid_cosine_after": {
            name: cos_after[i]
            for i, (name, _) in enumerate(CATEGORIES)
        },
        "gradient_norms": grad_norms,
        "history": history,
    }

    out_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "differentiable_training_results.json",
    )
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print()
    print(f"Results saved to {out_path}")

    # Save trained weights (prototype tensors + input embeddings)
    weights_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "differentiable_training_weights.pt",
    )
    torch.save({
        "prototypes": {
            name: prototypes[i].detach().cpu()
            for i, (name, _) in enumerate(CATEGORIES)
        },
        "centroids": {
            name: centroids[i].cpu()
            for i, (name, _) in enumerate(CATEGORIES)
        },
        "embeddings": {k: v.cpu() for k, v in vecs.items()},
    }, weights_path)
    print(f"Trained weights saved to {weights_path}")

    # ---- Assertions for SKILL.md reproduction ----
    assert acc_after > acc_before, (
        f"Training did not improve accuracy: {acc_before} -> {acc_after}"
    )
    assert all(g > 0 for g in grad_norms.values()), (
        f"Gradient blocked for some prototypes: {grad_norms}"
    )
    print("\nAll assertions passed.")


if __name__ == "__main__":
    main()
