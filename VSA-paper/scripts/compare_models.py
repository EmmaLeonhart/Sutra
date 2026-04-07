"""
Compare FOL discovery results across multiple embedding models.

Reads fol_results.json from each model's data directory and produces:
1. Cross-model operation overlap (which operations found by all models)
2. Correlation between consistency scores across models
3. Comparison table for paper inclusion
4. Figures comparing model performance

Usage:
    python papers/fol-discovery/scripts/compare_models.py

Expects data directories:
    papers/fol-discovery/data/           (mxbai-embed-large, 1024-dim)
    papers/fol-discovery/data-nomic/     (nomic-embed-text, 768-dim)
    papers/fol-discovery/data-minilm/    (all-minilm, 384-dim)
"""

import io
import sys
import json
import os
from pathlib import Path
from collections import defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

BASE_DIR = Path(__file__).resolve().parent.parent
FIG_DIR = BASE_DIR / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)

# Model configurations
MODELS = {
    "mxbai-embed-large": {
        "data_dir": BASE_DIR / "data",
        "dim": 1024,
        "label": "mxbai-embed-large (1024d)",
        "color": "#2196F3",
    },
    "nomic-embed-text": {
        "data_dir": BASE_DIR / "data-nomic",
        "dim": 768,
        "label": "nomic-embed-text (768d)",
        "color": "#FF9800",
    },
    "all-minilm": {
        "data_dir": BASE_DIR / "data-minilm",
        "dim": 384,
        "label": "all-minilm (384d)",
        "color": "#4CAF50",
    },
}


def load_model_results(model_name, config):
    """Load FOL results for a model. Returns None if not available."""
    results_path = config["data_dir"] / "fol_results.json"
    if not results_path.exists():
        return None
    with open(str(results_path), encoding='utf-8') as f:
        return json.load(f)


def extract_operations(results, min_alignment=0.5):
    """Extract discovered operations as a dict keyed by predicate ID."""
    ops = {}
    for op in results.get('discovered_operations', []):
        if op['mean_alignment'] >= min_alignment:
            ops[op['predicate']] = {
                'label': op['label'],
                'alignment': op['mean_alignment'],
                'n_triples': op['n_triples'],
            }
    return ops


