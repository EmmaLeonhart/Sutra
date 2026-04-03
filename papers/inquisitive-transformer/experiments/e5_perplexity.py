"""Experiment 5: Perplexity-based evaluation (forward and backward).

Question: Does alpha change how "surprised" the model is by violation passages?

Instead of multiple-choice accuracy, we measure perplexity directly:
- Forward perplexity: standard left-to-right perplexity on CVD passages
- Backward perplexity: perplexity on token-reversed passages

Hypothesis: If alpha modulates sensitivity to anomalies, positive alpha should
increase perplexity on passages containing violations (the model "notices" them).
Backward perplexity tests whether the effect depends on causal ordering —
reversing the text changes when the violation is encountered relative to context.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import torch
from transformers import GPT2Tokenizer

from experiments.common import get_base_parser, load_model, ALPHA_SWEEP
from src.benchmark.cvd_dataset import get_dataset, CATEGORIES


def compute_perplexity(model, tokenizer, text: str, device: str) -> float:
    """Compute perplexity of text under the model."""
    inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=1024).to(device)
    input_ids = inputs["input_ids"]

    if input_ids.shape[1] < 2:
        return float("nan")

    with torch.no_grad():
        outputs = model(input_ids, labels=input_ids)
        return torch.exp(outputs.loss).item()


def compute_backward_perplexity(model, tokenizer, text: str, device: str) -> float:
    """Compute perplexity on token-reversed text.

    Reverses the token sequence so the model processes the passage backwards.
    This changes when the violation is encountered relative to its context —
    a violation at the end of the forward text appears at the start in reverse.
    """
    token_ids = tokenizer.encode(text, add_special_tokens=False)

    if len(token_ids) < 2:
        return float("nan")

    # Reverse the token order
    reversed_ids = list(reversed(token_ids))
    input_ids = torch.tensor([reversed_ids], device=device)

    with torch.no_grad():
        outputs = model(input_ids, labels=input_ids)
        return torch.exp(outputs.loss).item()


def main():
    parser = get_base_parser("E5: Perplexity evaluation (forward + backward)")
    args = parser.parse_args()

    model = load_model(args)
    tokenizer = model.tokenizer
    device = model.device
    dataset = get_dataset()

    output_path = Path(args.output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 60)
    print("EXPERIMENT 5: Perplexity (Forward + Backward)")
    print("Measuring how alpha affects model surprise on CVD passages.")
    print("=" * 60)

    all_results = []

    for alpha in args.alphas:
        model.set_alpha(alpha)

        print(f"\n{'='*60}")
        print(f"[e5_perplexity] alpha={alpha:+.2f}")
        print(f"  Layer alphas: {model.get_alphas()}")

        start = time.time()

        item_results = []
        fwd_ppls = []
        bwd_ppls = []

        for item in dataset:
            passage = item["passage"]

            fwd_ppl = compute_perplexity(model.model, tokenizer, passage, device)
            bwd_ppl = compute_backward_perplexity(model.model, tokenizer, passage, device)

            ratio = bwd_ppl / fwd_ppl if fwd_ppl > 0 else float("nan")

            item_results.append({
                "category": item["category"],
                "violation_hint": item["violation_hint"],
                "forward_perplexity": fwd_ppl,
                "backward_perplexity": bwd_ppl,
                "bwd_fwd_ratio": ratio,
                "passage_length": len(tokenizer.encode(passage)),
            })

            fwd_ppls.append(fwd_ppl)
            bwd_ppls.append(bwd_ppl)

        elapsed = time.time() - start

        # Aggregate by category
        cat_stats = {}
        for cat in CATEGORIES:
            cat_items = [r for r in item_results if r["category"] == cat]
            if cat_items:
                cat_fwd = [r["forward_perplexity"] for r in cat_items]
                cat_bwd = [r["backward_perplexity"] for r in cat_items]
                cat_stats[cat] = {
                    "mean_forward_ppl": sum(cat_fwd) / len(cat_fwd),
                    "mean_backward_ppl": sum(cat_bwd) / len(cat_bwd),
                    "mean_ratio": sum(r["bwd_fwd_ratio"] for r in cat_items) / len(cat_items),
                }

        mean_fwd = sum(fwd_ppls) / len(fwd_ppls)
        mean_bwd = sum(bwd_ppls) / len(bwd_ppls)

        result = {
            "alpha": alpha,
            "mean_forward_perplexity": mean_fwd,
            "mean_backward_perplexity": mean_bwd,
            "mean_bwd_fwd_ratio": mean_bwd / mean_fwd if mean_fwd > 0 else float("nan"),
            "by_category": cat_stats,
            "items": item_results,
        }
        all_results.append(result)

        print(f"  Forward PPL:  {mean_fwd:.2f}")
        print(f"  Backward PPL: {mean_bwd:.2f}")
        print(f"  Bwd/Fwd ratio: {mean_bwd / mean_fwd:.3f}")
        print(f"  ({elapsed:.1f}s)")
        for cat, stats in cat_stats.items():
            print(f"    {cat}: fwd={stats['mean_forward_ppl']:.2f}  bwd={stats['mean_backward_ppl']:.2f}  ratio={stats['mean_ratio']:.3f}")

    # Summary table
    print(f"\n\n{'='*60}")
    print("E5 SUMMARY: Perplexity across alpha sweep")
    print(f"{'='*60}")
    print(f"  {'alpha':>6}  {'Fwd PPL':>10}  {'Bwd PPL':>10}  {'Ratio':>8}")
    print(f"  {'-'*6}  {'-'*10}  {'-'*10}  {'-'*8}")
    for r in all_results:
        print(f"  {r['alpha']:+6.2f}  {r['mean_forward_perplexity']:10.2f}  {r['mean_backward_perplexity']:10.2f}  {r['mean_bwd_fwd_ratio']:8.3f}")

    # Per-category summary
    print(f"\n  Per-category forward perplexity:")
    print(f"  {'alpha':>6}", end="")
    for cat in CATEGORIES:
        print(f"  {cat[:12]:>12}", end="")
    print()
    for r in all_results:
        print(f"  {r['alpha']:+6.2f}", end="")
        for cat in CATEGORIES:
            if cat in r["by_category"]:
                print(f"  {r['by_category'][cat]['mean_forward_ppl']:12.2f}", end="")
        print()

    print(f"\n  Per-category backward perplexity:")
    print(f"  {'alpha':>6}", end="")
    for cat in CATEGORIES:
        print(f"  {cat[:12]:>12}", end="")
    print()
    for r in all_results:
        print(f"  {r['alpha']:+6.2f}", end="")
        for cat in CATEGORIES:
            if cat in r["by_category"]:
                print(f"  {r['by_category'][cat]['mean_backward_ppl']:12.2f}", end="")
        print()

    # Save full results
    with open(output_path / "e5_perplexity_full.json", "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2)

    # Save summary CSV
    import csv
    with open(output_path / "e5_perplexity_summary.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        header = ["alpha", "mean_fwd_ppl", "mean_bwd_ppl", "bwd_fwd_ratio"]
        for cat in CATEGORIES:
            header.extend([f"fwd_{cat[:8]}", f"bwd_{cat[:8]}"])
        writer.writerow(header)
        for r in all_results:
            row = [r["alpha"], f"{r['mean_forward_perplexity']:.4f}",
                   f"{r['mean_backward_perplexity']:.4f}", f"{r['mean_bwd_fwd_ratio']:.4f}"]
            for cat in CATEGORIES:
                if cat in r["by_category"]:
                    row.append(f"{r['by_category'][cat]['mean_forward_ppl']:.4f}")
                    row.append(f"{r['by_category'][cat]['mean_backward_ppl']:.4f}")
            writer.writerow(row)

    print(f"\nResults saved to {output_path / 'e5_perplexity_*'}")


if __name__ == "__main__":
    main()
