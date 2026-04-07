"""
Generate publication figures for the FOL Discovery paper.

Figures:
1. Alignment vs MRR scatter plot (r=0.78 self-diagnostic correlation)
2. Operation discovery distribution (strong/moderate/weak histogram)
3. Collision type breakdown (genuine semantic vs trivial)
4. Three-zone regime illustration with empirical data

Output: papers/fol-discovery/figures/
"""

import io
import sys
import json
import os
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import numpy as np
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

DATA_DIR = Path(os.environ.get("FOL_DATA_DIR", str(Path(__file__).resolve().parent.parent / "data")))
FIG_DIR = Path(__file__).resolve().parent.parent / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)


def load_fol_results():
    with open(str(DATA_DIR / 'fol_results.json'), encoding='utf-8') as f:
        return json.load(f)


def load_collision_analysis():
    path = DATA_DIR / 'collision_analysis.json'
    if path.exists():
        with open(str(path), encoding='utf-8') as f:
            return json.load(f)
    return None


def fig1_alignment_vs_mrr(data):
    """Figure 1: The key finding — alignment predicts prediction accuracy."""
    preds = data.get('prediction_results', [])
    if not preds:
        print("  No prediction results, skipping fig1")
        return

    aligns = [p['alignment'] for p in preds]
    mrrs = [p['mrr'] for p in preds]
    n_triples = [p.get('n_triples', 10) for p in preds]

    fig, ax = plt.subplots(1, 1, figsize=(8, 6))

    # Size points by number of triples
    sizes = [max(20, min(200, n * 3)) for n in n_triples]

    scatter = ax.scatter(aligns, mrrs, s=sizes, alpha=0.6, c=aligns,
                         cmap='RdYlGn', edgecolors='black', linewidth=0.5)

    # Trend line
    z = np.polyfit(aligns, mrrs, 1)
    p = np.poly1d(z)
    x_line = np.linspace(min(aligns), max(aligns), 100)
    ax.plot(x_line, p(x_line), '--', color='red', alpha=0.7, linewidth=2)

    # Correlation annotation
    corr = np.corrcoef(aligns, mrrs)[0, 1]
    ax.annotate(f'r = {corr:.3f}', xy=(0.05, 0.92), xycoords='axes fraction',
                fontsize=14, fontweight='bold',
                bbox=dict(boxstyle='round,pad=0.3', facecolor='lightyellow', edgecolor='orange'))

    ax.set_xlabel('Displacement Consistency (Alignment)', fontsize=12)
    ax.set_ylabel('Prediction Accuracy (MRR)', fontsize=12)
    ax.set_title('Self-Diagnostic: Consistency Predicts Prediction Accuracy', fontsize=13)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1.05)
    ax.grid(True, alpha=0.3)

    # Legend for point sizes
    for n, label in [(10, '10 triples'), (50, '50 triples'), (100, '100+ triples')]:
        ax.scatter([], [], s=max(20, min(200, n * 3)), c='gray', alpha=0.5,
                   edgecolors='black', linewidth=0.5, label=label)
    ax.legend(loc='lower right', fontsize=9, title='Sample size')

    plt.tight_layout()
    path = FIG_DIR / 'fig1_alignment_vs_mrr.png'
    fig.savefig(str(path), dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f"  Saved: {path}")