def main():
    print("=" * 70)
    print("CROSS-MODEL FOL DISCOVERY COMPARISON")
    print("=" * 70)

    # Load all available results
    model_results = {}
    model_ops = {}
    for name, config in MODELS.items():
        results = load_model_results(name, config)
        if results is not None:
            model_results[name] = results
            model_ops[name] = extract_operations(results)
            summary = results['summary']
            print(f"\n  {config['label']}:")
            print(f"    Embeddings: {summary['total_embeddings']}")
            print(f"    Predicates analyzed: {summary['predicates_analyzed']}")
            print(f"    Discovered (>0.5): {summary['strong_operations'] + summary['moderate_operations']}")
            print(f"    Strong (>0.7): {summary['strong_operations']}")
        else:
            print(f"\n  {config['label']}: NOT AVAILABLE (run pipeline first)")

    available = list(model_results.keys())
    if len(available) < 2:
        print(f"\nNeed at least 2 models to compare. Only {len(available)} available.")
        print("Run the pipeline for more models first.")
        return

    print(f"\n{'=' * 70}")
    print(f"COMPARING {len(available)} MODELS")
    print(f"{'=' * 70}")

    # Find overlap
    all_predicates = set()
    for ops in model_ops.values():
        all_predicates.update(ops.keys())

    # Classify each predicate
    found_in_all = set()
    found_in_some = set()
    found_in_one = set()

    for pred in all_predicates:
        count = sum(1 for ops in model_ops.values() if pred in ops)
        if count == len(available):
            found_in_all.add(pred)
        elif count > 1:
            found_in_some.add(pred)
        else:
            found_in_one.add(pred)

    print(f"\n  Predicates discovered by ALL {len(available)} models: {len(found_in_all)}")
    print(f"  Predicates discovered by some (2+): {len(found_in_some)}")
    print(f"  Predicates discovered by only 1: {len(found_in_one)}")

    # Show the universal operations
    if found_in_all:
        print(f"\n  UNIVERSAL OPERATIONS (found across all models):")
        print(f"  {'Predicate':<10} {'Label':<35}", end="")
        for name in available:
            print(f" {name[:12]:>12}", end="")
        print()
        print("  " + "-" * (50 + 13 * len(available)))

        # Sort by average alignment across models
        universal_ops = []
        for pred in found_in_all:
            avg_align = np.mean([model_ops[m][pred]['alignment'] for m in available])
            label = model_ops[available[0]][pred]['label']
            aligns = {m: model_ops[m][pred]['alignment'] for m in available}
            universal_ops.append((pred, label, avg_align, aligns))

        universal_ops.sort(key=lambda x: x[2], reverse=True)

        for pred, label, avg, aligns in universal_ops[:25]:
            label_trunc = label[:33] + '..' if len(label) > 35 else label
            print(f"  {pred:<10} {label_trunc:<35}", end="")
            for name in available:
                print(f" {aligns[name]:>12.3f}", end="")
            print()

    # Correlation between models
    print(f"\n  CROSS-MODEL CONSISTENCY CORRELATION:")
    shared_preds = set()
    for m1 in available:
        for m2 in available:
            shared_preds.update(model_ops[m1].keys() & model_ops[m2].keys())

    for i, m1 in enumerate(available):
        for m2 in available[i + 1:]:
            shared = model_ops[m1].keys() & model_ops[m2].keys()
            if len(shared) >= 5:
                a1 = [model_ops[m1][p]['alignment'] for p in shared]
                a2 = [model_ops[m2][p]['alignment'] for p in shared]
                corr = np.corrcoef(a1, a2)[0, 1]
                print(f"  {m1} vs {m2}: r = {corr:.3f} (n = {len(shared)} shared predicates)")

    # Failure consistency — do the same predicates fail everywhere?
    print(f"\n  FAILURE CONSISTENCY:")
    # Get predicates that fail (<0.3) in each model
    for name in available:
        all_ops = model_results[name].get('discovered_operations', [])
        failures = [o for o in all_ops if o['mean_alignment'] < 0.3]
        fail_preds = {o['predicate'] for o in failures}
        print(f"  {name}: {len(fail_preds)} predicates with alignment < 0.3")

    # Save comparison results
    comparison = {
        "models_compared": available,
        "model_details": {m: {"dim": MODELS[m]["dim"], "label": MODELS[m]["label"]} for m in available},
        "universal_operations": [
            {"predicate": pred, "label": label, "avg_alignment": round(avg, 4),
             "per_model": {m: round(a, 4) for m, a in aligns.items()}}
            for pred, label, avg, aligns in universal_ops
        ] if found_in_all else [],
        "overlap_counts": {
            "found_in_all": len(found_in_all),
            "found_in_some": len(found_in_some),
            "found_in_one": len(found_in_one),
            "total_unique": len(all_predicates),
        },
        "per_model_summary": {
            m: {
                "total_discovered": len(model_ops[m]),
                "strong": sum(1 for o in model_ops[m].values() if o['alignment'] > 0.7),
            }
            for m in available
        },
    }

    output_path = BASE_DIR / "data" / "cross_model_comparison.json"
    with open(str(output_path), 'w', encoding='utf-8') as f:
        json.dump(comparison, f, indent=2, ensure_ascii=False)
    print(f"\n  Results saved to: {output_path}")

    # Generate comparison figure
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    # Left: per-model discovery counts
    ax = axes[0]
    model_labels = [MODELS[m]["label"] for m in available]
    discovered = [len(model_ops[m]) for m in available]
    strong = [sum(1 for o in model_ops[m].values() if o['alignment'] > 0.7) for m in available]
    x = range(len(available))
    w = 0.35
    bars1 = ax.bar([i - w / 2 for i in x], discovered, w, label='All discovered (>0.5)',
                    color=[MODELS[m]["color"] for m in available], alpha=0.7)
    bars2 = ax.bar([i + w / 2 for i in x], strong, w, label='Strong (>0.7)',
                    color=[MODELS[m]["color"] for m in available], alpha=1.0)
    ax.set_xticks(x)
    ax.set_xticklabels(model_labels, fontsize=9)
    ax.set_ylabel('Number of Operations')
    ax.set_title('Operations Discovered per Model')
    ax.legend()
    ax.grid(True, alpha=0.3, axis='y')
    for bar, val in zip(bars1, discovered):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.5,
                str(val), ha='center', fontsize=10, fontweight='bold')

    # Right: Venn-style overlap
    ax = axes[1]
    overlap_data = [len(found_in_all), len(found_in_some), len(found_in_one)]
    overlap_labels = [f'All {len(available)} models\n({len(found_in_all)})',
                      f'2+ models\n({len(found_in_some)})',
                      f'1 model only\n({len(found_in_one)})']
    overlap_colors = ['#27ae60', '#f39c12', '#e74c3c']
    bars = ax.bar(overlap_labels, overlap_data, color=overlap_colors, edgecolor='white', linewidth=2)
    ax.set_ylabel('Number of Predicates')
    ax.set_title('Cross-Model Operation Overlap')
    ax.grid(True, alpha=0.3, axis='y')
    for bar, val in zip(bars, overlap_data):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.5,
                str(val), ha='center', fontsize=12, fontweight='bold')

    plt.tight_layout()
    fig_path = FIG_DIR / "fig5_cross_model_comparison.png"
    fig.savefig(str(fig_path), dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f"  Figure saved to: {fig_path}")


if __name__ == "__main__":
    main()