def fig2_operation_distribution(data):
    """Figure 2: Distribution of discovered operations by consistency."""
    ops = data['discovered_operations']
    all_aligns = [o['mean_alignment'] for o in ops]

    # Also get the non-discovered ones from summary
    summary = data['summary']
    total_analyzed = summary['predicates_analyzed']
    discovered = len(ops)
    weak = total_analyzed - discovered  # predicates below 0.5

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    # Left: histogram of all alignments
    bins = np.arange(0, 1.05, 0.05)
    ax1.hist(all_aligns, bins=bins, color='steelblue', edgecolor='white', alpha=0.8)
    ax1.axvline(x=0.5, color='red', linestyle='--', linewidth=2, label='Discovery threshold')
    ax1.axvline(x=0.7, color='orange', linestyle='--', linewidth=1.5, label='Strong threshold')
    ax1.set_xlabel('Mean Displacement Alignment', fontsize=11)
    ax1.set_ylabel('Number of Predicates', fontsize=11)
    ax1.set_title('Distribution of Operation Consistency', fontsize=12)
    ax1.legend(fontsize=9)
    ax1.grid(True, alpha=0.3)

    # Right: category breakdown
    strong = summary['strong_operations']
    moderate = summary['moderate_operations']
    categories = ['Strong\n(>0.7)', 'Moderate\n(0.5-0.7)', 'Weak\n(<0.5)']
    counts = [strong, moderate, weak]
    colors = ['#2ecc71', '#f39c12', '#e74c3c']
    bars = ax2.bar(categories, counts, color=colors, edgecolor='white', linewidth=1.5)
    for bar, count in zip(bars, counts):
        ax2.text(bar.get_x() + bar.get_width() / 2., bar.get_height() + 1,
                 str(count), ha='center', va='bottom', fontweight='bold', fontsize=12)
    ax2.set_ylabel('Number of Predicates', fontsize=11)
    ax2.set_title(f'Operation Categories ({total_analyzed} predicates analyzed)', fontsize=12)
    ax2.grid(True, alpha=0.3, axis='y')

    plt.tight_layout()
    path = FIG_DIR / 'fig2_operation_distribution.png'
    fig.savefig(str(path), dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f"  Saved: {path}")


def fig3_collision_breakdown(collision_data):
    """Figure 3: Collision type analysis — evidence for three-zone taxonomy."""
    if collision_data is None:
        print("  No collision data, skipping fig3")
        return

    cats = collision_data['categories']
    labels = {
        'genuine_semantic': 'Genuine Semantic\n([UNK] token collapse)',
        'substring_overlap': 'Substring Overlap',
        'identical_text': 'Identical Text\n(trivial)',
        'near_identical_text': 'Near-Identical Text',
    }
    colors = ['#e74c3c', '#f39c12', '#95a5a6', '#bdc3c7']

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    # Left: pie chart
    values = [cats.get('genuine_semantic', 0), cats.get('substring_overlap', 0),
              cats.get('identical_text', 0), cats.get('near_identical_text', 0)]
    pie_labels = [labels.get(k, k) for k in ['genuine_semantic', 'substring_overlap',
                                               'identical_text', 'near_identical_text']]
    ax1.pie(values, labels=pie_labels, colors=colors, autopct='%1.1f%%',
            startangle=90, pctdistance=0.85)
    total = collision_data['metadata']['total_cross_entity_collisions']
    ax1.set_title(f'Cross-Entity Collisions at cosine >= 0.95\n(N = {total:,})', fontsize=12)

    # Right: top collision hubs bar chart
    examples = collision_data['examples'].get('genuine_semantic', [])
    if examples:
        # Count unique texts in examples
        from collections import Counter
        text_counts = Counter()
        for ex in examples:
            text_counts[ex['text_a']] += 1
            text_counts[ex['text_b']] += 1
        top_texts = text_counts.most_common(10)
        if top_texts:
            texts, counts = zip(*top_texts)
            texts = [t[:20] + '...' if len(t) > 20 else t for t in texts]
            y_pos = range(len(texts))
            ax2.barh(y_pos, counts, color='#e74c3c', alpha=0.8)
            ax2.set_yticks(y_pos)
            ax2.set_yticklabels(texts, fontsize=9)
            ax2.set_xlabel('Collision Count (in sample)', fontsize=11)
            ax2.set_title('Top Collision Hubs\n(undersymbolic manifold)', fontsize=12)
            ax2.invert_yaxis()
            ax2.grid(True, alpha=0.3, axis='x')

    plt.tight_layout()
    path = FIG_DIR / 'fig3_collision_breakdown.png'
    fig.savefig(str(path), dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f"  Saved: {path}")


def fig4_three_zones(data, collision_data):
    """Figure 4: Conceptual three-zone diagram with empirical anchoring."""
    fig, ax = plt.subplots(1, 1, figsize=(10, 6))

    # Draw three zones as overlapping regions
    from matplotlib.patches import FancyBboxPatch

    # Undersymbolic (left)
    rect1 = FancyBboxPatch((0.05, 0.15), 0.28, 0.7, boxstyle="round,pad=0.02",
                            facecolor='#e8d4f0', edgecolor='#8e44ad', linewidth=2)
    ax.add_patch(rect1)
    ax.text(0.19, 0.82, 'UNDERSYMBOLIC', ha='center', fontsize=11, fontweight='bold', color='#8e44ad')
    ax.text(0.19, 0.72, 'Low representational mass', ha='center', fontsize=8, style='italic')
    ax.text(0.19, 0.55, '147,687 collisions\n([UNK] token collapse)', ha='center', fontsize=9)
    ax.text(0.19, 0.38, 'instance-of: 0.244\nsibling: 0.026', ha='center', fontsize=8, color='#666')

    # Isosymbolic (center)
    rect2 = FancyBboxPatch((0.37, 0.15), 0.28, 0.7, boxstyle="round,pad=0.02",
                            facecolor='#d4f0d4', edgecolor='#27ae60', linewidth=2)
    ax.add_patch(rect2)
    ax.text(0.51, 0.82, 'ISOSYMBOLIC', ha='center', fontsize=11, fontweight='bold', color='#27ae60')
    ax.text(0.51, 0.72, 'Vector arithmetic works', ha='center', fontsize=8, style='italic')
    ax.text(0.51, 0.55, '86 operations\n(alignment > 0.5)', ha='center', fontsize=9)
    ax.text(0.51, 0.38, 'flag: 0.855\ndemographics: 0.899', ha='center', fontsize=8, color='#666')

    # Oversymbolic (right)
    rect3 = FancyBboxPatch((0.69, 0.15), 0.28, 0.7, boxstyle="round,pad=0.02",
                            facecolor='#f0d4d4', edgecolor='#c0392b', linewidth=2)
    ax.add_patch(rect3)
    ax.text(0.83, 0.82, 'OVERSYMBOLIC', ha='center', fontsize=11, fontweight='bold', color='#c0392b')
    ax.text(0.83, 0.72, 'Saturated resolution', ha='center', fontsize=8, style='italic')
    ax.text(0.83, 0.55, 'Rich concepts\ncompressed together', ha='center', fontsize=9)
    ax.text(0.83, 0.38, '(requires denser\ntraining data)', ha='center', fontsize=8, color='#666')

    # Arrow showing density gradient
    ax.annotate('', xy=(0.95, 0.08), xytext=(0.05, 0.08),
                arrowprops=dict(arrowstyle='->', lw=2, color='#333'))
    ax.text(0.5, 0.02, 'Representational Density', ha='center', fontsize=10, color='#333')

    ax.set_xlim(0, 1)
    ax.set_ylim(0, 0.95)
    ax.set_aspect('equal')
    ax.axis('off')
    ax.set_title('Three Regimes of Embedding Space\n(with empirical evidence from mxbai-embed-large)', fontsize=13)

    plt.tight_layout()
    path = FIG_DIR / 'fig4_three_zones.png'
    fig.savefig(str(path), dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f"  Saved: {path}")


def main():
    print("=" * 60)
    print("GENERATING FIGURES FOR FOL DISCOVERY PAPER")
    print("=" * 60)

    print("\nLoading data...")
    fol_data = load_fol_results()
    collision_data = load_collision_analysis()

    print("\nFigure 1: Alignment vs MRR (self-diagnostic correlation)")
    fig1_alignment_vs_mrr(fol_data)

    print("Figure 2: Operation discovery distribution")
    fig2_operation_distribution(fol_data)

    print("Figure 3: Collision type breakdown")
    fig3_collision_breakdown(collision_data)

    print("Figure 4: Three-zone regime diagram")
    fig4_three_zones(fol_data, collision_data)

    print(f"\nAll figures saved to: {FIG_DIR}")
    print(f"Files: {[f.name for f in FIG_DIR.glob('*.png')]}")


if __name__ == "__main__":
    main()
